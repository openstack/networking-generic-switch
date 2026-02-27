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
from networking_generic_switch import exceptions as exc


class AristaEos(netmiko_devices.NetmikoSwitch):
    """Device Name: Arista EOS

    VXLAN L2VNI Support
    ~~~~~~~~~~~~~~~~~~~

    For VXLAN L2VNI support, the ``ngs_bgp_asn`` configuration parameter is
    required. The ``vxlan_interface`` parameter can optionally be specified
    (defaults to ``Vxlan1``). The ``ngs_evpn_route_target`` parameter can
    optionally be specified to configure the route-target value (defaults
    to ``auto``). Uses BGP EVPN with ingress-replication for BUM traffic
    handling.

    .. code-block:: ini

        [genericswitch:arista-switch]
        device_type = netmiko_arista_eos
        ngs_bgp_asn = 65000
        vxlan_interface = Vxlan1
        ngs_evpn_route_target = auto
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
        'no vxlan vlan {segmentation_id}',
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

        super(AristaEos, self).__init__(device_cfg, *args, **kwargs)

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

        :param output: Command output from switch
        :param segmentation_id: VLAN identifier being checked
        :param vni: VNI to check for
        :returns: True if VLAN has this VNI, False otherwise
        """
        # Arista EOS output format:
        # Static VLAN to VNI mapping is [112, 112] [134, 134]
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

        Uses ingress-replication for BUM traffic handling with BGP EVPN
        control plane. This is the recommended approach for VXLAN
        deployments and avoids multicast group scaling issues.

        Configures the following in order:
        1. Configure EVPN VLAN (BGP control plane)
        2. Map VLAN to VNI on the VXLAN interface

        :param vni: VXLAN Network Identifier
        :param segmentation_id: VLAN identifier
        :param physnet: Physical network name (unused, kept for compatibility)
        :returns: Command output
        """
        if not self.bgp_asn:
            raise exc.GenericSwitchNetmikoConfigError(
                switch=self.device_name,
                error='ngs_bgp_asn configuration parameter is required '
                      'for L2VNI support on Arista EOS switches')

        cmds = []

        # Step 1: EVPN VLAN configuration (BGP control plane)
        evpn_cmds = [
            f'router bgp {self.bgp_asn}',
            f'vlan {segmentation_id}',
            'rd auto',
            f'route-target both {self.evpn_route_target}',
        ]
        cmds.extend(evpn_cmds)

        # Step 2: Map VLAN to VNI (ingress-replication is default)
        vxlan_cmds = self._format_commands(
            self.PLUG_SWITCH_TO_NETWORK,
            vni=vni,
            segmentation_id=segmentation_id,
            vxlan_interface=self.vxlan_interface)
        cmds.extend(vxlan_cmds)

        return self.send_commands_to_device(cmds)

    @netmiko_devices.check_output('unplug vni')
    def unplug_switch_from_network(self, vni: int, segmentation_id: int,
                                   physnet: str = None):
        """Remove L2VNI mapping and EVPN VLAN from Arista EOS.

        Removes configuration in reverse order of creation:
        1. Remove VXLAN map
        2. Remove EVPN VLAN configuration

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

        # Step 1: Remove VXLAN map
        cmds = self._format_commands(
            self.UNPLUG_SWITCH_FROM_NETWORK,
            vni=vni,
            segmentation_id=segmentation_id,
            vxlan_interface=self.vxlan_interface)

        # Step 2: Remove EVPN VLAN from BGP
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
