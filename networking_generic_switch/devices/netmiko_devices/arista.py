# Copyright 2016 Mirantis, Inc.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import re

from networking_generic_switch.devices import netmiko_devices
from networking_generic_switch.devices import utils as device_utils
from networking_generic_switch import exceptions as exc


class AristaEos(netmiko_devices.NetmikoSwitch):
    """Device Name: Arista EOS

    Port can be disabled: True

    VXLAN L2VNI Support
    ~~~~~~~~~~~~~~~~~~~

    For VXLAN L2VNI support, the ``ngs_bgp_asn`` configuration parameter is
    required. The ``vxlan_interface`` parameter can optionally be specified
    (defaults to ``Vxlan1``). The ``ngs_evpn_route_target`` parameter can
    optionally be specified to configure the route-target value. When set to
    ``auto`` (the default), the commands ``route-target export auto <ASN>``
    and ``route-target import auto <ASN>`` are used, which allows Arista
    EOS to automatically derive route-target values. Alternatively, an
    explicit value can be provided in the format ``<ASN>:<number>``
    (e.g., ``65000:100``).

    Supports two BUM (Broadcast, Unknown unicast, Multicast) traffic
    replication modes:

    1. **ingress-replication** (default) - Uses BGP EVPN for BUM traffic
    2. **multicast** - Uses ASM multicast groups with PIM Sparse Mode

    .. code-block:: ini

        [genericswitch:arista-switch]
        device_type = netmiko_arista_eos
        ngs_bgp_asn = 65000
        vxlan_interface = Vxlan1
        ngs_evpn_route_target = auto
        ngs_bum_replication_mode = ingress-replication
        ngs_mcast_group_base = 239.1.1.0
    """

    ADD_NETWORK = (
        'vlan {segmentation_id}',
        'name {network_name}',
    )

    DELETE_NETWORK = (
        'no vlan {segmentation_id}',
    )

    PLUG_SWITCH_TO_NETWORK = (
        'interface {vxlan_interface}',
        'vxlan vlan {segmentation_id} vni {vni}',
    )

    UNPLUG_SWITCH_FROM_NETWORK = (
        'interface {vxlan_interface}',
        'no vxlan vlan {segmentation_id} vni {vni}',
    )

    SHOW_VLAN_PORTS = ('show vlan id {segmentation_id}',)

    SHOW_VLAN_VNI = ('show interfaces {vxlan_interface}',)

    PLUG_PORT_TO_NETWORK = (
        'interface {port}',
        'switchport mode access',
        'switchport access vlan {segmentation_id}',
    )

    DELETE_PORT = (
        'interface {port}',
        'no switchport access vlan {segmentation_id}',
        'no switchport mode trunk',
        'switchport trunk allowed vlan none'
    )

    SET_NATIVE_VLAN = (
        'interface {port}',
        'switchport mode trunk',
        'switchport trunk native vlan {segmentation_id}',
        'switchport trunk allowed vlan add {segmentation_id}'
    )

    SET_NATIVE_VLAN_BOND = (
        'interface {bond}',
        'switchport mode trunk',
        'switchport trunk native vlan {segmentation_id}',
        'switchport trunk allowed vlan add {segmentation_id}'
    )

    DELETE_NATIVE_VLAN = (
        'interface {port}',
        'no switchport trunk native vlan {segmentation_id}',
        'switchport trunk allowed vlan remove {segmentation_id}',
    )

    DELETE_NATIVE_VLAN_BOND = (
        'interface {bond}',
        'no switchport trunk native vlan {segmentation_id}',
        'switchport trunk allowed vlan remove {segmentation_id}',
    )

    ADD_NETWORK_TO_TRUNK = (
        'interface {port}',
        'switchport trunk allowed vlan add {segmentation_id}'
    )

    ADD_NETWORK_TO_BOND_TRUNK = (
        'interface {bond}',
        'switchport trunk allowed vlan add {segmentation_id}'
    )

    REMOVE_NETWORK_FROM_TRUNK = (
        'interface {port}',
        'switchport trunk allowed vlan remove {segmentation_id}'
    )

    DELETE_NETWORK_ON_BOND_TRUNK = (
        'interface {bond}',
        'switchport trunk allowed vlan remove {segmentation_id}'
    )

    ERROR_MSG_PATTERNS = (
        re.compile(r'% Invalid input'),
        re.compile(r'% Incomplete command'),
        re.compile(r'% VLAN \d+ is already mapped to VNI \d+'),
    )

    ENABLE_PORT = (
        'interface {port}',
        'no shutdown',
    )

    DISABLE_PORT = (
        'interface {port}',
        'shutdown',
    )

    def __init__(self, device_cfg, *args, **kwargs):
        """Initialize Arista EOS device with VXLAN configuration support.

        Extracts VXLAN-related configuration before parent __init__ removes
        all ngs_* options.
        """
        # Extract VXLAN config before parent removes ngs_* options
        self.vxlan_interface = device_cfg.get('vxlan_interface', 'Vxlan1')
        self.bgp_asn = device_cfg.get('ngs_bgp_asn')
        self.evpn_route_target = device_cfg.get('ngs_evpn_route_target',
                                                'auto')

        # Use shared utility for multicast config parsing
        mcast_config = device_utils.parse_vxlan_multicast_config(device_cfg)
        self.bum_replication_mode = mcast_config.bum_replication_mode
        self.mcast_group_base = mcast_config.mcast_group_base
        self.mcast_group_increment = mcast_config.mcast_group_increment
        self.mcast_group_map = mcast_config.mcast_group_map

        super(AristaEos, self).__init__(device_cfg, *args, **kwargs)

    def _get_multicast_group(self, vni: int) -> str:
        """Calculate multicast group address for a given VNI.

        Delegates to shared utility function for consistent multicast
        group derivation logic across all vendors.

        :param vni: VXLAN Network Identifier
        :returns: Multicast group IP address (e.g., '239.1.1.100')
        :raises: GenericSwitchConfigError if no mapping or base configured
        """
        return device_utils.get_vxlan_multicast_group(
            vni, self.mcast_group_map, self.mcast_group_base,
            self.device_name)

    def _parse_vlan_ports(self, output: str, segmentation_id: int) -> bool:
        """Parse Arista EOS 'show vlan id X' output for ports.

        :param output: Command output from switch
        :param segmentation_id: VLAN identifier being checked
        :returns: True if VLAN has ports, False otherwise
        """
        # Arista EOS output format:
        # VLAN  Name                             Status    Ports
        # ----- -------------------------------- --------- ------
        # 100   VLAN0100                         active    Et1, Et2
        lines = output.strip().split('\n')
        for line in lines:
            # Skip empty lines and separator lines
            if not line.strip() or '---' in line:
                continue
            # Skip header line (starts with "VLAN " - note the space)
            if line.startswith('VLAN '):
                continue
            parts = line.split()
            # First part should be VLAN ID
            if parts and parts[0].isdigit() and \
               int(parts[0]) == segmentation_id:
                # Check if there are port entries (index 3 onwards)
                return len(parts) > 3
        # If no data row found, conservatively assume no ports
        return False

    def _parse_vlan_vni(self, output: str, segmentation_id: int,
                        vni: int) -> bool:
        """Parse Arista EOS 'show interfaces VxlanX' output.

        Detects VNI configuration in both ingress-replication and multicast
        modes.

        :param output: Command output from switch
        :param segmentation_id: VLAN identifier being checked
        :param vni: VNI to check for
        :returns: True if VLAN has this VNI, False otherwise
        """
        # Arista EOS output format:
        # Static VLAN to VNI mapping is [112, 112] [134, 134]
        # VLAN 100 flood VTEP 239.1.1.116 (multicast mode)
        # Format: [VLAN, VNI] pairs in brackets
        lines = output.strip().split('\n')
        for line in lines:
            if 'Static VLAN to VNI mapping' in line:
                # Extract all [VLAN, VNI] pairs from the line
                pairs = re.findall(r'\[(\d+),\s*(\d+)\]', line)
                for vlan_str, vni_str in pairs:
                    if int(vlan_str) == segmentation_id:
                        return int(vni_str) == vni
        # If we can't find the VNI, it's not configured
        return False

    @netmiko_devices.check_output('plug vni')
    def plug_switch_to_network(self, vni: int, segmentation_id: int,
                               physnet: str = None):
        """Configure L2VNI mapping with BGP EVPN on Arista EOS.

        Supports two BUM traffic replication modes:
        1. ingress-replication (default): Uses BGP EVPN for BUM
           replication. Recommended for most deployments.
        2. multicast: Uses ASM multicast groups for BUM replication.
           Requires PIM Sparse Mode with Anycast RP configured on the
           fabric infrastructure.

        Configures the following in order:
        1. Configure EVPN VLAN (BGP control plane for MAC/IP learning and
           redistribution of locally learned MACs)
        2. Map VLAN to VNI on the VXLAN interface
        3. Configure BUM replication (ingress-replication or flood vtep)

        :param vni: VXLAN Network Identifier
        :param segmentation_id: VLAN identifier
        :param physnet: Physical network name (unused, kept for
                        compatibility)
        :returns: Command output
        """
        if not self.bgp_asn:
            raise exc.GenericSwitchNetmikoConfigError(
                switch=self.device_name,
                error='ngs_bgp_asn configuration parameter is required '
                      'for L2VNI support on Arista EOS switches')

        cmds = []

        # Step 1: EVPN VLAN configuration (BGP control plane)
        # NOTE: EVPN used for MAC/IP learning in both modes
        evpn_cmds = [
            f'router bgp {self.bgp_asn}',
            f'vlan {segmentation_id}',
            'rd auto',
            'redistribute learned',
        ]

        if self.evpn_route_target == 'auto':
            evpn_cmds.extend([
                f'route-target export auto {self.bgp_asn}',
                f'route-target import auto {self.bgp_asn}',
            ])
        else:
            evpn_cmds.append(
                f'route-target both {self.evpn_route_target}')

        cmds.extend(evpn_cmds)

        # Step 2: Map VLAN to VNI
        vxlan_cmds = self._format_commands(
            self.PLUG_SWITCH_TO_NETWORK,
            vni=vni,
            segmentation_id=segmentation_id,
            vxlan_interface=self.vxlan_interface)
        cmds.extend(vxlan_cmds)

        # Step 3: BUM traffic replication configuration
        if self.bum_replication_mode == 'multicast':
            # Use multicast group for BUM traffic (ASM with PIM)
            mcast_group = self._get_multicast_group(vni)
            multicast_cmds = [
                f'interface {self.vxlan_interface}',
                f'vxlan vlan {segmentation_id} flood vtep {mcast_group}',
            ]
            cmds.extend(multicast_cmds)
        # else: ingress-replication is the default, no explicit config needed

        return self.send_commands_to_device(cmds)

    @netmiko_devices.check_output('unplug vni')
    def unplug_switch_from_network(self, vni: int, segmentation_id: int,
                                   physnet: str = None):
        """Remove L2VNI mapping and EVPN VLAN from Arista EOS.

        Removes configuration in reverse order of creation:
        1. Remove multicast flood vtep (if in multicast mode)
        2. Remove VXLAN map
        3. Remove EVPN VLAN configuration

        :param vni: VXLAN Network Identifier
        :param segmentation_id: VLAN identifier
        :param physnet: Physical network name (unused but kept for signature)
        :returns: Command output
        """
        if not self.bgp_asn:
            raise exc.GenericSwitchNetmikoConfigError(
                switch=self.device_name,
                error='ngs_bgp_asn configuration parameter is required '
                      'for L2VNI support on Arista EOS switches')

        cmds = []

        # Step 1: Remove multicast flood vtep (if in multicast mode)
        if self.bum_replication_mode == 'multicast':
            multicast_cmds = [
                f'interface {self.vxlan_interface}',
                f'no vxlan vlan {segmentation_id} flood vtep',
            ]
            cmds.extend(multicast_cmds)

        # Step 2: Remove VXLAN map
        vxlan_cmds = self._format_commands(
            self.UNPLUG_SWITCH_FROM_NETWORK,
            vni=vni,
            segmentation_id=segmentation_id,
            vxlan_interface=self.vxlan_interface)
        cmds.extend(vxlan_cmds)

        # Step 3: Remove EVPN VLAN from BGP
        evpn_cmds = [
            f'router bgp {self.bgp_asn}',
            f'no vlan {segmentation_id}',
        ]
        cmds.extend(evpn_cmds)

        return self.send_commands_to_device(cmds)

    def vlan_has_ports(self, segmentation_id: int) -> bool:
        """Check if a VLAN has any switch ports currently assigned.

        :param segmentation_id: VLAN identifier
        :returns: True if VLAN has ports, False otherwise
        """
        cmd = self._format_commands(
            self.SHOW_VLAN_PORTS,
            segmentation_id=segmentation_id,
            vxlan_interface=self.vxlan_interface)
        with self._get_connection() as net_connect:
            output = net_connect.send_command(cmd[0])
            return self._parse_vlan_ports(output, segmentation_id)

    def vlan_has_vni(self, segmentation_id: int, vni: int) -> bool:
        """Check if a VLAN already has a specific VNI mapping configured.

        :param segmentation_id: VLAN identifier
        :param vni: VNI to check for
        :returns: True if VLAN has this VNI, False otherwise
        """
        cmd = self._format_commands(
            self.SHOW_VLAN_VNI,
            segmentation_id=segmentation_id,
            vni=vni,
            vxlan_interface=self.vxlan_interface)
        with self._get_connection() as net_connect:
            output = net_connect.send_command(cmd[0])
            return self._parse_vlan_vni(output, segmentation_id, vni)
