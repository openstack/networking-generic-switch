# Copyright (c) 2022 VEXXHOST, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

from unittest import mock

from networking_generic_switch.devices.netmiko_devices import aruba
from networking_generic_switch.tests.unit.netmiko import test_netmiko_base


class TestNetmikoAruba(test_netmiko_base.NetmikoSwitchTestBase):

    def _make_switch_device(self, extra_cfg={}):
        device_cfg = {'device_type': 'netmiko_aruba_os'}
        device_cfg.update(extra_cfg)
        return aruba.ArubaOSCX(device_cfg)

    def test_constants(self):
        self.assertIsNone(self.switch.SAVE_CONFIGURATION)

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device')
    def test_add_network(self, m_exec):
        self.switch.add_network(33, '0ae071f5-5be9-43e4-80ea-e41fefe85b21')
        m_exec.assert_called_with(
            ['vlan 33', 'name 0ae071f55be943e480eae41fefe85b21'])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device')
    def test_del_network(self, mock_exec):
        self.switch.del_network(33, '0ae071f5-5be9-43e4-80ea-e41fefe85b21')
        mock_exec.assert_called_with(['no vlan 33'])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device')
    def test_plug_port_to_network(self, mock_exec):
        self.switch.plug_port_to_network(3333, 33)
        mock_exec.assert_called_with(
            ['interface 3333', 'no routing', 'vlan access 33'])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device')
    def test_plug_port_to_network_disable_inactive(self, m_sctd):
        switch = self._make_switch_device(
            {'ngs_disable_inactive_ports': 'true'})
        switch.plug_port_to_network(3333, 33)
        m_sctd.assert_called_with(
            ['interface 3333', 'no shutdown',
             'interface 3333', 'no routing', 'vlan access 33'])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device')
    def test_delete_port(self, mock_exec):
        self.switch.delete_port(3333, 33)
        mock_exec.assert_called_with(['interface 3333', 'no vlan access 33'])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device')
    def test_delete_port_disable_inactive(self, m_sctd):
        switch = self._make_switch_device(
            {'ngs_disable_inactive_ports': 'true'})
        switch.delete_port(3333, 33)
        m_sctd.assert_called_with(
            ['interface 3333', 'no vlan access 33',
             'interface 3333', 'shutdown'])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device')
    def test_add_network_with_trunk_ports(self, mock_exec):
        switch = self._make_switch_device({'ngs_trunk_ports': 'port1, port2'})
        switch.add_network(33, '0ae071f5-5be9-43e4-80ea-e41fefe85b21')
        mock_exec.assert_called_with(
            ['vlan 33',
             'name 0ae071f55be943e480eae41fefe85b21',
             'interface port1', 'no routing', 'vlan trunk allowed 33',
             'interface port2', 'no routing', 'vlan trunk allowed 33'])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device')
    def test_del_network_with_trunk_ports(self, mock_exec):
        switch = self._make_switch_device({'ngs_trunk_ports': 'port1, port2'})
        switch.del_network(33, '0ae071f55be943e480eae41fefe85b21')
        mock_exec.assert_called_with(
            ['interface port1', 'no vlan trunk allowed 33',
             'interface port2', 'no vlan trunk allowed 33',
             'no vlan 33'])

    def test__format_commands(self):
        cmd_set = self.switch._format_commands(
            aruba.ArubaOSCX.ADD_NETWORK,
            segmentation_id=22,
            network_id=22,
            network_name='vlan-22')
        self.assertEqual(cmd_set, ['vlan 22', 'name vlan-22'])

        cmd_set = self.switch._format_commands(
            aruba.ArubaOSCX.DELETE_NETWORK,
            segmentation_id=22)
        self.assertEqual(cmd_set, ['no vlan 22'])

        cmd_set = self.switch._format_commands(
            aruba.ArubaOSCX.PLUG_PORT_TO_NETWORK,
            port=3333,
            segmentation_id=33)
        plug_exp = ['interface 3333', 'no routing', 'vlan access 33']
        self.assertEqual(plug_exp, cmd_set)

        cmd_set = self.switch._format_commands(
            aruba.ArubaOSCX.DELETE_PORT,
            port=3333,
            segmentation_id=33)
        del_exp = ['interface 3333', 'no vlan access 33']
        self.assertEqual(del_exp, cmd_set)

        cmd_set = self.switch._format_commands(
            aruba.ArubaOSCX.ADD_NETWORK_TO_TRUNK,
            port=3333,
            segmentation_id=33)
        trunk_exp = ['interface 3333', 'no routing', 'vlan trunk allowed 33']
        self.assertEqual(trunk_exp, cmd_set)
        cmd_set = self.switch._format_commands(
            aruba.ArubaOSCX.REMOVE_NETWORK_FROM_TRUNK,
            port=3333,
            segmentation_id=33)
        self.assertEqual(cmd_set,
                         ['interface 3333', 'no vlan trunk allowed 33'])
