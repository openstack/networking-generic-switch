# Copyright 2026
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

from networking_generic_switch.devices.netmiko_devices import cumulus
from networking_generic_switch import exceptions as exc
from networking_generic_switch.tests.unit.netmiko import test_netmiko_base


class TestNetmikoCumulusNVUEMulticast(
        test_netmiko_base.NetmikoSwitchTestBase):
    """Tests for Cumulus NVUE multicast BUM replication mode."""

    def _make_switch_device(self, extra_cfg={}):
        device_cfg = {'device_type': 'netmiko_cumulus_nvue'}
        device_cfg.update(extra_cfg)
        return cumulus.CumulusNVUE(device_cfg)

    # BUM Replication Mode Auto-Detection Tests (Option B)

    def test_init_default_bum_mode_ingress_replication(self):
        """Test __init__ defaults to ingress-replication when no HER lists."""
        device_cfg = {'device_type': 'netmiko_cumulus_nvue'}
        switch = cumulus.CumulusNVUE(device_cfg)
        self.assertEqual(switch.bum_replication_mode, 'ingress-replication')

    def test_init_auto_detect_head_end_replication_global_her(self):
        """Test __init__ auto-detects head-end-replication with global HER."""
        device_cfg = {
            'device_type': 'netmiko_cumulus_nvue',
            'ngs_her_flood_list': '10.0.1.1,10.0.1.2'
        }
        switch = cumulus.CumulusNVUE(device_cfg)
        self.assertEqual(switch.bum_replication_mode, 'head-end-replication')

    def test_init_auto_detect_head_end_replication_physnet_her(self):
        """Test __init__ auto-detects head-end-replication with physnet HER."""
        device_cfg = {
            'device_type': 'netmiko_cumulus_nvue',
            'ngs_physnet_her_flood': 'physnet1:10.0.1.1'
        }
        switch = cumulus.CumulusNVUE(device_cfg)
        self.assertEqual(switch.bum_replication_mode, 'head-end-replication')

    def test_init_explicit_multicast_mode(self):
        """Test __init__ with explicitly set multicast mode."""
        device_cfg = {
            'device_type': 'netmiko_cumulus_nvue',
            'ngs_bum_replication_mode': 'multicast',
            'ngs_mcast_group_base': '239.1.1.0'
        }
        switch = cumulus.CumulusNVUE(device_cfg)
        self.assertEqual(switch.bum_replication_mode, 'multicast')
        self.assertEqual(switch.mcast_group_base, '239.1.1.0')

    def test_init_explicit_ingress_replication_overrides_her(self):
        """Test explicit ingress-replication overrides HER lists."""
        device_cfg = {
            'device_type': 'netmiko_cumulus_nvue',
            'ngs_bum_replication_mode': 'ingress-replication',
            'ngs_her_flood_list': '10.0.1.1'  # Should be ignored
        }
        switch = cumulus.CumulusNVUE(device_cfg)
        self.assertEqual(switch.bum_replication_mode, 'ingress-replication')

    def test_init_explicit_head_end_replication(self):
        """Test explicitly set head-end-replication mode."""
        device_cfg = {
            'device_type': 'netmiko_cumulus_nvue',
            'ngs_bum_replication_mode': 'head-end-replication',
            'ngs_her_flood_list': '10.0.1.1,10.0.1.2'
        }
        switch = cumulus.CumulusNVUE(device_cfg)
        self.assertEqual(switch.bum_replication_mode, 'head-end-replication')

    # Multicast Configuration Tests

    def test_init_multicast_with_base(self):
        """Test __init__ with multicast base configuration."""
        device_cfg = {
            'device_type': 'netmiko_cumulus_nvue',
            'ngs_bum_replication_mode': 'multicast',
            'ngs_mcast_group_base': '239.1.1.0'
        }
        switch = cumulus.CumulusNVUE(device_cfg)
        self.assertEqual(switch.mcast_group_base, '239.1.1.0')

    def test_init_multicast_with_map(self):
        """Test __init__ with multicast group map."""
        device_cfg = {
            'device_type': 'netmiko_cumulus_nvue',
            'ngs_bum_replication_mode': 'multicast',
            'ngs_mcast_group_map': '10100:239.1.1.100,10200:239.1.1.200'
        }
        switch = cumulus.CumulusNVUE(device_cfg)
        self.assertEqual(len(switch.mcast_group_map), 2)
        self.assertEqual(switch.mcast_group_map[10100], '239.1.1.100')
        self.assertEqual(switch.mcast_group_map[10200], '239.1.1.200')

    def test_get_multicast_group_from_base(self):
        """Test _get_multicast_group calculates from base."""
        device_cfg = {
            'device_type': 'netmiko_cumulus_nvue',
            'ngs_bum_replication_mode': 'multicast',
            'ngs_mcast_group_base': '239.1.1.0'
        }
        switch = cumulus.CumulusNVUE(device_cfg)
        # VNI 10100 % 256 = 116 -> 239.1.1.116
        self.assertEqual(switch._get_multicast_group(10100), '239.1.1.116')
        # VNI 10200 % 256 = 216 -> 239.1.1.216
        self.assertEqual(switch._get_multicast_group(10200), '239.1.1.216')

    def test_get_multicast_group_from_map(self):
        """Test _get_multicast_group uses explicit mapping."""
        device_cfg = {
            'device_type': 'netmiko_cumulus_nvue',
            'ngs_bum_replication_mode': 'multicast',
            'ngs_mcast_group_map': '10100:239.99.99.99'
        }
        switch = cumulus.CumulusNVUE(device_cfg)
        self.assertEqual(switch._get_multicast_group(10100), '239.99.99.99')

    def test_get_multicast_group_without_config_raises_error(self):
        """Test _get_multicast_group raises error without config."""
        device_cfg = {
            'device_type': 'netmiko_cumulus_nvue',
            'ngs_bum_replication_mode': 'multicast'
        }
        switch = cumulus.CumulusNVUE(device_cfg)
        self.assertRaises(
            exc.GenericSwitchNetmikoConfigError,
            switch._get_multicast_group,
            10100
        )

    # Plug/Unplug with Multicast Mode Tests

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device',
                return_value='', autospec=True)
    def test_plug_switch_to_network_multicast_mode(self, mock_exec):
        """Test plug_switch_to_network with multicast mode."""
        device_cfg = {
            'device_type': 'netmiko_cumulus_nvue',
            'ngs_bum_replication_mode': 'multicast',
            'ngs_mcast_group_base': '239.1.1.0'
        }
        switch = cumulus.CumulusNVUE(device_cfg)
        switch.plug_switch_to_network(10100, 100)

        # VNI 10100 % 256 = 116, so mcast group is 239.1.1.116
        mock_exec.assert_called_with(
            switch,
            ['nv set bridge domain br_default vlan 100 vni 10100',
             'nv set bridge domain br_default vlan 100 vni 10100 '
             'flooding multicast-group 239.1.1.116'])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device',
                return_value='', autospec=True)
    def test_plug_switch_to_network_multicast_with_map(self, mock_exec):
        """Test plug_switch_to_network multicast with explicit mapping."""
        device_cfg = {
            'device_type': 'netmiko_cumulus_nvue',
            'ngs_bum_replication_mode': 'multicast',
            'ngs_mcast_group_map': '10100:239.99.99.99'
        }
        switch = cumulus.CumulusNVUE(device_cfg)
        switch.plug_switch_to_network(10100, 100)

        mock_exec.assert_called_with(
            switch,
            ['nv set bridge domain br_default vlan 100 vni 10100',
             'nv set bridge domain br_default vlan 100 vni 10100 '
             'flooding multicast-group 239.99.99.99'])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device',
                return_value='', autospec=True)
    def test_plug_switch_to_network_multicast_with_evpn(self, mock_exec):
        """Test plug_switch_to_network multicast with EVPN VNI config."""
        device_cfg = {
            'device_type': 'netmiko_cumulus_nvue',
            'ngs_bum_replication_mode': 'multicast',
            'ngs_mcast_group_base': '239.2.2.0',
            'ngs_evpn_vni_config': 'true',
            'ngs_bgp_asn': '65000'
        }
        switch = cumulus.CumulusNVUE(device_cfg)
        switch.plug_switch_to_network(5000, 50)

        expected_evpn_cmd = (
            'vtysh -c "configure terminal" '
            '-c "router bgp 65000" '
            '-c "address-family l2vpn evpn" '
            '-c "vni 5000" '
            '-c "rd auto" '
            '-c "route-target import auto" '
            '-c "route-target export auto"')
        # VNI 5000 % 256 = 136 -> 239.2.2.136
        mock_exec.assert_called_with(
            switch,
            [expected_evpn_cmd,
             'nv set bridge domain br_default vlan 50 vni 5000',
             'nv set bridge domain br_default vlan 50 vni 5000 '
             'flooding multicast-group 239.2.2.136'])

    # Ingress-Replication (EVPN-learned VTEPs) Tests

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device',
                return_value='', autospec=True)
    def test_plug_switch_to_network_ingress_replication(self, mock_exec):
        """Test plug_switch_to_network with ingress-replication mode."""
        device_cfg = {
            'device_type': 'netmiko_cumulus_nvue',
            'ngs_bum_replication_mode': 'ingress-replication'
        }
        switch = cumulus.CumulusNVUE(device_cfg)
        switch.plug_switch_to_network(10100, 100)

        mock_exec.assert_called_with(
            switch,
            ['nv set bridge domain br_default vlan 100 vni 10100',
             'nv set bridge domain br_default vlan 100 vni 10100 '
             'flooding head-end-replication evpn'])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device',
                return_value='', autospec=True)
    def test_plug_switch_to_network_ingress_replication_default(
            self, mock_exec):
        """Test plug_switch_to_network defaults to ingress-replication."""
        device_cfg = {'device_type': 'netmiko_cumulus_nvue'}
        switch = cumulus.CumulusNVUE(device_cfg)
        switch.plug_switch_to_network(10100, 100)

        # No explicit mode, no HER lists -> ingress-replication
        mock_exec.assert_called_with(
            switch,
            ['nv set bridge domain br_default vlan 100 vni 10100',
             'nv set bridge domain br_default vlan 100 vni 10100 '
             'flooding head-end-replication evpn'])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device',
                return_value='', autospec=True)
    def test_plug_switch_to_network_ingress_replication_with_evpn(
            self, mock_exec):
        """Test plug_switch_to_network ingress-replication with EVPN VNI."""
        device_cfg = {
            'device_type': 'netmiko_cumulus_nvue',
            'ngs_bum_replication_mode': 'ingress-replication',
            'ngs_evpn_vni_config': 'true',
            'ngs_bgp_asn': '65000'
        }
        switch = cumulus.CumulusNVUE(device_cfg)
        switch.plug_switch_to_network(10100, 100)

        expected_evpn_cmd = (
            'vtysh -c "configure terminal" '
            '-c "router bgp 65000" '
            '-c "address-family l2vpn evpn" '
            '-c "vni 10100" '
            '-c "rd auto" '
            '-c "route-target import auto" '
            '-c "route-target export auto"')
        mock_exec.assert_called_with(
            switch,
            [expected_evpn_cmd,
             'nv set bridge domain br_default vlan 100 vni 10100',
             'nv set bridge domain br_default vlan 100 vni 10100 '
             'flooding head-end-replication evpn'])
