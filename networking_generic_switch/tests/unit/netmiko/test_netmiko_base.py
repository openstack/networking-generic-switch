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

import unittest

import mock

from networking_generic_switch.devices import netmiko_devices


class NetmikoSwitchTestBase(unittest.TestCase):
    def setUp(self):
        super(NetmikoSwitchTestBase, self).setUp()
        self.switch = self._make_switch_device()

    def _make_switch_device(self):
        patcher = mock.patch.object(
            netmiko_devices.netmiko, 'platforms', new=['base'])
        patcher.start()
        self.addCleanup(patcher.stop)
        device_cfg = {'device_type': 'netmiko_base'}
        return netmiko_devices.NetmikoSwitch(device_cfg)


class TestNetmikoSwitch(NetmikoSwitchTestBase):

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch._exec_commands')
    def test_add_network(self, m_exec):
        self.switch.add_network(22, 22)
        m_exec.assert_called_with(None, network_id=22, segmentation_id=22)

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch._exec_commands')
    def test_del_network(self, m_exec):
        self.switch.del_network(22)
        m_exec.assert_called_with(None, segmentation_id=22)

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch._exec_commands')
    def test_plug_port_to_network(self, m_exec):
        self.switch.plug_port_to_network(2222, 22)
        m_exec.assert_called_with(None, port=2222, segmentation_id=22)

    def test__format_commands(self):
        self.assertRaises(
            netmiko_devices.GenericSwitchNetmikoMethodError,
            self.switch._format_commands,
            netmiko_devices.NetmikoSwitch.ADD_NETWORK,
            segmentation_id=22,
            network_id=22)

    @mock.patch.object(netmiko_devices.netmiko, 'ConnectHandler')
    def test__exec_commands(self, nm_mock):
        connect_mock = mock.Mock()
        nm_mock.return_value = connect_mock
        self.switch._exec_commands(['spam ham {eggs}'], eggs='vikings')
        nm_mock.assert_called_once_with(device_type='base')
        connect_mock.send_config_set.assert_called_once_with(
            config_commands=['spam ham vikings'])
