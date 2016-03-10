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


import unittest

import mock
from neutron.plugins.ml2 import driver_context

from networking_generic_switch import devices
from networking_generic_switch import exceptions as exc
from networking_generic_switch import generic_switch_mech as gsm


@mock.patch('networking_generic_switch.devices.GenericSwitch._exec_commands')
class TestBaseSwitch(unittest.TestCase):
    def setUp(self):
        super(TestBaseSwitch, self).setUp()
        self.switch = devices.GenericSwitch('base')

    def test_add_network(self, m_exec):
        self.switch.add_network(22, 22)
        m_exec.assert_called_with(None, network_id=22, segmentation_id=22)

    def test_del_network(self, m_exec):
        self.switch.del_network(22)
        m_exec.assert_called_with(None, segmentation_id=22)

    def test_plug_port_to_network(self, m_exec):
        self.switch.plug_port_to_network(2222, 22)
        m_exec.assert_called_with(None, port=2222, segmentation_id=22)


class TestBaseSwitchExecFormat(unittest.TestCase):
    def setUp(self):
        super(TestBaseSwitchExecFormat, self).setUp()
        self.switch = devices.GenericSwitch('base')

    def test__format_commands(self):
        self.assertRaises(
            exc.GenericSwitchMethodError,
            self.switch._format_commands,
            devices.GenericSwitch.ADD_NETWORK,
            segmentation_id=22,
            network_id=22)

    def test__exec_commands(self):
        pass


@mock.patch('networking_generic_switch.devices.GenericSwitch._exec_commands')
@mock.patch('networking_generic_switch.devices.get_device')
@mock.patch('networking_generic_switch.config.get_device_list')
class TestGenericSwitchDriver(unittest.TestCase):
    def setUp(self):
        super(TestGenericSwitchDriver, self).setUp()

    def test_create_network_postcommit(self, m_list, m_device, m_exec):
        self.driver = gsm.GenericSwitchDriver()
        mock_context = mock.create_autospec(driver_context.NetworkContext)
        mock_context.current = {'id': 22,
                                'provider:network_type': 'vlan',
                                'provider:segmentation_id': 22}

        m_list.return_value = ['base']
        m_device.return_value = devices.GenericSwitch('base')

        self.driver.create_network_postcommit(mock_context)
        m_exec.assert_called_with(None, network_id=22, segmentation_id=22)

    def test_delete_network_postcommit(self, m_list, m_device, m_exec):
        self.driver = gsm.GenericSwitchDriver()
        mock_context = mock.create_autospec(driver_context.NetworkContext)
        mock_context.current = {'id': 22,
                                'provider:network_type': 'vlan',
                                'provider:segmentation_id': 22}

        m_list.return_value = ['base']
        m_device.return_value = devices.GenericSwitch('base')

        self.driver.delete_network_postcommit(mock_context)
        m_exec.assert_called_with(None, segmentation_id=22)

    def test_bind_port(self, m_list, m_device, m_exec):
        self.driver = gsm.GenericSwitchDriver()
        mock_context = mock.create_autospec(driver_context.PortContext)
        mock_context.current = {'binding:profile':
                                {'local_link_information':
                                    [
                                        {
                                            'switch_info': 'base',
                                            'port_id': 2222
                                        }
                                    ]
                                 },
                                'binding:vnic_type': 'baremetal'}
        mock_context.segments_to_bind = [
            {
                'segmentation_id': None,
                'id': 123
            }
        ]

        m_list.return_value = ['base']
        m_device.return_value = devices.GenericSwitch('base')

        self.driver.bind_port(mock_context)
        m_exec.assert_called_with(None, port=2222, segmentation_id='1')
        mock_context.set_binding.assert_called_with(123, 'other', {},
                                                    status='ACTIVE')

    def test_empty_methods(self, m_list, m_device, m_exec):
        self.driver = gsm.GenericSwitchDriver()
        mock_context = mock.create_autospec(driver_context.NetworkContext)
        mock_context.current = {'id': 22,
                                'provider:network_type': 'vlan',
                                'provider:segmentation_id': 22}

        m_list.return_value = ['base']
        m_device.return_value = devices.GenericSwitch('base')

        self.driver.initialize()

        self.driver.create_network_precommit(mock_context)
        self.driver.update_network_precommit(mock_context)
        self.driver.update_network_postcommit(mock_context)
        self.driver.delete_network_precommit(mock_context)
        self.driver.create_subnet_precommit(mock_context)
        self.driver.create_subnet_postcommit(mock_context)
        self.driver.update_subnet_precommit(mock_context)
        self.driver.update_subnet_postcommit(mock_context)
        self.driver.delete_subnet_precommit(mock_context)
        self.driver.delete_subnet_postcommit(mock_context)
        self.driver.create_port_precommit(mock_context)
        self.driver.create_port_postcommit(mock_context)
        self.driver.update_port_precommit(mock_context)
        self.driver.update_port_postcommit(mock_context)
        self.driver.delete_port_precommit(mock_context)
        self.driver.delete_port_postcommit(mock_context)
