# Copyright (c) 2018 StackHPC Ltd.
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

import netmiko
import tenacity

from networking_generic_switch.devices import netmiko_devices
from networking_generic_switch.devices.netmiko_devices import juniper
from networking_generic_switch import exceptions as exc
from networking_generic_switch.tests.unit.netmiko import test_netmiko_base


class TestNetmikoJuniper(test_netmiko_base.NetmikoSwitchTestBase):

    def _make_switch_device(self, extra_cfg={}):
        device_cfg = {'device_type': 'netmiko_juniper'}
        device_cfg.update(extra_cfg)
        return juniper.Juniper(device_cfg)

    def test_constants(self):
        self.assertIsNone(self.switch.SAVE_CONFIGURATION)

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device')
    def test_add_network(self, m_exec):
        self.switch.add_network(33, '0ae071f5-5be9-43e4-80ea-e41fefe85b21')
        m_exec.assert_called_with(
            ['set vlans 0ae071f55be943e480eae41fefe85b21 vlan-id 33'])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device')
    def test_add_network_with_trunk_ports(self, mock_exec):
        switch = self._make_switch_device({'ngs_trunk_ports': 'port1,port2'})
        switch.add_network(33, '0ae071f5-5be9-43e4-80ea-e41fefe85b21')
        mock_exec.assert_called_with(
            ['set vlans 0ae071f55be943e480eae41fefe85b21 vlan-id 33',
             'set interface port1 unit 0 family ethernet-switching '
             'vlan members 33',
             'set interface port2 unit 0 family ethernet-switching '
             'vlan members 33'])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device')
    def test_del_network(self, mock_exec):
        self.switch.del_network(33, '0ae071f55be943e480eae41fefe85b21')
        mock_exec.assert_called_with(
            ['delete vlans 0ae071f55be943e480eae41fefe85b21'])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device')
    def test_del_network_with_trunk_ports(self, mock_exec):
        switch = self._make_switch_device({'ngs_trunk_ports': 'port1,port2'})
        switch.del_network(33, '0ae071f55be943e480eae41fefe85b21')
        mock_exec.assert_called_with(
            ['delete interface port1 unit 0 family ethernet-switching '
             'vlan members 33',
             'delete interface port2 unit 0 family ethernet-switching '
             'vlan members 33',
             'delete vlans 0ae071f55be943e480eae41fefe85b21'])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device')
    def test_plug_port_to_network(self, mock_exec):
        self.switch.plug_port_to_network(3333, 33)
        mock_exec.assert_called_with(
            ['delete interface 3333 unit 0 family ethernet-switching '
             'vlan members',
             'set interface 3333 unit 0 family ethernet-switching '
             'vlan members 33'])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device')
    def test_plug_port_to_network_disable_inactive(self, m_sctd):
        switch = self._make_switch_device(
            {'ngs_disable_inactive_ports': 'true'})
        switch.plug_port_to_network(3333, 33)
        m_sctd.assert_called_with(
            ['delete interface 3333 disable',
             'delete interface 3333 unit 0 family ethernet-switching '
             'vlan members',
             'set interface 3333 unit 0 family ethernet-switching '
             'vlan members 33'])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device')
    def test_delete_port(self, mock_exec):
        self.switch.delete_port(3333, 33)
        mock_exec.assert_called_with(
            ['delete interface 3333 unit 0 family ethernet-switching '
             'vlan members'])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device')
    def test_delete_port_disable_inactive(self, m_sctd):
        switch = self._make_switch_device(
            {'ngs_disable_inactive_ports': 'true'})
        switch.delete_port(3333, 33)
        m_sctd.assert_called_with(
            ['delete interface 3333 unit 0 family ethernet-switching '
             'vlan members',
             'set interface 3333 disable'])

    def test_send_config_set(self):
        connect_mock = mock.MagicMock(netmiko.base_connection.BaseConnection)
        connect_mock.send_config_set.return_value = 'fake output'
        result = self.switch.send_config_set(connect_mock, ['spam ham aaaa'])
        self.assertFalse(connect_mock.enable.called)
        connect_mock.send_config_set.assert_called_once_with(
            config_commands=['spam ham aaaa'], exit_config_mode=False)
        self.assertEqual('fake output', result)

    def test_save_configuration(self):
        mock_connection = mock.Mock()
        self.switch.save_configuration(mock_connection)
        mock_connection.commit.assert_called_once_with()

    @mock.patch.object(netmiko_devices.tenacity, 'wait_fixed',
                       return_value=tenacity.wait_fixed(0.01))
    @mock.patch.object(netmiko_devices.tenacity, 'stop_after_delay',
                       return_value=tenacity.stop_after_attempt(2))
    def test_save_configuration_db_locked(self, m_stop, m_wait):
        mock_connection = mock.Mock()
        output = """
error: configuration database locked by:
  user terminal p0 (pid 1234) on since 2017-1-1 00:00:00 UTC
      exclusive private [edit]

{master:0}[edit]"""
        mock_connection.commit.side_effect = [
            ValueError(
                "Commit failed with the following errors:\n\n{0}"
                .format(output)
            ),
            None
        ]

        self.switch.save_configuration(mock_connection)
        m_stop.assert_called_once_with(60)
        m_wait.assert_called_once_with(5)

    @mock.patch.object(netmiko_devices.tenacity, 'wait_fixed',
                       return_value=tenacity.wait_fixed(0.01))
    @mock.patch.object(netmiko_devices.tenacity, 'stop_after_delay',
                       return_value=tenacity.stop_after_delay(0.1))
    def test_save_configuration_db_locked_timeout(self, m_stop, m_wait):
        mock_connection = mock.Mock()
        output = """
error: configuration database locked by:
  user terminal p0 (pid 1234) on since 2017-1-1 00:00:00 UTC
      exclusive private [edit]

{master:0}[edit]"""
        mock_connection.commit.side_effect = ValueError(
            "Commit failed with the following errors:\n\n{0}".format(output))

        self.assertRaisesRegexp(exc.GenericSwitchNetmikoConfigError,
                                "Reached timeout waiting for",
                                self.switch.save_configuration,
                                mock_connection)
        self.assertGreater(mock_connection.commit.call_count, 1)
        m_stop.assert_called_once_with(60)
        m_wait.assert_called_once_with(5)

    @mock.patch.object(netmiko_devices.tenacity, 'wait_fixed',
                       return_value=tenacity.wait_fixed(0.01))
    @mock.patch.object(netmiko_devices.tenacity, 'stop_after_delay',
                       return_value=tenacity.stop_after_attempt(2))
    def test_save_configuration_warn_already_exists(self, m_stop, m_wait):
        mock_connection = mock.Mock()
        output = """
[edit interfaces xe-0/0/1 unit 0 family ethernet-switching vlan]
  'members 1234'
        warning: statement already exists

{master:0}[edit]"""
        mock_connection.commit.side_effect = [
            ValueError(
                "Commit failed with the following errors:\n\n{0}"
                .format(output)
            ),
            None
        ]

        self.switch.save_configuration(mock_connection)
        m_stop.assert_called_once_with(60)
        m_wait.assert_called_once_with(5)

    @mock.patch.object(netmiko_devices.tenacity, 'wait_fixed',
                       return_value=tenacity.wait_fixed(0.01))
    @mock.patch.object(netmiko_devices.tenacity, 'stop_after_delay',
                       return_value=tenacity.stop_after_delay(0.1))
    def test_save_configuration_warn_already_exists_timeout(
            self, m_stop, m_wait):
        mock_connection = mock.Mock()
        output = """
[edit interfaces xe-0/0/1 unit 0 family ethernet-switching vlan]
  'members 1234'
        warning: statement already exists

{master:0}[edit]"""
        mock_connection.commit.side_effect = ValueError(
            "Commit failed with the following errors:\n\n{0}".format(output))

        self.assertRaisesRegexp(exc.GenericSwitchNetmikoConfigError,
                                "Reached timeout while attempting",
                                self.switch.save_configuration,
                                mock_connection)
        self.assertGreater(mock_connection.commit.call_count, 1)
        m_stop.assert_called_once_with(60)
        m_wait.assert_called_once_with(5)

    @mock.patch.object(netmiko_devices.tenacity, 'wait_fixed',
                       return_value=tenacity.wait_fixed(0.01))
    @mock.patch.object(netmiko_devices.tenacity, 'stop_after_delay',
                       return_value=tenacity.stop_after_attempt(2))
    def test_save_configuration_warn_does_not_exist(self, m_stop, m_wait):
        mock_connection = mock.Mock()
        output = """
[edit interfaces xe-0/0/1 unit 0 family ethernet-switching vlan]
  'members 1234'
        warning: statement does not exist

{master:0}[edit]"""
        mock_connection.commit.side_effect = [
            ValueError(
                "Commit failed with the following errors:\n\n{0}"
                .format(output)
            ),
            None
        ]

        self.switch.save_configuration(mock_connection)
        m_stop.assert_called_once_with(60)
        m_wait.assert_called_once_with(5)

    @mock.patch.object(netmiko_devices.tenacity, 'wait_fixed',
                       return_value=tenacity.wait_fixed(0.01))
    @mock.patch.object(netmiko_devices.tenacity, 'stop_after_delay',
                       return_value=tenacity.stop_after_delay(0.1))
    def test_save_configuration_warn_does_not_exist_timeout(
            self, m_stop, m_wait):
        mock_connection = mock.Mock()
        output = """
[edit interfaces xe-0/0/1 unit 0 family ethernet-switching vlan]
  'members 1234'
        warning: statement does not exist

{master:0}[edit]"""
        mock_connection.commit.side_effect = ValueError(
            "Commit failed with the following errors:\n\n{0}".format(output))

        self.assertRaisesRegexp(exc.GenericSwitchNetmikoConfigError,
                                "Reached timeout while attempting",
                                self.switch.save_configuration,
                                mock_connection)
        self.assertGreater(mock_connection.commit.call_count, 1)
        m_stop.assert_called_once_with(60)
        m_wait.assert_called_once_with(5)

    def test_save_configuration_error(self):
        mock_connection = mock.Mock()
        output = """
[edit vlans]
  'duplicate-vlan'
    l2ald: Duplicate vlan-id exists for vlan duplicate-vlan
[edit vlans]
  Failed to parse vlan hierarchy completely
error: configuration check-out failed

{master:0}[edit]"""
        mock_connection.commit.side_effect = ValueError(
            "Commit failed with the following errors:\n\n{0}".format(output))

        self.assertRaisesRegexp(exc.GenericSwitchNetmikoConfigError,
                                "Failed to commit configuration",
                                self.switch.save_configuration,
                                mock_connection)
        mock_connection.commit.assert_called_once_with()

    @mock.patch.object(netmiko_devices.tenacity, 'wait_fixed',
                       return_value=tenacity.wait_fixed(0.01))
    @mock.patch.object(netmiko_devices.tenacity, 'stop_after_delay',
                       return_value=tenacity.stop_after_delay(0.1))
    def test_save_configuration_non_default_timing(self, m_stop, m_wait):
        self.switch = self._make_switch_device({'ngs_commit_timeout': 42,
                                                'ngs_commit_interval': 43})
        mock_connection = mock.MagicMock(
            netmiko.base_connection.BaseConnection)
        self.switch.save_configuration(mock_connection)
        mock_connection.commit.assert_called_once_with()
        m_stop.assert_called_once_with(42)
        m_wait.assert_called_once_with(43)

    def test__format_commands(self):
        cmd_set = self.switch._format_commands(
            juniper.Juniper.ADD_NETWORK,
            segmentation_id=22,
            network_id=22,
            network_name='vlan-22')
        self.assertEqual(cmd_set, ['set vlans vlan-22 vlan-id 22'])

        cmd_set = self.switch._format_commands(
            juniper.Juniper.DELETE_NETWORK,
            segmentation_id=22,
            network_id=22,
            network_name='vlan-22')
        self.assertEqual(cmd_set, ['delete vlans vlan-22'])

        cmd_set = self.switch._format_commands(
            juniper.Juniper.PLUG_PORT_TO_NETWORK,
            port=3333,
            segmentation_id=33)
        self.assertEqual(cmd_set,
                         ['delete interface 3333 unit 0 '
                          'family ethernet-switching '
                          'vlan members',
                          'set interface 3333 unit 0 '
                          'family ethernet-switching '
                          'vlan members 33'])

        cmd_set = self.switch._format_commands(
            juniper.Juniper.DELETE_PORT,
            port=3333,
            segmentation_id=33)
        self.assertEqual(cmd_set,
                         ['delete interface 3333 unit 0 '
                          'family ethernet-switching '
                          'vlan members'])

        cmd_set = self.switch._format_commands(
            juniper.Juniper.ADD_NETWORK_TO_TRUNK,
            port=3333,
            segmentation_id=33)
        self.assertEqual(cmd_set,
                         ['set interface 3333 unit 0 '
                          'family ethernet-switching '
                          'vlan members 33'])

        cmd_set = self.switch._format_commands(
            juniper.Juniper.REMOVE_NETWORK_FROM_TRUNK,
            port=3333,
            segmentation_id=33)
        self.assertEqual(cmd_set,
                         ['delete interface 3333 unit 0 '
                          'family ethernet-switching '
                          'vlan members 33'])
