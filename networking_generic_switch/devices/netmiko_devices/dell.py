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

from neutron_lib import constants as const

from networking_generic_switch.devices import netmiko_devices
from networking_generic_switch import exceptions as exc


class DellOS10(netmiko_devices.NetmikoSwitch):
    """Device Name: Dell OS10 (netmiko_dell_os10)

    Port can be disabled: True

    Security Group Implementation
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Only IPv4 rules are implemented. Both ingress and egress rules are
    supported.
    """

    ADD_NETWORK = (
        "interface vlan {segmentation_id}",
        "description {network_name}",
        "exit",
    )

    DELETE_NETWORK = (
        "no interface vlan {segmentation_id}",
        "exit",
    )

    PLUG_PORT_TO_NETWORK = (
        "interface {port}",
        "switchport mode access",
        "switchport access vlan {segmentation_id}",
        "exit",
    )

    DELETE_PORT = (
        "interface {port}",
        "no switchport access vlan",
        "exit",
    )

    ADD_NETWORK_TO_TRUNK = (
        "interface {port}",
        "switchport mode trunk",
        "switchport trunk allowed vlan {segmentation_id}",
        "exit",
    )

    REMOVE_NETWORK_FROM_TRUNK = (
        "interface {port}",
        "no switchport trunk allowed vlan {segmentation_id}",
        "exit",
    )

    SET_NATIVE_VLAN = (
        'interface {port}',
        'switchport mode trunk',
        'switchport access vlan {segmentation_id}',
    )

    DELETE_NATIVE_VLAN = (
        'interface {port}',
        'no switchport access vlan',
    )

    ENABLE_PORT = (
        "interface {port}",
        "no shutdown",
        "exit",
    )

    DISABLE_PORT = (
        "interface {port}",
        "shutdown",
        "exit",
    )

    ADD_SECURITY_GROUP = (
        'ip access-list {security_group_ingress}',
        'exit',
        'ip access-list {security_group_egress}',
        'exit',
    )

    ADD_SECURITY_GROUP_COMPLETE = None

    REMOVE_SECURITY_GROUP = (
        'no ip access-list {security_group_ingress}',
        'no ip access-list {security_group_egress}',
    )

    ADD_SECURITY_GROUP_RULE_INGRESS = (
        'ip access-list {security_group_ingress}',
        'permit {protocol} {remote_ip_prefix} any {filter}',
        'exit',
    )

    ADD_SECURITY_GROUP_RULE_EGRESS = (
        'ip access-list {security_group_egress}',
        'permit {protocol} any {remote_ip_prefix} {filter}',
        'exit',
    )

    BIND_SECURITY_GROUP = (
        'interface {port}',
        'ip access-group {security_group_egress} in',
        'ip access-group {security_group_ingress} out',
        'exit',
        'show ip access-lists in',
        'show ip access-lists out',
    )

    UNBIND_SECURITY_GROUP = (
        'interface {port}',
        'no ip access-group {security_group_egress} in',
        'no ip access-group {security_group_ingress} out',
        'exit',
    )

    ERROR_MSG_PATTERNS = ()
    """Sequence of error message patterns.

    Sequence of re.RegexObject objects representing patterns to check for in
    device output that indicate a failure to apply configuration.
    """

    def _get_acl_names(self, sg_id):

        # Add 'in' and 'out' names interface ingress and egress (device egress
        # and ingress) rules
        return {
            'security_group_egress': f"ngs-in-{sg_id}",
            'security_group_ingress': f"ngs-out-{sg_id}"
        }

    def _prepare_security_group_rule(self, sg_id, rule):
        rule_dict = super(DellOS10, self)._prepare_security_group_rule(
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
        if not super(DellOS10, self)._validate_rule(rule):
            return False

        if rule.ethertype != const.IPv4:
            raise exc.GenericSwitchSecurityGroupRuleNotSupported(
                switch=self.device_name,
                error='Only IPv4 rules are supported.')
        if rule.protocol not in (const.PROTO_NAME_TCP,
                                 const.PROTO_NAME_UDP,
                                 const.PROTO_NAME_ICMP):
            raise exc.GenericSwitchSecurityGroupRuleNotSupported(
                switch=self.device_name,
                error='Only protocols tcp, udp, icmp are supported.')
        return True


class DellNos(netmiko_devices.NetmikoSwitch):
    """Device Name: Dell Force10 (OS9)(netmiko_dell_force10)"""

    ADD_NETWORK = (
        'interface vlan {segmentation_id}',
        # It's not possible to set the name on OS9: the field takes 32
        # chars max, and cannot begin with a number. Let's set the
        # description and leave the name empty.
        'description {network_name}',
        'exit',
    )

    DELETE_NETWORK = (
        'no interface vlan {segmentation_id}',
        'exit',
    )

    PLUG_PORT_TO_NETWORK = (
        'interface vlan {segmentation_id}',
        'untagged {port}',
        'exit',
    )

    DELETE_PORT = (
        'interface vlan {segmentation_id}',
        'no untagged {port}',
        'exit',
    )

    ADD_NETWORK_TO_TRUNK = (
        'interface vlan {segmentation_id}',
        'tagged {port}',
        'exit',
    )

    REMOVE_NETWORK_FROM_TRUNK = (
        'interface vlan {segmentation_id}',
        'no tagged {port}',
        'exit',
    )


class DellPowerConnect(netmiko_devices.NetmikoSwitch):
    """Device Name: Dell PowerConnect"""

    def _switch_to_general_mode(self):
        self.PLUG_PORT_TO_NETWORK = self.PLUG_PORT_TO_NETWORK_GENERAL
        self.DELETE_PORT = self.DELETE_PORT_GENERAL

    def __init__(self, device_cfg, *args, **kwargs):
        super(DellPowerConnect, self).__init__(device_cfg, *args, **kwargs)
        port_mode = self.ngs_config['ngs_switchport_mode']
        switchport_mode = {
            'general': self._switch_to_general_mode,
            'access': lambda: ()
        }

        def on_invalid_switchmode():
            raise exc.GenericSwitchConfigException(
                option="ngs_switchport_mode",
                allowed_options=switchport_mode.keys()
            )

        switchport_mode.get(port_mode.lower(), on_invalid_switchmode)()

    ADD_NETWORK = (
        'vlan database',
        'vlan {segmentation_id}',
        'exit',
    )

    DELETE_NETWORK = (
        'vlan database',
        'no vlan {segmentation_id}',
        'exit',
    )

    PLUG_PORT_TO_NETWORK_GENERAL = (
        'interface {port}',
        'switchport general allowed vlan add {segmentation_id} untagged',
        'switchport general pvid {segmentation_id}',
        'exit',
    )

    PLUG_PORT_TO_NETWORK = (
        'interface {port}',
        'switchport access vlan {segmentation_id}',
        'exit',
    )

    DELETE_PORT_GENERAL = (
        'interface {port}',
        'switchport general allowed vlan remove {segmentation_id}',
        'no switchport general pvid',
        'exit',
    )

    DELETE_PORT = (
        'interface {port}',
        'switchport access vlan none',
        'exit',
    )

    ADD_NETWORK_TO_TRUNK = (
        'interface {port}',
        'switchport general allowed vlan add {segmentation_id} tagged',
        'exit',
    )

    REMOVE_NETWORK_FROM_TRUNK = (
        'interface {port}',
        'switchport general allowed vlan remove {segmentation_id}',
        'exit',
    )

    ERROR_MSG_PATTERNS = (
        re.compile(r'\% Incomplete command'),
        re.compile(r'VLAN was not created by user'),
        re.compile(r'Configuration Database locked by another application \- '
                   r'try later'),
        re.compile(r'Port is not in Layer-2 mode'),
    )
