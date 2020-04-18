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
from unittest import mock

import fixtures
import netmiko
import netmiko.base_connection
from oslo_config import fixture as config_fixture
import paramiko
import tenacity
from tooz import coordination

from networking_generic_switch.devices import netmiko_devices
from networking_generic_switch import exceptions as exc


class NetmikoSwitchTestBase(fixtures.TestWithFixtures):
    def setUp(self):
        super(NetmikoSwitchTestBase, self).setUp()
        self.cfg = self.useFixture(config_fixture.Config())
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
                'NetmikoSwitch.send_commands_to_device',
                return_value='fake output')
    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.check_output')
    def test_add_network(self, m_check, m_sctd):
        self.switch.add_network(22, '0ae071f5-5be9-43e4-80ea-e41fefe85b21')
        m_sctd.assert_called_with([])
        m_check.assert_called_once_with('fake output', 'add network')

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device',
                return_value='fake output')
    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.check_output')
    def test_add_network_with_trunk_ports(self, m_check, m_sctd):
        switch = self._make_switch_device({'ngs_trunk_ports': 'port1,port2'})
        switch.add_network(22, '0ae071f5-5be9-43e4-80ea-e41fefe85b21')
        m_sctd.assert_called_with([])
        m_check.assert_called_once_with('fake output', 'add network')

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device',
                return_value='fake output')
    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.check_output')
    def test_del_network(self, m_check, m_sctd):
        self.switch.del_network(22, '0ae071f5-5be9-43e4-80ea-e41fefe85b21')
        m_sctd.assert_called_with([])
        m_check.assert_called_once_with('fake output', 'delete network')

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device',
                return_value='fake output')
    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.check_output')
    def test_del_network_with_trunk_ports(self, m_check, m_sctd):
        switch = self._make_switch_device({'ngs_trunk_ports': 'port1,port2'})
        switch.del_network(22, '0ae071f5-5be9-43e4-80ea-e41fefe85b21')
        m_sctd.assert_called_with([])
        m_check.assert_called_once_with('fake output', 'delete network')

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device',
                return_value='fake output')
    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.check_output')
    def test_plug_port_to_network(self, m_check, m_sctd):
        self.switch.plug_port_to_network(2222, 22)
        m_sctd.assert_called_with([])
        m_check.assert_called_once_with('fake output', 'plug port')

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device',
                return_value='fake output')
    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.check_output')
    def test_plug_port_has_default_vlan(self, m_check, m_sctd):
        switch = self._make_switch_device({'ngs_port_default_vlan': '20'})
        switch.plug_port_to_network(2222, 22)
        m_sctd.assert_called_with([])
        m_check.assert_called_once_with('fake output', 'plug port')

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device',
                return_value='fake output')
    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.check_output')
    def test_plug_port_to_network_disable_inactive(self, m_check, m_sctd):
        switch = self._make_switch_device(
            {'ngs_disable_inactive_ports': 'true'})
        switch.plug_port_to_network(2222, 22)
        m_sctd.assert_called_with([])
        m_check.assert_called_once_with('fake output', 'plug port')

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device',
                return_value='fake output')
    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.check_output')
    def test_delete_port(self, m_check, m_sctd):
        self.switch.delete_port(2222, 22)
        m_sctd.assert_called_with([])
        m_check.assert_called_once_with('fake output', 'unplug port')

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device',
                return_value='fake output')
    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.check_output')
    def test_delete_port_has_default_vlan(self, m_check, m_sctd):
        switch = self._make_switch_device({'ngs_port_default_vlan': '20'})
        switch.delete_port(2222, 22)
        m_sctd.assert_called_with([])
        m_check.assert_called_once_with('fake output', 'unplug port')

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device',
                return_value='fake output')
    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.check_output')
    def test_delete_port_disable_inactive(self, m_check, m_sctd):
        switch = self._make_switch_device(
            {'ngs_disable_inactive_ports': 'true'})
        switch.delete_port(2222, 22)
        m_sctd.assert_called_with([])
        m_check.assert_called_once_with('fake output', 'unplug port')

    def test__format_commands(self):
        self.switch._format_commands(
            netmiko_devices.NetmikoSwitch.ADD_NETWORK,
            segmentation_id=22, network_id=22)

    @mock.patch.object(netmiko_devices.tenacity, 'wait_fixed',
                       return_value=tenacity.wait_fixed(0.01))
    @mock.patch.object(netmiko_devices.tenacity, 'stop_after_delay',
                       return_value=tenacity.stop_after_delay(0.1))
    @mock.patch.object(netmiko, 'ConnectHandler')
    def test__get_connection_connect_fail(self, m_conn_handler,
                                          m_stop, m_wait):
        m_conn = mock.MagicMock()
        m_conn_handler.side_effect = [
            paramiko.SSHException, m_conn]
        with self.switch._get_connection() as conn:
            self.assertEqual(conn, m_conn)
        m_stop.assert_called_once_with(60)
        m_wait.assert_called_once_with(10)

    @mock.patch.object(netmiko_devices.tenacity, 'wait_fixed',
                       return_value=tenacity.wait_fixed(0.01))
    @mock.patch.object(netmiko_devices.tenacity, 'stop_after_delay',
                       return_value=tenacity.stop_after_delay(0.1))
    @mock.patch.object(netmiko, 'ConnectHandler')
    def test__get_connection_timeout(self, m_conn_handler, m_stop, m_wait):
        switch = self._make_switch_device({'ngs_ssh_connect_timeout': '1',
                                           'ngs_ssh_connect_interval': '1'})
        m_conn_handler.side_effect = (
            paramiko.SSHException)

        def get_connection():
            with switch._get_connection():
                self.fail()

        self.assertRaises(exc.GenericSwitchNetmikoConnectError, get_connection)
        m_stop.assert_called_once_with(1)
        m_wait.assert_called_once_with(1)

    @mock.patch.object(netmiko_devices.tenacity, 'wait_fixed',
                       return_value=tenacity.wait_fixed(0.01))
    @mock.patch.object(netmiko_devices.tenacity, 'stop_after_delay',
                       return_value=tenacity.stop_after_delay(0.1))
    @mock.patch.object(netmiko, 'ConnectHandler')
    def test__get_connection_caller_failure(self, m_conn_handler,
                                            m_stop, m_wait):
        m_conn = mock.MagicMock()
        m_conn_handler.return_value = m_conn

        class FakeError(Exception):
            pass

        def get_connection():
            with self.switch._get_connection():
                raise FakeError()

        self.assertRaises(FakeError, get_connection)
        m_conn.__exit__.assert_called_once_with(mock.ANY, mock.ANY, mock.ANY)

    @mock.patch.object(netmiko_devices.NetmikoSwitch, '_get_connection')
    def test_send_commands_to_device_empty(self, gc_mock):
        connect_mock = mock.MagicMock()
        gc_mock.return_value.__enter__.return_value = connect_mock
        self.assertIsNone(self.switch.send_commands_to_device([]))
        self.assertFalse(connect_mock.send_config_set.called)
        self.assertFalse(connect_mock.send_command.called)

    @mock.patch.object(netmiko_devices.NetmikoSwitch, '_get_connection')
    @mock.patch.object(netmiko_devices.NetmikoSwitch, 'send_config_set')
    @mock.patch.object(netmiko_devices.NetmikoSwitch, 'save_configuration')
    def test_send_commands_to_device(self, save_mock, send_mock, gc_mock):
        connect_mock = mock.MagicMock(netmiko.base_connection.BaseConnection)
        gc_mock.return_value.__enter__.return_value = connect_mock
        send_mock.return_value = 'fake output'
        result = self.switch.send_commands_to_device(['spam ham aaaa'])
        send_mock.assert_called_once_with(connect_mock, ['spam ham aaaa'])
        self.assertEqual('fake output', result)
        save_mock.assert_called_once_with(connect_mock)

    def test_send_config_set(self):
        connect_mock = mock.MagicMock(netmiko.base_connection.BaseConnection)
        connect_mock.send_config_set.return_value = 'fake output'
        result = self.switch.send_config_set(connect_mock, ['spam ham aaaa'])
        connect_mock.enable.assert_called_once_with()
        connect_mock.send_config_set.assert_called_once_with(
            config_commands=['spam ham aaaa'], cmd_verify=False)
        self.assertEqual('fake output', result)

    @mock.patch.object(netmiko_devices.NetmikoSwitch, '_get_connection')
    def test_send_commands_to_device_send_failure(self, gc_mock):
        connect_mock = mock.MagicMock(netmiko.base_connection.BaseConnection)
        gc_mock.return_value.__enter__.return_value = connect_mock

        class FakeError(Exception):
            pass
        connect_mock.send_config_set.side_effect = FakeError
        self.assertRaises(exc.GenericSwitchNetmikoConnectError,
                          self.switch.send_commands_to_device,
                          ['spam ham aaaa'])
        connect_mock.send_config_set.assert_called_once_with(
            config_commands=['spam ham aaaa'], cmd_verify=False)

    @mock.patch.object(netmiko_devices.NetmikoSwitch, '_get_connection')
    def test_send_commands_to_device_send_ngs_failure(self, gc_mock):
        connect_mock = mock.MagicMock(netmiko.base_connection.BaseConnection)
        gc_mock.return_value.__enter__.return_value = connect_mock

        class NGSFakeError(exc.GenericSwitchException):
            pass
        connect_mock.send_config_set.side_effect = NGSFakeError
        self.assertRaises(NGSFakeError, self.switch.send_commands_to_device,
                          ['spam ham aaaa'])
        connect_mock.send_config_set.assert_called_once_with(
            config_commands=['spam ham aaaa'], cmd_verify=False)

    @mock.patch.object(netmiko_devices.NetmikoSwitch, '_get_connection')
    @mock.patch.object(netmiko_devices.NetmikoSwitch, 'save_configuration')
    def test_send_commands_to_device_save_failure(self, save_mock, gc_mock):
        connect_mock = mock.MagicMock(netmiko.base_connection.BaseConnection)
        gc_mock.return_value.__enter__.return_value = connect_mock

        class FakeError(Exception):
            pass
        save_mock.side_effect = FakeError
        self.assertRaises(exc.GenericSwitchNetmikoConnectError,
                          self.switch.send_commands_to_device,
                          ['spam ham aaaa'])
        connect_mock.send_config_set.assert_called_once_with(
            config_commands=['spam ham aaaa'], cmd_verify=False)
        save_mock.assert_called_once_with(connect_mock)

    @mock.patch.object(netmiko_devices.NetmikoSwitch, '_get_connection')
    @mock.patch.object(netmiko_devices.NetmikoSwitch, 'save_configuration')
    def test_send_commands_to_device_save_ngs_failure(self, save_mock,
                                                      gc_mock):
        connect_mock = mock.MagicMock(netmiko.base_connection.BaseConnection)
        gc_mock.return_value.__enter__.return_value = connect_mock

        class NGSFakeError(exc.GenericSwitchException):
            pass
        save_mock.side_effect = NGSFakeError
        self.assertRaises(NGSFakeError, self.switch.send_commands_to_device,
                          ['spam ham aaaa'])
        connect_mock.send_config_set.assert_called_once_with(
            config_commands=['spam ham aaaa'], cmd_verify=False)
        save_mock.assert_called_once_with(connect_mock)

    def test_save_configuration(self):
        connect_mock = mock.MagicMock(netmiko.base_connection.BaseConnection,
                                      autospec=True)
        self.switch.save_configuration(connect_mock)
        connect_mock.save_config.assert_called_once_with()

    @mock.patch.object(netmiko_devices.NetmikoSwitch, 'SAVE_CONFIGURATION',
                       ('save', 'y'))
    def test_save_configuration_with_NotImplementedError(self):
        connect_mock = mock.MagicMock(netmiko.base_connection.BaseConnection,
                                      autospec=True)

        def fake_save_config():
            raise NotImplementedError
        connect_mock.save_config = fake_save_config
        self.switch.save_configuration(connect_mock)
        connect_mock.send_command.assert_has_calls([mock.call('save'),
                                                    mock.call('y')])

    @mock.patch.object(netmiko_devices.ngs_lock, 'PoolLock', autospec=True)
    @mock.patch.object(netmiko_devices.netmiko, 'ConnectHandler')
    @mock.patch.object(coordination, 'get_coordinator', autospec=True)
    def test_switch_send_commands_with_coordinator(self, get_coord_mock,
                                                   nm_mock, lock_mock):
        self.cfg.config(acquire_timeout=120, backend_url='mysql://localhost',
                        group='ngs_coordination')
        self.cfg.config(host='viking')
        coord = mock.Mock()
        get_coord_mock.return_value = coord

        switch = self._make_switch_device(
            extra_cfg={'ngs_max_connections': 2})
        self.assertEqual(coord, switch.locker)
        get_coord_mock.assert_called_once_with('mysql://localhost',
                                               'ngs-viking'.encode('ascii'))

        connect_mock = mock.MagicMock(SAVE_CONFIGURATION=None)
        connect_mock.__enter__.return_value = connect_mock
        nm_mock.return_value = connect_mock
        lock_mock.return_value.__enter__.return_value = lock_mock
        switch.send_commands_to_device(['spam ham'])

        lock_mock.assert_called_once_with(coord, locks_pool_size=2,
                                          locks_prefix='host',
                                          timeout=120)
        lock_mock.return_value.__exit__.assert_called_once()
        lock_mock.return_value.__enter__.assert_called_once()

    def test_check_output(self):
        self.switch.check_output('fake output', 'fake op')

    def test_check_output_error(self):
        self.switch.ERROR_MSG_PATTERNS = (re.compile('fake error message'),)
        output = """
fake switch command
fake error message
"""
        msg = ("Found invalid configuration in device response. Operation: "
               "fake op. Output: %s" % output)
        self.assertRaisesRegexp(exc.GenericSwitchNetmikoConfigError, msg,
                                self.switch.check_output, output, 'fake op')
