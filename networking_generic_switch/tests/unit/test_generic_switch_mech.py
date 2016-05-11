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

from networking_generic_switch import generic_switch_mech as gsm


@mock.patch('networking_generic_switch.config.get_devices',
            return_value={'foo': {'device_type': 'bar', 'spam': 'ham'}})
class TestGenericSwitchDriver(unittest.TestCase):
    def setUp(self):
        super(TestGenericSwitchDriver, self).setUp()
        self.switch_mock = mock.Mock()
        patcher = mock.patch(
            'networking_generic_switch.devices.device_manager',
            return_value=self.switch_mock)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_create_network_postcommit(self, m_list):
        driver = gsm.GenericSwitchDriver()
        driver.initialize()
        mock_context = mock.create_autospec(driver_context.NetworkContext)
        mock_context.current = {'id': 22,
                                'provider:network_type': 'vlan',
                                'provider:segmentation_id': 22}

        driver.create_network_postcommit(mock_context)
        self.switch_mock.add_network.assert_called_once_with(22, 22)

    def test_delete_network_postcommit(self, m_list):
        driver = gsm.GenericSwitchDriver()
        driver.initialize()
        mock_context = mock.create_autospec(driver_context.NetworkContext)
        mock_context.current = {'id': 22,
                                'provider:network_type': 'vlan',
                                'provider:segmentation_id': 22}

        driver.delete_network_postcommit(mock_context)
        self.switch_mock.del_network.assert_called_once_with(22)

    def test_bind_port(self, m_list):
        driver = gsm.GenericSwitchDriver()
        driver.initialize()
        mock_context = mock.create_autospec(driver_context.PortContext)
        mock_context.current = {'binding:profile':
                                {'local_link_information':
                                    [
                                        {
                                            'switch_info': 'foo',
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

        driver.bind_port(mock_context)
        self.switch_mock.plug_port_to_network.assert_called_once_with(
            2222, '1')
        mock_context.set_binding.assert_called_with(123, 'other', {},
                                                    status='ACTIVE')

    def test_empty_methods(self, m_list):
        driver = gsm.GenericSwitchDriver()
        driver.initialize()
        mock_context = mock.create_autospec(driver_context.NetworkContext)
        mock_context.current = {'id': 22,
                                'provider:network_type': 'vlan',
                                'provider:segmentation_id': 22}

        driver.initialize()

        driver.create_network_precommit(mock_context)
        driver.update_network_precommit(mock_context)
        driver.update_network_postcommit(mock_context)
        driver.delete_network_precommit(mock_context)
        driver.create_subnet_precommit(mock_context)
        driver.create_subnet_postcommit(mock_context)
        driver.update_subnet_precommit(mock_context)
        driver.update_subnet_postcommit(mock_context)
        driver.delete_subnet_precommit(mock_context)
        driver.delete_subnet_postcommit(mock_context)
        driver.create_port_precommit(mock_context)
        driver.create_port_postcommit(mock_context)
        driver.update_port_precommit(mock_context)
        driver.update_port_postcommit(mock_context)
        driver.delete_port_precommit(mock_context)
        driver.delete_port_postcommit(mock_context)
