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

from unittest import mock

from networking_generic_switch.devices.netmiko_devices import cisco
from networking_generic_switch import exceptions as exc
from networking_generic_switch.tests.unit.netmiko import test_netmiko_base


class TestNetmikoCiscoNxOS(test_netmiko_base.NetmikoSwitchTestBase):

    def _make_switch_device(self):
        device_cfg = {'device_type': 'netmiko_cisco_nxos'}
        return cisco.CiscoNxOS(device_cfg)

    def test_constants(self):
        self.assertIsNone(self.switch.SAVE_CONFIGURATION)

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device', autospec=True)
    def test_add_network(self, m_exec):
        self.switch.add_network(33, '0ae071f5-5be9-43e4-80ea-e41fefe85b21')
        m_exec.assert_called_with(
            self.switch,
            ['vlan 33', 'name 0ae071f55be943e480eae41fefe85b21', 'exit'])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device', autospec=True)
    def test_del_network(self, mock_exec):
        self.switch.del_network(33, '0ae071f5-5be9-43e4-80ea-e41fefe85b21')
        mock_exec.assert_called_with(self.switch, ['no vlan 33'])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device', autospec=True)
    def test_plug_port_to_network(self, mock_exec):
        self.switch.plug_port_to_network(3333, 33)
        mock_exec.assert_called_with(
            self.switch,
            ['interface 3333', 'switchport mode access',
             'switchport access vlan 33', 'exit'])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device', autospec=True)
    def test_delete_port(self, mock_exec):
        self.switch.delete_port(3333, 33)
        mock_exec.assert_called_with(
            self.switch,
            ['interface 3333', 'no switchport access vlan', 'exit'])

    def test__format_commands(self):
        cmd_set = self.switch._format_commands(
            cisco.CiscoNxOS.ADD_NETWORK,
            segmentation_id=22,
            network_id=22,
            network_name='vlan-22')
        self.assertEqual(cmd_set, ['vlan 22', 'name vlan-22', 'exit'])

        cmd_set = self.switch._format_commands(
            cisco.CiscoNxOS.DELETE_NETWORK,
            segmentation_id=22)
        self.assertEqual(cmd_set, ['no vlan 22'])

        cmd_set = self.switch._format_commands(
            cisco.CiscoNxOS.PLUG_PORT_TO_NETWORK,
            port=3333,
            segmentation_id=33)
        plug_exp = ['interface 3333', 'switchport mode access',
                    'switchport access vlan 33', 'exit']
        self.assertEqual(plug_exp, cmd_set)

        cmd_set = self.switch._format_commands(
            cisco.CiscoNxOS.DELETE_PORT,
            port=3333,
            segmentation_id=33)
        del_exp = ['interface 3333', 'no switchport access vlan', 'exit']
        self.assertEqual(del_exp, cmd_set)

        cmd_set = self.switch._format_commands(
            cisco.CiscoNxOS.ADD_NETWORK_TO_TRUNK,
            port=3333,
            segmentation_id=33)
        add_trunk_exp = ['interface 3333', 'switchport mode trunk',
                         'switchport trunk allowed vlan add 33', 'exit']
        self.assertEqual(add_trunk_exp, cmd_set)

        cmd_set = self.switch._format_commands(
            cisco.CiscoNxOS.REMOVE_NETWORK_FROM_TRUNK,
            port=3333,
            segmentation_id=33)
        del_trunk_exp = ['interface 3333',
                         'switchport trunk allowed vlan remove 33',
                         'exit']
        self.assertEqual(del_trunk_exp, cmd_set)

        cmd_set = self.switch._format_commands(
            cisco.CiscoNxOS.ENABLE_PORT,
            port=3333)
        enable_exp = ['interface 3333', 'no shutdown', 'exit']
        self.assertEqual(enable_exp, cmd_set)

        cmd_set = self.switch._format_commands(
            cisco.CiscoNxOS.DISABLE_PORT,
            port=3333)
        disable_exp = ['interface 3333', 'shutdown', 'exit']
        self.assertEqual(disable_exp, cmd_set)

        self.assertEqual([
            'ip access-list ngs-1234',
        ], self.switch._format_commands(
            cisco.CiscoNxOS.ADD_SECURITY_GROUP,
            security_group='ngs-1234'))

        self.assertEqual([
            'exit',
        ], self.switch._format_commands(
            cisco.CiscoNxOS.ADD_SECURITY_GROUP_COMPLETE))

        self.assertEqual([
            'no ip access-list ngs-1234',
        ], self.switch._format_commands(
            cisco.CiscoNxOS.REMOVE_SECURITY_GROUP,
            security_group='ngs-1234'))

        self.assertEqual([
            'permit tcp any 0.0.0.0/0 eq 80',
        ], self.switch._format_commands(
            cisco.CiscoNxOS.ADD_SECURITY_GROUP_RULE_EGRESS,
            security_group='ngs-1234',
            protocol='tcp',
            remote_ip_prefix='0.0.0.0/0',
            filter='eq 80'))

        self.assertEqual([
            'interface ethernet1/1',
            'ip port access-group ngs-1234 in',
            'exit'
        ], self.switch._format_commands(
            cisco.CiscoNxOS.BIND_SECURITY_GROUP,
            security_group='ngs-1234',
            port='ethernet1/1'))

        self.assertEqual([
            'interface ethernet1/1',
            'no ip port access-group ngs-1234 in',
            'exit'
        ], self.switch._format_commands(
            cisco.CiscoNxOS.UNBIND_SECURITY_GROUP,
            security_group='ngs-1234',
            port='ethernet1/1'))

    def test__prepare_security_group_rule(self):
        # empty rule
        rule = mock.Mock(
            ethertype=None,
            protocol=None,
            direction=None,
            remote_ip_prefix=None,
            normalized_cidr=None,
            port_range_min=None,
            port_range_max=None,
        )
        self.assertEqual(
            {
                'security_group': 'ngs-in-1234',
                'filter': ''
            },
            self.switch._prepare_security_group_rule('1234', rule))

        # tcp, no ports
        rule = mock.Mock(
            ethertype=None,
            protocol='tcp',
            direction=None,
            remote_ip_prefix=None,
            normalized_cidr=None,
            port_range_min=None,
            port_range_max=None,
        )
        self.assertEqual(
            {
                'security_group': 'ngs-in-1234',
                'protocol': 'tcp',
                'filter': ''
            },
            self.switch._prepare_security_group_rule('1234', rule))

        # udp, one port
        rule = mock.Mock(
            ethertype=None,
            protocol='udp',
            direction=None,
            remote_ip_prefix=None,
            normalized_cidr=None,
            port_range_min=53,
            port_range_max=None,
        )
        self.assertEqual(
            {
                'security_group': 'ngs-in-1234',
                'protocol': 'udp',
                'port_range_min': 53,
                'filter': 'eq 53'
            },
            self.switch._prepare_security_group_rule('1234', rule))

        # # tcp, port range
        rule = mock.Mock(
            ethertype=None,
            protocol='tcp',
            direction=None,
            remote_ip_prefix=None,
            normalized_cidr=None,
            port_range_min=8080,
            port_range_max=8089,
        )
        self.assertEqual(
            {
                'security_group': 'ngs-in-1234',
                'protocol': 'tcp',
                'port_range_min': 8080,
                'port_range_max': 8089,
                'filter': 'range 8080 8089'
            },
            self.switch._prepare_security_group_rule('1234', rule))

        # # icmp, all
        rule = mock.Mock(
            ethertype=None,
            protocol='icmp',
            direction=None,
            remote_ip_prefix=None,
            normalized_cidr=None,
            port_range_min=None,
            port_range_max=None,
        )
        self.assertEqual(
            {
                'security_group': 'ngs-in-1234',
                'protocol': 'icmp',
                'filter': ''
            },
            self.switch._prepare_security_group_rule('1234', rule))

        # # icmp, type
        rule = mock.Mock(
            ethertype=None,
            protocol='icmp',
            direction=None,
            remote_ip_prefix=None,
            normalized_cidr=None,
            port_range_min=3,
            port_range_max=None,
        )
        self.assertEqual(
            {
                'security_group': 'ngs-in-1234',
                'protocol': 'icmp',
                'port_range_min': 3,
                'filter': '3'
            },
            self.switch._prepare_security_group_rule('1234', rule))

        # # icmp, type and code
        rule = mock.Mock(
            ethertype=None,
            protocol='icmp',
            direction=None,
            remote_ip_prefix=None,
            normalized_cidr=None,
            port_range_min=3,
            port_range_max=1,
        )
        self.assertEqual(
            {
                'security_group': 'ngs-in-1234',
                'protocol': 'icmp',
                'port_range_min': 3,
                'port_range_max': 1,
                'filter': '3 1'
            },
            self.switch._prepare_security_group_rule('1234', rule))

    def test__validate_rule(self):
        # acceptable rule
        self.assertTrue(self.switch._validate_rule(mock.Mock(
            protocol='tcp',
            ethertype='IPv4',
            direction='egress'
        )))

        # no ipv6
        self.assertRaises(
            exc.GenericSwitchSecurityGroupRuleNotSupported,
            self.switch._validate_rule,
            mock.Mock(
                protocol='tcp',
                ethertype='IPv6',
                direction='egress'
            )
        )

        # no ingress
        self.assertRaises(
            exc.GenericSwitchSecurityGroupRuleNotSupported,
            self.switch._validate_rule,
            mock.Mock(
                protocol='tcp',
                ethertype='IPv4',
                direction='ingress'
            )
        )

        # restricted protocols
        self.assertRaises(
            exc.GenericSwitchSecurityGroupRuleNotSupported,
            self.switch._validate_rule,
            mock.Mock(
                protocol='vrrp',
                ethertype='IPv4',
                direction='egress'
            )
        )

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device',
                return_value='fake output', autospec=True)
    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.check_output', autospec=True)
    def test_add_security_group(self, m_check, m_sctd):
        rule1 = mock.Mock(
            ethertype='IPv4',
            protocol='tcp',
            direction='egress',
            remote_ip_prefix='0.0.0.0/0',
            normalized_cidr='0.0.0.0/0',
            port_range_min='22',
            port_range_max='23'
        )
        rule2 = mock.Mock(
            ethertype='IPv4',
            protocol='tcp',
            direction='egress',
            remote_ip_prefix='0.0.0.0/0',
            normalized_cidr='0.0.0.0/0',
            port_range_min='80',
            port_range_max='80'
        )
        sg = mock.Mock()
        sg.id = '1234'
        sg.rules = [rule1, rule2]
        self.switch.add_security_group(sg)
        m_sctd.assert_called_with(self.switch, [
            'ip access-list ngs-in-1234',
            'permit tcp any 0.0.0.0/0 range 22 23',
            'permit tcp any 0.0.0.0/0 eq 80',
            'exit'])
        m_check.assert_called_once_with(self.switch, 'fake output',
                                        'add security group')

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device',
                return_value="", autospec=True)
    def test_del_security_group(self, mock_exec):
        self.switch.del_security_group('1234abcd')
        mock_exec.assert_called_with(
            self.switch,
            ['no ip access-list ngs-in-1234abcd'])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device',
                return_value='fake output', autospec=True)
    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.check_output', autospec=True)
    def test_bind_security_group(self, m_check, m_sctd):
        sg = mock.Mock()
        sg.id = '1234'
        sg.rules = []
        self.switch.bind_security_group(sg, 'port1', ['port1', 'port2'])
        m_sctd.assert_called_with(self.switch, [
            'no ip access-list ngs-in-1234',
            'ip access-list ngs-in-1234',
            'exit',
            'interface port1',
            'ip port access-group ngs-in-1234 in',
            'exit',
            'interface port2',
            'ip port access-group ngs-in-1234 in',
            'exit'])
        m_check.assert_called_once_with(self.switch, 'fake output',
                                        'bind security group')

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device',
                return_value='fake output', autospec=True)
    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.check_output', autospec=True)
    def test_unbind_security_group(self, m_check, m_sctd):
        self.switch.unbind_security_group('1234', 'port1', ['port2'])
        m_sctd.assert_called_with(self.switch, [
            'interface port1',
            'no ip port access-group ngs-in-1234 in',
            'exit',
            'interface port2',
            'ip port access-group ngs-in-1234 in',
            'exit'])
        m_check.assert_called_once_with(self.switch, 'fake output',
                                        'unbind security group')
