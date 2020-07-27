# Copyright 2020 StackHPC
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

from networking_generic_switch.devices.netmiko_devices import cumulus
from networking_generic_switch import exceptions as exc
from networking_generic_switch.tests.unit.netmiko import test_netmiko_base


class TestNetmikoCumulus(test_netmiko_base.NetmikoSwitchTestBase):

    def _make_switch_device(self, extra_cfg={}):
        device_cfg = {
            'device_type': 'netmiko_cumulus',
            'ngs_port_default_vlan': '123',
            'ngs_disable_inactive_ports': 'True',
        }
        device_cfg.update(extra_cfg)
        return cumulus.Cumulus(device_cfg)

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device',
                return_value="")
    def test_add_network(self, mock_exec):
        self.switch.add_network(3333, '0ae071f5-5be9-43e4-80ea-e41fefe85b21')
        mock_exec.assert_called_with(
            ['net add vlan 3333'])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device',
                return_value="")
    def test_delete_network(self, mock_exec):
        self.switch.del_network(3333, '0ae071f5-5be9-43e4-80ea-e41fefe85b21')
        mock_exec.assert_called_with(
            ['net del vlan 3333'])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device',
                return_value="")
    def test_plug_port_to_network(self, mock_exec):
        self.switch.plug_port_to_network(3333, 33)
        mock_exec.assert_called_with(
            ['net del interface 3333 link down',
             'net del interface 3333 bridge access 123',
             'net add interface 3333 bridge access 33'])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device')
    def test_plug_port_to_network_fails(self, mock_exec):
        mock_exec.return_value = (
            'ERROR: Command not found.\n\nasdf'
        )
        self.assertRaises(exc.GenericSwitchNetmikoConfigError,
                          self.switch.plug_port_to_network, 3333, 33)

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device')
    def test_plug_port_to_network_fails_bad_port(self, mock_exec):
        mock_exec.return_value = (
            'ERROR: asd123 is not a physical interface on this switch.'
            '\n\nasdf'
        )
        self.assertRaises(exc.GenericSwitchNetmikoConfigError,
                          self.switch.plug_port_to_network, 3333, 33)

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device',
                return_value="")
    def test_plug_port_simple(self, mock_exec):
        switch = self._make_switch_device({
            'ngs_disable_inactive_ports': 'false',
            'ngs_port_default_vlan': '',
        })
        switch.plug_port_to_network(3333, 33)
        mock_exec.assert_called_with(
            ['net add interface 3333 bridge access 33'])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device',
                return_value="")
    def test_delete_port(self, mock_exec):
        self.switch.delete_port(3333, 33)
        mock_exec.assert_called_with(
            ['net del interface 3333 bridge access 33',
             'net add vlan 123',
             'net add interface 3333 bridge access 123',
             'net add interface 3333 link down'])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device',
                return_value="")
    def test_delete_port_simple(self, mock_exec):
        switch = self._make_switch_device({
            'ngs_disable_inactive_ports': 'false',
            'ngs_port_default_vlan': '',
        })
        switch.delete_port(3333, 33)
        mock_exec.assert_called_with(
            ['net del interface 3333 bridge access 33'])

    def test_save(self):
        mock_connect = mock.MagicMock()
        mock_connect.save_config.side_effect = NotImplementedError
        self.switch.save_configuration(mock_connect)
        mock_connect.send_command.assert_called_with('net commit')
