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

from networking_generic_switch.devices import netmiko_devices
from networking_generic_switch import exceptions as exc


class CiscoIos(netmiko_devices.NetmikoSwitch):
    """Device Name: Cisco IOS"""
    ADD_NETWORK = (
        'vlan {segmentation_id}',
        'name {network_name}',
    )

    DELETE_NETWORK = (
        'no vlan {segmentation_id}',
    )

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
