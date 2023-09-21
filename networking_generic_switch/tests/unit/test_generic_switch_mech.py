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
from unittest import mock

from neutron.db import provisioning_blocks
from neutron.plugins.ml2 import driver_context
from neutron_lib.callbacks import resources

from networking_generic_switch import exceptions
from networking_generic_switch import generic_switch_mech as gsm


@mock.patch('networking_generic_switch.config.get_devices',
            return_value={'foo': {'device_type': 'bar', 'spam': 'ham',
                                  'ip': 'ip'}})
class TestGenericSwitchDriver(unittest.TestCase):
    def setUp(self):
        super(TestGenericSwitchDriver, self).setUp()
        self.switch_mock = mock.Mock()
        self.switch_mock.config = {'device_type': 'bar', 'spam': 'ham',
                                   'ip': 'ip'}
        self.switch_mock._get_physical_networks.return_value = []
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
                                'provider:segmentation_id': 22,
                                'provider:physical_network': 'physnet1'}

        driver.create_network_postcommit(mock_context)
        self.switch_mock.add_network.assert_called_once_with(22, 22)

    def test_create_network_postcommit_with_physnet(self, m_list):
        driver = gsm.GenericSwitchDriver()
        driver.initialize()
        mock_context = mock.create_autospec(driver_context.NetworkContext)
        mock_context.current = {'id': 22,
                                'provider:network_type': 'vlan',
                                'provider:segmentation_id': 22,
                                'provider:physical_network': 'physnet1'}
        self.switch_mock._get_physical_networks.return_value = ['physnet1']

        driver.create_network_postcommit(mock_context)
        self.switch_mock.add_network.assert_called_once_with(22, 22)

    def test_create_network_postcommit_with_multiple_physnets(self, m_list):
        driver = gsm.GenericSwitchDriver()
        driver.initialize()
        mock_context = mock.create_autospec(driver_context.NetworkContext)
        mock_context.current = {'id': 22,
                                'provider:network_type': 'vlan',
                                'provider:segmentation_id': 22,
                                'provider:physical_network': 'physnet1'}
        self.switch_mock._get_physical_networks.return_value = ['physnet1',
                                                                'physnet2']

        driver.create_network_postcommit(mock_context)
        self.switch_mock.add_network.assert_called_once_with(22, 22)
        self.assertEqual(self.switch_mock.add_network.call_count, 1)

    def test_create_network_postcommit_with_different_physnet(self, m_list):
        driver = gsm.GenericSwitchDriver()
        driver.initialize()
        mock_context = mock.create_autospec(driver_context.NetworkContext)
        mock_context.current = {'id': 22,
                                'provider:network_type': 'vlan',
                                'provider:segmentation_id': 22,
                                'provider:physical_network': 'physnet1'}
        self.switch_mock._get_physical_networks.return_value = ['physnet2']

        driver.create_network_postcommit(mock_context)
        self.assertFalse(self.switch_mock.add_network.called)

    @mock.patch('networking_generic_switch.generic_switch_mech.LOG')
    def test_create_network_postcommit_failure(self, m_log, m_list):
        driver = gsm.GenericSwitchDriver()
        driver.initialize()
        self.switch_mock.add_network.side_effect = ValueError('boom')
        mock_context = mock.create_autospec(driver_context.NetworkContext)
        mock_context.current = {'id': 22,
                                'provider:network_type': 'vlan',
                                'provider:segmentation_id': 22,
                                'provider:physical_network': 'physnet1'}

        self.assertRaisesRegex(ValueError, "boom",
                               driver.create_network_postcommit, mock_context)
        self.switch_mock.add_network.assert_called_once_with(22, 22)
        self.assertEqual(1, m_log.error.call_count)
        self.assertIn('Failed to create network', m_log.error.call_args[0][0])
        self.assertNotIn('has been added', m_log.info.call_args[0][0])

    @mock.patch('networking_generic_switch.generic_switch_mech.LOG')
    def test_create_network_postcommit_failure_multiple(self, m_log, m_list):
        m_list.return_value = {
            'foo': {'device_type': 'bar', 'spam': 'ham', 'ip': 'ip'},
            'bar': {'device_type': 'bar', 'spam': 'ham', 'ip': 'ip'},
        }
        driver = gsm.GenericSwitchDriver()
        driver.initialize()
        self.switch_mock.add_network.side_effect = ValueError('boom')
        mock_context = mock.create_autospec(driver_context.NetworkContext)
        mock_context.current = {'id': 22,
                                'provider:network_type': 'vlan',
                                'provider:segmentation_id': 22,
                                'provider:physical_network': 'physnet1'}

        self.assertRaisesRegex(ValueError, "boom",
                               driver.create_network_postcommit, mock_context)
        self.switch_mock.add_network.assert_called_once_with(22, 22)
        self.assertEqual(1, m_log.error.call_count)
        self.assertIn('Failed to create network', m_log.error.call_args[0][0])

    def test_delete_network_postcommit(self, m_list):
        driver = gsm.GenericSwitchDriver()
        driver.initialize()
        mock_context = mock.create_autospec(driver_context.NetworkContext)
        mock_context.current = {'id': 22,
                                'provider:network_type': 'vlan',
                                'provider:segmentation_id': 22,
                                'provider:physical_network': 'physnet1'}

        driver.delete_network_postcommit(mock_context)
        self.switch_mock.del_network.assert_called_once_with(22, 22)

    def test_delete_network_postcommit_with_physnet(self, m_list):
        driver = gsm.GenericSwitchDriver()
        driver.initialize()
        mock_context = mock.create_autospec(driver_context.NetworkContext)
        mock_context.current = {'id': 22,
                                'provider:network_type': 'vlan',
                                'provider:segmentation_id': 22,
                                'provider:physical_network': 'physnet1'}
        self.switch_mock._get_physical_networks.return_value = ['physnet1']

        driver.delete_network_postcommit(mock_context)
        self.switch_mock.del_network.assert_called_once_with(22, 22)

    def test_delete_network_postcommit_with_multiple_physnets(self, m_list):
        driver = gsm.GenericSwitchDriver()
        driver.initialize()
        mock_context = mock.create_autospec(driver_context.NetworkContext)
        mock_context.current = {'id': 22,
                                'provider:network_type': 'vlan',
                                'provider:segmentation_id': 22,
                                'provider:physical_network': 'physnet1'}
        self.switch_mock._get_physical_networks.return_value = ['physnet1',
                                                                'physnet2']

        driver.delete_network_postcommit(mock_context)
        self.switch_mock.del_network.assert_called_once_with(22, 22)
        self.assertEqual(self.switch_mock.del_network.call_count, 1)

    def test_delete_network_postcommit_with_different_physnet(self, m_list):
        driver = gsm.GenericSwitchDriver()
        driver.initialize()
        mock_context = mock.create_autospec(driver_context.NetworkContext)
        mock_context.current = {'id': 22,
                                'provider:network_type': 'vlan',
                                'provider:segmentation_id': 22,
                                'provider:physical_network': 'physnet1'}
        self.switch_mock._get_physical_networks.return_value = ['physnet2']

        driver.delete_network_postcommit(mock_context)
        self.assertFalse(self.switch_mock.del_network.called)

    @mock.patch('networking_generic_switch.generic_switch_mech.LOG')
    def test_delete_network_postcommit_failure(self, m_log, m_list):
        driver = gsm.GenericSwitchDriver()
        driver.initialize()
        self.switch_mock.del_network.side_effect = ValueError('boom')
        mock_context = mock.create_autospec(driver_context.NetworkContext)
        mock_context.current = {'id': 22,
                                'provider:network_type': 'vlan',
                                'provider:segmentation_id': 22,
                                'provider:physical_network': 'physnet1'}

        self.assertRaisesRegex(ValueError, "boom",
                               driver.delete_network_postcommit, mock_context)
        self.switch_mock.del_network.assert_called_once_with(22, 22)
        self.assertEqual(1, m_log.error.call_count)
        self.assertIn('Failed to delete network', m_log.error.call_args[0][0])
        self.assertNotIn('has been deleted', m_log.info.call_args[0][0])

    @mock.patch('networking_generic_switch.generic_switch_mech.LOG')
    def test_delete_network_postcommit_failure_multiple(self, m_log, m_list):
        m_list.return_value = {
            'foo': {'device_type': 'bar', 'spam': 'ham', 'ip': 'ip'},
            'bar': {'device_type': 'bar', 'spam': 'ham', 'ip': 'ip'},
        }
        driver = gsm.GenericSwitchDriver()
        driver.initialize()
        self.switch_mock.del_network.side_effect = ValueError('boom')
        mock_context = mock.create_autospec(driver_context.NetworkContext)
        mock_context.current = {'id': 22,
                                'provider:network_type': 'vlan',
                                'provider:segmentation_id': 22,
                                'provider:physical_network': 'physnet1'}

        self.assertRaisesRegex(ValueError, "boom",
                               driver.delete_network_postcommit, mock_context)
        self.switch_mock.del_network.assert_called_with(22, 22)
        self.assertEqual(2, self.switch_mock.del_network.call_count)
        self.assertEqual(2, m_log.error.call_count)
        self.assertIn('Failed to delete network', m_log.error.call_args[0][0])

    def test_delete_port_postcommit(self, m_list):
        driver = gsm.GenericSwitchDriver()
        driver.initialize()
        mock_context = mock.create_autospec(driver_context.PortContext)
        mock_context.current = {'binding:profile':
                                {'local_link_information':
                                    [
                                        {
                                            'switch_info': 'foo',
                                            'port_id': '2222'
                                        }
                                    ]
                                 },
                                'binding:vnic_type': 'baremetal',
                                'binding:vif_type': 'other',
                                'id': 'aaaa-bbbb-cccc'}
        mock_context.network = mock.Mock()
        mock_context.network.current = {'provider:segmentation_id': 123,
                                        'id': 'aaaa-bbbb-cccc'}
        mock_context.segments_to_bind = [mock_context.network.current]

        driver.delete_port_postcommit(mock_context)
        self.switch_mock.delete_port.assert_called_once_with(
            '2222', 123)

    def test_delete_portgroup_postcommit(self, m_list):
        driver = gsm.GenericSwitchDriver()
        driver.initialize()
        mock_context = mock.create_autospec(driver_context.PortContext)
        mock_context.current = {'binding:profile':
                                {'local_link_information':
                                    [
                                        {
                                            'switch_info': 'foo',
                                            'port_id': 2222
                                        },
                                        {
                                            'switch_info': 'foo',
                                            'port_id': 3333
                                        },
                                    ]
                                 },
                                'binding:vnic_type': 'baremetal',
                                'binding:vif_type': 'other',
                                'id': 'aaaa-bbbb-cccc'}
        mock_context.network = mock.Mock()
        mock_context.network.current = {'provider:segmentation_id': 123,
                                        'id': 'aaaa-bbbb-cccc'}
        mock_context.segments_to_bind = [mock_context.network.current]

        driver.delete_port_postcommit(mock_context)
        self.switch_mock.delete_port.assert_has_calls(
            [mock.call(2222, 123),
             mock.call(3333, 123)])

    def test_delete_portgroup_postcommit_802_3ad(self, m_list):
        driver = gsm.GenericSwitchDriver()
        driver.initialize()
        mock_context = mock.create_autospec(driver_context.PortContext)
        mock_context.current = {'binding:profile':
                                {'local_link_information':
                                    [
                                        {
                                            'switch_info': 'foo',
                                            'port_id': 2222
                                        },
                                        {
                                            'switch_info': 'foo',
                                            'port_id': 3333
                                        },
                                    ],
                                 'local_group_information':
                                    {
                                        'bond_mode': '4'
                                    }
                                 },
                                'binding:vnic_type': 'baremetal',
                                'binding:vif_type': 'other',
                                'id': 'aaaa-bbbb-cccc'}
        mock_context.network = mock.Mock()
        mock_context.network.current = {'provider:segmentation_id': 123,
                                        'id': 'aaaa-bbbb-cccc'}
        mock_context.segments_to_bind = [mock_context.network.current]

        driver.delete_port_postcommit(mock_context)
        self.switch_mock.unplug_bond_from_network.assert_has_calls(
            [mock.call(2222, 123),
             mock.call(3333, 123)])

    def test_delete_port_postcommit_failure(self, m_list):
        driver = gsm.GenericSwitchDriver()
        driver.initialize()
        mock_context = mock.create_autospec(driver_context.PortContext)
        self.switch_mock.delete_port.side_effect = (
            exceptions.GenericSwitchNetmikoMethodError(cmds='foo',
                                                       args='bar'))
        mock_context.current = {'binding:profile':
                                {'local_link_information':
                                    [
                                        {
                                            'switch_info': 'foo',
                                            'port_id': 2222
                                        }
                                    ]
                                 },
                                'binding:vnic_type': 'baremetal',
                                'binding:vif_type': 'other',
                                'id': 'aaaa-bbbb-cccc'}
        mock_context.network = mock.Mock()
        mock_context.network.current = {'provider:segmentation_id': 123,
                                        'id': 'aaaa-bbbb-cccc'}
        mock_context.segments_to_bind = [mock_context.network.current]

        self.assertRaises(exceptions.GenericSwitchNetmikoMethodError,
                          driver.delete_port_postcommit,
                          mock_context)

    def test_delete_port_postcommit_unknown_switch(self, m_list):
        driver = gsm.GenericSwitchDriver()
        driver.initialize()
        mock_context = mock.create_autospec(driver_context.PortContext)
        mock_context.current = {'binding:profile':
                                {'local_link_information':
                                    [
                                        {
                                            'switch_info': 'bar',
                                            'port_id': 2222
                                        }
                                    ]
                                 },
                                'binding:vnic_type': 'baremetal',
                                'binding:vif_type': 'other'}
        mock_context.segments_to_bind = [
            {
                'segmentation_id': None,
                'id': 123
            }
        ]
        self.assertIsNone(driver.delete_port_postcommit(mock_context))
        self.switch_mock.delete_port.assert_not_called()

    def test_delete_port_postcommit_no_segmentation_id(self, m_list):
        driver = gsm.GenericSwitchDriver()
        driver.initialize()
        mock_context = mock.create_autospec(driver_context.PortContext)
        mock_context.current = {'binding:profile':
                                {'local_link_information':
                                    [
                                        {
                                            'switch_info': 'foo',
                                            'port_id': '2222'
                                        }
                                    ]
                                 },
                                'binding:vnic_type': 'baremetal',
                                'binding:vif_type': 'other',
                                'id': 'aaaa-bbbb-cccc'}
        mock_context.network = mock.Mock()
        mock_context.network.current = {'provider:segmentation_id': None,
                                        'id': 'aaaa-bbbb-cccc'}
        mock_context.segments_to_bind = [mock_context.network.current]

        driver.delete_port_postcommit(mock_context)
        self.switch_mock.delete_port.assert_called_once_with(
            '2222', 1)

    @mock.patch.object(provisioning_blocks, 'provisioning_complete')
    def test_update_port_postcommit_not_bound(self, m_pc, m_list):
        driver = gsm.GenericSwitchDriver()
        driver.initialize()
        mock_context = mock.create_autospec(driver_context.PortContext)
        mock_context._plugin_context = mock.MagicMock()
        mock_context.current = {'binding:profile':
                                {'local_link_information':
                                    [
                                        {
                                            'switch_info': 'foo',
                                            'port_id': 2222
                                        }
                                    ]
                                 },
                                'binding:vnic_type': 'baremetal',
                                'id': '123',
                                'binding:vif_type': 'unbound',
                                'status': 'DOWN'}
        mock_context.original = {'binding:profile': {},
                                 'binding:vnic_type': 'baremetal',
                                 'id': '123',
                                 'binding:vif_type': 'unbound'}
        driver.update_port_postcommit(mock_context)
        self.switch_mock.plug_port_to_network.assert_not_called()
        self.assertFalse(m_pc.called)

    @mock.patch.object(provisioning_blocks, 'provisioning_complete')
    def test_update_port_postcommit_not_baremetal(self, m_pc, m_list):
        driver = gsm.GenericSwitchDriver()
        driver.initialize()
        mock_context = mock.create_autospec(driver_context.PortContext)
        mock_context._plugin_context = mock.MagicMock()
        mock_context.current = {'binding:profile':
                                {'local_link_information':
                                    [
                                        {
                                            'switch_info': 'foo',
                                            'port_id': 2222
                                        }
                                    ]
                                 },
                                'binding:vnic_type': 'mcvtap',
                                'id': '123',
                                'binding:vif_type': 'other',
                                'status': 'DOWN'}
        mock_context.original = {'binding:profile': {},
                                 'binding:vnic_type': 'mcvtap',
                                 'id': '123',
                                 'binding:vif_type': 'unbound'}
        driver.update_port_postcommit(mock_context)
        self.switch_mock.plug_port_to_network.assert_not_called()
        self.assertFalse(m_pc.called)

    @mock.patch.object(provisioning_blocks, 'provisioning_complete')
    def test_update_port_postcommit_no_llc(self, m_pc, m_list):
        driver = gsm.GenericSwitchDriver()
        driver.initialize()
        mock_context = mock.create_autospec(driver_context.PortContext)
        mock_context._plugin_context = mock.MagicMock()
        mock_context.current = {'binding:profile': {},
                                'binding:vnic_type': 'baremetal',
                                'id': '123',
                                'binding:vif_type': 'other',
                                'status': 'DOWN'}
        mock_context.original = {'binding:profile': {},
                                 'binding:vnic_type': 'baremetal',
                                 'id': '123',
                                 'binding:vif_type': 'unbound'}
        driver.update_port_postcommit(mock_context)
        self.switch_mock.plug_port_to_network.assert_not_called()
        self.assertFalse(m_pc.called)

    @mock.patch.object(provisioning_blocks, 'provisioning_complete')
    def test_update_port_postcommit_not_managed_by_ngs(self, m_pc, m_list):
        driver = gsm.GenericSwitchDriver()
        driver.initialize()
        mock_context = mock.create_autospec(driver_context.PortContext)
        mock_context._plugin_context = mock.MagicMock()
        mock_context.current = {'binding:profile':
                                {'local_link_information':
                                    [
                                        {
                                            'switch_info': 'ughh',
                                            'port_id': 2222
                                        }
                                    ]
                                 },
                                'binding:vnic_type': 'baremetal',
                                'id': '123',
                                'binding:vif_type': 'other',
                                'status': 'DOWN'}
        mock_context.original = {'binding:profile': {},
                                 'binding:vnic_type': 'baremetal',
                                 'id': '123',
                                 'binding:vif_type': 'unbound'}
        driver.update_port_postcommit(mock_context)
        self.switch_mock.plug_port_to_network.assert_not_called()
        self.assertFalse(m_pc.called)

    @mock.patch.object(provisioning_blocks, 'provisioning_complete')
    def test_update_port_postcommit_complete_provisioning(self, m_pc, m_list):
        driver = gsm.GenericSwitchDriver()
        driver.initialize()
        mock_context = mock.create_autospec(driver_context.PortContext)
        mock_context._plugin_context = mock.MagicMock()
        mock_context.current = {'binding:profile':
                                {'local_link_information':
                                    [
                                        {
                                            'switch_info': 'foo',
                                            'port_id': 2222
                                        }
                                    ]
                                 },
                                'binding:vnic_type': 'baremetal',
                                'id': '123',
                                'binding:vif_type': 'other',
                                'status': 'DOWN'}
        mock_context.original = {'binding:profile': {},
                                 'binding:vnic_type': 'baremetal',
                                 'id': '123',
                                 'binding:vif_type': 'unbound'}
        mock_context.network = mock.Mock()
        mock_context.network.current = {
            'provider:segmentation_id': 42,
            'provider:physical_network': 'physnet1'
        }
        driver.update_port_postcommit(mock_context)
        self.switch_mock.plug_port_to_network.assert_called_once_with(
            2222, 42)
        m_pc.assert_called_once_with(mock_context._plugin_context,
                                     mock_context.current['id'],
                                     resources.PORT,
                                     'GENERICSWITCH')

    @mock.patch.object(provisioning_blocks, 'provisioning_complete')
    def test_update_portgroup_postcommit_complete_provisioning(self,
                                                               m_pc,
                                                               m_list):
        driver = gsm.GenericSwitchDriver()
        driver.initialize()
        mock_context = mock.create_autospec(driver_context.PortContext)
        mock_context._plugin_context = mock.MagicMock()
        mock_context.current = {'binding:profile':
                                {'local_link_information':
                                    [
                                        {
                                            'switch_info': 'foo',
                                            'port_id': 2222
                                        },
                                        {
                                            'switch_info': 'foo',
                                            'port_id': 3333
                                        },
                                    ]
                                 },
                                'binding:vnic_type': 'baremetal',
                                'id': '123',
                                'binding:vif_type': 'other',
                                'status': 'DOWN'}
        mock_context.original = {'binding:profile': {},
                                 'binding:vnic_type': 'baremetal',
                                 'id': '123',
                                 'binding:vif_type': 'unbound'}
        mock_context.network = mock.Mock()
        mock_context.network.current = {
            'provider:segmentation_id': 42,
            'provider:physical_network': 'physnet1'
        }
        driver.update_port_postcommit(mock_context)
        self.switch_mock.plug_port_to_network.assert_has_calls(
            [mock.call(2222, 42),
             mock.call(3333, 42)]
        )
        self.switch_mock.plug_bond_to_network.assert_not_called()
        m_pc.assert_has_calls([mock.call(mock_context._plugin_context,
                                         mock_context.current['id'],
                                         resources.PORT,
                                         'GENERICSWITCH')])

    @mock.patch.object(provisioning_blocks, 'provisioning_complete')
    def test_update_portgroup_postcommit_complete_provisioning_802_3ad(self,
                                                                       m_pc,
                                                                       m_list):
        driver = gsm.GenericSwitchDriver()
        driver.initialize()
        mock_context = mock.create_autospec(driver_context.PortContext)
        mock_context._plugin_context = mock.MagicMock()
        mock_context.current = {'binding:profile':
                                {'local_link_information':
                                    [
                                        {
                                            'switch_info': 'foo',
                                            'port_id': 2222
                                        },
                                        {
                                            'switch_info': 'foo',
                                            'port_id': 3333
                                        },
                                    ],
                                 'local_group_information':
                                    {
                                        'bond_mode': '802.3ad'
                                    }
                                 },
                                'binding:vnic_type': 'baremetal',
                                'id': '123',
                                'binding:vif_type': 'other',
                                'status': 'DOWN'}
        mock_context.original = {'binding:profile': {},
                                 'binding:vnic_type': 'baremetal',
                                 'id': '123',
                                 'binding:vif_type': 'unbound'}
        mock_context.network = mock.Mock()
        mock_context.network.current = {
            'provider:segmentation_id': 42,
            'provider:physical_network': 'physnet1'
        }
        driver.update_port_postcommit(mock_context)
        self.switch_mock.plug_bond_to_network.assert_has_calls(
            [mock.call(2222, 42),
             mock.call(3333, 42)]
        )
        self.switch_mock.plug_port_to_network.assert_not_called()
        m_pc.assert_has_calls([mock.call(mock_context._plugin_context,
                                         mock_context.current['id'],
                                         resources.PORT,
                                         'GENERICSWITCH')])

    @mock.patch.object(provisioning_blocks, 'provisioning_complete')
    def test_update_port_postcommit_with_physnet(self, m_pc, m_list):
        driver = gsm.GenericSwitchDriver()
        driver.initialize()
        mock_context = mock.create_autospec(driver_context.PortContext)
        mock_context._plugin_context = mock.MagicMock()
        mock_context.current = {'binding:profile':
                                {'local_link_information':
                                    [
                                        {
                                            'switch_info': 'foo',
                                            'port_id': 2222
                                        }
                                    ]
                                 },
                                'binding:vnic_type': 'baremetal',
                                'id': '123',
                                'binding:vif_type': 'other',
                                'status': 'DOWN'}
        mock_context.original = {'binding:profile': {},
                                 'binding:vnic_type': 'baremetal',
                                 'id': '123',
                                 'binding:vif_type': 'unbound'}
        mock_context.network = mock.Mock()
        mock_context.network.current = {
            'provider:physical_network': 'physnet1'
        }
        self.switch_mock._get_physical_networks.return_value = ['physnet1']

        driver.update_port_postcommit(mock_context)
        self.switch_mock.plug_port_to_network.assert_called_once_with(
            2222, 1)
        m_pc.assert_called_once_with(mock_context._plugin_context,
                                     mock_context.current['id'],
                                     resources.PORT,
                                     'GENERICSWITCH')

    @mock.patch.object(provisioning_blocks, 'provisioning_complete')
    def test_update_port_postcommit_with_different_physnet(self, m_pc, m_list):
        driver = gsm.GenericSwitchDriver()
        driver.initialize()
        mock_context = mock.create_autospec(driver_context.PortContext)
        mock_context._plugin_context = mock.MagicMock()
        mock_context.current = {'binding:profile':
                                {'local_link_information':
                                    [
                                        {
                                            'switch_info': 'foo',
                                            'port_id': 2222
                                        }
                                    ]
                                 },
                                'binding:vnic_type': 'baremetal',
                                'id': '123',
                                'binding:vif_type': 'other',
                                'status': 'DOWN'}
        mock_context.original = {'binding:profile': {},
                                 'binding:vnic_type': 'baremetal',
                                 'id': '123',
                                 'binding:vif_type': 'unbound'}
        mock_context.network.current = {
            'provider:physical_network': 'physnet1'
        }
        self.switch_mock._get_physical_networks.return_value = ['physnet2']

        driver.update_port_postcommit(mock_context)
        self.switch_mock.plug_port_to_network.assert_not_called()
        m_pc.assert_not_called()

    @mock.patch.object(provisioning_blocks, 'provisioning_complete')
    def test_update_port_postcommit_unbind_not_bound(self, m_pc, m_list):
        driver = gsm.GenericSwitchDriver()
        driver.initialize()
        mock_context = mock.create_autospec(driver_context.PortContext)
        mock_context._plugin_context = mock.MagicMock()
        mock_context.current = {'binding:profile': {},
                                'binding:vnic_type': 'baremetal',
                                'id': '123',
                                'binding:vif_type': 'unbound'}
        mock_context.original = {'binding:profile': {},
                                 'binding:vnic_type': 'baremetal',
                                 'id': '123',
                                 'binding:vif_type': 'unbound'}

        driver.update_port_postcommit(mock_context)
        self.switch_mock.delete_port.assert_not_called()
        m_pc.assert_not_called()

    @mock.patch.object(provisioning_blocks, 'provisioning_complete')
    def test_update_port_postcommit_unbind_not_baremetal(self, m_pc, m_list):
        driver = gsm.GenericSwitchDriver()
        driver.initialize()
        mock_context = mock.create_autospec(driver_context.PortContext)
        mock_context._plugin_context = mock.MagicMock()
        mock_context.current = {'binding:profile': {},
                                'binding:vnic_type': 'mcvtap',
                                'id': '123',
                                'binding:vif_type': 'unbound'}
        mock_context.original = {'binding:profile':
                                 {'local_link_information':
                                     [
                                         {
                                             'switch_info': 'foo',
                                             'port_id': 2222
                                         }
                                     ]
                                  },
                                 'binding:vnic_type': 'mcvtap',
                                 'id': '123',
                                 'binding:vif_type': 'other'}

        driver.update_port_postcommit(mock_context)
        self.switch_mock.delete_port.assert_not_called()
        m_pc.assert_not_called()

    @mock.patch.object(provisioning_blocks, 'provisioning_complete')
    def test_update_port_postcommit_unbind_no_llc(self, m_pc, m_list):
        driver = gsm.GenericSwitchDriver()
        driver.initialize()
        mock_context = mock.create_autospec(driver_context.PortContext)
        mock_context._plugin_context = mock.MagicMock()
        mock_context.current = {'binding:profile': {},
                                'binding:vnic_type': 'baremetal',
                                'id': '123',
                                'binding:vif_type': 'unbound'}
        mock_context.original = {'binding:profile': {},
                                 'binding:vnic_type': 'baremetal',
                                 'id': '123',
                                 'binding:vif_type': 'other'}

        driver.update_port_postcommit(mock_context)
        self.switch_mock.delete_port.assert_not_called()
        m_pc.assert_not_called()

    @mock.patch.object(provisioning_blocks, 'provisioning_complete')
    def test_update_port_postcommit_unbind_not_managed_by_ngs(self, m_pc,
                                                              m_list):
        driver = gsm.GenericSwitchDriver()
        driver.initialize()
        mock_context = mock.create_autospec(driver_context.PortContext)
        mock_context._plugin_context = mock.MagicMock()
        mock_context.current = {'binding:profile': {},
                                'binding:vnic_type': 'baremetal',
                                'id': '123',
                                'binding:vif_type': 'unbound'}
        mock_context.original = {'binding:profile':
                                 {'local_link_information':
                                     [
                                         {
                                             'switch_info': 'ughh',
                                             'port_id': 2222
                                         }
                                     ]
                                  },
                                 'binding:vnic_type': 'baremetal',
                                 'id': '123',
                                 'binding:vif_type': 'other'}

        driver.update_port_postcommit(mock_context)
        self.switch_mock.delete_port.assert_not_called()
        m_pc.assert_not_called()

    @mock.patch.object(provisioning_blocks, 'provisioning_complete')
    def test_update_port_postcommit_unbind(self, m_pc, m_list):
        driver = gsm.GenericSwitchDriver()
        driver.initialize()
        mock_context = mock.create_autospec(driver_context.PortContext)
        mock_context._plugin_context = mock.MagicMock()
        mock_context.current = {'binding:profile': {},
                                'binding:vnic_type': 'baremetal',
                                'id': '123',
                                'binding:vif_type': 'unbound'}
        mock_context.original = {'binding:profile':
                                 {'local_link_information':
                                     [
                                         {
                                             'switch_info': 'foo',
                                             'port_id': 2222
                                         }
                                     ]
                                  },
                                 'binding:vnic_type': 'baremetal',
                                 'id': '123',
                                 'binding:vif_type': 'other'}
        mock_context.network = mock.Mock()
        mock_context.network.current = {'provider:segmentation_id': 123,
                                        'id': 'aaaa-bbbb-cccc'}
        mock_context.segments_to_bind = [mock_context.network.current]

        driver.update_port_postcommit(mock_context)
        self.switch_mock.delete_port.assert_called_once_with(2222, 123)
        m_pc.assert_not_called()

    @mock.patch.object(provisioning_blocks, 'provisioning_complete')
    def test_update_portgroup_postcommit_unbind(self, m_pc, m_list):
        driver = gsm.GenericSwitchDriver()
        driver.initialize()
        mock_context = mock.create_autospec(driver_context.PortContext)
        mock_context._plugin_context = mock.MagicMock()
        mock_context.current = {'binding:profile': {},
                                'binding:vnic_type': 'baremetal',
                                'id': '123',
                                'binding:vif_type': 'unbound'}
        mock_context.original = {'binding:profile':
                                 {'local_link_information':
                                     [
                                         {
                                             'switch_info': 'foo',
                                             'port_id': 2222
                                         },
                                         {
                                             'switch_info': 'foo',
                                             'port_id': 3333
                                         },
                                     ]
                                  },
                                 'binding:vnic_type': 'baremetal',
                                 'id': '123',
                                 'binding:vif_type': 'other'}
        mock_context.network = mock.Mock()
        mock_context.network.current = {'provider:segmentation_id': 123,
                                        'id': 'aaaa-bbbb-cccc'}
        mock_context.segments_to_bind = [mock_context.network.current]

        driver.update_port_postcommit(mock_context)
        self.switch_mock.delete_port.assert_has_calls(
            [mock.call(2222, 123),
             mock.call(3333, 123)])
        m_pc.assert_not_called()

    @mock.patch.object(provisioning_blocks, 'add_provisioning_component')
    def test_bind_port(self, m_apc, m_list):
        driver = gsm.GenericSwitchDriver()
        driver.initialize()
        mock_context = mock.create_autospec(driver_context.PortContext)
        mock_context._plugin_context = mock.MagicMock()
        mock_context.current = {'binding:profile':
                                {'local_link_information':
                                    [
                                        {
                                            'switch_info': 'foo',
                                            'port_id': 2222
                                        }
                                    ]
                                 },
                                'binding:vnic_type': 'baremetal',
                                'id': '123'}
        mock_context.network.current = {
            'provider:physical_network': 'physnet1'
        }
        mock_context.segments_to_bind = [
            {
                'segmentation_id': None,
                'id': 123
            }
        ]

        driver.bind_port(mock_context)
        mock_context.set_binding.assert_called_with(123, 'other', {})
        m_apc.assert_called_once_with(mock_context._plugin_context,
                                      mock_context.current['id'],
                                      resources.PORT,
                                      'GENERICSWITCH')
        self.switch_mock.plug_port_to_network.assert_not_called()

    @mock.patch.object(provisioning_blocks, 'add_provisioning_component')
    def test_bind_portgroup(self, m_apc, m_list):
        driver = gsm.GenericSwitchDriver()
        driver.initialize()
        mock_context = mock.create_autospec(driver_context.PortContext)
        mock_context._plugin_context = mock.MagicMock()
        mock_context.current = {'binding:profile':
                                {'local_link_information':
                                    [
                                        {
                                            'switch_info': 'foo',
                                            'port_id': 2222
                                        },
                                        {
                                            'switch_info': 'foo',
                                            'port_id': 3333
                                        },
                                    ]
                                 },
                                'binding:vnic_type': 'baremetal',
                                'id': '123'}
        mock_context.network.current = {
            'provider:physical_network': 'physnet1'
        }
        mock_context.segments_to_bind = [
            {
                'segmentation_id': None,
                'id': 123
            }
        ]

        driver.bind_port(mock_context)
        mock_context.set_binding.assert_has_calls(
            [mock.call(123, 'other', {})]
        )
        m_apc.assert_has_calls([mock.call(mock_context._plugin_context,
                                          mock_context.current['id'],
                                          resources.PORT,
                                          'GENERICSWITCH')])
        self.switch_mock.plug_port_to_network.assert_not_called()

    @mock.patch.object(provisioning_blocks, 'add_provisioning_component')
    def test_bind_portgroup_802_3ad(self, m_apc, m_list):
        driver = gsm.GenericSwitchDriver()
        driver.initialize()
        mock_context = mock.create_autospec(driver_context.PortContext)
        mock_context._plugin_context = mock.MagicMock()
        mock_context.current = {'binding:profile':
                                {'local_link_information':
                                    [
                                        {
                                            'switch_info': 'foo',
                                            'port_id': 2222
                                        },
                                        {
                                            'switch_info': 'foo',
                                            'port_id': 3333
                                        },
                                    ],
                                 'local_group_information':
                                    {
                                        'bond_mode': '802.3ad'
                                    }
                                 },
                                'binding:vnic_type': 'baremetal',
                                'id': '123'}
        mock_context.network.current = {
            'provider:physical_network': 'physnet1'
        }
        mock_context.segments_to_bind = [
            {
                'segmentation_id': None,
                'id': 123
            }
        ]

        driver.bind_port(mock_context)
        mock_context.set_binding.assert_has_calls(
            [mock.call(123, 'other', {})]
        )
        m_apc.assert_has_calls([mock.call(mock_context._plugin_context,
                                          mock_context.current['id'],
                                          resources.PORT,
                                          'GENERICSWITCH')])
        self.switch_mock.plug_port_to_network.assert_not_called()
        self.switch_mock.plug_bond_to_network.assert_not_called()

    @mock.patch.object(provisioning_blocks, 'add_provisioning_component')
    def test_bind_port_with_physnet(self, m_apc, m_list):
        driver = gsm.GenericSwitchDriver()
        driver.initialize()
        mock_context = mock.create_autospec(driver_context.PortContext)
        mock_context._plugin_context = mock.MagicMock()
        mock_context.current = {'binding:profile':
                                {'local_link_information':
                                    [
                                        {
                                            'switch_info': 'foo',
                                            'port_id': 2222
                                        }
                                    ]
                                 },
                                'binding:vnic_type': 'baremetal',
                                'id': '123'}
        mock_context.network.current = {
            'provider:physical_network': 'physnet1'
        }
        mock_context.segments_to_bind = [
            {
                'segmentation_id': None,
                'id': 123
            }
        ]
        self.switch_mock._get_physical_networks.return_value = ['physnet1']

        driver.bind_port(mock_context)
        mock_context.set_binding.assert_called_with(123, 'other', {})
        m_apc.assert_called_once_with(mock_context._plugin_context,
                                      mock_context.current['id'],
                                      resources.PORT,
                                      'GENERICSWITCH')
        self.switch_mock.plug_port_to_network.assert_not_called()

    @mock.patch.object(provisioning_blocks, 'add_provisioning_component')
    def test_bind_port_unknown_switch(self, m_apc, m_list):
        driver = gsm.GenericSwitchDriver()
        driver.initialize()
        mock_context = mock.create_autospec(driver_context.PortContext)
        mock_context._plugin_context = mock.MagicMock()
        mock_context.current = {'binding:profile':
                                {'local_link_information':
                                    [
                                        {
                                            'switch_info': 'bar',
                                            'port_id': 2222
                                        }
                                    ]
                                 },
                                'binding:vnic_type': 'baremetal',
                                'id': '123'}
        mock_context.network.current = {
            'provider:physical_network': 'physnet1'
        }
        mock_context.segments_to_bind = [
            {
                'segmentation_id': None,
                'id': 123
            }
        ]
        self.assertIsNone(driver.bind_port(mock_context))
        self.assertFalse(mock_context.set_binding.called)
        self.switch_mock.plug_port_to_network.assert_not_called()
        self.assertFalse(m_apc.called)

    @mock.patch.object(provisioning_blocks, 'add_provisioning_component')
    def test_bind_port_with_different_physnet(self, m_apc, m_list):
        driver = gsm.GenericSwitchDriver()
        driver.initialize()
        mock_context = mock.create_autospec(driver_context.PortContext)
        mock_context._plugin_context = mock.MagicMock()
        mock_context.current = {'binding:profile':
                                {'local_link_information':
                                    [
                                        {
                                            'switch_info': 'bar',
                                            'port_id': 2222
                                        }
                                    ]
                                 },
                                'binding:vnic_type': 'baremetal',
                                'id': '123'}
        mock_context.network.current = {
            'provider:physical_network': 'physnet1'
        }
        mock_context.segments_to_bind = [
            {
                'segmentation_id': None,
                'id': 123
            }
        ]
        self.switch_mock._get_physical_networks.return_value = ['physnet2']
        self.assertIsNone(driver.bind_port(mock_context))
        self.assertFalse(mock_context.set_binding.called)
        self.switch_mock.plug_port_to_network.assert_not_called()
        self.assertFalse(m_apc.called)

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
        driver.delete_port_precommit(mock_context)


class TestGenericSwitchDriverStaticMethods(unittest.TestCase):

    def test__is_802_3ad_no_lgi(self):
        driver = gsm.GenericSwitchDriver()
        port = {'binding:profile': {}}
        self.assertFalse(driver._is_802_3ad(port))

    def test__is_802_3ad_no_bond_mode(self):
        driver = gsm.GenericSwitchDriver()
        port = {'binding:profile': {'local_group_information': {}}}
        self.assertFalse(driver._is_802_3ad(port))

    def test__is_802_3ad_wrong_bond_mode(self):
        driver = gsm.GenericSwitchDriver()
        port = {'binding:profile': {'local_group_information':
                {'bond_mode': 42}}}
        self.assertFalse(driver._is_802_3ad(port))

    def test__is_802_3ad_numeric(self):
        driver = gsm.GenericSwitchDriver()
        port = {'binding:profile': {'local_group_information':
                {'bond_mode': '4'}}}
        self.assertTrue(driver._is_802_3ad(port))

    def test__is_802_3ad_string(self):
        driver = gsm.GenericSwitchDriver()
        port = {'binding:profile': {'local_group_information':
                {'bond_mode': '802.3ad'}}}
        self.assertTrue(driver._is_802_3ad(port))
