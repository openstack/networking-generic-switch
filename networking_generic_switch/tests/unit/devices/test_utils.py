# Copyright 2017 Mirantis, Inc.
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

from networking_generic_switch import devices
from networking_generic_switch.devices import utils as device_utils


class TestDevices(unittest.TestCase):

    def setUp(self):
        self.devices = {
            'A': devices.device_manager({"device_type": 'netmiko_ovs_linux'}),
            'B': devices.device_manager({"device_type": 'netmiko_cisco_ios',
                                         "ngs_mac_address":
                                         'aa:bb:cc:dd:ee:ff'}),
        }

    def test_get_switch_device_match(self):
        self.assertEqual(device_utils.get_switch_device(
            self.devices, switch_info='A'), self.devices['A'])
        self.assertEqual(device_utils.get_switch_device(
            self.devices, ngs_mac_address='aa:bb:cc:dd:ee:ff'),
            self.devices['B'])

    def test_get_switch_device_match_priority(self):
        self.assertEqual(device_utils.get_switch_device(
            self.devices, switch_info='A',
            ngs_mac_address='aa:bb:cc:dd:ee:ff'),
            self.devices['B'])

    def test_get_switch_device_match_mac_ignore_case(self):
        self.assertEqual(device_utils.get_switch_device(
            self.devices, switch_info='A',
            ngs_mac_address='AA:BB:CC:DD:EE:FF'),
            self.devices['B'])

    def test_get_switch_device_no_match(self):
        self.assertIsNone(device_utils.get_switch_device(
            self.devices, switch_info='C'))
        self.assertIsNone(device_utils.get_switch_device(
            self.devices, ngs_mac_address='11:22:33:44:55:66'))

    def test_get_switch_device_fallback_to_switch_info(self):
        self.assertEqual(self.devices['A'], device_utils.get_switch_device(
            self.devices, switch_info='A',
            ngs_mac_address='11:22:33:44:55:77'))

    def test_sanitise_config(self):
        config = {'username': 'fake-user', 'password': 'fake-password'}
        result = device_utils.sanitise_config(config)
        expected = {'username': 'fake-user', 'password': '******'}
        self.assertEqual(expected, result)
