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
