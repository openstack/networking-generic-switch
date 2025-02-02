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

from oslo_utils import uuidutils

from networking_generic_switch.devices.netmiko_devices import ovs
from networking_generic_switch.tests.unit.netmiko import test_netmiko_base


class TestNetmikoOvsLinux(test_netmiko_base.NetmikoSwitchTestBase):

    def _make_switch_device(self):
        device_cfg = {'device_type': 'netmiko_ovs_linux',
                      'ip': 'localhost'}
        return ovs.OvsLinux(device_cfg)

    def test_constants(self):
        self.assertIsNone(self.switch.SAVE_CONFIGURATION)

    def test_features(self):
        self.assertTrue(self.switch.support_trunk_on_ports)
        self.assertTrue(self.switch.support_trunk_on_bond_ports)

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device', autospec=True)
    def test_add_network(self, m_exec):
        self.switch.add_network(44, '0ae071f5-5be9-43e4-80ea-e41fefe85b21')
        m_exec.assert_called_with(self.switch, [])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device', autospec=True)
    def test_del_network(self, mock_exec):
        self.switch.del_network(44, '0ae071f5-5be9-43e4-80ea-e41fefe85b21')
        mock_exec.assert_called_with(self.switch, [])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device', autospec=True)
    def test_plug_port_to_network(self, mock_exec):
        self.switch.plug_port_to_network(4444, 44)
        mock_exec.assert_called_with(
            self.switch,
            ['ovs-vsctl set port 4444 vlan_mode=access',
             'ovs-vsctl set port 4444 tag=44'])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device', autospec=True)
    def test_plug_port_to_network_subports(self, mock_exec):
        trunk_details = {"sub_ports": [{"segmentation_id": "tag1"},
                                       {"segmentation_id": "tag2"}]}
        self.switch.plug_port_to_network(4444, 44, trunk_details=trunk_details)
        mock_exec.assert_called_with(
            self.switch,
            ['ovs-vsctl set port 4444 vlan_mode=native-untagged',
             'ovs-vsctl set port 4444 tag=44',
             'ovs-vsctl add port 4444 trunks 44',
             'ovs-vsctl add port 4444 trunks tag1',
             'ovs-vsctl add port 4444 trunks tag2'])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device', autospec=True)
    def test_delete_port(self, mock_exec):
        self.switch.delete_port(4444, 44)
        mock_exec.assert_called_with(
            self.switch,
            ['ovs-vsctl clear port 4444 tag',
             'ovs-vsctl clear port 4444 trunks',
             'ovs-vsctl clear port 4444 vlan_mode'])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device', autospec=True)
    def test_delete_port_subports(self, mock_exec):
        trunk_details = {"sub_ports": [{"segmentation_id": "tag1"},
                                       {"segmentation_id": "tag2"}]}
        self.switch.delete_port(4444, 44, trunk_details=trunk_details)
        mock_exec.assert_called_with(
            self.switch,
            ['ovs-vsctl clear port 4444 tag',
             'ovs-vsctl clear port 4444 trunks',
             'ovs-vsctl clear port 4444 vlan_mode',
             'ovs-vsctl clear port 4444 vlan_mode',
             'ovs-vsctl clear port 4444 tag',
             'ovs-vsctl remove port 4444 trunks 44',
             'ovs-vsctl remove port 4444 trunks tag1',
             'ovs-vsctl remove port 4444 trunks tag2'])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device', autospec=True)
    def test_plug_bond_to_network_subports(self, mock_exec):
        trunk_details = {"sub_ports": [{"segmentation_id": "tag1"},
                                       {"segmentation_id": "tag2"}]}
        self.switch.plug_bond_to_network(4444, 44, trunk_details=trunk_details)
        mock_exec.assert_called_with(
            self.switch,
            ['ovs-vsctl set port 4444 vlan_mode=native-untagged',
             'ovs-vsctl set port 4444 tag=44',
             'ovs-vsctl add port 4444 trunks 44',
             'ovs-vsctl add port 4444 trunks tag1',
             'ovs-vsctl add port 4444 trunks tag2'])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device', autospec=True)
    def test_unplug_bond_from_network_subports(self, mock_exec):
        trunk_details = {"sub_ports": [{"segmentation_id": "tag1"},
                                       {"segmentation_id": "tag2"}]}
        self.switch.unplug_bond_from_network(
            4444, 44, trunk_details=trunk_details)
        mock_exec.assert_called_with(
            self.switch,
            ['ovs-vsctl clear port 4444 tag',
             'ovs-vsctl clear port 4444 trunks',
             'ovs-vsctl clear port 4444 vlan_mode',
             'ovs-vsctl clear port 4444 vlan_mode',
             'ovs-vsctl clear port 4444 tag',
             'ovs-vsctl remove port 4444 trunks 44',
             'ovs-vsctl remove port 4444 trunks tag1',
             'ovs-vsctl remove port 4444 trunks tag2'])

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
        mock_exec.assert_called_with(self.switch,
                                     ['ovs-vsctl add port 44 trunks tag1',
                                      'ovs-vsctl add port 44 trunks tag2'])

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
        mock_exec.assert_called_with(self.switch,
                                     ['ovs-vsctl remove port 44 trunks tag1',
                                      'ovs-vsctl remove port 44 trunks tag2'])

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
