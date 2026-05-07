# Copyright 2020 StackHPC
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
import json
import re

from networking_generic_switch.devices import netmiko_devices
from networking_generic_switch.devices import utils as device_utils


class Cumulus(netmiko_devices.NetmikoSwitch):
    """Device Name: Cumulus Linux (via NCLU)

    Port can be disabled: True

    Built for Cumulus 4.x

    Note for this switch you want config like this,
    where secret is the password needed for sudo su:

    .. code-block:: ini

        [genericswitch:<hostname>]
        device_type = netmiko_cumulus
        ip = <ip>
        username = <username>
        password = <password>
        secret = <password for sudo>
        ngs_physical_networks = physnet1
        ngs_max_connections = 1
        ngs_port_default_vlan = 123
        ngs_disable_inactive_ports = False
    """
    NETMIKO_DEVICE_TYPE = "linux"

    ADD_NETWORK = (
        'net add vlan {segmentation_id}',
    )

    DELETE_NETWORK = (
        'net del vlan {segmentation_id}',
    )

    PLUG_PORT_TO_NETWORK = (
        'net add interface {port} bridge access {segmentation_id}',
    )

    DELETE_PORT = (
        'net del interface {port} bridge access {segmentation_id}',
    )

    PLUG_BOND_TO_NETWORK = (
        'net add bond {bond} bridge access {segmentation_id}',
    )

    UNPLUG_BOND_FROM_NETWORK = (
        'net del bond {bond} bridge access {segmentation_id}',
    )

    ENABLE_PORT = (
        'net del interface {port} link down',
    )

    DISABLE_PORT = (
        'net add interface {port} link down',
    )

    ENABLE_BOND = (
        'net del bond {bond} link down',
    )

    DISABLE_BOND = (
        'net add bond {bond} link down',
    )

    SAVE_CONFIGURATION = (
        'net commit',
    )

    ERROR_MSG_PATTERNS = (
        # Its tempting to add this error message, but as only one
        # bridge-access is allowed, we ignore that error for now:
        # re.compile(r'configuration does not have "bridge-access')
        re.compile(r'ERROR: Command not found.'),
        re.compile(r'command not found'),
        re.compile(r'is not a physical interface on this switch'),
    )


class CumulusNVUE(netmiko_devices.NetmikoSwitch):
    """Device Name: Cumulus Linux(via NVUE)

    Port can be disabled: True

    Built for Cumulus 5.x

    Note for this switch you want config like this,
    where secret is the password needed for sudo su:

    .. code-block:: ini

        [genericswitch:<hostname>]
        device_type = netmiko_cumulus_nvue
        ip = <ip>
        username = <username>
        password = <password>
        secret = <password for sudo>
        ngs_physical_networks = physnet1
        ngs_max_connections = 1
        ngs_port_default_vlan = 123
        ngs_disable_inactive_ports = False

    VXLAN L2VNI Support
    ~~~~~~~~~~~~~~~~~~~

    Cumulus NVUE supports VXLAN L2VNI configuration. VLANs are mapped to VNIs
    on the default bridge domain ``br_default``.

    Supports three BUM (Broadcast, Unknown unicast, Multicast) traffic
    replication modes:

    1. **ingress-replication** (default when no HER lists configured):
       Uses EVPN-learned VTEPs for dynamic replication
    2. **head-end-replication** (default when HER lists configured):
       Uses static VTEP flood lists
    3. **multicast**: Uses PIM multicast groups

    Configuration parameters:

    * ``ngs_bum_replication_mode`` - BUM traffic replication mode (default:
      auto-detected based on HER list presence). Options:
      ``ingress-replication``, ``head-end-replication``, ``multicast``
    * ``ngs_her_flood_list`` - Global HER flood list (comma-separated VTEP IPs)
    * ``ngs_physnet_her_flood`` - Per-physnet HER flood lists
      (format: ``physnet1:ip1,ip2;physnet2:ip3,ip4``)
    * ``ngs_mcast_group_map`` - Explicit VNI-to-multicast-group mappings
    * ``ngs_mcast_group_base`` - Base multicast group address for automatic
      derivation
    * ``ngs_evpn_vni_config`` - Enable EVPN VNI control plane configuration
      (default: false)
    * ``ngs_bgp_asn`` - BGP AS number (required when ``ngs_evpn_vni_config``
      is enabled)

    """
    NETMIKO_DEVICE_TYPE = "linux"

    ADD_NETWORK = (
        'nv set bridge domain br_default vlan {segmentation_id}',
    )

    DELETE_NETWORK = (
        'nv unset bridge domain br_default vlan {segmentation_id}',
    )

    PLUG_SWITCH_TO_NETWORK = (
        'nv set bridge domain br_default vlan {segmentation_id} '
        'vni {vni}',
    )

    UNPLUG_SWITCH_FROM_NETWORK = (
        'nv unset bridge domain br_default vlan {segmentation_id} vni',
    )

    SHOW_VLAN_PORTS = ('nv show bridge domain br_default vlan '
                       '{segmentation_id} -o json',)

    SHOW_VLAN_VNI = ('nv show bridge domain br_default vlan-vni-map '
                     '-o json',)

    PLUG_PORT_TO_NETWORK = (
        'nv unset interface {port} bridge domain br_default untagged',
        'nv set interface {port} bridge domain br_default access '
        '{segmentation_id}',
    )

    ADD_NETWORK_TO_TRUNK = (
        'nv unset interface {port} bridge domain br_default access',
        'nv set interface {port} bridge domain br_default vlan '
        '{segmentation_id}',
    )

    ADD_NETWORK_TO_BOND_TRUNK = (
        'nv unset interface {bond} bridge domain br_default access',
        'nv set interface {bond} bridge domain br_default vlan '
        '{segmentation_id}',
    )

    REMOVE_NETWORK_FROM_TRUNK = (
        'nv unset interface {port} bridge domain br_default vlan '
        '{segmentation_id}',
    )

    DELETE_NETWORK_ON_BOND_TRUNK = (
        'nv unset interface {bond} bridge domain br_default vlan '
        '{segmentation_id}',
    )

    SET_NATIVE_VLAN = (
        'nv unset interface {port} bridge domain br_default access',
        'nv set interface {port} bridge domain br_default untagged '
        '{segmentation_id}',
        'nv set interface {port} bridge domain br_default vlan '
        '{segmentation_id}',
    )

    SET_NATIVE_VLAN_BOND = (
        'nv unset interface {bond} bridge domain br_default access',
        'nv set interface {bond} bridge domain br_default untagged '
        '{segmentation_id}',
        'nv set interface {bond} bridge domain br_default vlan '
        '{segmentation_id}',
    )

    DELETE_NATIVE_VLAN = (
        'nv unset interface {port} bridge domain br_default untagged '
        '{segmentation_id}',
        'nv unset interface {port} bridge domain br_default vlan '
        '{segmentation_id}',
    )

    DELETE_NATIVE_VLAN_BOND = (
        'nv unset interface {bond} bridge domain br_default untagged '
        '{segmentation_id}',
        'nv unset interface {bond} bridge domain br_default vlan '
        '{segmentation_id}',
    )

    DELETE_PORT = (
        'nv unset interface {port} bridge domain br_default access',
        'nv unset interface {port} bridge domain br_default untagged',
        'nv unset interface {port} bridge domain br_default vlan',
    )

    ENABLE_PORT = (
        'nv set interface {port} link state up',
    )

    DISABLE_PORT = (
        'nv set interface {port} link state down',
    )

    SAVE_CONFIGURATION = (
        'nv config save',
    )

    ERROR_MSG_PATTERNS = (
        # Its tempting to add this error message, but as only one
        # bridge-access is allowed, we ignore that error for now:
        # re.compile(r'configuration does not have "bridge-access')
        re.compile(r'Invalid config'),
        re.compile(r'Config invalid at'),
        re.compile(r'ERROR: Command not found.'),
        re.compile(r'command not found'),
        re.compile(r'is not a physical interface on this switch'),
        re.compile(r'Error: Invalid parameter'),
        re.compile(r'Unable to restart services'),
        re.compile(r'Failure during apply'),
    )

    PLUG_EVPN_VNI = (
        'vtysh -c "configure terminal" '
        '-c "router bgp {bgp_asn}" '
        '-c "address-family l2vpn evpn" '
        '-c "vni {vni}" '
        '-c "rd auto" '
        '-c "route-target import auto" '
        '-c "route-target export auto"',
    )

    UNPLUG_EVPN_VNI = (
        'vtysh -c "configure terminal" '
        '-c "router bgp {bgp_asn}" '
        '-c "address-family l2vpn evpn" '
        '-c "no vni {vni}"',
    )

    PLUG_HER_FLOOD = (
        'nv set nve vxlan flooding head-end-replication '
        '{vtep_ip}',
    )

    PLUG_MCAST_FLOOD = (
        'nv set bridge domain br_default vlan {segmentation_id} '
        'vni {vni} flooding multicast-group {mcast_group}',
    )

    PLUG_INGRESS_REPLICATION = (
        'nv set bridge domain br_default vlan {segmentation_id} '
        'vni {vni} flooding head-end-replication evpn',
    )

    def __init__(self, device_cfg, *args, **kwargs):
        """Initialize Cumulus NVUE with VXLAN configuration support.

        Extracts VXLAN-related configuration before parent __init__ removes
        all ngs_* options.
        """
        # Extract HER flood list config before parent removes ngs_* options
        self.her_flood_list = device_cfg.get('ngs_her_flood_list')
        self.physnet_her_flood = device_cfg.get('ngs_physnet_her_flood')

        # EVPN VNI configuration (for distributed EVPN deployments)
        evpn_config = device_cfg.get('ngs_evpn_vni_config', 'false')
        self.evpn_vni_config = evpn_config.lower() in ('true', 'yes', '1')
        self.bgp_asn = device_cfg.get('ngs_bgp_asn')

        # Use shared utility for multicast config parsing
        mcast_config = device_utils.parse_vxlan_multicast_config(device_cfg)
        self.mcast_group_base = mcast_config.mcast_group_base
        self.mcast_group_increment = mcast_config.mcast_group_increment
        self.mcast_group_map = mcast_config.mcast_group_map

        # Determine BUM replication mode with backward compatibility
        # Option B: Auto-detect head-end-replication if HER lists exist,
        # otherwise default to ingress-replication
        explicit_mode = device_cfg.get('ngs_bum_replication_mode')
        if explicit_mode:
            # User explicitly set the mode, use it
            self.bum_replication_mode = mcast_config.bum_replication_mode
        elif self.her_flood_list or self.physnet_her_flood:
            # Backward compatibility: HER lists present, use static HER
            self.bum_replication_mode = 'head-end-replication'
        else:
            # Default: EVPN-learned VTEPs
            self.bum_replication_mode = 'ingress-replication'

        # Parse per-physnet HER flood mapping if provided
        self._physnet_her_map = {}
        if self.physnet_her_flood:
            try:
                # Format: physnet1:ip1,ip2;physnet2:ip3,ip4
                for mapping in self.physnet_her_flood.split(';'):
                    physnet, vteps = mapping.strip().split(':')
                    vtep_list = [v.strip() for v in vteps.split(',')]
                    self._physnet_her_map[physnet.strip()] = vtep_list
            except ValueError as e:
                from oslo_log import log as logging
                LOG = logging.getLogger(__name__)
                LOG.error(
                    "Invalid ngs_physnet_her_flood format. "
                    "Expected 'physnet1:ip1,ip2;physnet2:ip3,ip4', got: "
                    "'%s'. Error: %s",
                    self.physnet_her_flood, e)
                from networking_generic_switch import exceptions as exc
                raise exc.GenericSwitchNetmikoConfigError()

        super(CumulusNVUE, self).__init__(device_cfg, *args, **kwargs)

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

    def _get_her_flood_list_for_physnet(self, physnet):
        """Resolve HER flood list for a given physical network.

        Resolution order:
        1. Check per-physnet mapping (ngs_physnet_her_flood)
        2. Check global fallback (ngs_her_flood_list)
        3. Default to None (use EVPN learned VTEPs only)

        :param physnet: Physical network name
        :returns: List of HER flood VTEP IPs or None
        """
        # Check per-physnet mapping first
        if physnet and physnet in self._physnet_her_map:
            return self._physnet_her_map[physnet]

        # Fall back to global setting
        if self.her_flood_list:
            return [v.strip() for v in self.her_flood_list.split(',')]

        # Default: EVPN-only (return None)
        return None

    def _parse_vlan_ports(self, output: str, segmentation_id: int) -> bool:
        """Parse Cumulus NVUE 'nv show bridge domain vlan X' output.

        :param output: Command output from switch (JSON format)
        :param segmentation_id: VLAN identifier being checked
        :returns: True if VLAN has ports, False otherwise
        """
        # Cumulus NVUE JSON output format for vlan details:
        # {
        #   "multicast": {...},
        #   "port": {
        #     "swp1": {...},
        #     "swp2": {...}
        #   },
        #   ...
        # }
        try:
            data = json.loads(output)
            # Check if the 'port' key exists and has content
            ports = data.get('port', {})
            return len(ports) > 0
        except (json.JSONDecodeError, AttributeError, TypeError):
            # If parsing fails, conservatively assume no ports
            return False

    def _parse_vlan_vni(self, output: str, segmentation_id: int,
                        vni: int) -> bool:
        """Parse Cumulus NVUE 'nv show bridge vlan-vni-map' output.

        :param output: Command output from switch (JSON format)
        :param segmentation_id: VLAN identifier being checked
        :param vni: VNI to check for
        :returns: True if VLAN has this VNI, False otherwise
        """
        # Cumulus NVUE JSON output format:
        # {
        #   "br_default": {
        #     "vlan-vni-map": {
        #       "10": {
        #         "vni": 10
        #       },
        #       "20": {
        #         "vni": 20
        #       }
        #     }
        #   }
        # }
        try:
            data = json.loads(output)
            # Navigate to the vlan-vni-map for br_default
            vlan_vni_map = data.get('br_default', {}).get('vlan-vni-map', {})
            # Check if our VLAN exists and has the expected VNI
            vlan_data = vlan_vni_map.get(str(segmentation_id), {})
            configured_vni = vlan_data.get('vni')
            return configured_vni == vni
        except (json.JSONDecodeError, AttributeError, TypeError,
                KeyError):
            # If parsing fails, VNI is not configured
            return False

    @netmiko_devices.check_output('plug vni')
    def plug_switch_to_network(self, vni: int, segmentation_id: int,
                               physnet: str = None):
        """Configure L2VNI mapping with BUM replication on Cumulus NVUE.

        Supports three BUM (Broadcast, Unknown unicast, Multicast) traffic
        replication modes:
        1. **ingress-replication** (default): Uses EVPN-learned VTEPs
        2. **head-end-replication**: Uses static VTEP flood lists
        3. **multicast**: Uses PIM multicast groups

        Dynamically generates commands based on configuration:
        1. Configure EVPN VNI (if ngs_evpn_vni_config enabled)
        2. Map VLAN to VNI on the bridge
        3. Configure BUM replication based on mode

        :param vni: VXLAN Network Identifier
        :param segmentation_id: VLAN identifier
        :param physnet: Physical network name for HER flood list resolution
        :returns: Command output
        """
        cmds = []

        # Step 1: EVPN VNI configuration (distributed EVPN deployments)
        if self.evpn_vni_config:
            if not self.bgp_asn:
                from networking_generic_switch import exceptions as exc
                raise exc.GenericSwitchNetmikoConfigError(
                    switch=self.device_name,
                    error='ngs_bgp_asn configuration parameter is '
                          'required when ngs_evpn_vni_config is enabled')
            cmds.extend(self._format_commands(
                self.PLUG_EVPN_VNI,
                bgp_asn=self.bgp_asn,
                vni=vni))

        # Step 2: Map VLAN to VNI
        cmds.extend(self._format_commands(
            self.PLUG_SWITCH_TO_NETWORK,
            vni=vni,
            segmentation_id=segmentation_id))

        # Step 3: Configure BUM replication based on mode
        if self.bum_replication_mode == 'multicast':
            mcast_group = self._get_multicast_group(vni)
            cmds.extend(self._format_commands(
                self.PLUG_MCAST_FLOOD,
                segmentation_id=segmentation_id,
                vni=vni,
                mcast_group=mcast_group))
        elif self.bum_replication_mode == 'head-end-replication':
            her_flood_list = self._get_her_flood_list_for_physnet(
                physnet)
            if her_flood_list:
                for vtep_ip in her_flood_list:
                    cmds.extend(self._format_commands(
                        self.PLUG_HER_FLOOD,
                        vtep_ip=vtep_ip))
        elif self.bum_replication_mode == 'ingress-replication':
            cmds.extend(self._format_commands(
                self.PLUG_INGRESS_REPLICATION,
                segmentation_id=segmentation_id,
                vni=vni))

        return self.send_commands_to_device(cmds)

    @netmiko_devices.check_output('unplug vni')
    def unplug_switch_from_network(self, vni: int, segmentation_id: int,
                                   physnet: str = None):
        """Remove L2VNI mapping and EVPN VNI from Cumulus NVUE.

        Removes configuration in reverse order of creation:
        1. Remove VXLAN map (per-VNI BUM replication config removed
           automatically for multicast and ingress-replication modes;
           global HER flood list is NOT removed for head-end-replication
           mode as it may be used by other VNIs)
        2. Remove EVPN VNI configuration (if enabled)

        :param vni: VXLAN Network Identifier
        :param segmentation_id: VLAN identifier
        :param physnet: Physical network name (unused but kept for signature)
        :returns: Command output
        """
        # Step 1: Remove VXLAN map
        cmds = self._format_commands(
            self.UNPLUG_SWITCH_FROM_NETWORK,
            vni=vni,
            segmentation_id=segmentation_id)

        # Step 2: Remove EVPN VNI configuration if it was created
        if self.evpn_vni_config:
            if not self.bgp_asn:
                from networking_generic_switch import exceptions as exc
                raise exc.GenericSwitchNetmikoConfigError(
                    switch=self.device_name,
                    error='ngs_bgp_asn configuration parameter is '
                          'required when ngs_evpn_vni_config is enabled')
            cmds.extend(self._format_commands(
                self.UNPLUG_EVPN_VNI,
                bgp_asn=self.bgp_asn,
                vni=vni))

        return self.send_commands_to_device(cmds)

    def vlan_has_ports(self, segmentation_id: int) -> bool:
        """Check if a VLAN has any switch ports currently assigned.

        :param segmentation_id: VLAN identifier
        :returns: True if VLAN has ports, False otherwise
        """
        cmd = self._format_commands(
            self.SHOW_VLAN_PORTS,
            segmentation_id=segmentation_id)
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
            vni=vni)
        with self._get_connection() as net_connect:
            output = net_connect.send_command(cmd[0])
            return self._parse_vlan_vni(output, segmentation_id, vni)

    def send_config_set(self, net_connect, cmd_set):
        """Send a set of configuration lines to the device.

        :param net_connect: a netmiko connection object.
        :param cmd_set: a list of configuration lines to send.
        :returns: The output of the configuration commands.
        """
        cmd_set.append('nv config apply --assume-yes')
        # NOTE: Do not exit config mode because save needs elevated
        # privileges
        return net_connect.send_config_set(config_commands=cmd_set,
                                           cmd_verify=False,
                                           enter_config_mode=False,
                                           exit_config_mode=False)
