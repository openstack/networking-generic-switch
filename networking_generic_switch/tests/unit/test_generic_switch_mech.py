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
from neutron_lib import constants as const
from neutron_lib.plugins import directory

from networking_generic_switch import devices
from networking_generic_switch.devices import utils as device_utils
from networking_generic_switch import exceptions
from networking_generic_switch import generic_switch_mech as gsm
from networking_generic_switch import utils as ngs_utils


@mock.patch('networking_generic_switch.config.get_devices',
            return_value={'foo': {'device_type': 'bar', 'spam': 'ham',
                                  'ip': 'ip'}}, autospec=True)
class TestGenericSwitchDriver(unittest.TestCase):
    def setUp(self):
        super(TestGenericSwitchDriver, self).setUp()
        devices.DEVICES.clear()
        self.switch_mock = mock.Mock()
        self.switch_mock.config = {'device_type': 'bar', 'spam': 'ham',
                                   'ip': 'ip'}
        self.switch_mock._get_physical_networks.return_value = []
        self.ctxt = mock.MagicMock()
        self.db = mock.MagicMock()
        patcher = mock.patch(
            'networking_generic_switch.devices.device_manager',
            return_value=self.switch_mock, autospec=True)
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

    @mock.patch('networking_generic_switch.generic_switch_mech.LOG',
                autospec=True)
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

    @mock.patch('networking_generic_switch.generic_switch_mech.LOG',
                autospec=True)
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

    @mock.patch('networking_generic_switch.generic_switch_mech.LOG',
                autospec=True)
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

    @mock.patch('networking_generic_switch.generic_switch_mech.LOG',
                autospec=True)
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
        mock_context.bottom_bound_segment = {'segmentation_id': 123,
                                             'physical_network': 'physnet1',
                                             'network_id': 'aaaa-bbbb-ccc'}

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
        mock_context.bottom_bound_segment = {'segmentation_id': 123,
                                             'physical_network': 'physnet1',
                                             'network_id': 'aaaa-bbbb-ccc'}

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
        mock_context.bottom_bound_segment = {'segmentation_id': 123,
                                             'physical_network': 'physnet1',
                                             'network_id': 'aaaa-bbbb-ccc'}

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
        mock_context.bottom_bound_segment = {'segmentation_id': 123,
                                             'physical_network': 'physnet1',
                                             'network_id': 'aaaa-bbbb-ccc'}

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
        mock_context.bottom_bound_segment = {'segmentation_id': None,
                                             'physical_network': 'physnet1',
                                             'network_id': 'aaaa-bbbb-cccc'}

        driver.delete_port_postcommit(mock_context)
        self.switch_mock.delete_port.assert_called_once_with(
            '2222', 1)

    @mock.patch.object(provisioning_blocks, 'provisioning_complete',
                       autospec=True)
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

    @mock.patch.object(provisioning_blocks, 'provisioning_complete',
                       autospec=True)
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

    @mock.patch.object(provisioning_blocks, 'provisioning_complete',
                       autospec=True)
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

    @mock.patch.object(provisioning_blocks, 'provisioning_complete',
                       autospec=True)
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

    @mock.patch.object(provisioning_blocks, 'provisioning_complete',
                       autospec=True)
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
        mock_context.bottom_bound_segment = {'segmentation_id': 42,
                                             'physical_network': 'physnet1',
                                             'network_id': 'aaaa-bbbb-ccc'}
        driver.update_port_postcommit(mock_context)
        self.switch_mock.plug_port_to_network.assert_called_once_with(
            2222, 42)
        m_pc.assert_called_once_with(mock_context._plugin_context,
                                     mock_context.current['id'],
                                     resources.PORT,
                                     'GENERICSWITCH')

    @mock.patch.object(provisioning_blocks, 'provisioning_complete',
                       autospec=True)
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
        mock_context.bottom_bound_segment = {'segmentation_id': 42,
                                             'physical_network': 'physnet1',
                                             'network_id': 'aaaa-bbbb-ccc'}
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

    @mock.patch.object(provisioning_blocks, 'provisioning_complete',
                       autospec=True)
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
        mock_context.bottom_bound_segment = {'segmentation_id': 42,
                                             'physical_network': 'physnet1',
                                             'network_id': 'aaaa-bbbb-ccc'}
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

    @mock.patch.object(provisioning_blocks, 'provisioning_complete',
                       autospec=True)
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
        mock_context.bottom_bound_segment = {'physical_network': 'physnet1'}
        self.switch_mock._get_physical_networks.return_value = ['physnet1']

        driver.update_port_postcommit(mock_context)
        self.switch_mock.plug_port_to_network.assert_called_once_with(
            2222, 1)
        m_pc.assert_called_once_with(mock_context._plugin_context,
                                     mock_context.current['id'],
                                     resources.PORT,
                                     'GENERICSWITCH')

    @mock.patch.object(provisioning_blocks, 'provisioning_complete',
                       autospec=True)
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
        mock_context.bottom_bound_segment = {'physical_network': 'physnet1'}
        self.switch_mock._get_physical_networks.return_value = ['physnet2']

        driver.update_port_postcommit(mock_context)
        self.switch_mock.plug_port_to_network.assert_not_called()
        m_pc.assert_not_called()

    @mock.patch.object(provisioning_blocks, 'provisioning_complete',
                       autospec=True)
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

    @mock.patch.object(provisioning_blocks, 'provisioning_complete',
                       autospec=True)
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

    @mock.patch.object(provisioning_blocks, 'provisioning_complete',
                       autospec=True)
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

    @mock.patch.object(provisioning_blocks, 'provisioning_complete',
                       autospec=True)
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

    @mock.patch.object(provisioning_blocks, 'provisioning_complete',
                       autospec=True)
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
        mock_context.original_bottom_bound_segment = {
            'segmentation_id': 123,
            'physical_network': 'physnet1',
            'network_id': 'aaaa-bbbb-ccc'
        }

        driver.update_port_postcommit(mock_context)
        self.switch_mock.delete_port.assert_called_once_with(2222, 123)
        m_pc.assert_not_called()

    @mock.patch.object(provisioning_blocks, 'provisioning_complete',
                       autospec=True)
    def test_update_port_postcommit_trunk_not_supported(self, m_pc, m_list):
        driver = gsm.GenericSwitchDriver()
        driver.initialize()
        mock_context = mock.create_autospec(driver_context.PortContext)
        mock_context._plugin_context = mock.MagicMock()
        mock_context._plugin = mock.MagicMock()
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
                                'status': 'DOWN',
                                'trunk_details': {
                                    'sub_ports': [
                                        {'segmentation_id': 1234,
                                         'port_id': 's1'}
                                    ]
                                }}
        mock_context.original = {'binding:profile': {},
                                 'binding:vnic_type': 'baremetal',
                                 'id': '123',
                                 'binding:vif_type': 'unbound'}

        mock_context.bottom_bound_segment = {'physical_network': 'physnet1',
                                             'network_id': 'aaaa-bbbb-ccc',
                                             'segmentation_id': 123}
        self.switch_mock._get_physical_networks.return_value = ['physnet1']
        self.switch_mock.support_trunk_on_bond_ports = False
        self.switch_mock.support_trunk_on_ports = False

        exception_regex = (
            'Requested feature trunks is not supported by '
            'networking-generic-switch on the .*. Trunks are not supported on '
            'ports.')
        with self.assertRaisesRegex(exceptions.GenericSwitchNotSupported,
                                    exception_regex):
            driver.update_port_postcommit(mock_context)
        self.switch_mock.plug_port_to_network.assert_not_called()
        m_pc.assert_not_called()

    @mock.patch.object(provisioning_blocks, 'provisioning_complete',
                       autospec=True)
    def test_update_port_postcommit_trunk(self, m_pc, m_list):
        driver = gsm.GenericSwitchDriver()
        driver.initialize()
        mock_context = mock.create_autospec(driver_context.PortContext)
        mock_context._plugin_context = mock.MagicMock()
        mock_context._plugin = mock.MagicMock()
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
                                'status': 'DOWN',
                                'trunk_details': {
                                    'sub_ports': [
                                        {'segmentation_id': 1234,
                                         'port_id': 's1'}
                                    ]
                                }}
        mock_context.original = {'binding:profile': {},
                                 'binding:vnic_type': 'baremetal',
                                 'id': '123',
                                 'binding:vif_type': 'unbound'}
        mock_context.bottom_bound_segment = {'physical_network': 'physnet1',
                                             'network_id': 'aaaa-bbbb-ccc',
                                             'segmentation_id': 123}
        self.switch_mock._get_physical_networks.return_value = ['physnet1']
        self.switch_mock.support_trunk_on_bond_ports = True
        self.switch_mock.support_trunk_on_ports = True

        driver.update_port_postcommit(mock_context)
        self.switch_mock.plug_port_to_network.assert_called_once()
        m_pc.assert_called_once()

    @mock.patch.object(provisioning_blocks, 'provisioning_complete',
                       autospec=True)
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
        mock_context.original_bottom_bound_segment = {
            'segmentation_id': 123,
            'physical_network': 'physnet1',
            'network_id': 'aaaa-bbbb-ccc'
        }

        driver.update_port_postcommit(mock_context)
        self.switch_mock.delete_port.assert_has_calls(
            [mock.call(2222, 123),
             mock.call(3333, 123)])
        m_pc.assert_not_called()

    @mock.patch.object(provisioning_blocks, 'add_provisioning_component',
                       autospec=True)
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
        mock_context.segments_to_bind = [
            {
                'segmentation_id': None,
                'id': 123,
                'physical_network': 'physnet1'
            }
        ]

        driver.bind_port(mock_context)
        mock_context.set_binding.assert_called_with(123, 'other', {})
        m_apc.assert_called_once_with(mock_context._plugin_context,
                                      mock_context.current['id'],
                                      resources.PORT,
                                      'GENERICSWITCH')
        self.switch_mock.plug_port_to_network.assert_not_called()

    @mock.patch.object(provisioning_blocks, 'add_provisioning_component',
                       autospec=True)
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
        mock_context.segments_to_bind = [
            {
                'segmentation_id': None,
                'id': 123,
                'physical_network': 'physnet1'
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

    @mock.patch.object(provisioning_blocks, 'add_provisioning_component',
                       autospec=True)
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
        mock_context.segments_to_bind = [
            {
                'segmentation_id': None,
                'id': 123,
                'physical_network': 'physnet1'
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

    @mock.patch.object(provisioning_blocks, 'add_provisioning_component',
                       autospec=True)
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
        mock_context.segments_to_bind = [
            {
                'segmentation_id': None,
                'id': 123,
                'physical_network': 'physnet1'
            }
        ]
        self.switch_mock._get_physical_networks.return_value = ['physnet1']

        driver.bind_port(mock_context)
        mock_context.set_binding.assert_called_with(123, 'other', {})
        m_apc.assert_called_once_with(mock_context._plugin_context,
                                      mock_context.current['id'],
                                      resources.PORT,
                                      'GENERICSWITCH')
        # NOTE(vsaienko): make sure we do not call heavy methods in bind_port
        self.switch_mock.plug_port_to_network.assert_not_called()

    @mock.patch.object(provisioning_blocks, 'add_provisioning_component',
                       autospec=True)
    @mock.patch.object(ngs_utils, 'is_port_supported', autospec=True)
    def test_bind_portgroup_port_not_supported(self, m_ips, m_apc, m_list):
        driver = gsm.GenericSwitchDriver()
        driver.initialize()
        m_ips.return_value = False
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
                                    ]},
                                'binding:vnic_type': 'baremetal',
                                'id': '123'}
        mock_context.segments_to_bind = [
            {
                'segmentation_id': None,
                'id': 123,
                'physical_network': 'physnet1'
            }
        ]

        driver.bind_port(mock_context)
        mock_context.set_binding.assert_not_called()
        m_apc.assert_not_called()
        self.switch_mock.plug_port_to_network.assert_not_called()

    @mock.patch.object(provisioning_blocks, 'add_provisioning_component',
                       autospec=True)
    @mock.patch.object(ngs_utils, 'is_port_supported', autospec=True)
    def test_bind_port_with_physnet_port_not_supported(self, m_ips, m_apc,
                                                       m_list):
        driver = gsm.GenericSwitchDriver()
        driver.initialize()
        m_ips.return_value = False
        mock_context = mock.create_autospec(driver_context.PortContext)
        mock_context._plugin_context = mock.MagicMock()
        mock_context.current = {'binding:profile':
                                {'local_link_information':
                                    [
                                        {
                                            'switch_info': 'foo',
                                            'port_id': 2222
                                        }
                                    ]},
                                'binding:vnic_type': 'baremetal',
                                'id': '123'}
        mock_context.segments_to_bind = [
            {
                'segmentation_id': None,
                'id': 123,
                'physical_network': 'physnet1'
            }
        ]
        self.switch_mock._get_physical_networks.return_value = ['physnet1']

        driver.bind_port(mock_context)
        mock_context.set_binding.assert_not_called()
        m_apc.assert_not_called()
        self.switch_mock.plug_port_to_network.assert_not_called()

    @mock.patch.object(provisioning_blocks, 'add_provisioning_component',
                       autospec=True)
    @mock.patch.object(ngs_utils, 'is_port_supported', autospec=True)
    def test_bind_port_port_not_supported(self, m_ips, m_apc, m_list):
        driver = gsm.GenericSwitchDriver()
        driver.initialize()
        m_ips.return_value = False
        mock_context = mock.create_autospec(driver_context.PortContext)
        mock_context._plugin_context = mock.MagicMock()
        mock_context.current = {'binding:profile':
                                {'local_link_information':
                                    [
                                        {
                                            'switch_info': 'foo',
                                            'port_id': 2222
                                        }
                                    ]},
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
        mock_context.set_binding.assert_not_called()
        m_apc.assert_not_called()
        self.switch_mock.plug_port_to_network.assert_not_called()

    @mock.patch.object(provisioning_blocks, 'add_provisioning_component',
                       autospec=True)
    @mock.patch.object(ngs_utils, 'is_port_supported', autospec=True)
    def test_bind_portgroup_802_3ad_port_not_supported(self, m_ips, m_apc,
                                                       m_list):
        driver = gsm.GenericSwitchDriver()
        driver.initialize()
        m_ips.return_value = False
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
                                    }},
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
        mock_context.set_binding.assert_not_called()
        m_apc.assert_not_called()
        self.switch_mock.plug_port_to_network.assert_not_called()
        self.switch_mock.plug_bond_to_network.assert_not_called()

    @mock.patch.object(provisioning_blocks, 'add_provisioning_component',
                       autospec=True)
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
                                    ]},
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

    @mock.patch.object(provisioning_blocks, 'add_provisioning_component',
                       autospec=True)
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
                                    ]},
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

    @mock.patch.object(directory, "get_plugin", autospec=True)
    @mock.patch.object(device_utils, "get_switch_device", autospec=True)
    def test_subports_added_other_port(self, mock_get_switch, mock_plugin,
                                       m_list):
        driver = gsm.GenericSwitchDriver()
        driver.initialize()

        parent_port = {
            'binding:profile': {
                'local_link_information': [
                    {
                        'switch_info': 'bar',
                        'port_id': 2222
                    }
                ]},
            'binding:vnic_type': 'baremetal',
            'id': '123'
        }
        subports = [{"segmentation_id": "tag1", "port_id": "s1"},
                    {"segmentation_id": "tag2", "port_id": "s2"}]

        mock_plugin.return_value = mock.MagicMock()
        mock_plugin.return_value.get_port.return_value = {"status": "DOWN"}

        driver.subports_added(self.ctxt, parent_port, subports=subports)
        mock_get_switch.return_value.add_subports_on_trunk.assart_not_called()

    @mock.patch.object(device_utils, "get_switch_device", autospec=True)
    def test_subports_added_no_llc(self, mock_get_switch, m_list):
        driver = gsm.GenericSwitchDriver()
        driver.initialize()

        parent_port = {
            'binding:profile': {},
            'binding:vnic_type': 'baremetal',
            'id': '123'
        }
        subports = [{"segmentation_id": "tag1"},
                    {"segmentation_id": "tag2"}]

        driver.subports_added(self.ctxt, parent_port, subports=subports)
        mock_get_switch.return_value.add_subports_on_trunk.assart_not_called()

    @mock.patch.object(directory, "get_plugin", autospec=True)
    @mock.patch.object(device_utils, "get_switch_device", autospec=True)
    def test_subports_added(self, mock_get_switch, mock_plugin, m_list):
        """Verify subports_added configures switch and updates status.

        Regression test for bug #2103760.
        """
        driver = gsm.GenericSwitchDriver()
        driver.initialize()

        parent_port = {
            'binding:profile': {
                'local_link_information': [
                    {
                        'switch_info': 'bar',
                        'port_id': 2222
                    }
                ]},
            'binding:vnic_type': 'baremetal',
            'id': '123'
        }
        subports = [{"segmentation_id": "tag1", "port_id": "s1"},
                    {"segmentation_id": "tag2", "port_id": "s2"}]

        mock_plugin.return_value = mock.MagicMock()
        mock_plugin.return_value.get_port.return_value = {"status": "DOWN"}

        driver.subports_added(self.ctxt, parent_port, subports=subports)

        # Verify switch configuration was called
        mock_get_switch.return_value.add_subports_on_trunk.assert_has_calls(
            [mock.call(parent_port['binding:profile'], 2222, subports)])

        # Verify status was updated for each subport
        self.assertEqual(
            mock_plugin.return_value.update_port_status.call_count, 2)
        mock_plugin.return_value.update_port_status.assert_any_call(
            self.ctxt, "s1", const.PORT_STATUS_ACTIVE)
        mock_plugin.return_value.update_port_status.assert_any_call(
            self.ctxt, "s2", const.PORT_STATUS_ACTIVE)

    @mock.patch.object(directory, "get_plugin", autospec=True)
    @mock.patch.object(device_utils, "get_switch_device", autospec=True)
    def test_subports_deleted_other_port(self, mock_get_switch, mock_plugin,
                                         m_list):
        driver = gsm.GenericSwitchDriver()
        driver.initialize()

        parent_port = {
            'binding:profile': {
                'local_link_information': [
                    {
                        'switch_info': 'bar',
                        'port_id': 2222
                    }
                ]},
            'binding:vnic_type': 'baremetal',
            'id': '123'
        }
        subports = [{"segmentation_id": "tag1", "port_id": "s1"},
                    {"segmentation_id": "tag2", "port_id": "s2"}]

        driver.subports_deleted(self.ctxt, parent_port, subports=subports)
        mock_get_switch.return_value.del_subports_on_trunk.assart_not_called()

    @mock.patch.object(device_utils, "get_switch_device", autospec=True)
    def test_subports_deleted_no_llc(self, mock_get_switch, m_list):
        driver = gsm.GenericSwitchDriver()
        driver.initialize()

        parent_port = {
            'binding:profile': {},
            'binding:vnic_type': 'baremetal',
            'id': '123'
        }
        subports = [{"segmentation_id": "tag1"},
                    {"segmentation_id": "tag2"}]

        driver.subports_deleted(self.ctxt, parent_port, subports=subports)
        mock_get_switch.return_value.del_subports_on_trunk.assart_not_called()

    @mock.patch.object(directory, "get_plugin", autospec=True)
    @mock.patch.object(device_utils, "get_switch_device", autospec=True)
    def test_subports_deleted(self, mock_get_switch, mock_plugin, m_list):
        driver = gsm.GenericSwitchDriver()
        driver.initialize()

        parent_port = {
            'binding:profile': {
                'local_link_information': [
                    {
                        'switch_info': 'bar',
                        'port_id': 2222
                    }
                ]},
            'binding:vnic_type': 'baremetal',
            'id': '123'
        }
        subports = [{"segmentation_id": "tag1", "port_id": "s1"},
                    {"segmentation_id": "tag2", "port_id": "s2"}]

        driver.subports_deleted(self.ctxt, parent_port, subports=subports)
        mock_get_switch.return_value.del_subports_on_trunk.assert_has_calls(
            [mock.call(parent_port['binding:profile'], 2222, subports)])

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

    @mock.patch.object(provisioning_blocks, 'provisioning_complete',
                       autospec=True)
    def test_update_port_postcommit_l2vni_plug(self, m_pc, m_list):
        """Test L2VNI configuration on port plug with VXLAN+VLAN segments."""
        driver = gsm.GenericSwitchDriver()
        driver.initialize()
        # Mock switch supports L2VNI
        self.switch_mock.PLUG_SWITCH_TO_NETWORK = ['mock', 'commands']
        self.switch_mock.vlan_has_vni.return_value = False

        mock_context = mock.create_autospec(driver_context.PortContext)
        mock_context._plugin_context = mock.MagicMock()
        mock_context.current = {
            'binding:profile': {
                'local_link_information': [
                    {'switch_info': 'foo', 'port_id': 2222}
                ]
            },
            'binding:vnic_type': 'baremetal',
            'id': '123',
            'binding:vif_type': 'other',
            'status': 'DOWN'
        }
        mock_context.original = {
            'binding:profile': {},
            'binding:vnic_type': 'baremetal',
            'id': '123',
            'binding:vif_type': 'unbound'
        }
        # Bottom segment is VLAN
        mock_context.bottom_bound_segment = {
            'segmentation_id': 100,
            'network_type': 'vlan',
            'physical_network': 'physnet1',
            'network_id': 'aaaa-bbbb-ccc'
        }
        # Top segment is VXLAN
        mock_context.top_bound_segment = {
            'segmentation_id': 5000,
            'network_type': 'vxlan',
            'network_id': 'aaaa-bbbb-ccc'
        }

        driver.update_port_postcommit(mock_context)

        # Verify VNI was checked and configured with physnet
        self.switch_mock.vlan_has_vni.assert_called_once_with(100, 5000)
        self.switch_mock.plug_switch_to_network.assert_called_once_with(
            5000, 100, physnet='physnet1')
        self.switch_mock.plug_port_to_network.assert_called_once_with(
            2222, 100)

    @mock.patch.object(provisioning_blocks, 'provisioning_complete',
                       autospec=True)
    def test_update_port_postcommit_l2vni_unsupported_switch(self,
                                                             m_pc, m_list):
        """Test L2VNI with unsupported switch logs warning."""
        driver = gsm.GenericSwitchDriver()
        driver.initialize()
        # Mock switch does NOT support L2VNI
        self.switch_mock.PLUG_SWITCH_TO_NETWORK = None

        mock_context = mock.create_autospec(driver_context.PortContext)
        mock_context._plugin_context = mock.MagicMock()
        mock_context.current = {
            'binding:profile': {
                'local_link_information': [
                    {'switch_info': 'foo', 'port_id': 2222}
                ]
            },
            'binding:vnic_type': 'baremetal',
            'id': '123',
            'binding:vif_type': 'other',
            'status': 'DOWN'
        }
        mock_context.original = {
            'binding:profile': {},
            'binding:vnic_type': 'baremetal',
            'id': '123',
            'binding:vif_type': 'unbound'
        }
        mock_context.bottom_bound_segment = {
            'segmentation_id': 100,
            'network_type': 'vlan',
            'physical_network': 'physnet1',
            'network_id': 'aaaa-bbbb-ccc'
        }
        mock_context.top_bound_segment = {
            'segmentation_id': 5000,
            'network_type': 'vxlan',
            'network_id': 'aaaa-bbbb-ccc'
        }

        driver.update_port_postcommit(mock_context)

        # Verify VNI was NOT configured
        self.switch_mock.plug_switch_to_network.assert_not_called()
        # But port was still plugged
        self.switch_mock.plug_port_to_network.assert_called_once_with(
            2222, 100)

    @mock.patch.object(provisioning_blocks, 'provisioning_complete',
                       autospec=True)
    def test_update_port_postcommit_l2vni_already_configured(self,
                                                             m_pc, m_list):
        """Test L2VNI idempotency when VNI already configured."""
        driver = gsm.GenericSwitchDriver()
        driver.initialize()
        self.switch_mock.PLUG_SWITCH_TO_NETWORK = ['mock', 'commands']
        # VNI already configured
        self.switch_mock.vlan_has_vni.return_value = True

        mock_context = mock.create_autospec(driver_context.PortContext)
        mock_context._plugin_context = mock.MagicMock()
        mock_context.current = {
            'binding:profile': {
                'local_link_information': [
                    {'switch_info': 'foo', 'port_id': 2222}
                ]
            },
            'binding:vnic_type': 'baremetal',
            'id': '123',
            'binding:vif_type': 'other',
            'status': 'DOWN'
        }
        mock_context.original = {
            'binding:profile': {},
            'binding:vnic_type': 'baremetal',
            'id': '123',
            'binding:vif_type': 'unbound'
        }
        mock_context.bottom_bound_segment = {
            'segmentation_id': 100,
            'network_type': 'vlan',
            'physical_network': 'physnet1',
            'network_id': 'aaaa-bbbb-ccc'
        }
        mock_context.top_bound_segment = {
            'segmentation_id': 5000,
            'network_type': 'vxlan',
            'network_id': 'aaaa-bbbb-ccc'
        }

        driver.update_port_postcommit(mock_context)

        # Verify VNI configuration was skipped (idempotent)
        self.switch_mock.vlan_has_vni.assert_called_once_with(100, 5000)
        self.switch_mock.plug_switch_to_network.assert_not_called()

    @mock.patch('networking_generic_switch.generic_switch_mech.segments_db',
                autospec=True)
    def test_delete_port_postcommit_l2vni_with_remaining_ports(
            self, mock_segments_db, m_list):
        """Test L2VNI cleanup when segment exists and VLAN has ports."""
        driver = gsm.GenericSwitchDriver()
        driver.initialize()

        # Segment exists in Neutron
        mock_segments_db.get_network_segments.return_value = [{
            'network_type': 'vlan',
            'segmentation_id': 100,
            'physical_network': 'physnet1',
            'network_id': 'aaaa-bbbb-ccc'
        }]
        # VLAN still has other ports on this switch
        self.switch_mock.vlan_has_ports.return_value = True

        mock_context = mock.create_autospec(driver_context.PortContext)
        mock_context.current = {
            'binding:profile': {
                'local_link_information': [
                    {'switch_info': 'foo', 'port_id': 2222}
                ]
            },
            'binding:vnic_type': 'baremetal',
            'id': '123',
            'binding:vif_type': 'other'
        }
        mock_context.bottom_bound_segment = {
            'segmentation_id': 100,
            'network_type': 'vlan',
            'physical_network': 'physnet1',
            'network_id': 'aaaa-bbbb-ccc'
        }
        mock_context.top_bound_segment = {
            'segmentation_id': 5000,
            'network_type': 'vxlan',
            'network_id': 'aaaa-bbbb-ccc'
        }

        driver.delete_port_postcommit(mock_context)

        # Verify port was unplugged
        self.switch_mock.delete_port.assert_called_once_with(2222, 100)
        # Verify segment was queried
        mock_segments_db.get_network_segments.assert_called_once_with(
            mock_context.plugin_context, 'aaaa-bbbb-ccc', filter_dynamic=None)
        # Verify VNI was NOT removed (segment exists and ports remain)
        self.switch_mock.vlan_has_ports.assert_called_once_with(100)
        self.switch_mock.unplug_switch_from_network.assert_not_called()

    @mock.patch('networking_generic_switch.generic_switch_mech.segments_db',
                autospec=True)
    def test_delete_port_postcommit_l2vni_no_ports_remaining(
            self, mock_segments_db, m_list):
        """Test L2VNI cleanup when segment exists but no ports on switch."""
        driver = gsm.GenericSwitchDriver()
        driver.initialize()

        # Segment exists in Neutron
        mock_segments_db.get_network_segments.return_value = [{
            'network_type': 'vlan',
            'segmentation_id': 100,
            'physical_network': 'physnet1',
            'network_id': 'aaaa-bbbb-ccc'
        }]
        # No ports remaining on this switch's VLAN
        self.switch_mock.vlan_has_ports.return_value = False

        mock_context = mock.create_autospec(driver_context.PortContext)
        mock_context.current = {
            'binding:profile': {
                'local_link_information': [
                    {'switch_info': 'foo', 'port_id': 2222}
                ]
            },
            'binding:vnic_type': 'baremetal',
            'id': '123',
            'binding:vif_type': 'other'
        }
        mock_context.bottom_bound_segment = {
            'segmentation_id': 100,
            'network_type': 'vlan',
            'physical_network': 'physnet1',
            'network_id': 'aaaa-bbbb-ccc'
        }
        mock_context.top_bound_segment = {
            'segmentation_id': 5000,
            'network_type': 'vxlan',
            'network_id': 'aaaa-bbbb-ccc'
        }

        driver.delete_port_postcommit(mock_context)

        # Verify port was unplugged
        self.switch_mock.delete_port.assert_called_once_with(2222, 100)
        # Verify segment was queried
        mock_segments_db.get_network_segments.assert_called_once_with(
            mock_context.plugin_context, 'aaaa-bbbb-ccc', filter_dynamic=None)
        # Verify VNI was removed (segment exists but no ports on this switch)
        self.switch_mock.vlan_has_ports.assert_called_once_with(100)
        self.switch_mock.unplug_switch_from_network.assert_called_once_with(
            5000, 100, physnet='physnet1')

    @mock.patch('networking_generic_switch.generic_switch_mech.segments_db',
                autospec=True)
    def test_delete_port_postcommit_l2vni_segment_deleted_with_ports(
            self, mock_segments_db, m_list):
        """Test L2VNI cleanup when segment deleted (unconditional cleanup)."""
        driver = gsm.GenericSwitchDriver()
        driver.initialize()

        # Segment does NOT exist in Neutron (was deleted)
        mock_segments_db.get_network_segments.return_value = []
        # Even though VLAN has ports, cleanup should happen
        self.switch_mock.vlan_has_ports.return_value = True

        mock_context = mock.create_autospec(driver_context.PortContext)
        mock_context.current = {
            'binding:profile': {
                'local_link_information': [
                    {'switch_info': 'foo', 'port_id': 2222}
                ]
            },
            'binding:vnic_type': 'baremetal',
            'id': '123',
            'binding:vif_type': 'other'
        }
        mock_context.bottom_bound_segment = {
            'segmentation_id': 100,
            'network_type': 'vlan',
            'physical_network': 'physnet1',
            'network_id': 'aaaa-bbbb-ccc'
        }
        mock_context.top_bound_segment = {
            'segmentation_id': 5000,
            'network_type': 'vxlan',
            'network_id': 'aaaa-bbbb-ccc'
        }

        driver.delete_port_postcommit(mock_context)

        # Verify port was unplugged
        self.switch_mock.delete_port.assert_called_once_with(2222, 100)
        # Verify segment was queried
        mock_segments_db.get_network_segments.assert_called_once_with(
            mock_context.plugin_context, 'aaaa-bbbb-ccc', filter_dynamic=None)
        # Verify VNI was removed unconditionally (segment deleted)
        # Port check should NOT have been called
        self.switch_mock.vlan_has_ports.assert_not_called()
        self.switch_mock.unplug_switch_from_network.assert_called_once_with(
            5000, 100, physnet='physnet1')

    @mock.patch('networking_generic_switch.generic_switch_mech.segments_db',
                autospec=True)
    def test_delete_port_postcommit_l2vni_segment_deleted_no_ports(
            self, mock_segments_db, m_list):
        """Test L2VNI cleanup when segment deleted and no ports."""
        driver = gsm.GenericSwitchDriver()
        driver.initialize()

        # Segment does NOT exist in Neutron (was deleted)
        mock_segments_db.get_network_segments.return_value = []
        # No ports on VLAN
        self.switch_mock.vlan_has_ports.return_value = False

        mock_context = mock.create_autospec(driver_context.PortContext)
        mock_context.current = {
            'binding:profile': {
                'local_link_information': [
                    {'switch_info': 'foo', 'port_id': 2222}
                ]
            },
            'binding:vnic_type': 'baremetal',
            'id': '123',
            'binding:vif_type': 'other'
        }
        mock_context.bottom_bound_segment = {
            'segmentation_id': 100,
            'network_type': 'vlan',
            'physical_network': 'physnet1',
            'network_id': 'aaaa-bbbb-ccc'
        }
        mock_context.top_bound_segment = {
            'segmentation_id': 5000,
            'network_type': 'vxlan',
            'network_id': 'aaaa-bbbb-ccc'
        }

        driver.delete_port_postcommit(mock_context)

        # Verify port was unplugged
        self.switch_mock.delete_port.assert_called_once_with(2222, 100)
        # Verify segment was queried
        mock_segments_db.get_network_segments.assert_called_once_with(
            mock_context.plugin_context, 'aaaa-bbbb-ccc', filter_dynamic=None)
        # Verify VNI was removed unconditionally (segment deleted)
        # Port check should NOT have been called
        self.switch_mock.vlan_has_ports.assert_not_called()
        self.switch_mock.unplug_switch_from_network.assert_called_once_with(
            5000, 100, physnet='physnet1')

    @mock.patch('networking_generic_switch.generic_switch_mech.network_obj',
                autospec=True)
    @mock.patch.object(directory, "get_plugin", autospec=True)
    @mock.patch.object(device_utils, "get_switch_device", autospec=True)
    def test_subports_deleted_l2vni_segment_deleted_via_segment_id(
            self, mock_get_switch, mock_plugin, mock_network_obj, m_list):
        """Test L2VNI cleanup uses segment_id for direct lookup."""
        driver = gsm.GenericSwitchDriver()
        driver.initialize()

        parent_port = {
            'binding:profile': {
                'local_link_information': [
                    {'switch_info': 'foo', 'port_id': 2222}
                ]
            },
            'binding:vnic_type': 'baremetal',
            'id': '123'
        }
        subports = [{"segmentation_id": 100, "port_id": "s1"}]

        mock_plugin.return_value = mock.MagicMock()
        # Subport has VNI and segment_id in binding_profile
        subport_s1 = {
            'id': 's1',
            'network_id': 'anchor-network-id',
            'binding:profile': {
                'vni': 5000,
                'physical_network': 'physnet1',
                'segment_id': 'segment-uuid-100'
            }
        }
        mock_plugin.return_value.get_port.return_value = subport_s1

        # Segment does NOT exist (deleted)
        mock_network_obj.NetworkSegment.get_object.return_value = None

        mock_switch = mock.MagicMock()
        mock_switch.PLUG_SWITCH_TO_NETWORK = ['mock', 'commands']
        mock_get_switch.return_value = mock_switch

        driver.subports_deleted(self.ctxt, parent_port, subports=subports)

        # Verify segment was queried directly by ID
        mock_network_obj.NetworkSegment.get_object.assert_called_once_with(
            self.ctxt, id='segment-uuid-100')

        # Verify VNI was removed unconditionally (segment deleted)
        # Port check should NOT have been called
        mock_switch.vlan_has_ports.assert_not_called()
        mock_switch.unplug_switch_from_network.assert_called_once_with(
            5000, 100, physnet='physnet1')

    @mock.patch('networking_generic_switch.generic_switch_mech.network_obj',
                autospec=True)
    @mock.patch.object(directory, "get_plugin", autospec=True)
    @mock.patch.object(device_utils, "get_switch_device", autospec=True)
    def test_subports_deleted_l2vni_segment_exists_via_segment_id(
            self, mock_get_switch, mock_plugin, mock_network_obj, m_list):
        """Test L2VNI cleanup with segment_id when segment exists."""
        driver = gsm.GenericSwitchDriver()
        driver.initialize()

        parent_port = {
            'binding:profile': {
                'local_link_information': [
                    {'switch_info': 'foo', 'port_id': 2222}
                ]
            },
            'binding:vnic_type': 'baremetal',
            'id': '123'
        }
        subports = [{"segmentation_id": 100, "port_id": "s1"}]

        mock_plugin.return_value = mock.MagicMock()
        # Subport has VNI and segment_id in binding_profile
        subport_s1 = {
            'id': 's1',
            'network_id': 'anchor-network-id',
            'binding:profile': {
                'vni': 5000,
                'physical_network': 'physnet1',
                'segment_id': 'segment-uuid-100'
            }
        }
        mock_plugin.return_value.get_port.return_value = subport_s1

        # Segment EXISTS
        mock_segment = mock.MagicMock()
        mock_network_obj.NetworkSegment.get_object.return_value = mock_segment

        # No ports on this switch
        mock_switch = mock.MagicMock()
        mock_switch.PLUG_SWITCH_TO_NETWORK = ['mock', 'commands']
        mock_switch.vlan_has_ports.return_value = False
        mock_get_switch.return_value = mock_switch

        driver.subports_deleted(self.ctxt, parent_port, subports=subports)

        # Verify segment was queried directly by ID
        mock_network_obj.NetworkSegment.get_object.assert_called_once_with(
            self.ctxt, id='segment-uuid-100')

        # Verify port check WAS called (segment exists)
        mock_switch.vlan_has_ports.assert_called_once_with(100)

        # Verify VNI was removed (no ports on this switch)
        mock_switch.unplug_switch_from_network.assert_called_once_with(
            5000, 100, physnet='physnet1')

    @mock.patch.object(provisioning_blocks, 'provisioning_complete',
                       autospec=True)
    def test_update_port_postcommit_l2vni_with_different_physnets(self,
                                                                  m_pc,
                                                                  m_list):
        """Test L2VNI passes correct physnet for different networks."""
        driver = gsm.GenericSwitchDriver()
        driver.initialize()
        self.switch_mock.PLUG_SWITCH_TO_NETWORK = ['mock', 'commands']
        self.switch_mock.vlan_has_vni.return_value = False

        # Test with physnet2
        mock_context = mock.create_autospec(driver_context.PortContext)
        mock_context._plugin_context = mock.MagicMock()
        mock_context.current = {
            'binding:profile': {
                'local_link_information': [
                    {'switch_info': 'foo', 'port_id': 3333}
                ]
            },
            'binding:vnic_type': 'baremetal',
            'id': '456',
            'binding:vif_type': 'other',
            'status': 'DOWN'
        }
        mock_context.original = {
            'binding:profile': {},
            'binding:vnic_type': 'baremetal',
            'id': '456',
            'binding:vif_type': 'unbound'
        }
        mock_context.bottom_bound_segment = {
            'segmentation_id': 200,
            'network_type': 'vlan',
            'physical_network': 'physnet2',
            'network_id': 'dddd-eeee-fff'
        }
        mock_context.top_bound_segment = {
            'segmentation_id': 6000,
            'network_type': 'vxlan',
            'network_id': 'dddd-eeee-fff'
        }

        driver.update_port_postcommit(mock_context)

        # Verify physnet2 was passed
        self.switch_mock.plug_switch_to_network.assert_called_once_with(
            6000, 200, physnet='physnet2')

    @mock.patch.object(provisioning_blocks, 'provisioning_complete',
                       autospec=True)
    def test_update_port_postcommit_l2vni_no_physnet(self, m_pc, m_list):
        """Test L2VNI handles missing physical_network gracefully."""
        driver = gsm.GenericSwitchDriver()
        driver.initialize()
        self.switch_mock.PLUG_SWITCH_TO_NETWORK = ['mock', 'commands']
        self.switch_mock.vlan_has_vni.return_value = False

        mock_context = mock.create_autospec(driver_context.PortContext)
        mock_context._plugin_context = mock.MagicMock()
        mock_context.current = {
            'binding:profile': {
                'local_link_information': [
                    {'switch_info': 'foo', 'port_id': 4444}
                ]
            },
            'binding:vnic_type': 'baremetal',
            'id': '789',
            'binding:vif_type': 'other',
            'status': 'DOWN'
        }
        mock_context.original = {
            'binding:profile': {},
            'binding:vnic_type': 'baremetal',
            'id': '789',
            'binding:vif_type': 'unbound'
        }
        # Bottom segment without physical_network
        mock_context.bottom_bound_segment = {
            'segmentation_id': 300,
            'network_type': 'vlan',
            'network_id': 'gggg-hhhh-iii'
        }
        mock_context.top_bound_segment = {
            'segmentation_id': 7000,
            'network_type': 'vxlan',
            'network_id': 'gggg-hhhh-iii'
        }

        driver.update_port_postcommit(mock_context)

        # Verify physnet=None was passed
        self.switch_mock.plug_switch_to_network.assert_called_once_with(
            7000, 300, physnet=None)

    @mock.patch.object(directory, "get_plugin", autospec=True)
    @mock.patch.object(device_utils, "get_switch_device", autospec=True)
    def test_subports_added_with_l2vni(self, mock_get_switch, mock_plugin,
                                       m_list):
        """Test subports_added configures L2VNI when VNI in binding_profile."""
        driver = gsm.GenericSwitchDriver()
        driver.initialize()

        parent_port = {
            'binding:profile': {
                'local_link_information': [
                    {'switch_info': 'foo', 'port_id': 2222}
                ]
            },
            'binding:vnic_type': 'baremetal',
            'id': '123'
        }
        subports = [
            {"segmentation_id": 100, "port_id": "s1"},
            {"segmentation_id": 200, "port_id": "s2"}
        ]

        mock_plugin.return_value = mock.MagicMock()
        # Subport s1 has VNI in binding_profile
        subport_s1 = {
            'id': 's1',
            'status': 'DOWN',
            'binding:profile': {
                'vni': 5000,
                'physical_network': 'physnet1'
            }
        }
        # Subport s2 has no VNI
        subport_s2 = {
            'id': 's2',
            'status': 'DOWN',
            'binding:profile': {}
        }

        def get_port_side_effect(context, port_id):
            if port_id == 's1':
                return subport_s1
            elif port_id == 's2':
                return subport_s2

        mock_plugin.return_value.get_port.side_effect = get_port_side_effect

        # Mock switch supports L2VNI
        mock_switch = mock.MagicMock()
        mock_switch.PLUG_SWITCH_TO_NETWORK = ['mock', 'commands']
        mock_switch.vlan_has_vni.return_value = False
        mock_get_switch.return_value = mock_switch

        driver.subports_added(self.ctxt, parent_port, subports=subports)

        # Verify VLAN trunking was configured for both subports
        mock_switch.add_subports_on_trunk.assert_called_once_with(
            parent_port['binding:profile'], 2222, subports)

        # Verify L2VNI was configured only for s1 (has VNI)
        mock_switch.vlan_has_vni.assert_called_once_with(100, 5000)
        mock_switch.plug_switch_to_network.assert_called_once_with(
            5000, 100, physnet='physnet1')

        # Verify port status updates
        self.assertEqual(
            mock_plugin.return_value.update_port_status.call_count, 2)

    @mock.patch.object(directory, "get_plugin", autospec=True)
    @mock.patch.object(device_utils, "get_switch_device", autospec=True)
    def test_subports_added_without_l2vni(self, mock_get_switch, mock_plugin,
                                          m_list):
        """Test subports_added works when VNI not in binding_profile."""
        driver = gsm.GenericSwitchDriver()
        driver.initialize()

        parent_port = {
            'binding:profile': {
                'local_link_information': [
                    {'switch_info': 'foo', 'port_id': 2222}
                ]
            },
            'binding:vnic_type': 'baremetal',
            'id': '123'
        }
        subports = [
            {"segmentation_id": 100, "port_id": "s1"}
        ]

        mock_plugin.return_value = mock.MagicMock()
        # Subport has no VNI
        subport_s1 = {
            'id': 's1',
            'status': 'DOWN',
            'binding:profile': {}
        }
        mock_plugin.return_value.get_port.return_value = subport_s1

        mock_switch = mock.MagicMock()
        mock_switch.PLUG_SWITCH_TO_NETWORK = ['mock', 'commands']
        mock_get_switch.return_value = mock_switch

        driver.subports_added(self.ctxt, parent_port, subports=subports)

        # Verify VLAN trunking was configured
        mock_switch.add_subports_on_trunk.assert_called_once_with(
            parent_port['binding:profile'], 2222, subports)

        # Verify L2VNI was NOT configured (no VNI in binding_profile)
        mock_switch.vlan_has_vni.assert_not_called()
        mock_switch.plug_switch_to_network.assert_not_called()

        # Verify port status was updated
        mock_plugin.return_value.update_port_status.assert_called_once()

    @mock.patch.object(directory, "get_plugin", autospec=True)
    @mock.patch.object(device_utils, "get_switch_device", autospec=True)
    def test_subports_deleted_with_l2vni_cleanup(self, mock_get_switch,
                                                 mock_plugin, m_list):
        """Test subports_deleted cleans up L2VNI when VLAN is empty."""
        driver = gsm.GenericSwitchDriver()
        driver.initialize()

        parent_port = {
            'binding:profile': {
                'local_link_information': [
                    {'switch_info': 'foo', 'port_id': 2222}
                ]
            },
            'binding:vnic_type': 'baremetal',
            'id': '123'
        }
        subports = [
            {"segmentation_id": 100, "port_id": "s1"}
        ]

        mock_plugin.return_value = mock.MagicMock()
        # Subport has VNI in binding_profile
        subport_s1 = {
            'id': 's1',
            'binding:profile': {
                'vni': 5000,
                'physical_network': 'physnet1'
            },
            'segmentation_id': 100
        }
        mock_plugin.return_value.get_port.return_value = subport_s1

        mock_switch = mock.MagicMock()
        mock_switch.PLUG_SWITCH_TO_NETWORK = ['mock', 'commands']
        # VLAN has no ports remaining
        mock_switch.vlan_has_ports.return_value = False
        mock_get_switch.return_value = mock_switch

        driver.subports_deleted(self.ctxt, parent_port, subports=subports)

        # Verify VLAN was removed from trunk
        mock_switch.del_subports_on_trunk.assert_called_once_with(
            parent_port['binding:profile'], 2222, subports)

        # Verify L2VNI cleanup was performed
        mock_switch.vlan_has_ports.assert_called_once_with(100)
        mock_switch.unplug_switch_from_network.assert_called_once_with(
            5000, 100, physnet='physnet1')

    @mock.patch.object(directory, "get_plugin", autospec=True)
    @mock.patch.object(device_utils, "get_switch_device", autospec=True)
    def test_subports_deleted_with_l2vni_no_cleanup(
            self, mock_get_switch, mock_plugin, m_list):
        """Test subports_deleted skips L2VNI cleanup when VLAN has ports."""
        driver = gsm.GenericSwitchDriver()
        driver.initialize()

        parent_port = {
            'binding:profile': {
                'local_link_information': [
                    {'switch_info': 'foo', 'port_id': 2222}
                ]
            },
            'binding:vnic_type': 'baremetal',
            'id': '123'
        }
        subports = [
            {"segmentation_id": 100, "port_id": "s1"}
        ]

        mock_plugin.return_value = mock.MagicMock()
        # Subport has VNI in binding_profile
        subport_s1 = {
            'id': 's1',
            'binding:profile': {
                'vni': 5000,
                'physical_network': 'physnet1'
            }
        }
        mock_plugin.return_value.get_port.return_value = subport_s1

        mock_switch = mock.MagicMock()
        mock_switch.PLUG_SWITCH_TO_NETWORK = ['mock', 'commands']
        # VLAN still has other ports
        mock_switch.vlan_has_ports.return_value = True
        mock_get_switch.return_value = mock_switch

        driver.subports_deleted(self.ctxt, parent_port, subports=subports)

        # Verify VLAN was removed from trunk
        mock_switch.del_subports_on_trunk.assert_called_once_with(
            parent_port['binding:profile'], 2222, subports)

        # Verify L2VNI cleanup was skipped (VLAN still has ports)
        mock_switch.vlan_has_ports.assert_called_once_with(100)
        mock_switch.unplug_switch_from_network.assert_not_called()

    @mock.patch.object(directory, "get_plugin", autospec=True)
    @mock.patch.object(device_utils, "get_switch_device", autospec=True)
    def test_configure_l2vni_idempotency(self, mock_get_switch, mock_plugin,
                                         m_list):
        """Test configure_l2vni_for_subport is idempotent."""
        driver = gsm.GenericSwitchDriver()
        driver.initialize()

        parent_port = {
            'binding:profile': {
                'local_link_information': [
                    {'switch_info': 'foo', 'port_id': 2222}
                ]
            },
            'binding:vnic_type': 'baremetal',
            'id': '123'
        }
        subports = [
            {"segmentation_id": 100, "port_id": "s1"}
        ]

        mock_plugin.return_value = mock.MagicMock()
        # Subport has VNI in binding_profile
        subport_s1 = {
            'id': 's1',
            'status': 'DOWN',
            'binding:profile': {
                'vni': 5000,
                'physical_network': 'physnet1'
            }
        }
        mock_plugin.return_value.get_port.return_value = subport_s1

        mock_switch = mock.MagicMock()
        mock_switch.PLUG_SWITCH_TO_NETWORK = ['mock', 'commands']
        # VNI already configured on VLAN
        mock_switch.vlan_has_vni.return_value = True
        mock_get_switch.return_value = mock_switch

        driver.subports_added(self.ctxt, parent_port, subports=subports)

        # Verify idempotency check was performed
        mock_switch.vlan_has_vni.assert_called_once_with(100, 5000)
        # Verify L2VNI configuration was skipped (already configured)
        mock_switch.plug_switch_to_network.assert_not_called()

    @mock.patch.object(directory, "get_plugin", autospec=True)
    @mock.patch.object(device_utils, "get_switch_device", autospec=True)
    @mock.patch('networking_generic_switch.generic_switch_mech.LOG',
                autospec=True)
    def test_cleanup_l2vni_error_handling(self, m_log, mock_get_switch,
                                          mock_plugin, m_list):
        """Test cleanup_l2vni_for_subport handles exceptions gracefully."""
        driver = gsm.GenericSwitchDriver()
        driver.initialize()

        parent_port = {
            'binding:profile': {
                'local_link_information': [
                    {'switch_info': 'foo', 'port_id': 2222}
                ]
            },
            'binding:vnic_type': 'baremetal',
            'id': '123'
        }
        subports = [
            {"segmentation_id": 100, "port_id": "s1"}
        ]

        mock_plugin.return_value = mock.MagicMock()
        # Subport has VNI in binding_profile
        subport_s1 = {
            'id': 's1',
            'binding:profile': {
                'vni': 5000,
                'physical_network': 'physnet1'
            }
        }
        mock_plugin.return_value.get_port.return_value = subport_s1

        mock_switch = mock.MagicMock()
        mock_switch.PLUG_SWITCH_TO_NETWORK = ['mock', 'commands']
        mock_switch.vlan_has_ports.return_value = False
        # Simulate error during cleanup
        mock_switch.unplug_switch_from_network.side_effect = \
            exceptions.GenericSwitchNetmikoConfigError(
                cmds='test', args='test')
        mock_get_switch.return_value = mock_switch

        # Should not raise exception
        driver.subports_deleted(self.ctxt, parent_port, subports=subports)

        # Verify error was logged
        self.assertEqual(m_log.error.call_count, 1)
        self.assertIn('Failed to remove VNI', m_log.error.call_args[0][0])

    @mock.patch.object(directory, "get_plugin", autospec=True)
    @mock.patch.object(device_utils, "get_switch_device", autospec=True)
    @mock.patch('networking_generic_switch.generic_switch_mech.LOG',
                autospec=True)
    def test_subports_added_l2vni_unsupported_switch(self, m_log,
                                                     mock_get_switch,
                                                     mock_plugin, m_list):
        """Test subports_added logs warning for unsupported switches."""
        driver = gsm.GenericSwitchDriver()
        driver.initialize()

        parent_port = {
            'binding:profile': {
                'local_link_information': [
                    {'switch_info': 'foo', 'port_id': 2222}
                ]
            },
            'binding:vnic_type': 'baremetal',
            'id': '123'
        }
        subports = [
            {"segmentation_id": 100, "port_id": "s1"}
        ]

        mock_plugin.return_value = mock.MagicMock()
        # Subport has VNI in binding_profile
        subport_s1 = {
            'id': 's1',
            'status': 'DOWN',
            'binding:profile': {
                'vni': 5000,
                'physical_network': 'physnet1'
            }
        }
        mock_plugin.return_value.get_port.return_value = subport_s1

        # Mock switch does NOT support L2VNI
        mock_switch = mock.MagicMock()
        mock_switch.PLUG_SWITCH_TO_NETWORK = None
        mock_get_switch.return_value = mock_switch

        driver.subports_added(self.ctxt, parent_port, subports=subports)

        # Verify warning was logged
        self.assertEqual(m_log.warning.call_count, 1)
        self.assertIn('does not support L2VNI', m_log.warning.call_args[0][0])

        # Verify L2VNI was NOT configured
        mock_switch.plug_switch_to_network.assert_not_called()

        # Verify VLAN trunking still happened
        mock_switch.add_subports_on_trunk.assert_called_once()
