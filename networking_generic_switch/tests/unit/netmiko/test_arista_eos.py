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

import mock

from networking_generic_switch.devices.netmiko_devices import arista
from networking_generic_switch.tests.unit.netmiko import test_netmiko_base


class TestNetmikoAristaEos(test_netmiko_base.NetmikoSwitchTestBase):

    def _make_switch_device(self):
        device_cfg = {'device_type': 'netmiko_arista_eos'}
        return arista.AristaEos(device_cfg)

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch._exec_commands')
    def test_add_network(self, m_exec):
        self.switch.add_network(33, 33)
        m_exec.assert_called_with(
            ('vlan {segmentation_id}', 'name {network_id}'),
            network_id=33, segmentation_id=33)

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch._exec_commands')
    def test_del_network(self, mock_exec):
        self.switch.del_network(33)
        mock_exec.assert_called_with(
            ('no vlan {segmentation_id}',),
            segmentation_id=33)

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch._exec_commands')
    def test_plug_port_to_network(self, mock_exec):
        self.switch.plug_port_to_network(3333, 33)
        mock_exec.assert_called_with(
            ('interface {port}', 'switchport access vlan {segmentation_id}'),
            port=3333, segmentation_id=33)

    def test__format_commands(self):
        cmd_set = self.switch._format_commands(
            arista.AristaEos.ADD_NETWORK,
            segmentation_id=22,
            network_id=22)
        self.assertEqual(cmd_set, ['vlan 22', 'name 22'])

        cmd_set = self.switch._format_commands(
            arista.AristaEos.DELETE_NETWORK,
            segmentation_id=22)
        self.assertEqual(cmd_set, ['no vlan 22'])

        cmd_set = self.switch._format_commands(
            arista.AristaEos.PLUG_PORT_TO_NETWORK,
            port=3333,
            segmentation_id=33)
        self.assertEqual(cmd_set,
                         ['interface 3333', 'switchport access vlan 33'])
