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

from networking_generic_switch import devices
from networking_generic_switch import exceptions as exc


class FakeFaultyDevice(devices.GenericSwitchDevice):
    pass


class FakeDevice(devices.GenericSwitchDevice):

    def add_network(s, n):
        pass

    def del_network(s):
        pass

    def plug_port_to_network(s, p):
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
        self.assertEqual(device.config, device_cfg)

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

    def test_driver_load_fail_load(self):
        device_cfg = {'device_type': 'fake_device'}
        device = None
        with self.assertRaises(exc.GenericSwitchEntrypointLoadError) as ex:
            device = devices.device_manager(device_cfg)
        self.assertIn("fake_device", ex.exception.msg)
        self.assertIsNone(device)
