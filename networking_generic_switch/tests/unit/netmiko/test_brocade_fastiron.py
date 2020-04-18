# Copyright 2017 Servers.com
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
# based on test_cisco_ios.py by Mirantis


from unittest import mock

from networking_generic_switch.devices.netmiko_devices import brocade
from networking_generic_switch.tests.unit.netmiko import test_netmiko_base


class TestNetmikoBrocadeFastIron(test_netmiko_base.NetmikoSwitchTestBase):

    def _make_switch_device(self):
        device_cfg = {'device_type': 'netmiko_brocade_fastiron'}
        return brocade.BrocadeFastIron(device_cfg)

    def test_constants(self):
        self.assertIsNone(self.switch.SAVE_CONFIGURATION)

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device')
    def test_add_network(self, m_exec):
        self.switch.add_network(33, '0ae071f5-5be9-43e4-80ea-e41fefe85b21')
        m_exec.assert_called_with(
            ['vlan 33 by port', 'name 0ae071f55be943e480eae41fefe85b21'])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device')
    def test_del_network(self, mock_exec):
        self.switch.del_network(33, '0ae071f5-5be9-43e4-80ea-e41fefe85b21')
        mock_exec.assert_called_with(['no vlan 33'])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device')
    def test_plug_port_to_network(self, mock_exec):
        self.switch.plug_port_to_network(3333, 33)
        mock_exec.assert_called_with(
            ['vlan 33 by port', 'untagged ether 3333'])

    def test_plug_port_to_network_with_cleaning(self):
        with mock.patch(
            'networking_generic_switch.devices.netmiko_devices.'
            'NetmikoSwitch.send_commands_to_device'
        ) as m_exec:
            m_exec.return_value = "Member of L2 VLAN ID 22, port is untagged."
            self.switch.plug_port_to_network(3333, 33)
            m_exec.assert_has_calls([
                mock.call(['show interfaces ether 3333 | include VLAN']),
                mock.call(['vlan 22 by port', 'no untagged ether 3333']),
                mock.call(['vlan 33 by port', 'untagged ether 3333']),
            ])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device')
    def test_delete_port(self, mock_exec):
        self.switch.delete_port(3333, 33)
        mock_exec.assert_called_with(
            ['vlan 33 by port', 'no untagged ether 3333'])

    def test__format_commands(self):
        cmd_set = self.switch._format_commands(
            brocade.BrocadeFastIron.ADD_NETWORK,
            segmentation_id=22,
            network_id=22,
            network_name='vlan-22')
        self.assertEqual(cmd_set, ['vlan 22 by port', 'name vlan-22'])

        cmd_set = self.switch._format_commands(
            brocade.BrocadeFastIron.DELETE_NETWORK,
            segmentation_id=22)
        self.assertEqual(cmd_set, ['no vlan 22'])

    def test__process_raw_output_empty(self):
        self.assertIsNone(self.switch._process_raw_output(''))

    def test__process_raw_output_tagged(self):
        self.assertIsNone(self.switch._process_raw_output(
            '  Member of 1 L2 VLANs, port is tagged, port state is FORWARDING'
        ))

    def test__process_raw_output_untagged(self):
        self.assertEqual(self.switch._process_raw_output(
            ' Member of L2 VLAN ID 22, port is untagged, port state is...'
        ), '22')
