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

from networking_generic_switch.devices.netmiko_devices import dell
from networking_generic_switch import exceptions as exc
from networking_generic_switch.tests.unit.netmiko import test_netmiko_base


class TestNetmikoDellNos(test_netmiko_base.NetmikoSwitchTestBase):

    def _make_switch_device(self, extra_cfg={}):
        device_cfg = {'device_type': 'netmiko_dell_force10'}
        device_cfg.update(extra_cfg)
        return dell.DellNos(device_cfg)

    def test_constants(self):
        self.assertIsNone(self.switch.SAVE_CONFIGURATION)

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device', autospec=True)
    def test_add_network(self, m_exec):
        self.switch.add_network(33, '0ae071f5-5be9-43e4-80ea-e41fefe85b21')
        m_exec.assert_called_with(
            self.switch,
            ['interface vlan 33',
             'description 0ae071f55be943e480eae41fefe85b21',
             'exit'])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device', autospec=True)
    def test_add_network_with_trunk_ports(self, mock_exec):
        switch = self._make_switch_device({'ngs_trunk_ports': 'port1, port2'})
        switch.add_network(33, '0ae071f5-5be9-43e4-80ea-e41fefe85b21')
        mock_exec.assert_called_with(
            switch,
            ['interface vlan 33',
             'description 0ae071f55be943e480eae41fefe85b21',
             'exit',
             'interface vlan 33', 'tagged port1', 'exit',
             'interface vlan 33', 'tagged port2', 'exit'])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device', autospec=True)
    def test_del_network(self, mock_exec):
        self.switch.del_network(33, '0ae071f5-5be9-43e4-80ea-e41fefe85b21')
        mock_exec.assert_called_with(self.switch,
                                     ['no interface vlan 33', 'exit'])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device', autospec=True)
    def test_del_network_with_trunk_ports(self, mock_exec):
        switch = self._make_switch_device({'ngs_trunk_ports': 'port1, port2'})
        switch.del_network(33, '0ae071f55be943e480eae41fefe85b21')
        mock_exec.assert_called_with(
            switch,
            ['interface vlan 33', 'no tagged port1', 'exit',
             'interface vlan 33', 'no tagged port2', 'exit',
             'no interface vlan 33', 'exit'])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device', autospec=True)
    def test_plug_port_to_network(self, mock_exec):
        self.switch.plug_port_to_network(3333, 33)
        mock_exec.assert_called_with(
            self.switch,
            ['interface vlan 33', 'untagged 3333', 'exit'])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device', autospec=True)
    def test_delete_port(self, mock_exec):
        self.switch.delete_port(3333, 33)
        mock_exec.assert_called_with(
            self.switch,
            ['interface vlan 33', 'no untagged 3333', 'exit'])

    def test__format_commands(self):
        cmd_set = self.switch._format_commands(
            dell.DellNos.ADD_NETWORK,
            segmentation_id=22,
            network_id=22,
            network_name='vlan-22')
        self.assertEqual(cmd_set,
                         ['interface vlan 22', 'description vlan-22', 'exit'])

        cmd_set = self.switch._format_commands(
            dell.DellNos.DELETE_NETWORK,
            segmentation_id=22)
        self.assertEqual(cmd_set, ['no interface vlan 22', 'exit'])

        cmd_set = self.switch._format_commands(
            dell.DellNos.PLUG_PORT_TO_NETWORK,
            port=3333,
            segmentation_id=33)
        self.assertEqual(cmd_set,
                         ['interface vlan 33', 'untagged 3333', 'exit'])
        cmd_set = self.switch._format_commands(
            dell.DellNos.DELETE_PORT,
            port=3333,
            segmentation_id=33)
        self.assertEqual(cmd_set,
                         ['interface vlan 33', 'no untagged 3333', 'exit'])

        cmd_set = self.switch._format_commands(
            dell.DellNos.ADD_NETWORK_TO_TRUNK,
            port=3333,
            segmentation_id=33)
        self.assertEqual(cmd_set,
                         ['interface vlan 33', 'tagged 3333', 'exit'])
        cmd_set = self.switch._format_commands(
            dell.DellNos.REMOVE_NETWORK_FROM_TRUNK,
            port=3333,
            segmentation_id=33)
        self.assertEqual(cmd_set,
                         ['interface vlan 33', 'no tagged 3333', 'exit'])


class TestNetmikoDellOS10(test_netmiko_base.NetmikoSwitchTestBase):

    def _make_switch_device(self, extra_cfg={}):
        device_cfg = {'device_type': 'netmiko_dell_os10'}
        device_cfg.update(extra_cfg)
        return dell.DellOS10(device_cfg)

    def test_constants(self):
        self.assertIsNone(self.switch.SAVE_CONFIGURATION)

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device', autospec=True)
    def test_add_network(self, m_exec):
        self.switch.add_network(33, '0ae071f5-5be9-43e4-80ea-e41fefe85b21')
        m_exec.assert_called_with(
            self.switch,
            ['interface vlan 33',
             'description 0ae071f55be943e480eae41fefe85b21',
             'exit']
        )

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device', autospec=True)
    def test_add_network_with_trunk_ports(self, mock_exec):
        switch = self._make_switch_device({'ngs_trunk_ports': 'port1, port2'})
        switch.add_network(33, '0ae071f5-5be9-43e4-80ea-e41fefe85b21')
        mock_exec.assert_called_with(
            switch,
            ['interface vlan 33',
             'description 0ae071f55be943e480eae41fefe85b21',
             'exit',
             'interface port1', 'switchport mode trunk',
             'switchport trunk allowed vlan 33', 'exit',
             'interface port2', 'switchport mode trunk',
             'switchport trunk allowed vlan 33', 'exit']
        )

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device', autospec=True)
    def test_del_network(self, mock_exec):
        self.switch.del_network(33, '0ae071f5-5be9-43e4-80ea-e41fefe85b21')
        mock_exec.assert_called_with(self.switch,
                                     ['no interface vlan 33', 'exit'])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device',
                return_value="", autospec=True)
    def test_plug_bond_to_network(self, mock_exec):
        self.switch.plug_bond_to_network(3333, 33)
        mock_exec.assert_called_with(
            self.switch,
            ['interface 3333', 'switchport mode access',
             'switchport access vlan 33',
             'exit']
        )

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device', autospec=True)
    def test_unplug_bond_from_network(self, mock_exec):
        self.switch.unplug_bond_from_network(3333, 33)
        mock_exec.assert_called_with(
            self.switch,
            ['interface 3333', 'no switchport access vlan', 'exit']
        )

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device', autospec=True)
    def test_del_network_with_trunk_ports(self, mock_exec):
        switch = self._make_switch_device({'ngs_trunk_ports': 'port1, port2'})
        switch.del_network(33, '0ae071f55be943e480eae41fefe85b21')
        mock_exec.assert_called_with(
            switch,
            ['interface port1', 'no switchport trunk allowed vlan 33', 'exit',
             'interface port2', 'no switchport trunk allowed vlan 33', 'exit',
             'no interface vlan 33', 'exit'])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device', autospec=True)
    def test_plug_port_to_network(self, mock_exec):
        self.switch.plug_port_to_network(3333, 33)
        mock_exec.assert_called_with(
            self.switch,
            ['interface 3333', 'switchport mode access',
             'switchport access vlan 33',
             'exit']
        )

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device', autospec=True)
    def test_delete_port(self, mock_exec):
        self.switch.delete_port(3333, 33)
        mock_exec.assert_called_with(
            self.switch,
            ['interface 3333', 'no switchport access vlan', 'exit']
        )

    def test__format_commands(self):
        cmd_set = self.switch._format_commands(
            dell.DellOS10.ADD_NETWORK,
            segmentation_id=22,
            network_id=22,
            network_name='vlan-22')
        self.assertEqual(cmd_set,
                         ['interface vlan 22',
                          'description vlan-22',
                          'exit']
                         )

        cmd_set = self.switch._format_commands(
            dell.DellOS10.DELETE_NETWORK,
            segmentation_id=22)
        self.assertEqual(cmd_set, ['no interface vlan 22', 'exit'])

        cmd_set = self.switch._format_commands(
            dell.DellOS10.PLUG_PORT_TO_NETWORK,
            port=3333,
            segmentation_id=33)
        self.assertEqual(cmd_set, ['interface 3333', 'switchport mode access',
                                   'switchport access vlan 33', 'exit'])
        cmd_set = self.switch._format_commands(
            dell.DellOS10.DELETE_PORT,
            port=3333,
            segmentation_id=33)
        self.assertEqual(cmd_set,
                         ['interface 3333', 'no switchport access vlan',
                          'exit'])

        cmd_set = self.switch._format_commands(
            dell.DellOS10.ADD_NETWORK_TO_TRUNK,
            port=3333,
            segmentation_id=33)
        self.assertEqual(cmd_set,
                         ['interface 3333', 'switchport mode trunk',
                          'switchport trunk allowed vlan 33',
                          'exit'])
        cmd_set = self.switch._format_commands(
            dell.DellOS10.REMOVE_NETWORK_FROM_TRUNK,
            port=3333,
            segmentation_id=33)
        self.assertEqual(cmd_set,
                         ['interface 3333',
                          'no switchport trunk allowed vlan 33',
                          'exit'])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device', autospec=True)
    def test_plug_port_to_network_subports(self, mock_exec):
        trunk_details = {"sub_ports": [{"segmentation_id": "tag1"},
                                       {"segmentation_id": "tag2"}]}
        self.switch.plug_port_to_network(4444, 44, trunk_details=trunk_details)
        mock_exec.assert_called_with(
            self.switch,
            ['interface 4444', 'switchport mode trunk',
             'switchport access vlan 44', 'interface 4444',
             'switchport mode trunk', 'switchport trunk allowed vlan tag1',
             'exit', 'interface 4444', 'switchport mode trunk',
             'switchport trunk allowed vlan tag2', 'exit'])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device', autospec=True)
    def test_delete_port_subports(self, mock_exec):
        trunk_details = {"sub_ports": [{"segmentation_id": "tag1"},
                                       {"segmentation_id": "tag2"}]}
        self.switch.delete_port(4444, 44, trunk_details=trunk_details)
        mock_exec.assert_called_with(
            self.switch,
            ['interface 4444', 'no switchport access vlan', 'exit',
             'interface 4444', 'no switchport access vlan', 'interface 4444',
             'no switchport trunk allowed vlan tag1', 'exit', 'interface 4444',
             'no switchport trunk allowed vlan tag2', 'exit'])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device', autospec=True)
    def test_plug_bond_to_network_subports(self, mock_exec):
        trunk_details = {"sub_ports": [{"segmentation_id": "tag1"},
                                       {"segmentation_id": "tag2"}]}
        self.switch.plug_bond_to_network(4444, 44, trunk_details=trunk_details)
        mock_exec.assert_called_with(
            self.switch,
            ['interface 4444', 'switchport mode trunk',
             'switchport access vlan 44', 'interface 4444',
             'switchport mode trunk', 'switchport trunk allowed vlan tag1',
             'exit', 'interface 4444', 'switchport mode trunk',
             'switchport trunk allowed vlan tag2', 'exit'])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device', autospec=True)
    def test_unplug_bond_from_network_subports(self, mock_exec):
        trunk_details = {"sub_ports": [{"segmentation_id": "tag1"},
                                       {"segmentation_id": "tag2"}]}
        self.switch.unplug_bond_from_network(
            4444, 44, trunk_details=trunk_details)
        mock_exec.assert_called_with(
            self.switch,
            ['interface 4444', 'no switchport access vlan', 'exit',
             'interface 4444', 'no switchport access vlan', 'interface 4444',
             'no switchport trunk allowed vlan tag1', 'exit', 'interface 4444',
             'no switchport trunk allowed vlan tag2', 'exit'])

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
            ['interface 44', 'switchport mode trunk',
             'switchport trunk allowed vlan tag1', 'exit', 'interface 44',
             'switchport mode trunk', 'switchport trunk allowed vlan tag2',
             'exit'])

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
            ['interface 44', 'no switchport trunk allowed vlan tag1', 'exit',
             'interface 44', 'no switchport trunk allowed vlan tag2', 'exit'])


class TestNetmikoDellPowerConnect(test_netmiko_base.NetmikoSwitchTestBase):

    def _make_switch_device(self, extra_cfg={}):
        device_cfg = {'device_type': 'netmiko_dell_powerconnect'}
        device_cfg.update(extra_cfg)
        return dell.DellPowerConnect(device_cfg)

    def test_constants(self):
        self.assertIsNone(self.switch.SAVE_CONFIGURATION)

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device',
                return_value='fake output', autospec=True)
    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.check_output', autospec=True)
    def test_add_network(self, mock_check, mock_exec):
        self.switch.add_network(33, '0ae071f5-5be9-43e4-80ea-e41fefe85b21')
        mock_exec.assert_called_with(
            self.switch,
            ['vlan database', 'vlan 33', 'exit'])
        mock_check.assert_called_once_with(self.switch,
                                           'fake output', 'add network')

    def test_invalid_switchmode(self):
        with self.assertRaises(exc.GenericSwitchConfigException):
            self._make_switch_device({'ngs_switchport_mode': 'BAD_PORT_MODE'})

    def test_switchmode_general(self):
        # should not raise an exception
        self._make_switch_device({'ngs_switchport_mode': 'GENERAL'})

    def test_switchmode_access(self):
        # should not raise an exception
        self._make_switch_device({'ngs_switchport_mode': 'access'})

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device',
                return_value='fake output', autospec=True)
    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.check_output', autospec=True)
    def test_add_network_with_trunk_ports(self, mock_check, mock_exec):
        switch = self._make_switch_device({'ngs_trunk_ports': 'port1, port2'})
        switch.add_network(33, '0ae071f5-5be9-43e4-80ea-e41fefe85b21')
        mock_exec.assert_called_with(
            switch,
            ['vlan database', 'vlan 33', 'exit',
             'interface port1',
             'switchport general allowed vlan add 33 tagged',
             'exit',
             'interface port2',
             'switchport general allowed vlan add 33 tagged',
             'exit'])
        mock_check.assert_called_once_with(
            switch, 'fake output', 'add network')

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device',
                return_value='fake output', autospec=True)
    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.check_output', autospec=True)
    def test_del_network(self, mock_check, mock_exec):
        self.switch.del_network(33, '0ae071f5-5be9-43e4-80ea-e41fefe85b21')
        mock_exec.assert_called_with(
            self.switch, ['vlan database', 'no vlan 33', 'exit'])
        mock_check.assert_called_once_with(
            self.switch, 'fake output', 'delete network')

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device',
                return_value='fake output', autospec=True)
    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.check_output', autospec=True)
    def test_del_network_with_trunk_ports(self, mock_check, mock_exec):
        switch = self._make_switch_device({'ngs_trunk_ports': 'port1,port2'})
        switch.del_network(33, '0ae071f55be943e480eae41fefe85b21')
        mock_exec.assert_called_with(
            switch,
            ['interface port1', 'switchport general allowed vlan remove 33',
             'exit',
             'interface port2', 'switchport general allowed vlan remove 33',
             'exit',
             'vlan database', 'no vlan 33', 'exit'])
        mock_check.assert_called_once_with(
            switch, 'fake output', 'delete network')

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device',
                return_value='fake output', autospec=True)
    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.check_output', autospec=True)
    def test_plug_port_to_network(self, mock_check, mock_exec):
        self.switch.plug_port_to_network(3333, 33)
        mock_exec.assert_called_with(
            self.switch,
            ['interface 3333', 'switchport access vlan 33', 'exit'])
        mock_check.assert_called_once_with(self.switch, 'fake output',
                                           'plug port')

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device',
                return_value='fake output', autospec=True)
    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.check_output', autospec=True)
    def test_plug_port_to_network_general_mode(self, mock_check, mock_exec):
        switch = self._make_switch_device({'ngs_switchport_mode': 'GENERAL'})
        switch.plug_port_to_network(3333, 33)
        mock_exec.assert_called_with(
            switch,
            ['interface 3333',
             'switchport general allowed vlan add 33 untagged',
             'switchport general pvid 33',
             'exit'])
        mock_check.assert_called_once_with(switch,
                                           'fake output',
                                           'plug port')

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device',
                return_value='fake output', autospec=True)
    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.check_output', autospec=True)
    def test_delete_port(self, mock_check, mock_exec):
        self.switch.delete_port(3333, 33)
        mock_exec.assert_called_with(
            self.switch,
            ['interface 3333', 'switchport access vlan none', 'exit'])
        mock_check.assert_called_once_with(
            self.switch, 'fake output', 'unplug port')

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device',
                return_value='fake output', autospec=True)
    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.check_output', autospec=True)
    def test_delete_port_general(self, mock_check, mock_exec):
        switch = self._make_switch_device({'ngs_switchport_mode': 'GENERAL'})
        switch.delete_port(3333, 33)
        mock_exec.assert_called_with(
            switch,
            ['interface 3333',
             'switchport general allowed vlan remove 33',
             'no switchport general pvid',
             'exit'])
        mock_check.assert_called_once_with(
            switch, 'fake output', 'unplug port')

    def test_check_output(self):
        self.switch.check_output('fake output', 'fake op')

    def _test_check_output_error(self, output):
        self.assertRaisesRegex(exc.GenericSwitchNetmikoConfigError,
                               "switch configuration operation failed",
                               self.switch.check_output, output, 'fake op')

    def test_check_output_incomplete_command(self):
        output = """
vlan database
vlan 33
exit
% Incomplete command
"""
        self._test_check_output_error(output)

    def test_check_output_vlan_not_recognised(self):
        output = """
vlan database
vlan 33
exit
VLAN was not created by user
"""
        self._test_check_output_error(output)

    def test_check_output_incomplete_db_locked(self):
        output = """
vlan database
vlan 33
exit
Configuration Database locked by another application - try later
"""
        self._test_check_output_error(output)

    def test__format_commands(self):
        cmd_set = self.switch._format_commands(
            dell.DellPowerConnect.ADD_NETWORK,
            segmentation_id=22,
            network_id=22)
        self.assertEqual(cmd_set, ['vlan database', 'vlan 22', 'exit'])

        cmd_set = self.switch._format_commands(
            dell.DellPowerConnect.DELETE_NETWORK,
            segmentation_id=22)
        self.assertEqual(cmd_set, ['vlan database', 'no vlan 22', 'exit'])

        cmd_set = self.switch._format_commands(
            dell.DellPowerConnect.PLUG_PORT_TO_NETWORK,
            port=3333,
            segmentation_id=33)
        self.assertEqual(cmd_set,
                         ['interface 3333', 'switchport access vlan 33',
                          'exit'])
        cmd_set = self.switch._format_commands(
            dell.DellPowerConnect.DELETE_PORT,
            port=3333,
            segmentation_id=33)
        self.assertEqual(cmd_set,
                         ['interface 3333', 'switchport access vlan none',
                          'exit'])

        cmd_set = self.switch._format_commands(
            dell.DellPowerConnect.ADD_NETWORK_TO_TRUNK,
            port=3333,
            segmentation_id=33)
        self.assertEqual(cmd_set,
                         ['interface 3333',
                          'switchport general allowed vlan add 33 tagged',
                          'exit'])
        cmd_set = self.switch._format_commands(
            dell.DellPowerConnect.REMOVE_NETWORK_FROM_TRUNK,
            port=3333,
            segmentation_id=33)
        self.assertEqual(cmd_set,
                         ['interface 3333',
                          'switchport general allowed vlan remove 33', 'exit'])

    def test__format_commands_general_mode(self):
        switch = self._make_switch_device({'ngs_switchport_mode': 'GENERAL'})
        cmd_set = switch._format_commands(
            dell.DellPowerConnect.PLUG_PORT_TO_NETWORK_GENERAL,
            port=3333,
            segmentation_id=33)
        self.assertEqual(cmd_set,
                         ['interface 3333',
                          'switchport general allowed vlan add 33 untagged',
                          'switchport general pvid 33',
                          'exit'])
        cmd_set = switch._format_commands(
            dell.DellPowerConnect.DELETE_PORT_GENERAL,
            port=3333,
            segmentation_id=33)
        self.assertEqual(cmd_set,
                         ['interface 3333',
                          'switchport general allowed vlan remove 33',
                          'no switchport general pvid',
                          'exit'])
