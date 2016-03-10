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

from networking_generic_switch.devices import cisco_ios
from networking_generic_switch.tests.unit import test_base_switch


@mock.patch('networking_generic_switch.devices.GenericSwitch._exec_commands')
class TestCiscoIos(test_base_switch.TestBaseSwitch):
    def setUp(self):
        super(test_base_switch.TestBaseSwitch, self).setUp()
        self.switch = cisco_ios.generic_switch_device("cisco_ios")

    def test_add_network(self, m_exec):
        self.switch.add_network(33, 33)
        m_exec.assert_called_with(
            ('vlan {segmentation_id}', 'name {network_id}'),
            network_id=33, segmentation_id=33)

    def test_del_network(self, mock_exec):
        self.switch.del_network(33)
        mock_exec.assert_called_with(
            ('no vlan {segmentation_id}',),
            segmentation_id=33)

    def test_plug_port_to_network(self, mock_exec):
        self.switch.plug_port_to_network(3333, 33)
        mock_exec.assert_called_with(
            ('interface {port}', 'switchport access vlan {segmentation_id}'),
            port=3333, segmentation_id=33)


class TestCiscoIosExecFormat(test_base_switch.TestBaseSwitchExecFormat):
    def setUp(self):
        super(TestCiscoIosExecFormat, self).setUp()
        self.switch = cisco_ios.generic_switch_device("cisco_ios")

    def test__format_commands(self):
        cmd_set = self.switch._format_commands(
            cisco_ios.generic_switch_device.ADD_NETWORK,
            segmentation_id=22,
            network_id=22)
        self.assertEqual(cmd_set, ['vlan 22', 'name 22'])

        cmd_set = self.switch._format_commands(
            cisco_ios.generic_switch_device.DELETE_NETWORK,
            segmentation_id=22,
            network_id=22)
        self.assertEqual(cmd_set, ['no vlan 22'])

        cmd_set = self.switch._format_commands(
            cisco_ios.generic_switch_device.PLUG_PORT_TO_NETWORK,
            port=3333,
            segmentation_id=33)
        self.assertEqual(cmd_set,
                         ['interface 3333', 'switchport access vlan 33'])

    def test__exec_commands(self):
        pass
