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
        self.assertTrue(self.switch.PLUG_SWITCH_TO_NETWORK)
        self.assertTrue(self.switch.UNPLUG_SWITCH_FROM_NETWORK)

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

    # NVE Interface / L2VNI Tests

    def test_init_default_nve_config(self):
        """Test __init__ with default NVE configuration."""
        device_cfg = {'device_type': 'netmiko_cisco_nxos'}
        switch = cisco.CiscoNxOS(device_cfg)
        self.assertEqual(switch.nve_interface, 'nve1')

    def test_init_custom_nve_interface(self):
        """Test __init__ with custom NVE interface."""
        device_cfg = {
            'device_type': 'netmiko_cisco_nxos',
            'ngs_nve_interface': 'nve2'
        }
        switch = cisco.CiscoNxOS(device_cfg)
        self.assertEqual(switch.nve_interface, 'nve2')

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device', autospec=True)
    def test_plug_switch_to_network_with_ingress_replication(self, mock_exec):
        """Test plug_switch_to_network uses ingress-replication with EVPN."""
        device_cfg = {'device_type': 'netmiko_cisco_nxos'}
        switch = cisco.CiscoNxOS(device_cfg)
        switch.plug_switch_to_network(10100, 100, physnet='physnet1')
        mock_exec.assert_called_with(
            switch,
            ['evpn', 'vni 10100 l2', 'rd auto', 'route-target both auto',
             'exit', 'vlan 100', 'vn-segment 10100', 'exit',
             'interface nve1', 'member vni 10100',
             'ingress-replication protocol bgp', 'exit'])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device', autospec=True)
    def test_plug_switch_to_network_custom_nve_interface(self, mock_exec):
        """Test plug_switch_to_network uses custom NVE interface."""
        device_cfg = {
            'device_type': 'netmiko_cisco_nxos',
            'ngs_nve_interface': 'nve2'
        }
        switch = cisco.CiscoNxOS(device_cfg)
        switch.plug_switch_to_network(10100, 100)
        mock_exec.assert_called_with(
            switch,
            ['evpn', 'vni 10100 l2', 'rd auto', 'route-target both auto',
             'exit', 'vlan 100', 'vn-segment 10100', 'exit',
             'interface nve2', 'member vni 10100',
             'ingress-replication protocol bgp', 'exit'])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device', autospec=True)
    def test_unplug_switch_from_network(self, mock_exec):
        """Test unplug_switch_from_network removes NVE and EVPN config."""
        device_cfg = {'device_type': 'netmiko_cisco_nxos'}
        switch = cisco.CiscoNxOS(device_cfg)
        switch.unplug_switch_from_network(10100, 100)
        mock_exec.assert_called_with(
            switch,
            ['interface nve1', 'no member vni 10100', 'exit',
             'vlan 100', 'no vn-segment', 'exit',
             'evpn', 'no vni 10100', 'exit'])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device', autospec=True)
    def test_unplug_switch_from_network_custom_nve(self, mock_exec):
        """Test unplug_switch_from_network uses custom NVE interface."""
        device_cfg = {
            'device_type': 'netmiko_cisco_nxos',
            'ngs_nve_interface': 'nve2'
        }
        switch = cisco.CiscoNxOS(device_cfg)
        switch.unplug_switch_from_network(10100, 100)
        mock_exec.assert_called_with(
            switch,
            ['interface nve2', 'no member vni 10100', 'exit',
             'vlan 100', 'no vn-segment', 'exit',
             'evpn', 'no vni 10100', 'exit'])

    # Multicast BUM replication tests

    def test_init_multicast_config(self):
        """Test __init__ with multicast BUM replication configuration."""
        device_cfg = {
            'device_type': 'netmiko_cisco_nxos',
            'ngs_bum_replication_mode': 'multicast',
            'ngs_mcast_group_base': '239.1.1.0',
            'ngs_mcast_group_increment': 'vni_last_octet'
        }
        switch = cisco.CiscoNxOS(device_cfg)
        self.assertEqual(switch.bum_replication_mode, 'multicast')
        self.assertEqual(switch.mcast_group_base, '239.1.1.0')
        self.assertEqual(switch.mcast_group_increment, 'vni_last_octet')

    def test_init_default_bum_replication_mode(self):
        """Test __init__ defaults to ingress-replication mode."""
        device_cfg = {'device_type': 'netmiko_cisco_nxos'}
        switch = cisco.CiscoNxOS(device_cfg)
        self.assertEqual(switch.bum_replication_mode,
                         'ingress-replication')
        self.assertIsNone(switch.mcast_group_base)

    def test_get_multicast_group(self):
        """Test _get_multicast_group calculates correct addresses."""
        device_cfg = {
            'device_type': 'netmiko_cisco_nxos',
            'ngs_bum_replication_mode': 'multicast',
            'ngs_mcast_group_base': '239.1.1.0'
        }
        switch = cisco.CiscoNxOS(device_cfg)

        # VNI 10100 % 256 = 116 -> 239.1.1.116
        self.assertEqual(switch._get_multicast_group(10100), '239.1.1.116')

        # VNI 10200 % 256 = 216 -> 239.1.1.216
        self.assertEqual(switch._get_multicast_group(10200), '239.1.1.216')

        # VNI 10001 % 256 = 17 -> 239.1.1.17
        self.assertEqual(switch._get_multicast_group(10001), '239.1.1.17')

        # VNI 5000 % 256 = 136 -> 239.1.1.136
        self.assertEqual(switch._get_multicast_group(5000), '239.1.1.136')

        # VNI 100 % 256 = 100 -> 239.1.1.100 (clean example)
        self.assertEqual(switch._get_multicast_group(100), '239.1.1.100')

    def test_get_multicast_group_without_base_raises_error(self):
        """Test _get_multicast_group raises error without base config."""
        device_cfg = {
            'device_type': 'netmiko_cisco_nxos',
            'ngs_bum_replication_mode': 'multicast'
        }
        switch = cisco.CiscoNxOS(device_cfg)

        self.assertRaises(
            exc.GenericSwitchNetmikoConfigError,
            switch._get_multicast_group,
            10100
        )

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device', autospec=True)
    def test_plug_switch_to_network_with_multicast(self, mock_exec):
        """Test plug_switch_to_network uses multicast groups."""
        device_cfg = {
            'device_type': 'netmiko_cisco_nxos',
            'ngs_bum_replication_mode': 'multicast',
            'ngs_mcast_group_base': '239.1.1.0'
        }
        switch = cisco.CiscoNxOS(device_cfg)
        switch.plug_switch_to_network(10100, 100, physnet='physnet1')
        # VNI 10100 % 256 = 116, so mcast group is 239.1.1.116
        mock_exec.assert_called_with(
            switch,
            ['evpn', 'vni 10100 l2', 'rd auto', 'route-target both auto',
             'exit', 'vlan 100', 'vn-segment 10100', 'exit',
             'interface nve1', 'member vni 10100',
             'mcast-group 239.1.1.116', 'exit'])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device', autospec=True)
    def test_plug_switch_to_network_multicast_custom_nve(self, mock_exec):
        """Test multicast mode with custom NVE interface."""
        device_cfg = {
            'device_type': 'netmiko_cisco_nxos',
            'ngs_bum_replication_mode': 'multicast',
            'ngs_mcast_group_base': '239.2.2.0',
            'ngs_nve_interface': 'nve2'
        }
        switch = cisco.CiscoNxOS(device_cfg)
        switch.plug_switch_to_network(5000, 50)
        # VNI 5000 % 256 = 136, so mcast group is 239.2.2.136
        mock_exec.assert_called_with(
            switch,
            ['evpn', 'vni 5000 l2', 'rd auto', 'route-target both auto',
             'exit', 'vlan 50', 'vn-segment 5000', 'exit',
             'interface nve2', 'member vni 5000',
             'mcast-group 239.2.2.136', 'exit'])

    def test_init_with_mcast_group_map(self):
        """Test __init__ parses ngs_mcast_group_map correctly."""
        device_cfg = {
            'device_type': 'netmiko_cisco_nxos',
            'ngs_bum_replication_mode': 'multicast',
            'ngs_mcast_group_map': '10100:239.1.1.100, 10200:239.1.1.200'
        }
        switch = cisco.CiscoNxOS(device_cfg)
        self.assertEqual(switch.mcast_group_map[10100], '239.1.1.100')
        self.assertEqual(switch.mcast_group_map[10200], '239.1.1.200')
        self.assertEqual(len(switch.mcast_group_map), 2)

    def test_get_multicast_group_from_explicit_map(self):
        """Test _get_multicast_group uses explicit mapping first."""
        device_cfg = {
            'device_type': 'netmiko_cisco_nxos',
            'ngs_bum_replication_mode': 'multicast',
            'ngs_mcast_group_map': '10100:239.5.5.100, 5000:239.10.10.50',
            'ngs_mcast_group_base': '239.1.1.0'
        }
        switch = cisco.CiscoNxOS(device_cfg)

        # Explicit mapping should take precedence
        self.assertEqual(switch._get_multicast_group(10100),
                         '239.5.5.100')
        self.assertEqual(switch._get_multicast_group(5000),
                         '239.10.10.50')

        # Unmapped VNI should fall back to base calculation
        # VNI 10200 % 256 = 216 -> 239.1.1.216
        self.assertEqual(switch._get_multicast_group(10200),
                         '239.1.1.216')

    def test_get_multicast_group_map_without_base_fallback(self):
        """Test explicit map works without base for mapped VNIs."""
        device_cfg = {
            'device_type': 'netmiko_cisco_nxos',
            'ngs_bum_replication_mode': 'multicast',
            'ngs_mcast_group_map': '10100:239.1.1.100'
        }
        switch = cisco.CiscoNxOS(device_cfg)

        # Mapped VNI should work
        self.assertEqual(switch._get_multicast_group(10100),
                         '239.1.1.100')

        # Unmapped VNI should raise error (no base configured)
        self.assertRaises(
            exc.GenericSwitchNetmikoConfigError,
            switch._get_multicast_group,
            10200
        )

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device', autospec=True)
    def test_plug_switch_to_network_with_explicit_mcast_map(self, mock_exec):
        """Test plug_switch_to_network uses explicit mapping."""
        device_cfg = {
            'device_type': 'netmiko_cisco_nxos',
            'ngs_bum_replication_mode': 'multicast',
            'ngs_mcast_group_map': '10100:239.99.99.99'
        }
        switch = cisco.CiscoNxOS(device_cfg)
        switch.plug_switch_to_network(10100, 100)

        # Should use explicit mapping instead of calculation
        mock_exec.assert_called_with(
            switch,
            ['evpn', 'vni 10100 l2', 'rd auto', 'route-target both auto',
             'exit', 'vlan 100', 'vn-segment 10100', 'exit',
             'interface nve1', 'member vni 10100',
             'mcast-group 239.99.99.99', 'exit'])

    def test_mcast_group_map_validation_invalid_ip(self):
        """Test ngs_mcast_group_map rejects invalid IP addresses."""
        device_cfg = {
            'device_type': 'netmiko_cisco_nxos',
            'ngs_mcast_group_map': '10100:not.an.ip, 10200:239.1.1.200'
        }
        switch = cisco.CiscoNxOS(device_cfg)
        # Invalid entry should be skipped
        self.assertNotIn(10100, switch.mcast_group_map)
        # Valid entry should be parsed
        self.assertIn(10200, switch.mcast_group_map)

    def test_mcast_group_map_validation_non_multicast_ip(self):
        """Test ngs_mcast_group_map rejects non-multicast addresses."""
        device_cfg = {
            'device_type': 'netmiko_cisco_nxos',
            'ngs_mcast_group_map': '10100:192.168.1.1, 10200:239.1.1.200'
        }
        switch = cisco.CiscoNxOS(device_cfg)
        # Unicast IP should be rejected
        self.assertNotIn(10100, switch.mcast_group_map)
        # Multicast IP should be accepted
        self.assertIn(10200, switch.mcast_group_map)

    def test_mcast_group_map_validation_invalid_vni(self):
        """Test ngs_mcast_group_map rejects invalid VNI values."""
        device_cfg = {
            'device_type': 'netmiko_cisco_nxos',
            'ngs_mcast_group_map': 'abc:239.1.1.100, 10200:239.1.1.200'
        }
        switch = cisco.CiscoNxOS(device_cfg)
        # Non-integer VNI should be rejected
        self.assertNotIn('abc', switch.mcast_group_map)
        # Valid entry should be parsed
        self.assertIn(10200, switch.mcast_group_map)

    def test_mcast_group_map_validation_vni_out_of_range(self):
        """Test ngs_mcast_group_map rejects VNI out of valid range."""
        device_cfg = {
            'device_type': 'netmiko_cisco_nxos',
            'ngs_mcast_group_map': '0:239.1.1.1, 16777216:239.1.1.2, '
                                   '10100:239.1.1.100'
        }
        switch = cisco.CiscoNxOS(device_cfg)
        # VNI 0 (below minimum) should be rejected
        self.assertNotIn(0, switch.mcast_group_map)
        # VNI 16777216 (above maximum) should be rejected
        self.assertNotIn(16777216, switch.mcast_group_map)
        # Valid VNI should be accepted
        self.assertIn(10100, switch.mcast_group_map)

    def test_mcast_group_map_duplicate_vni_uses_last(self):
        """Test ngs_mcast_group_map uses last entry for duplicate VNIs."""
        device_cfg = {
            'device_type': 'netmiko_cisco_nxos',
            'ngs_mcast_group_map': '10100:239.1.1.1, 10100:239.1.1.2'
        }
        switch = cisco.CiscoNxOS(device_cfg)
        # Should use last entry for duplicate VNI
        self.assertEqual(switch.mcast_group_map[10100], '239.1.1.2')

    def test_mcast_group_map_handles_whitespace(self):
        """Test ngs_mcast_group_map handles extra whitespace."""
        device_cfg = {
            'device_type': 'netmiko_cisco_nxos',
            'ngs_mcast_group_map': '  10100 : 239.1.1.100 , '
                                   '10200:239.1.1.200  '
        }
        switch = cisco.CiscoNxOS(device_cfg)
        self.assertEqual(switch.mcast_group_map[10100], '239.1.1.100')
        self.assertEqual(switch.mcast_group_map[10200], '239.1.1.200')

    def test_parse_vlan_vni_with_ingress_replication(self):
        """Test _parse_vlan_vni detects VNI with ingress-replication."""
        device_cfg = {'device_type': 'netmiko_cisco_nxos'}
        switch = cisco.CiscoNxOS(device_cfg)
        output = """
  member vni 10100
    ingress-replication protocol bgp
"""
        self.assertTrue(switch._parse_vlan_vni(output, 100, 10100))

    def test_parse_vlan_vni_with_multicast(self):
        """Test _parse_vlan_vni detects VNI with multicast group."""
        device_cfg = {'device_type': 'netmiko_cisco_nxos'}
        switch = cisco.CiscoNxOS(device_cfg)
        output = """
  member vni 10100
    mcast-group 239.1.1.100
"""
        self.assertTrue(switch._parse_vlan_vni(output, 100, 10100))

    def test_parse_vlan_vni_not_found(self):
        """Test _parse_vlan_vni returns False when VNI not found."""
        device_cfg = {'device_type': 'netmiko_cisco_nxos'}
        switch = cisco.CiscoNxOS(device_cfg)
        output = """
  member vni 10200
    ingress-replication protocol bgp
"""
        self.assertFalse(switch._parse_vlan_vni(output, 100, 10100))

    def test_parse_vlan_vni_empty_output(self):
        """Test _parse_vlan_vni handles empty output."""
        device_cfg = {'device_type': 'netmiko_cisco_nxos'}
        switch = cisco.CiscoNxOS(device_cfg)
        self.assertFalse(switch._parse_vlan_vni('', 100, 10100))
        self.assertFalse(switch._parse_vlan_vni('   ', 100, 10100))

    def test_parse_vlan_ports_with_ports(self):
        """Test _parse_vlan_ports detects VLAN with ports."""
        device_cfg = {'device_type': 'netmiko_cisco_nxos'}
        switch = cisco.CiscoNxOS(device_cfg)
        output = """
VLAN Name                             Status    Ports
---- -------------------------------- --------- -------------------------------
100  VLAN0100                         active    Eth1/1, Eth1/2, Eth1/3
"""
        self.assertTrue(switch._parse_vlan_ports(output, 100))

    def test_parse_vlan_ports_without_ports(self):
        """Test _parse_vlan_ports detects empty VLAN."""
        device_cfg = {'device_type': 'netmiko_cisco_nxos'}
        switch = cisco.CiscoNxOS(device_cfg)
        output = """
VLAN Name                             Status    Ports
---- -------------------------------- --------- -------------------------------
100  VLAN0100                         active
"""
        self.assertFalse(switch._parse_vlan_ports(output, 100))

    def test_parse_vlan_ports_with_custom_name_containing_vlan(self):
        """Test _parse_vlan_ports with custom VLAN name containing 'VLAN'."""
        device_cfg = {'device_type': 'netmiko_cisco_nxos'}
        switch = cisco.CiscoNxOS(device_cfg)
        output = """
VLAN Name                             Status    Ports
---- -------------------------------- --------- -------------------------------
200  MyVLAN-Network                   active    Eth1/5, Eth1/6
"""
        self.assertTrue(switch._parse_vlan_ports(output, 200))

    def test_parse_vlan_ports_not_found(self):
        """Test _parse_vlan_ports returns True when VLAN not found."""
        device_cfg = {'device_type': 'netmiko_cisco_nxos'}
        switch = cisco.CiscoNxOS(device_cfg)
        output = """
VLAN Name                             Status    Ports
---- -------------------------------- --------- -------------------------------
200  VLAN0200                         active    Eth1/1
"""
        # Conservatively assumes ports exist when VLAN not found
        self.assertTrue(switch._parse_vlan_ports(output, 100))

    def test_parse_vlan_ports_empty_output(self):
        """Test _parse_vlan_ports handles empty output."""
        device_cfg = {'device_type': 'netmiko_cisco_nxos'}
        switch = cisco.CiscoNxOS(device_cfg)
        # Conservatively assumes ports exist on empty output
        self.assertTrue(switch._parse_vlan_ports('', 100))
        self.assertTrue(switch._parse_vlan_ports('   ', 100))

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch._get_connection', autospec=True)
    def test_vlan_has_vni_default_nve(self, mock_conn):
        """Test vlan_has_vni uses default nve1 interface."""
        device_cfg = {'device_type': 'netmiko_cisco_nxos'}
        switch = cisco.CiscoNxOS(device_cfg)

        mock_net_connect = mock.MagicMock()
        mock_conn.return_value.__enter__.return_value = mock_net_connect
        mock_net_connect.send_command.return_value = (
            '  member vni 10100\n    ingress-replication protocol bgp')

        result = switch.vlan_has_vni(100, 10100)

        mock_net_connect.send_command.assert_called_once_with(
            'show interface nve1 | include "member vni 10100"')
        self.assertTrue(result)

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch._get_connection', autospec=True)
    def test_vlan_has_vni_custom_nve(self, mock_conn):
        """Test vlan_has_vni uses custom NVE interface."""
        device_cfg = {
            'device_type': 'netmiko_cisco_nxos',
            'ngs_nve_interface': 'nve2'
        }
        switch = cisco.CiscoNxOS(device_cfg)

        mock_net_connect = mock.MagicMock()
        mock_conn.return_value.__enter__.return_value = mock_net_connect
        mock_net_connect.send_command.return_value = ''

        result = switch.vlan_has_vni(100, 10100)

        mock_net_connect.send_command.assert_called_once_with(
            'show interface nve2 | include "member vni 10100"')
        self.assertFalse(result)

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch._get_connection', autospec=True)
    def test_vlan_has_vni_vni_not_found(self, mock_conn):
        """Test vlan_has_vni returns False when VNI not found."""
        device_cfg = {'device_type': 'netmiko_cisco_nxos'}
        switch = cisco.CiscoNxOS(device_cfg)

        mock_net_connect = mock.MagicMock()
        mock_conn.return_value.__enter__.return_value = mock_net_connect
        mock_net_connect.send_command.return_value = (
            '  member vni 10200\n    ingress-replication protocol bgp')

        result = switch.vlan_has_vni(100, 10100)

        mock_net_connect.send_command.assert_called_once_with(
            'show interface nve1 | include "member vni 10100"')
        self.assertFalse(result)
