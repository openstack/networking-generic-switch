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

import time
import unittest

import mock
import netmiko
import paramiko

from networking_generic_switch.devices import netmiko_devices
from networking_generic_switch import exceptions as exc


class NetmikoSwitchTestBase(unittest.TestCase):
    def setUp(self):
        super(NetmikoSwitchTestBase, self).setUp()
        self.switch = self._make_switch_device()

    def _make_switch_device(self, extra_cfg={}):
        patcher = mock.patch.object(
            netmiko_devices.netmiko, 'platforms', new=['base'])
        patcher.start()
        self.addCleanup(patcher.stop)
        device_cfg = {'device_type': 'netmiko_base',
                      'ip': 'host'}
        device_cfg.update(extra_cfg)
        return netmiko_devices.NetmikoSwitch(device_cfg)


class TestNetmikoSwitch(NetmikoSwitchTestBase):

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device')
    def test_add_network(self, m_sctd):
        self.switch.add_network(22, '0ae071f5-5be9-43e4-80ea-e41fefe85b21')
        m_sctd.assert_called_with(None)

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device')
    def test_del_network(self, m_sctd):
        self.switch.del_network(22)
        m_sctd.assert_called_with(None)

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device')
    def test_plug_port_to_network(self, m_sctd):
        self.switch.plug_port_to_network(2222, 22)
        m_sctd.assert_called_with(None)

    def test__format_commands(self):
        self.switch._format_commands(
            netmiko_devices.NetmikoSwitch.ADD_NETWORK,
            segmentation_id=22, network_id=22)

    @mock.patch.object(netmiko_devices.NetmikoSwitch, '_sleep')
    @mock.patch.object(netmiko, 'ConnectHandler')
    def test__get_connection(self, m_conn_handler, m_sleep):
        m_conn = mock.MagicMock()
        m_conn_handler.return_value = m_conn
        with self.switch._get_connection() as conn:
            self.assertEqual(conn, m_conn)
        m_sleep.assert_not_called()

    @mock.patch.object(netmiko_devices.NetmikoSwitch, '_sleep')
    @mock.patch.object(netmiko, 'ConnectHandler')
    def test__get_connection_connect_fail(self, m_conn_handler, m_sleep):
        m_conn = mock.MagicMock()
        m_conn_handler.side_effect = [
            paramiko.SSHException, m_conn]
        with self.switch._get_connection() as conn:
            self.assertEqual(conn, m_conn)
        m_sleep.assert_called_once_with(10)

    @mock.patch.object(netmiko_devices.NetmikoSwitch, '_sleep')
    @mock.patch.object(netmiko, 'ConnectHandler')
    def test__get_connection_timeout(self, m_conn_handler, m_sleep):
        # It doesn't seem to be possible to mock the timeout mechanism in
        # tenacity, so let's at least sleep rather than spin while waiting.
        m_sleep.side_effect = lambda x: time.sleep(x)
        switch = self._make_switch_device({'ngs_ssh_connect_timeout': '1',
                                           'ngs_ssh_connect_interval': '1'})
        m_conn_handler.side_effect = (
            paramiko.SSHException)

        def get_connection():
            with switch._get_connection():
                self.fail()

        self.assertRaises(exc.GenericSwitchNetmikoConnectError, get_connection)
        m_sleep.assert_called_with(1)

    @mock.patch.object(netmiko_devices.NetmikoSwitch, '_sleep')
    @mock.patch.object(netmiko, 'ConnectHandler')
    def test__get_connection_caller_failure(self, m_conn_handler, m_sleep):
        m_conn = mock.MagicMock()
        m_conn_handler.return_value = m_conn

        class FakeError(Exception):
            pass

        def get_connection():
            with self.switch._get_connection():
                raise FakeError()

        self.assertRaises(FakeError, get_connection)
        m_conn.__exit__.assert_called_once_with(mock.ANY, mock.ANY, mock.ANY)
        m_sleep.assert_not_called()

    @mock.patch.object(netmiko_devices.NetmikoSwitch, '_get_connection')
    def test_send_commands_to_device_empty(self, gc_mock):
        connect_mock = mock.MagicMock()
        gc_mock.return_value.__enter__.return_value = connect_mock
        self.assertIsNone(self.switch.send_commands_to_device([]))
        self.assertFalse(connect_mock.send_config_set.called)
        self.assertFalse(connect_mock.send_command.called)

    @mock.patch.object(netmiko_devices.NetmikoSwitch, '_get_connection')
    def test_send_commands_to_device(self, gc_mock):
        connect_mock = mock.MagicMock(SAVE_CONFIGURATION=None)
        gc_mock.return_value.__enter__.return_value = connect_mock
        self.switch.send_commands_to_device(['spam ham aaaa'])
        gc_mock.assert_called_once_with()
        connect_mock.send_config_set.assert_called_once_with(
            config_commands=['spam ham aaaa'])
        self.assertFalse(connect_mock.send_command.called)

    @mock.patch.object(netmiko_devices.NetmikoSwitch, '_get_connection')
    def test_send_commands_to_device_save_configuration(self, gc_mock):
        connect_mock = mock.MagicMock(SAVE_CONFIGURAION='save me')
        gc_mock.return_value.__enter__.return_value = connect_mock
        self.switch.send_commands_to_device(['spam ham aaaa'])
        connect_mock.send_config_set.assert_called_once_with(
            config_commands=['spam ham aaaa'])
        connect_mock.send_command.called_once_with('save me')
