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


from networking_generic_switch import devices
from networking_generic_switch import exceptions as exc


class FakeFaultyDevice(devices.GenericSwitchDevice):
    pass


class FakeDevice(devices.GenericSwitchDevice):

    def add_network(s, n):
        pass

    def del_network(s):
        pass

    def plug_port_to_network(p, s):
        pass

    def delete_port(p, s):
        pass


class TestGenericSwitchDevice(unittest.TestCase):

    def test_correct_class(self):
        device = FakeDevice({'spam': 'ham'})
        self.assertEqual({'spam': 'ham'}, device.config)

    def test_fault_class(self):
        device = None
        missing_methods = ('add_network',
                           'del_network',
                           'plug_port_to_network')
        with self.assertRaises(TypeError) as ex:
            device = FakeFaultyDevice({'spam': 'ham'})
        for m in missing_methods:
            self.assertIn(m, ex.exception.args[0])
        self.assertIsNone(device)


class TestDeviceManager(unittest.TestCase):

    def test_driver_load(self):
        device_cfg = {"device_type": 'netmiko_ovs_linux'}
        device = devices.device_manager(device_cfg)
        self.assertIsInstance(device, devices.GenericSwitchDevice)
        self.assertEqual({'device_type': 'ovs_linux'}, device.config)

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.__init__')
    def test_driver_load_fail_invoke(self, switch_init_mock):
        switch_init_mock.side_effect = exc.GenericSwitchException(
            method='fake_method')
        device_cfg = {'device_type': 'netmiko_ovs_linux'}
        device = None
        with self.assertRaises(exc.GenericSwitchEntrypointLoadError) as ex:
            device = devices.device_manager(device_cfg)
        self.assertIn("fake_method", ex.exception.msg)
        self.assertIsNone(device)

    @mock.patch.object(devices.GenericSwitchDevice,
                       '_validate_network_name_format')
    def test_driver_load_fail_validate_network_name_format(self,
                                                           mock_validate):
        mock_validate.side_effect = exc.GenericSwitchConfigException()
        device_cfg = {'device_type': 'netmiko_ovs_linux'}
        device = None
        with self.assertRaises(exc.GenericSwitchEntrypointLoadError):
            device = devices.device_manager(device_cfg)
        self.assertIsNone(device)

    def test_driver_load_fail_load(self):
        device_cfg = {'device_type': 'fake_device'}
        device = None
        with self.assertRaises(exc.GenericSwitchEntrypointLoadError) as ex:
            device = devices.device_manager(device_cfg)
        self.assertIn("fake_device", ex.exception.msg)
        self.assertIsNone(device)

    def test_driver_ngs_config(self):
        device_cfg = {"device_type": 'netmiko_ovs_linux',
                      "ngs_mac_address": 'aa:bb:cc:dd:ee:ff',
                      "ngs_ssh_connect_timeout": "120",
                      "ngs_ssh_connect_interval": "20",
                      "ngs_trunk_ports": "port1,port2",
                      "ngs_physical_networks": "physnet1,physnet2",
                      "ngs_port_default_vlan": "20",
                      "ngs_disable_inactive_ports": "true",
                      "ngs_network_name_format": "net-{network_id}"}
        device = devices.device_manager(device_cfg)
        self.assertIsInstance(device, devices.GenericSwitchDevice)
        self.assertNotIn('ngs_mac_address', device.config)
        self.assertNotIn('ngs_ssh_connect_timeout', device.config)
        self.assertNotIn('ngs_ssh_connect_interval', device.config)
        self.assertNotIn('ngs_trunk_ports', device.config)
        self.assertNotIn('ngs_physical_networks', device.config)
        self.assertNotIn('ngs_port_default_vlan', device.config)
        self.assertEqual('aa:bb:cc:dd:ee:ff',
                         device.ngs_config['ngs_mac_address'])
        self.assertEqual('120', device.ngs_config['ngs_ssh_connect_timeout'])
        self.assertEqual('20', device.ngs_config['ngs_ssh_connect_interval'])
        self.assertEqual('port1,port2', device.ngs_config['ngs_trunk_ports'])
        self.assertEqual('physnet1,physnet2',
                         device.ngs_config['ngs_physical_networks'])
        self.assertEqual('20', device.ngs_config['ngs_port_default_vlan'])
        self.assertEqual('true',
                         device.ngs_config['ngs_disable_inactive_ports'])
        self.assertEqual('net-{network_id}',
                         device.ngs_config['ngs_network_name_format'])

    def test_driver_ngs_config_defaults(self):
        device_cfg = {"device_type": 'netmiko_ovs_linux'}
        device = devices.device_manager(device_cfg)
        self.assertIsInstance(device, devices.GenericSwitchDevice)
        self.assertNotIn('ngs_mac_address', device.ngs_config)
        self.assertEqual(60, device.ngs_config['ngs_ssh_connect_timeout'])
        self.assertEqual(10, device.ngs_config['ngs_ssh_connect_interval'])
        self.assertNotIn('ngs_trunk_ports', device.ngs_config)
        self.assertNotIn('ngs_physical_networks', device.ngs_config)
        self.assertNotIn('ngs_port_default_vlan', device.ngs_config)
        self.assertFalse(device.ngs_config['ngs_disable_inactive_ports'])
        self.assertEqual('{network_id}',
                         device.ngs_config['ngs_network_name_format'])

    def test__disable_inactive_ports(self):
        device_cfg = {"device_type": 'netmiko_ovs_linux',
                      "ngs_disable_inactive_ports": "true"}
        device = devices.device_manager(device_cfg)
        self.assertEqual(True, device._disable_inactive_ports())

    def test__validate_network_name_format(self):
        device_cfg = {
            'ngs_network_name_format': '{network_id}{segmentation_id}'}
        device = FakeDevice(device_cfg)
        device._validate_network_name_format()

    def test__validate_network_name_format_failure(self):
        device_cfg = {'ngs_network_name_format': '{invalid}'}
        self.assertRaisesRegexp(
            exc.GenericSwitchNetworkNameFormatInvalid,
            r"Invalid value for 'ngs_network_name_format'",
            FakeDevice, device_cfg)

    def test__get_network_name_default(self):
        device = FakeDevice({})
        name = device._get_network_name('fake-id', 22)
        self.assertEqual('fake-id', name)

    def test__get_network_name_segmentation_id(self):
        device_cfg = {'ngs_network_name_format': '{segmentation_id}'}
        device = FakeDevice(device_cfg)
        name = device._get_network_name('fake-id', 22)
        self.assertEqual('22', name)

    def test__get_network_name_both(self):
        device_cfg = {
            'ngs_network_name_format': '{network_id}_net_{segmentation_id}'}
        device = FakeDevice(device_cfg)
        name = device._get_network_name('fake-id', 22)
        self.assertEqual('fake-id_net_22', name)
