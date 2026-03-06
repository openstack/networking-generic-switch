# Copyright 2016 Mirantis, Inc.
# Copyright 2022 Baptiste Jonglez, Inria
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

from neutron_lib import constants as const
from oslo_log import log as logging

from networking_generic_switch.devices import netmiko_devices
from networking_generic_switch import exceptions as exc

LOG = logging.getLogger(__name__)


class CiscoIos(netmiko_devices.NetmikoSwitch):
    """Device Name: Cisco IOS"""
    ADD_NETWORK = (
        'vlan {segmentation_id}',
        'name {network_name}',
    )

    DELETE_NETWORK = (
        'no vlan {segmentation_id}',
    )

    # NOTE: Classic Cisco IOS does not support VXLAN L2VNI.
    # VXLAN is only supported in NX-OS and IOS-XE (Catalyst 9K, etc.)

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
        'switchport trunk allowed vlan add {segmentation_id}',
    )

    DELETE_NATIVE_VLAN = (
        'interface {port}',
        'no switchport mode trunk',
        'no switchport trunk native vlan {segmentation_id}',
        'switchport trunk allowed vlan remove {segmentation_id}',
    )

    ADD_NETWORK_TO_TRUNK = (
        'interface {port}',
        'switchport mode trunk',
        'switchport trunk allowed vlan add {segmentation_id}',
    )

    REMOVE_NETWORK_FROM_TRUNK = (
        'interface {port}',
        'switchport trunk allowed vlan remove {segmentation_id}',
    )


class CiscoNxOS(netmiko_devices.NetmikoSwitch):
    """Device Name: Cisco NX-OS (Nexus)

    Port can be disabled: True

    Security Group Implementation
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Only IPv4 rules are implemented. Based on the capabilities of 9000 series
    Cisco switches, only ingress rules are allowed.
    """

    ADD_NETWORK = (
        'vlan {segmentation_id}',
        'name {network_name}',
        'exit',
    )

    DELETE_NETWORK = (
        'no vlan {segmentation_id}',
    )

    # NOTE: PLUG_SWITCH_TO_NETWORK is dynamically generated based on
    # configuration. See plug_switch_to_network() method.
    PLUG_SWITCH_TO_NETWORK = None

    # NOTE: UNPLUG_SWITCH_FROM_NETWORK is dynamically generated based on
    # configuration. See unplug_switch_from_network() method.
    UNPLUG_SWITCH_FROM_NETWORK = None

    SHOW_VLAN_PORTS = ('show vlan id {segmentation_id}',)

    SHOW_VLAN_VNI = (
        'show interface {nve_interface} | include "member vni {vni}"',)

    PLUG_PORT_TO_NETWORK = (
        'interface {port}',
        'switchport mode access',
        'switchport access vlan {segmentation_id}',
        'exit',
    )

    DELETE_PORT = (
        'interface {port}',
        'no switchport access vlan',
        'exit',
    )

    ADD_NETWORK_TO_TRUNK = (
        'interface {port}',
        'switchport mode trunk',
        'switchport trunk allowed vlan add {segmentation_id}',
        'exit',
    )

    REMOVE_NETWORK_FROM_TRUNK = (
        'interface {port}',
        'switchport trunk allowed vlan remove {segmentation_id}',
        'exit',
    )

    ENABLE_PORT = (
        'interface {port}',
        'no shutdown',
        'exit',
    )

    DISABLE_PORT = (
        'interface {port}',
        'shutdown',
        'exit',
    )

    ADD_SECURITY_GROUP = (
        'ip access-list {security_group}',
    )

    ADD_SECURITY_GROUP_COMPLETE = (
        'exit',
    )

    REMOVE_SECURITY_GROUP = (
        'no ip access-list {security_group}',
    )

    ADD_SECURITY_GROUP_RULE_EGRESS = (
        'permit {protocol} any {remote_ip_prefix} {filter}',
    )

    BIND_SECURITY_GROUP = (
        'interface {port}',
        'ip port access-group {security_group} in',
        'exit',
    )

    UNBIND_SECURITY_GROUP = (
        'interface {port}',
        'no ip port access-group {security_group} in',
        'exit',
    )

    def __init__(self, device_cfg, *args, **kwargs):
        """Initialize Cisco NX-OS device with NVE configuration support.

        Extracts NVE-related and BUM replication configuration before
        parent __init__ removes all ngs_* options.
        """
        # Extract NVE config before parent removes ngs_* options
        self.nve_interface = device_cfg.get('ngs_nve_interface', 'nve1')

        # Extract BUM replication configuration
        self.bum_replication_mode = device_cfg.get(
            'ngs_bum_replication_mode', 'ingress-replication')
        self.mcast_group_base = device_cfg.get(
            'ngs_mcast_group_base', None)
        self.mcast_group_increment = device_cfg.get(
            'ngs_mcast_group_increment', 'vni_last_octet')

        # Parse and validate explicit VNI-to-multicast-group mappings
        self.mcast_group_map = {}
        mcast_map_str = device_cfg.get('ngs_mcast_group_map', '')
        if mcast_map_str:
            import ipaddress
            for mapping in mcast_map_str.split(','):
                mapping = mapping.strip()
                if not mapping:
                    continue
                if ':' not in mapping:
                    LOG.warning('Invalid mapping format in '
                                'ngs_mcast_group_map (expected VNI:group): '
                                '%s', mapping)
                    continue

                vni_str, group_str = mapping.split(':', 1)
                vni_str = vni_str.strip()
                group_str = group_str.strip()

                # Validate VNI
                try:
                    vni = int(vni_str)
                    if vni < 1 or vni > 16777215:
                        LOG.warning('VNI %s out of valid range (1-16777215) '
                                    'in ngs_mcast_group_map', vni)
                        continue
                except ValueError:
                    LOG.warning('Invalid VNI "%s" in ngs_mcast_group_map: '
                                'must be an integer', vni_str)
                    continue

                # Validate multicast group IP address
                try:
                    mcast_ip = ipaddress.IPv4Address(group_str)
                    # Validate it's in multicast range (224.0.0.0/4)
                    if not mcast_ip.is_multicast:
                        LOG.warning('IP address %s is not a valid '
                                    'multicast address in '
                                    'ngs_mcast_group_map', group_str)
                        continue
                except (ipaddress.AddressValueError, ValueError):
                    LOG.warning('Invalid IP address "%s" in '
                                'ngs_mcast_group_map', group_str)
                    continue

                # Warn on duplicate VNI
                if vni in self.mcast_group_map:
                    LOG.warning('Duplicate VNI %s in ngs_mcast_group_map, '
                                'using last entry: %s', vni, group_str)

                self.mcast_group_map[vni] = group_str

        super(CiscoNxOS, self).__init__(device_cfg, *args, **kwargs)

    def _get_multicast_group(self, vni: int) -> str:
        """Calculate multicast group address for a given VNI.

        Supports two methods for multicast group assignment:
        1. Explicit mapping via ngs_mcast_group_map (checked first)
        2. Automatic derivation from ngs_mcast_group_base (fallback)

        :param vni: VXLAN Network Identifier
        :returns: Multicast group IP address (e.g., '239.1.1.100')
        :raises: GenericSwitchConfigError if no mapping or base configured
        """
        # Check explicit mapping first
        if vni in self.mcast_group_map:
            return self.mcast_group_map[vni]

        # Fall back to automatic derivation from base
        if not self.mcast_group_base:
            LOG.error('VNI %s not found in ngs_mcast_group_map and '
                      'ngs_mcast_group_base not configured for switch %s',
                      vni, self.device_name)
            raise exc.GenericSwitchNetmikoConfigError()

        # Import here to avoid dependency if multicast not used
        import ipaddress

        base_ip = ipaddress.IPv4Address(self.mcast_group_base)

        # Use last octet of VNI as offset from base
        # Example: VNI 10100 with base 239.1.1.0 -> 239.1.1.100
        offset = vni % 256
        mcast_ip = ipaddress.IPv4Address(int(base_ip) + offset)

        return str(mcast_ip)

    def plug_switch_to_network(self, vni: int, segmentation_id: int,
                               physnet: str = None):
        """Configure L2VNI mapping with NVE interface membership.

        Supports two BUM traffic replication modes:
        1. ingress-replication (default): Uses BGP EVPN for BUM
           replication. Recommended for most deployments.
        2. multicast: Uses ASM multicast groups for BUM replication.
           Requires PIM Sparse Mode with Anycast RP configured on the
           fabric infrastructure.

        Configures the following in order:
        1. Configure EVPN VNI (BGP control plane for MAC/IP learning)
        2. Map VLAN to VNI (vn-segment)
        3. Add VNI as member to NVE interface
        4. Configure BUM replication (ingress-replication or mcast-group)

        :param vni: VXLAN Network Identifier
        :param segmentation_id: VLAN ID
        :param physnet: Physical network name (unused, kept for
                        compatibility)
        """
        cmds = [
            # Step 1: EVPN VNI configuration (BGP control plane)
            # NOTE: EVPN used for MAC/IP learning in both modes
            'evpn',
            'vni {vni} l2',
            'rd auto',
            'route-target both auto',
            'exit',
            # Step 2: VLAN to VNI mapping
            'vlan {segmentation_id}',
            'vn-segment {vni}',
            'exit',
            # Step 3: NVE interface membership
            'interface {nve_interface}',
            'member vni {vni}',
        ]

        # Step 4: BUM traffic replication configuration
        format_params = {
            'vni': vni,
            'segmentation_id': segmentation_id,
            'nve_interface': self.nve_interface,
        }

        if self.bum_replication_mode == 'multicast':
            # Use multicast group for BUM traffic (ASM with PIM)
            mcast_group = self._get_multicast_group(vni)
            cmds.extend([
                'mcast-group {mcast_group}',
                'exit',
            ])
            format_params['mcast_group'] = mcast_group
        else:
            # Use ingress-replication with BGP (default)
            cmds.extend([
                'ingress-replication protocol bgp',
                'exit',
            ])

        formatted_cmds = self._format_commands(tuple(cmds),
                                               **format_params)

        return self.send_commands_to_device(formatted_cmds)

    def unplug_switch_from_network(self, vni: int, segmentation_id: int,
                                   physnet: str = None):
        """Remove L2VNI mapping and NVE interface membership.

        Removes configuration in reverse order of creation:
        1. Remove NVE interface membership
        2. Remove VLAN to VNI mapping
        3. Remove EVPN VNI configuration

        :param vni: VXLAN Network Identifier to remove
        :param segmentation_id: VLAN ID
        :param physnet: Physical network name (unused but kept for signature)
        """
        cmds = [
            'interface {nve_interface}',
            'no member vni {vni}',
            'exit',
            'vlan {segmentation_id}',
            'no vn-segment',
            'exit',
            'evpn',
            'no vni {vni}',
            'exit',
        ]

        formatted_cmds = self._format_commands(
            tuple(cmds),
            vni=vni,
            segmentation_id=segmentation_id,
            nve_interface=self.nve_interface)

        return self.send_commands_to_device(formatted_cmds)

    def _get_acl_names(self, sg_id):
        # Add 'in' to the name to denote that this ACL contains switch
        # interface ingress (device egress) rules
        return {'security_group': f"ngs-in-{sg_id}"}

    def _prepare_security_group_rule(self, sg_id, rule):
        rule_dict = super(CiscoNxOS, self)._prepare_security_group_rule(
            sg_id, rule)
        min_port = rule_dict.get('port_range_min')
        max_port = rule_dict.get('port_range_max')
        filter = ''
        if rule_dict.get('protocol') in (const.PROTO_NAME_TCP,
                                         const.PROTO_NAME_UDP):
            if min_port and max_port and min_port != max_port:
                filter = f'range {min_port} {max_port}'
            elif min_port:
                filter = f'eq {min_port}'

        if rule_dict.get('protocol') == const.PROTO_NAME_ICMP:
            if min_port is not None and max_port is not None:
                filter = f'{min_port} {max_port}'
            elif min_port is not None:
                filter = f'{min_port}'

        rule_dict['filter'] = filter
        return rule_dict

    def _validate_rule(self, rule):
        if not super(CiscoNxOS, self)._validate_rule(rule):
            return False

        if rule.ethertype != const.IPv4:
            raise exc.GenericSwitchSecurityGroupRuleNotSupported(
                switch=self.device_name,
                error='Only IPv4 rules are supported.')
        if rule.direction == const.INGRESS_DIRECTION:
            raise exc.GenericSwitchSecurityGroupRuleNotSupported(
                switch=self.device_name,
                error='Only egress rules are supported '
                      '(switch interface ingress rules).')
        if rule.protocol not in (const.PROTO_NAME_TCP,
                                 const.PROTO_NAME_UDP,
                                 const.PROTO_NAME_ICMP):
            raise exc.GenericSwitchSecurityGroupRuleNotSupported(
                switch=self.device_name,
                error='Only protocols tcp, udp, icmp are supported.')
        return True

    def _parse_vlan_ports(self, output: str, segmentation_id: int) -> bool:
        """Parse Cisco NX-OS 'show vlan id X' output for ports.

        :param output: Command output from switch
        :param segmentation_id: VLAN identifier being checked
        :returns: True if VLAN has ports, False otherwise
        """
        # NX-OS output format:
        # VLAN Name                             Status    Ports
        # ---- -------------------------------- --------- -----------
        # 100  VLAN0100                         active    Eth1/1, Eth1/2
        lines = output.strip().split('\n')
        for line in lines:
            stripped = line.strip()
            # Skip empty lines, header, and separator
            if (not stripped
                    or stripped.startswith('VLAN Name')
                    or stripped.startswith('----')):
                continue
            # Look for line starting with our VLAN ID
            parts = line.split()
            if parts and parts[0] == str(segmentation_id):
                # Check if there are ports listed (index 3 onwards)
                return len(parts) > 3
        # If we can't find the VLAN, conservatively assume it has ports
        return True

    def _parse_vlan_vni(self, output: str, segmentation_id: int,
                        vni: int) -> bool:
        """Parse Cisco NX-OS 'show interface nveX' output for VNI membership.

        :param output: Command output from switch
        :param segmentation_id: VLAN identifier being checked (unused)
        :param vni: VNI to check for
        :returns: True if NVE interface has this VNI member, False otherwise
        """
        # NX-OS output format for 'show interface nve1 | include "member vni"':
        #   member vni 5000
        #     mcast-group 239.1.1.100
        #   member vni 6000
        #     ingress-replication protocol bgp
        #
        # We just need to check if "member vni {vni}" appears in output
        # The grep filter in SHOW_VLAN_VNI already filters for our VNI
        if not output or not output.strip():
            return False

        # Check if output contains "member vni {vni}"
        # The command already includes a grep filter, so any output means match
        return f'member vni {vni}' in output.lower()
