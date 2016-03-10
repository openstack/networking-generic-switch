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

from networking_generic_switch.devices import ovs_linux
from networking_generic_switch.tests.unit import test_base_switch


@mock.patch('networking_generic_switch.devices.GenericSwitch._exec_commands')
class TestOvsLinux(test_base_switch.TestBaseSwitch):
    def setUp(self):
        super(test_base_switch.TestBaseSwitch, self).setUp()

    def test_add_network(self, m_exec):
        self.switch = ovs_linux.generic_switch_device("ovs_linux")
        self.switch.add_network(44, 44)
        m_exec.assert_called_with(None, network_id=44, segmentation_id=44)

    def test_del_network(self, mock_exec):
        self.switch = ovs_linux.generic_switch_device("ovs_linux")
        self.switch.del_network(44)
        mock_exec.assert_called_with(None, segmentation_id=44)

    def test_plug_port_to_network(self, mock_exec):
        self.switch = ovs_linux.generic_switch_device("ovs_linux")
        self.switch.plug_port_to_network(4444, 44)
        mock_exec.assert_called_with(
            ('ovs-vsctl set port {port} tag={segmentation_id}',),
            port=4444, segmentation_id=44)


class TestOvsLinuxExecFormat(test_base_switch.TestBaseSwitchExecFormat):
    def setUp(self):
        super(TestOvsLinuxExecFormat, self).setUp()
        self.switch = ovs_linux.generic_switch_device("ovs_linux")

    def test__format_commands(self):
        cmd_set = self.switch._format_commands(
            ovs_linux.generic_switch_device.PLUG_PORT_TO_NETWORK,
            port=3333,
            segmentation_id=33)
        self.assertEqual(cmd_set,
                         ['ovs-vsctl set port 3333 tag=33'])

    def test__exec_commands(self):
        pass
