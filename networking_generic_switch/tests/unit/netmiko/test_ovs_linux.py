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

from networking_generic_switch.devices.netmiko_devices import ovs
from networking_generic_switch.tests.unit.netmiko import test_netmiko_base


class TestNetmikoOvsLinux(test_netmiko_base.NetmikoSwitchTestBase):

    def _make_switch_device(self):
        device_cfg = {'device_type': 'netmiko_ovs_linux'}
        return ovs.OvsLinux(device_cfg)

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch._exec_commands')
    def test_add_network(self, m_exec):
        self.switch.add_network(44, 44)
        m_exec.assert_called_with(None, network_id=44, segmentation_id=44)

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch._exec_commands')
    def test_del_network(self, mock_exec):
        self.switch.del_network(44)
        mock_exec.assert_called_with(None, segmentation_id=44)

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch._exec_commands')
    def test_plug_port_to_network(self, mock_exec):
        self.switch.plug_port_to_network(4444, 44)
        mock_exec.assert_called_with(
            ('ovs-vsctl set port {port} tag={segmentation_id}',),
            port=4444, segmentation_id=44)

    def test__format_commands(self):
        cmd_set = self.switch._format_commands(
            ovs.OvsLinux.PLUG_PORT_TO_NETWORK,
            port=3333,
            segmentation_id=33)
        self.assertEqual(cmd_set,
                         ['ovs-vsctl set port 3333 tag=33'])
