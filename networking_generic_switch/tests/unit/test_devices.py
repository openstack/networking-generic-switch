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

    def plug_port_to_network(self, p, s):
        pass

    def delete_port(self, p, s):
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

    @mock.patch.object(FakeDevice, 'plug_port_to_network', autospec=True)
    def test_plug_bond_to_network_fallback(self, mock_plug):
        device = FakeDevice({'spam': 'ham'})
        device.plug_bond_to_network(22, 33)
        mock_plug.assert_called_once_with(device, 22, 33)

    @mock.patch.object(FakeDevice, 'delete_port', autospec=True)
    def test_unplug_bond_from_network_fallback(self, mock_delete):
        device = FakeDevice({'spam': 'ham'})
        device.unplug_bond_from_network(22, 33)
        mock_delete.assert_called_once_with(device, 22, 33)


class TestDeviceManager(unittest.TestCase):

    def test_driver_load(self):
        device_cfg = {"device_type": 'netmiko_ovs_linux'}
        device = devices.device_manager(device_cfg)
        self.assertIsInstance(device, devices.GenericSwitchDevice)
        self.assertEqual({'device_type': 'ovs_linux'}, device.config)

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.__init__', autospec=True)
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
                       '_validate_network_name_format', autospec=True)
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
                      "ngs_network_name_format": "net-{network_id}",
                      "ngs_allowed_vlans": "123,124",
                      "ngs_allowed_ports": "Ethernet1/1,Ethernet1/2"}
        device = devices.device_manager(device_cfg)
        self.assertIsInstance(device, devices.GenericSwitchDevice)
        self.assertNotIn('ngs_mac_address', device.config)
        self.assertNotIn('ngs_ssh_connect_timeout', device.config)
        self.assertNotIn('ngs_ssh_connect_interval', device.config)
        self.assertNotIn('ngs_trunk_ports', device.config)
        self.assertNotIn('ngs_physical_networks', device.config)
        self.assertNotIn('ngs_port_default_vlan', device.config)
        self.assertNotIn('ngs_allowed_vlans', device.config)
        self.assertNotIn('ngs_allowed_ports', device.config)
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
        self.assertEqual("123,124",
                         device.ngs_config['ngs_allowed_vlans'])
        self.assertEqual(["123", "124"],
                         device._get_allowed_vlans())
        self.assertEqual("Ethernet1/1,Ethernet1/2",
                         device.ngs_config['ngs_allowed_ports'])
        self.assertEqual(["Ethernet1/1", "Ethernet1/2"],
                         device._get_allowed_ports())

    def test_driver_ngs_is_allowed(self):
        device_cfg = {"device_type": 'netmiko_ovs_linux',
                      "ngs_allowed_vlans": "123,124",
                      "ngs_allowed_ports": "Ethernet1/1,Ethernet1/2"}
        device = devices.device_manager(device_cfg)

        # test all allowed
        self.assertTrue(device.is_allowed("Ethernet1/1", 123))
        self.assertTrue(device.is_allowed("Ethernet1/2", 124))
        # fail on vlan
        self.assertFalse(device.is_allowed("Ethernet1/2", 125))
        # fail on port
        self.assertFalse(device.is_allowed("Ethernet1/3", 124))
        # fail on both
        self.assertFalse(device.is_allowed("Ethernet2/2", 1))

    def test_driver_ngs_is_allowed_fails_on_empty_ports(self):
        device_cfg = {"device_type": 'netmiko_ovs_linux',
                      "ngs_allowed_vlans": "123",
                      "ngs_allowed_ports": ""}
        device = devices.device_manager(device_cfg)
        self.assertFalse(device.is_allowed("Ethernet1/1", 123))

    def test_driver_ngs_is_allowed_fails_on_empty_vlans(self):
        device_cfg = {"device_type": 'netmiko_ovs_linux',
                      "ngs_allowed_vlans": "",
                      "ngs_allowed_ports": "Ethernet1/1"}
        device = devices.device_manager(device_cfg)
        self.assertFalse(device.is_allowed("Ethernet1/1", 123))

    def test_driver_ngs_is_allowed_default(self):
        device_cfg = {"device_type": 'netmiko_ovs_linux'}
        device = devices.device_manager(device_cfg)
        self.assertTrue(device.is_allowed("Ethernet1/1", 123))

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
        self.assertNotIn('ngs_allowed_vlans', device.ngs_config)
        self.assertNotIn('ngs_allowed_ports', device.ngs_config)

    def test__get_trunk_ports(self):
        device_cfg = {"ngs_trunk_ports": 'port1, Po 1/30,port42'}
        device = FakeDevice(device_cfg)
        trunk_ports = device._get_trunk_ports()
        self.assertEqual(["port1", "Po 1/30", "port42"], trunk_ports)

    def test__get_physical_networks(self):
        device_cfg = {"ngs_physical_networks": 'net1,  net2, net3  '}
        device = FakeDevice(device_cfg)
        physnets = device._get_physical_networks()
        self.assertEqual(["net1", "net2", "net3"], physnets)

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
        self.assertRaisesRegex(
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

    def test__get_ssh_disabled_algorithms(self):
        algos = (
            "kex:diffie-hellman-group-exchange-sha1, "
            "ciphers:blowfish-cbc, ciphers:3des-cbc"
        )
        device_cfg = {
            "ngs_ssh_disabled_algorithms": algos
        }
        device = FakeDevice(device_cfg)
        algos = device._get_ssh_disabled_algorithms()
        expected = {
            "kex": ["diffie-hellman-group-exchange-sha1"],
            "ciphers": ["blowfish-cbc", "3des-cbc"],
        }
        self.assertEqual(expected, algos)
