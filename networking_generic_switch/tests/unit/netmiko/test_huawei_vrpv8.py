# Copyright 2016 Huawei Technologies Co., Ltd.
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

from networking_generic_switch.devices.netmiko_devices import huawei_vrpv8
from networking_generic_switch.tests.unit.netmiko import test_netmiko_base


class TestNetmikoHuawei_vrpv8(test_netmiko_base.NetmikoSwitchTestBase):

    def _make_switch_device(self, extra_cfg={}):
        device_cfg = {'device_type': 'netmiko_huawei'}
        device_cfg.update(extra_cfg)
        return huawei_vrpv8.Huawei(device_cfg)

    def test_constants(self):
        self.assertIsNone(self.switch.SAVE_CONFIGURATION)

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device')
    def test_add_network(self, m_exec):
        self.switch.add_network(33, '0ae071f5-5be9-43e4-80ea-e41fefe85b21')
        m_exec.assert_called_with(['vlan 33', 'commit'])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device')
    def test_del_network(self, mock_exec):
        self.switch.del_network(33, '0ae071f5-5be9-43e4-80ea-e41fefe85b21')
        mock_exec.assert_called_with(['undo vlan 33', 'commit'])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device')
    def test_plug_port_to_network(self, mock_exec):
        self.switch.plug_port_to_network(3333, 33)
        mock_exec.assert_called_with(
            ['interface 3333',
             'port link-type access',
             'port default vlan 33',
             'commit'])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device')
    def test_plug_port_has_default_vlan(self, m_sctd):
        switch = self._make_switch_device({'ngs_port_default_vlan': '20'})
        switch.plug_port_to_network(2222, 22)
        m_sctd.assert_called_with(
            ['interface 2222',
             'undo port default vlan 20',
             'commit',
             'interface 2222',
             'port link-type access',
             'port default vlan 22',
             'commit'])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device')
    def test_delete_port(self, mock_exec):
        self.switch.delete_port(3333, 33)
        mock_exec.assert_called_with(
            ['interface 3333',
             'undo port default vlan 33',
             'commit'])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device')
    def test_delete_port_has_default_vlan(self, mock_exec):
        switch = self._make_switch_device({'ngs_port_default_vlan': '20'})
        switch.delete_port(2222, 22)
        mock_exec.assert_called_with(
            ['interface 2222',
             'undo port default vlan 22',
             'commit',
             'vlan 20',
             'commit',
             'interface 2222',
             'port link-type access',
             'port default vlan 20',
             'commit'])

    def test__format_commands(self):
        cmd_set = self.switch._format_commands(
            huawei_vrpv8.Huawei.ADD_NETWORK,
            segmentation_id=22,
            network_id=22)
        self.assertEqual(cmd_set, ['vlan 22', 'commit'])

        cmd_set = self.switch._format_commands(
            huawei_vrpv8.Huawei.DELETE_NETWORK,
            segmentation_id=22)
        self.assertEqual(cmd_set, ['undo vlan 22', 'commit'])

        cmd_set = self.switch._format_commands(
            huawei_vrpv8.Huawei.PLUG_PORT_TO_NETWORK,
            port=3333,
            segmentation_id=33)
        self.assertEqual(cmd_set,
                         ['interface 3333',
                          'port link-type access',
                          'port default vlan 33',
                          'commit'])
