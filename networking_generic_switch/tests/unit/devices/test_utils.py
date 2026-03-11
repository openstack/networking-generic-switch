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
from networking_generic_switch import exceptions as exc


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
        config = {'username': 'fake-user', 'password': 'fake-password',
                  'ip': '123.456.789', 'session_log': '/some/path/here',
                  "device_type": "my_device"}
        result = device_utils.sanitise_config(config)
        expected = {k: '******' for k in config}
        self.assertEqual(expected, result)


class TestVxlanMulticastConfig(unittest.TestCase):
    """Test VXLAN multicast configuration parsing."""

    def test_parse_vxlan_multicast_config_defaults(self):
        """Test default values when no multicast config provided."""
        device_cfg = {'device_type': 'test_device'}
        result = device_utils.parse_vxlan_multicast_config(device_cfg)

        self.assertEqual(result.bum_replication_mode,
                         'ingress-replication')
        self.assertIsNone(result.mcast_group_base)
        self.assertEqual(result.mcast_group_increment, 'vni_last_octet')
        self.assertEqual(result.mcast_group_map, {})

    def test_parse_vxlan_multicast_config_multicast_mode(self):
        """Test multicast mode with base group."""
        device_cfg = {
            'device_type': 'test_device',
            'ngs_bum_replication_mode': 'multicast',
            'ngs_mcast_group_base': '239.1.1.0'
        }
        result = device_utils.parse_vxlan_multicast_config(device_cfg)

        self.assertEqual(result.bum_replication_mode, 'multicast')
        self.assertEqual(result.mcast_group_base, '239.1.1.0')
        self.assertEqual(result.mcast_group_increment, 'vni_last_octet')
        self.assertEqual(result.mcast_group_map, {})

    def test_parse_vxlan_multicast_config_with_map(self):
        """Test explicit VNI-to-multicast-group mappings."""
        device_cfg = {
            'device_type': 'test_device',
            'ngs_mcast_group_map': '10100:239.1.1.100, 10200:239.1.1.200'
        }
        result = device_utils.parse_vxlan_multicast_config(device_cfg)

        self.assertEqual(len(result.mcast_group_map), 2)
        self.assertEqual(result.mcast_group_map[10100], '239.1.1.100')
        self.assertEqual(result.mcast_group_map[10200], '239.1.1.200')

    def test_parse_vxlan_multicast_config_map_with_whitespace(self):
        """Test explicit map handles extra whitespace."""
        device_cfg = {
            'device_type': 'test_device',
            'ngs_mcast_group_map': '  10100 : 239.1.1.100 , '
                                   '10200:239.1.1.200  '
        }
        result = device_utils.parse_vxlan_multicast_config(device_cfg)

        self.assertEqual(result.mcast_group_map[10100], '239.1.1.100')
        self.assertEqual(result.mcast_group_map[10200], '239.1.1.200')

    def test_parse_vxlan_multicast_config_map_invalid_format(self):
        """Test invalid mapping format is skipped."""
        device_cfg = {
            'device_type': 'test_device',
            'ngs_mcast_group_map': 'invalid_entry, 10200:239.1.1.200'
        }
        result = device_utils.parse_vxlan_multicast_config(device_cfg)

        # Invalid entry should be skipped
        self.assertEqual(len(result.mcast_group_map), 1)
        self.assertNotIn('invalid_entry', result.mcast_group_map)
        self.assertEqual(result.mcast_group_map[10200], '239.1.1.200')

    def test_parse_vxlan_multicast_config_map_invalid_vni(self):
        """Test non-integer VNI is rejected."""
        device_cfg = {
            'device_type': 'test_device',
            'ngs_mcast_group_map': 'abc:239.1.1.100, 10200:239.1.1.200'
        }
        result = device_utils.parse_vxlan_multicast_config(device_cfg)

        # Non-integer VNI should be rejected
        self.assertEqual(len(result.mcast_group_map), 1)
        self.assertNotIn('abc', result.mcast_group_map)
        self.assertEqual(result.mcast_group_map[10200], '239.1.1.200')

    def test_parse_vxlan_multicast_config_map_vni_out_of_range(self):
        """Test VNI out of valid range is rejected."""
        device_cfg = {
            'device_type': 'test_device',
            'ngs_mcast_group_map': '0:239.1.1.1, 16777216:239.1.1.2, '
                                   '10100:239.1.1.100'
        }
        result = device_utils.parse_vxlan_multicast_config(device_cfg)

        # VNI 0 (below minimum) and 16777216 (above max) should be rejected
        self.assertEqual(len(result.mcast_group_map), 1)
        self.assertNotIn(0, result.mcast_group_map)
        self.assertNotIn(16777216, result.mcast_group_map)
        self.assertEqual(result.mcast_group_map[10100], '239.1.1.100')

    def test_parse_vxlan_multicast_config_map_invalid_ip(self):
        """Test invalid IP address is rejected."""
        device_cfg = {
            'device_type': 'test_device',
            'ngs_mcast_group_map': '10100:not.an.ip, 10200:239.1.1.200'
        }
        result = device_utils.parse_vxlan_multicast_config(device_cfg)

        # Invalid IP should be rejected
        self.assertEqual(len(result.mcast_group_map), 1)
        self.assertNotIn(10100, result.mcast_group_map)
        self.assertEqual(result.mcast_group_map[10200], '239.1.1.200')

    def test_parse_vxlan_multicast_config_map_non_multicast_ip(self):
        """Test non-multicast IP address is rejected."""
        device_cfg = {
            'device_type': 'test_device',
            'ngs_mcast_group_map': '10100:192.168.1.1, 10200:239.1.1.200'
        }
        result = device_utils.parse_vxlan_multicast_config(device_cfg)

        # Unicast IP should be rejected
        self.assertEqual(len(result.mcast_group_map), 1)
        self.assertNotIn(10100, result.mcast_group_map)
        self.assertEqual(result.mcast_group_map[10200], '239.1.1.200')

    def test_parse_vxlan_multicast_config_map_duplicate_vni(self):
        """Test duplicate VNI uses last entry."""
        device_cfg = {
            'device_type': 'test_device',
            'ngs_mcast_group_map': '10100:239.1.1.1, 10100:239.1.1.2'
        }
        result = device_utils.parse_vxlan_multicast_config(device_cfg)

        # Should use last entry for duplicate VNI
        self.assertEqual(len(result.mcast_group_map), 1)
        self.assertEqual(result.mcast_group_map[10100], '239.1.1.2')

    def test_parse_vxlan_multicast_config_empty_entries(self):
        """Test empty entries are skipped."""
        device_cfg = {
            'device_type': 'test_device',
            'ngs_mcast_group_map': '10100:239.1.1.100, , ,10200:239.1.1.200'
        }
        result = device_utils.parse_vxlan_multicast_config(device_cfg)

        self.assertEqual(len(result.mcast_group_map), 2)
        self.assertEqual(result.mcast_group_map[10100], '239.1.1.100')
        self.assertEqual(result.mcast_group_map[10200], '239.1.1.200')


class TestGetVxlanMulticastGroup(unittest.TestCase):
    """Test VXLAN multicast group derivation."""

    def test_get_multicast_group_from_explicit_map(self):
        """Test explicit mapping takes precedence."""
        mcast_map = {10100: '239.5.5.100'}
        result = device_utils.get_vxlan_multicast_group(
            10100, mcast_map, '239.1.1.0')

        self.assertEqual(result, '239.5.5.100')

    def test_get_multicast_group_from_base(self):
        """Test automatic derivation from base."""
        result = device_utils.get_vxlan_multicast_group(
            10100, {}, '239.1.1.0')

        # VNI 10100 % 256 = 116 -> 239.1.1.116
        self.assertEqual(result, '239.1.1.116')

    def test_get_multicast_group_various_vnis(self):
        """Test derivation for various VNI values."""
        base = '239.1.1.0'

        # VNI 10200 % 256 = 216 -> 239.1.1.216
        result = device_utils.get_vxlan_multicast_group(10200, {}, base)
        self.assertEqual(result, '239.1.1.216')

        # VNI 10001 % 256 = 17 -> 239.1.1.17
        result = device_utils.get_vxlan_multicast_group(10001, {}, base)
        self.assertEqual(result, '239.1.1.17')

        # VNI 5000 % 256 = 136 -> 239.1.1.136
        result = device_utils.get_vxlan_multicast_group(5000, {}, base)
        self.assertEqual(result, '239.1.1.136')

        # VNI 100 % 256 = 100 -> 239.1.1.100
        result = device_utils.get_vxlan_multicast_group(100, {}, base)
        self.assertEqual(result, '239.1.1.100')

    def test_get_multicast_group_without_base_raises_error(self):
        """Test error raised when no base or mapping configured."""
        with self.assertRaises(exc.GenericSwitchNetmikoConfigError):
            device_utils.get_vxlan_multicast_group(10100, {}, None)

    def test_get_multicast_group_without_base_with_device_name(self):
        """Test error message includes device name when provided."""
        with self.assertRaises(exc.GenericSwitchNetmikoConfigError):
            device_utils.get_vxlan_multicast_group(
                10100, {}, None, device_name='test-switch')

    def test_get_multicast_group_fallback_to_base(self):
        """Test fallback to base when VNI not in explicit map."""
        mcast_map = {10100: '239.5.5.100'}

        # VNI in map
        result = device_utils.get_vxlan_multicast_group(
            10100, mcast_map, '239.1.1.0')
        self.assertEqual(result, '239.5.5.100')

        # VNI not in map, fallback to base
        result = device_utils.get_vxlan_multicast_group(
            10200, mcast_map, '239.1.1.0')
        self.assertEqual(result, '239.1.1.216')

    def test_get_multicast_group_different_base_addresses(self):
        """Test derivation with different base addresses."""
        # Base 239.2.2.0
        result = device_utils.get_vxlan_multicast_group(
            5000, {}, '239.2.2.0')
        # VNI 5000 % 256 = 136 -> 239.2.2.136
        self.assertEqual(result, '239.2.2.136')

        # Base 225.0.0.0
        result = device_utils.get_vxlan_multicast_group(
            10100, {}, '225.0.0.0')
        # VNI 10100 % 256 = 116 -> 225.0.0.116
        self.assertEqual(result, '225.0.0.116')
