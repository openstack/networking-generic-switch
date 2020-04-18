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

from unittest import mock

from networking_generic_switch.devices.netmiko_devices import ovs
from networking_generic_switch.tests.unit.netmiko import test_netmiko_base


class TestNetmikoOvsLinux(test_netmiko_base.NetmikoSwitchTestBase):

    def _make_switch_device(self):
        device_cfg = {'device_type': 'netmiko_ovs_linux',
                      'ip': 'localhost'}
        return ovs.OvsLinux(device_cfg)

    def test_constants(self):
        self.assertIsNone(self.switch.SAVE_CONFIGURATION)

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device')
    def test_add_network(self, m_exec):
        self.switch.add_network(44, '0ae071f5-5be9-43e4-80ea-e41fefe85b21')
        m_exec.assert_called_with([])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device')
    def test_del_network(self, mock_exec):
        self.switch.del_network(44, '0ae071f5-5be9-43e4-80ea-e41fefe85b21')
        mock_exec.assert_called_with([])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device')
    def test_plug_port_to_network(self, mock_exec):
        self.switch.plug_port_to_network(4444, 44)
        mock_exec.assert_called_with(
            ['ovs-vsctl set port 4444 vlan_mode=access',
             'ovs-vsctl set port 4444 tag=44'])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device')
    def test_delete_port(self, mock_exec):
        self.switch.delete_port(4444, 44)
        mock_exec.assert_called_with(
            ['ovs-vsctl clear port 4444 tag',
             'ovs-vsctl clear port 4444 trunks',
             'ovs-vsctl clear port 4444 vlan_mode'])

    def test__format_commands(self):
        cmd_set = self.switch._format_commands(
            ovs.OvsLinux.PLUG_PORT_TO_NETWORK,
            port=3333,
            segmentation_id=33)
        plug_exp = ['ovs-vsctl set port 3333 vlan_mode=access',
                    'ovs-vsctl set port 3333 tag=33']
        self.assertEqual(plug_exp, cmd_set)

        cmd_set = self.switch._format_commands(
            ovs.OvsLinux.DELETE_PORT,
            port=3333,
            segmentation_id=33)
        del_exp = ['ovs-vsctl clear port 3333 tag',
                   'ovs-vsctl clear port 3333 trunks',
                   'ovs-vsctl clear port 3333 vlan_mode']
        self.assertEqual(del_exp, cmd_set)
