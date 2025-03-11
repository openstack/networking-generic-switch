# Copyright 2024 UKRI STFC
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

from oslo_utils import uuidutils

from networking_generic_switch.devices.netmiko_devices import cumulus
from networking_generic_switch import exceptions as exc
from networking_generic_switch.tests.unit.netmiko import test_netmiko_base


class TestNetmikoCumulusNVUE(test_netmiko_base.NetmikoSwitchTestBase):

    def _make_switch_device(self, extra_cfg={}):
        device_cfg = {
            'device_type': 'netmiko_cumulus_nvue',
            'ngs_port_default_vlan': '123',
            'ngs_disable_inactive_ports': 'True',
        }
        device_cfg.update(extra_cfg)
        return cumulus.CumulusNVUE(device_cfg)

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device',
                return_value="", autospec=True)
    def test_add_network(self, mock_exec):
        self.switch.add_network(3333, '0ae071f5-5be9-43e4-80ea-e41fefe85b21')
        mock_exec.assert_called_with(
            self.switch,
            ['nv set bridge domain br_default vlan 3333'])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device',
                return_value="", autospec=True)
    def test_delete_network(self, mock_exec):
        self.switch.del_network(3333, '0ae071f5-5be9-43e4-80ea-e41fefe85b21')
        mock_exec.assert_called_with(
            self.switch,
            ['nv unset bridge domain br_default vlan 3333'])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device',
                return_value="", autospec=True)
    def test_plug_port_to_network(self, mock_exec):
        self.switch.plug_port_to_network(3333, 33)
        mock_exec.assert_called_with(
            self.switch,
            ['nv set interface 3333 link state up',
             'nv unset interface 3333 bridge domain br_default access',
             'nv unset interface 3333 bridge domain br_default untagged',
             'nv unset interface 3333 bridge domain br_default vlan',
             'nv unset interface 3333 bridge domain br_default untagged',
             'nv set interface 3333 bridge domain br_default access 33'])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device', autospec=True)
    def test_plug_port_to_network_fails(self, mock_exec):
        mock_exec.return_value = (
            'ERROR: Command not found.\n\nasdf'
        )
        self.assertRaises(exc.GenericSwitchNetmikoConfigError,
                          self.switch.plug_port_to_network, 3333, 33)

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device', autospec=True)
    def test_plug_port_to_network_fails_bad_port(self, mock_exec):
        mock_exec.return_value = (
            'ERROR: asd123 is not a physical interface on this switch.'
            '\n\nasdf'
        )
        self.assertRaises(exc.GenericSwitchNetmikoConfigError,
                          self.switch.plug_port_to_network, 3333, 33)

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device',
                return_value="", autospec=True)
    def test_plug_port_simple(self, mock_exec):
        switch = self._make_switch_device({
            'ngs_disable_inactive_ports': 'false',
            'ngs_port_default_vlan': '',
        })
        switch.plug_port_to_network(3333, 33)
        mock_exec.assert_called_with(
            switch,
            ['nv unset interface 3333 bridge domain br_default untagged',
             'nv set interface 3333 bridge domain br_default access 33'])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device',
                return_value="", autospec=True)
    def test_delete_port(self, mock_exec):
        self.switch.delete_port(3333, 33)
        mock_exec.assert_called_with(
            self.switch,
            ['nv unset interface 3333 bridge domain br_default access',
             'nv unset interface 3333 bridge domain br_default untagged',
             'nv unset interface 3333 bridge domain br_default vlan',
             'nv set bridge domain br_default vlan 123',
             'nv unset interface 3333 bridge domain br_default untagged',
             'nv set interface 3333 bridge domain br_default access 123',
             'nv set interface 3333 link state down'])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device',
                return_value="", autospec=True)
    def test_delete_port_simple(self, mock_exec):
        switch = self._make_switch_device({
            'ngs_disable_inactive_ports': 'false',
            'ngs_port_default_vlan': '',
        })
        switch.delete_port(3333, 33)
        mock_exec.assert_called_with(
            switch,
            ['nv unset interface 3333 bridge domain br_default access',
             'nv unset interface 3333 bridge domain br_default untagged',
             'nv unset interface 3333 bridge domain br_default vlan'])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device',
                return_value="", autospec=True)
    def test_plug_bond_to_network(self, mock_exec):
        self.switch.plug_bond_to_network(3333, 33)
        mock_exec.assert_called_with(
            self.switch,
            ['nv set interface 3333 link state up',
             'nv unset interface 3333 bridge domain br_default access',
             'nv unset interface 3333 bridge domain br_default untagged',
             'nv unset interface 3333 bridge domain br_default vlan',
             'nv unset interface 3333 bridge domain br_default untagged',
             'nv set interface 3333 bridge domain br_default access 33'])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device',
                return_value="", autospec=True)
    def test_plug_bond_simple(self, mock_exec):
        switch = self._make_switch_device({
            'ngs_disable_inactive_ports': 'false',
            'ngs_port_default_vlan': '',
        })
        switch.plug_bond_to_network(3333, 33)
        mock_exec.assert_called_with(
            switch,
            ['nv unset interface 3333 bridge domain br_default untagged',
             'nv set interface 3333 bridge domain br_default access 33'])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device',
                return_value="", autospec=True)
    def test_unplug_bond_from_network(self, mock_exec):
        self.switch.unplug_bond_from_network(3333, 33)
        mock_exec.assert_called_with(
            self.switch,
            ['nv unset interface 3333 bridge domain br_default access',
             'nv unset interface 3333 bridge domain br_default untagged',
             'nv unset interface 3333 bridge domain br_default vlan',
             'nv set bridge domain br_default vlan 123',
             'nv unset interface 3333 bridge domain br_default untagged',
             'nv set interface 3333 bridge domain br_default access 123',
             'nv set interface 3333 link state down'])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device',
                return_value="", autospec=True)
    def test_unplug_bond_from_network_simple(self, mock_exec):
        switch = self._make_switch_device({
            'ngs_disable_inactive_ports': 'false',
            'ngs_port_default_vlan': '',
        })
        switch.unplug_bond_from_network(3333, 33)
        mock_exec.assert_called_with(
            switch,
            ['nv unset interface 3333 bridge domain br_default access',
             'nv unset interface 3333 bridge domain br_default untagged',
             'nv unset interface 3333 bridge domain br_default vlan'])

    def test_save(self):
        mock_connect = mock.MagicMock()
        mock_connect.save_config.side_effect = NotImplementedError
        self.switch.save_configuration(mock_connect)
        mock_connect.send_command.assert_called_with('nv config save')

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device', autospec=True)
    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.check_output', autospec=True)
    def test_plug_port_to_network_subports(self, _, mock_exec):
        trunk_details = {"sub_ports": [{"segmentation_id": "tag1"},
                                       {"segmentation_id": "tag2"}]}
        self.switch.plug_port_to_network(4444, 44, trunk_details=trunk_details)
        mock_exec.assert_called_with(
            self.switch,
            ['nv set interface 4444 link state up',
             'nv unset interface 4444 bridge domain br_default access',
             'nv unset interface 4444 bridge domain br_default untagged',
             'nv unset interface 4444 bridge domain br_default vlan',
             'nv unset interface 4444 bridge domain br_default access',
             'nv set interface 4444 bridge domain br_default untagged 44',
             'nv set interface 4444 bridge domain br_default vlan 44',
             'nv unset interface 4444 bridge domain br_default access',
             'nv set interface 4444 bridge domain br_default vlan tag1',
             'nv unset interface 4444 bridge domain br_default access',
             'nv set interface 4444 bridge domain br_default vlan tag2'])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device', autospec=True)
    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.check_output', autospec=True)
    def test_delete_port_subports(self, _, mock_exec):
        trunk_details = {"sub_ports": [{"segmentation_id": "tag1"},
                                       {"segmentation_id": "tag2"}]}
        self.switch.delete_port(4444, 44, trunk_details=trunk_details)
        mock_exec.assert_called_with(
            self.switch,
            ['nv unset interface 4444 bridge domain br_default access',
             'nv unset interface 4444 bridge domain br_default untagged',
             'nv unset interface 4444 bridge domain br_default vlan',
             'nv unset interface 4444 bridge domain br_default untagged 44',
             'nv unset interface 4444 bridge domain br_default vlan 44',
             'nv unset interface 4444 bridge domain br_default vlan tag1',
             'nv unset interface 4444 bridge domain br_default vlan tag2',
             'nv set bridge domain br_default vlan 123',
             'nv unset interface 4444 bridge domain br_default untagged',
             'nv set interface 4444 bridge domain br_default access 123',
             'nv set interface 4444 link state down'])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device', autospec=True)
    def test_add_subports_on_trunk_no_subports(self, mock_exec):
        port_id = uuidutils.generate_uuid()
        parent_port = {
            'binding:profile': {
                'local_link_information': [
                    {
                        'switch_info': 'bar',
                        'port_id': 2222
                    }
                ]},
            'binding:vnic_type': 'baremetal',
            'id': port_id
        }
        subports = []
        self.switch.add_subports_on_trunk(parent_port, 44, subports=subports)
        mock_exec.assert_called_with(self.switch, [])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device', autospec=True)
    def test_add_subports_on_trunk_subports(self, mock_exec):
        port_id = uuidutils.generate_uuid()
        parent_port = {
            'binding:profile': {
                'local_link_information': [
                    {
                        'switch_info': 'bar',
                        'port_id': 2222
                    }
                ]},
            'binding:vnic_type': 'baremetal',
            'id': port_id
        }
        subports = [{"segmentation_id": "tag1"},
                    {"segmentation_id": "tag2"}]
        self.switch.add_subports_on_trunk(parent_port, 44, subports=subports)
        mock_exec.assert_called_with(
            self.switch,
            ['nv unset interface 44 bridge domain br_default access',
             'nv set interface 44 bridge domain br_default vlan tag1',
             'nv unset interface 44 bridge domain br_default access',
             'nv set interface 44 bridge domain br_default vlan tag2'])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device', autospec=True)
    def test_del_subports_on_trunk_no_subports(self, mock_exec):
        port_id = uuidutils.generate_uuid()
        parent_port = {
            'binding:profile': {
                'local_link_information': [
                    {
                        'switch_info': 'bar',
                        'port_id': 2222
                    }
                ]},
            'binding:vnic_type': 'baremetal',
            'id': port_id
        }
        subports = []
        self.switch.del_subports_on_trunk(parent_port, 44, subports=subports)
        mock_exec.assert_called_with(self.switch, [])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device', autospec=True)
    def test_del_subports_on_trunk_subports(self, mock_exec):
        port_id = uuidutils.generate_uuid()
        parent_port = {
            'binding:profile': {
                'local_link_information': [
                    {
                        'switch_info': 'bar',
                        'port_id': 2222
                    }
                ]},
            'binding:vnic_type': 'baremetal',
            'id': port_id
        }
        subports = [{"segmentation_id": "tag1"},
                    {"segmentation_id": "tag2"}]
        self.switch.del_subports_on_trunk(parent_port, 44, subports=subports)
        mock_exec.assert_called_with(
            self.switch,
            ['nv unset interface 44 bridge domain br_default vlan tag1',
             'nv unset interface 44 bridge domain br_default vlan tag2'])
