# Copyright 2024 UKRI STFC
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

from oslo_utils import uuidutils

from networking_generic_switch.devices.netmiko_devices import cumulus
from networking_generic_switch import exceptions as exc
from networking_generic_switch.tests.unit.netmiko import test_netmiko_base


class TestNetmikoCumulusNVUE(test_netmiko_base.NetmikoSwitchTestBase):

    def _make_switch_device(self, extra_cfg={}):
        device_cfg = {
            'device_type': 'netmiko_cumulus_nvue',
            'ngs_port_default_vlan': '123',
            'ngs_disable_inactive_ports': 'True',
        }
        device_cfg.update(extra_cfg)
        return cumulus.CumulusNVUE(device_cfg)

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device',
                return_value="", autospec=True)
    def test_add_network(self, mock_exec):
        self.switch.add_network(3333, '0ae071f5-5be9-43e4-80ea-e41fefe85b21')
        mock_exec.assert_called_with(
            self.switch,
            ['nv set bridge domain br_default vlan 3333'])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device',
                return_value="", autospec=True)
    def test_delete_network(self, mock_exec):
        self.switch.del_network(3333, '0ae071f5-5be9-43e4-80ea-e41fefe85b21')
        mock_exec.assert_called_with(
            self.switch,
            ['nv unset bridge domain br_default vlan 3333'])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device',
                return_value="", autospec=True)
    def test_plug_port_to_network(self, mock_exec):
        self.switch.plug_port_to_network(3333, 33)
        mock_exec.assert_called_with(
            self.switch,
            ['nv set interface 3333 link state up',
             'nv unset interface 3333 bridge domain br_default access',
             'nv unset interface 3333 bridge domain br_default untagged',
             'nv unset interface 3333 bridge domain br_default vlan',
             'nv unset interface 3333 bridge domain br_default untagged',
             'nv set interface 3333 bridge domain br_default access 33'])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device', autospec=True)
    def test_plug_port_to_network_fails(self, mock_exec):
        mock_exec.return_value = (
            'ERROR: Command not found.\n\nasdf'
        )
        self.assertRaises(exc.GenericSwitchNetmikoConfigError,
                          self.switch.plug_port_to_network, 3333, 33)

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device', autospec=True)
    def test_plug_port_to_network_fails_bad_port(self, mock_exec):
        mock_exec.return_value = (
            'ERROR: asd123 is not a physical interface on this switch.'
            '\n\nasdf'
        )
        self.assertRaises(exc.GenericSwitchNetmikoConfigError,
                          self.switch.plug_port_to_network, 3333, 33)

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device',
                return_value="", autospec=True)
    def test_plug_port_simple(self, mock_exec):
        switch = self._make_switch_device({
            'ngs_disable_inactive_ports': 'false',
            'ngs_port_default_vlan': '',
        })
        switch.plug_port_to_network(3333, 33)
        mock_exec.assert_called_with(
            switch,
            ['nv unset interface 3333 bridge domain br_default untagged',
             'nv set interface 3333 bridge domain br_default access 33'])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device',
                return_value="", autospec=True)
    def test_delete_port(self, mock_exec):
        self.switch.delete_port(3333, 33)
        mock_exec.assert_called_with(
            self.switch,
            ['nv unset interface 3333 bridge domain br_default access',
             'nv unset interface 3333 bridge domain br_default untagged',
             'nv unset interface 3333 bridge domain br_default vlan',
             'nv set bridge domain br_default vlan 123',
             'nv unset interface 3333 bridge domain br_default untagged',
             'nv set interface 3333 bridge domain br_default access 123',
             'nv set interface 3333 link state down'])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device',
                return_value="", autospec=True)
    def test_delete_port_simple(self, mock_exec):
        switch = self._make_switch_device({
            'ngs_disable_inactive_ports': 'false',
            'ngs_port_default_vlan': '',
        })
        switch.delete_port(3333, 33)
        mock_exec.assert_called_with(
            switch,
            ['nv unset interface 3333 bridge domain br_default access',
             'nv unset interface 3333 bridge domain br_default untagged',
             'nv unset interface 3333 bridge domain br_default vlan'])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device',
                return_value="", autospec=True)
    def test_plug_bond_to_network(self, mock_exec):
        self.switch.plug_bond_to_network(3333, 33)
        mock_exec.assert_called_with(
            self.switch,
            ['nv set interface 3333 link state up',
             'nv unset interface 3333 bridge domain br_default access',
             'nv unset interface 3333 bridge domain br_default untagged',
             'nv unset interface 3333 bridge domain br_default vlan',
             'nv unset interface 3333 bridge domain br_default untagged',
             'nv set interface 3333 bridge domain br_default access 33'])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device',
                return_value="", autospec=True)
    def test_plug_bond_simple(self, mock_exec):
        switch = self._make_switch_device({
            'ngs_disable_inactive_ports': 'false',
            'ngs_port_default_vlan': '',
        })
        switch.plug_bond_to_network(3333, 33)
        mock_exec.assert_called_with(
            switch,
            ['nv unset interface 3333 bridge domain br_default untagged',
             'nv set interface 3333 bridge domain br_default access 33'])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device',
                return_value="", autospec=True)
    def test_unplug_bond_from_network(self, mock_exec):
        self.switch.unplug_bond_from_network(3333, 33)
        mock_exec.assert_called_with(
            self.switch,
            ['nv unset interface 3333 bridge domain br_default access',
             'nv unset interface 3333 bridge domain br_default untagged',
             'nv unset interface 3333 bridge domain br_default vlan',
             'nv set bridge domain br_default vlan 123',
             'nv unset interface 3333 bridge domain br_default untagged',
             'nv set interface 3333 bridge domain br_default access 123',
             'nv set interface 3333 link state down'])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device',
                return_value="", autospec=True)
    def test_unplug_bond_from_network_simple(self, mock_exec):
        switch = self._make_switch_device({
            'ngs_disable_inactive_ports': 'false',
            'ngs_port_default_vlan': '',
        })
        switch.unplug_bond_from_network(3333, 33)
        mock_exec.assert_called_with(
            switch,
            ['nv unset interface 3333 bridge domain br_default access',
             'nv unset interface 3333 bridge domain br_default untagged',
             'nv unset interface 3333 bridge domain br_default vlan'])

    def test_save(self):
        mock_connect = mock.MagicMock()
        mock_connect.save_config.side_effect = NotImplementedError
        self.switch.save_configuration(mock_connect)
        mock_connect.send_command.assert_called_with('nv config save')

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device', autospec=True)
    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.check_output', autospec=True)
    def test_plug_port_to_network_subports(self, _, mock_exec):
        trunk_details = {"sub_ports": [{"segmentation_id": "tag1"},
                                       {"segmentation_id": "tag2"}]}
        self.switch.plug_port_to_network(4444, 44, trunk_details=trunk_details)
        mock_exec.assert_called_with(
            self.switch,
            ['nv set interface 4444 link state up',
             'nv unset interface 4444 bridge domain br_default access',
             'nv unset interface 4444 bridge domain br_default untagged',
             'nv unset interface 4444 bridge domain br_default vlan',
             'nv unset interface 4444 bridge domain br_default access',
             'nv set interface 4444 bridge domain br_default untagged 44',
             'nv set interface 4444 bridge domain br_default vlan 44',
             'nv unset interface 4444 bridge domain br_default access',
             'nv set interface 4444 bridge domain br_default vlan tag1',
             'nv unset interface 4444 bridge domain br_default access',
             'nv set interface 4444 bridge domain br_default vlan tag2'])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device', autospec=True)
    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.check_output', autospec=True)
    def test_delete_port_subports(self, _, mock_exec):
        trunk_details = {"sub_ports": [{"segmentation_id": "tag1"},
                                       {"segmentation_id": "tag2"}]}
        self.switch.delete_port(4444, 44, trunk_details=trunk_details)
        mock_exec.assert_called_with(
            self.switch,
            ['nv unset interface 4444 bridge domain br_default access',
             'nv unset interface 4444 bridge domain br_default untagged',
             'nv unset interface 4444 bridge domain br_default vlan',
             'nv unset interface 4444 bridge domain br_default untagged 44',
             'nv unset interface 4444 bridge domain br_default vlan 44',
             'nv unset interface 4444 bridge domain br_default vlan tag1',
             'nv unset interface 4444 bridge domain br_default vlan tag2',
             'nv set bridge domain br_default vlan 123',
             'nv unset interface 4444 bridge domain br_default untagged',
             'nv set interface 4444 bridge domain br_default access 123',
             'nv set interface 4444 link state down'])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device', autospec=True)
    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.check_output', autospec=True)
    def test_add_subports_on_trunk_no_subports(self, _, mock_exec):
        port_id = uuidutils.generate_uuid()
        parent_port = {
            'binding:profile': {
                'local_link_information': [
                    {
                        'switch_info': 'bar',
                        'port_id': 2222
                    }
                ]},
            'binding:vnic_type': 'baremetal',
            'id': port_id
        }
        subports = []
        self.switch.add_subports_on_trunk(parent_port, 44, subports=subports)
        mock_exec.assert_called_with(self.switch, [])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device', autospec=True)
    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.check_output', autospec=True)
    def test_add_subports_on_trunk_subports(self, _, mock_exec):
        port_id = uuidutils.generate_uuid()
        parent_port = {
            'binding:profile': {
                'local_link_information': [
                    {
                        'switch_info': 'bar',
                        'port_id': 2222
                    }
                ]},
            'binding:vnic_type': 'baremetal',
            'id': port_id
        }
        subports = [{"segmentation_id": "tag1"},
                    {"segmentation_id": "tag2"}]
        self.switch.add_subports_on_trunk(parent_port, 44, subports=subports)
        mock_exec.assert_called_with(
            self.switch,
            ['nv unset interface 44 bridge domain br_default access',
             'nv set interface 44 bridge domain br_default vlan tag1',
             'nv unset interface 44 bridge domain br_default access',
             'nv set interface 44 bridge domain br_default vlan tag2'])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device', autospec=True)
    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.check_output', autospec=True)
    def test_del_subports_on_trunk_no_subports(self, _, mock_exec):
        port_id = uuidutils.generate_uuid()
        parent_port = {
            'binding:profile': {
                'local_link_information': [
                    {
                        'switch_info': 'bar',
                        'port_id': 2222
                    }
                ]},
            'binding:vnic_type': 'baremetal',
            'id': port_id
        }
        subports = []
        self.switch.del_subports_on_trunk(parent_port, 44, subports=subports)
        mock_exec.assert_called_with(self.switch, [])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device', autospec=True)
    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.check_output', autospec=True)
    def test_del_subports_on_trunk_subports(self, _, mock_exec):
        port_id = uuidutils.generate_uuid()
        parent_port = {
            'binding:profile': {
                'local_link_information': [
                    {
                        'switch_info': 'bar',
                        'port_id': 2222
                    }
                ]},
            'binding:vnic_type': 'baremetal',
            'id': port_id
        }
        subports = [{"segmentation_id": "tag1"},
                    {"segmentation_id": "tag2"}]
        self.switch.del_subports_on_trunk(parent_port, 44, subports=subports)
        mock_exec.assert_called_with(
            self.switch,
            ['nv unset interface 44 bridge domain br_default vlan tag1',
             'nv unset interface 44 bridge domain br_default vlan tag2'])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device',
                return_value="", autospec=True)
    def test_plug_switch_to_network(self, mock_exec):
        self.switch.plug_switch_to_network(5000, 100)
        mock_exec.assert_called_with(
            self.switch,
            ['nv set bridge domain br_default vlan 100 vni 5000'])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device',
                return_value="", autospec=True)
    def test_unplug_switch_from_network(self, mock_exec):
        self.switch.unplug_switch_from_network(5000, 100)
        mock_exec.assert_called_with(
            self.switch,
            ['nv unset bridge domain br_default vlan 100 vni'])

    def test__parse_vlan_ports_with_ports(self):
        output = '''{
  "multicast": {},
  "port": {
    "swp1": {},
    "swp2": {}
  }
}'''
        result = self.switch._parse_vlan_ports(output, 100)
        self.assertTrue(result)

    def test__parse_vlan_ports_without_ports(self):
        output = '''{
  "multicast": {},
  "port": {}
}'''
        result = self.switch._parse_vlan_ports(output, 100)
        self.assertFalse(result)

    def test__parse_vlan_ports_invalid_json(self):
        output = 'Invalid JSON'
        result = self.switch._parse_vlan_ports(output, 100)
        self.assertFalse(result)

    def test__parse_vlan_vni_match(self):
        output = '''{
  "br_default": {
    "vlan-vni-map": {
      "10": {
        "vni": 10
      },
      "100": {
        "vni": 5000
      },
      "200": {
        "vni": 6000
      }
    }
  }
}'''
        result = self.switch._parse_vlan_vni(output, 100, 5000)
        self.assertTrue(result)

    def test__parse_vlan_vni_no_match(self):
        output = '''{
  "br_default": {
    "vlan-vni-map": {
      "10": {
        "vni": 10
      },
      "100": {
        "vni": 5000
      },
      "200": {
        "vni": 6000
      }
    }
  }
}'''
        result = self.switch._parse_vlan_vni(output, 100, 9999)
        self.assertFalse(result)

    def test__parse_vlan_vni_vlan_not_found(self):
        output = '''{
  "br_default": {
    "vlan-vni-map": {
      "10": {
        "vni": 10
      },
      "200": {
        "vni": 6000
      }
    }
  }
}'''
        result = self.switch._parse_vlan_vni(output, 100, 5000)
        self.assertFalse(result)

    def test__parse_vlan_vni_invalid_json(self):
        output = 'Invalid JSON'
        result = self.switch._parse_vlan_vni(output, 100, 5000)
        self.assertFalse(result)

    # Configuration Tests

    def test_init_default_config(self):
        """Test __init__ with default configuration."""
        device_cfg = {'device_type': 'netmiko_cumulus_nvue'}
        switch = cumulus.CumulusNVUE(device_cfg)
        self.assertIsNone(switch.her_flood_list)
        self.assertIsNone(switch.physnet_her_flood)
        self.assertEqual(switch._physnet_her_map, {})
        self.assertFalse(switch.evpn_vni_config)

    def test_init_with_global_her_flood_list(self):
        """Test __init__ with global HER flood list."""
        device_cfg = {
            'device_type': 'netmiko_cumulus_nvue',
            'ngs_her_flood_list': '10.0.1.1,10.0.1.2'
        }
        switch = cumulus.CumulusNVUE(device_cfg)
        self.assertEqual(switch.her_flood_list, '10.0.1.1,10.0.1.2')

    def test_init_with_physnet_her_flood(self):
        """Test __init__ with per-physnet HER flood mapping."""
        device_cfg = {
            'device_type': 'netmiko_cumulus_nvue',
            'ngs_physnet_her_flood': 'physnet1:10.0.1.1,10.0.1.2;'
                                     'physnet2:10.0.2.1'
        }
        switch = cumulus.CumulusNVUE(device_cfg)
        expected_map = {
            'physnet1': ['10.0.1.1', '10.0.1.2'],
            'physnet2': ['10.0.2.1']
        }
        self.assertEqual(switch._physnet_her_map, expected_map)

    def test_init_physnet_her_flood_with_spaces(self):
        """Test __init__ handles spaces in physnet HER flood mapping."""
        device_cfg = {
            'device_type': 'netmiko_cumulus_nvue',
            'ngs_physnet_her_flood': 'physnet1: 10.0.1.1 , 10.0.1.2 ; '
                                     'physnet2 : 10.0.2.1'
        }
        switch = cumulus.CumulusNVUE(device_cfg)
        expected_map = {
            'physnet1': ['10.0.1.1', '10.0.1.2'],
            'physnet2': ['10.0.2.1']
        }
        self.assertEqual(switch._physnet_her_map, expected_map)

    def test_init_invalid_physnet_her_flood_format(self):
        """Test __init__ raises error on invalid physnet mapping."""
        device_cfg = {
            'device_type': 'netmiko_cumulus_nvue',
            'ngs_physnet_her_flood': 'invalid_format'
        }
        self.assertRaises(exc.GenericSwitchNetmikoConfigError,
                          cumulus.CumulusNVUE, device_cfg)

    def test_init_evpn_vni_config_enabled(self):
        """Test __init__ with EVPN VNI config enabled."""
        device_cfg = {
            'device_type': 'netmiko_cumulus_nvue',
            'ngs_evpn_vni_config': 'true',
            'ngs_bgp_asn': '65000'
        }
        switch = cumulus.CumulusNVUE(device_cfg)
        self.assertTrue(switch.evpn_vni_config)
        self.assertEqual(switch.bgp_asn, '65000')

    # HER Flood List Resolution Tests

    def test_get_her_flood_list_for_physnet_with_mapping(self):
        """Test _get_her_flood_list_for_physnet returns mapped value."""
        device_cfg = {
            'device_type': 'netmiko_cumulus_nvue',
            'ngs_physnet_her_flood': 'physnet1:10.0.1.1,10.0.1.2'
        }
        switch = cumulus.CumulusNVUE(device_cfg)
        self.assertEqual(
            switch._get_her_flood_list_for_physnet('physnet1'),
            ['10.0.1.1', '10.0.1.2'])

    def test_get_her_flood_list_for_physnet_fallback_to_global(self):
        """Test _get_her_flood_list_for_physnet falls back to global."""
        device_cfg = {
            'device_type': 'netmiko_cumulus_nvue',
            'ngs_physnet_her_flood': 'physnet1:10.0.1.1',
            'ngs_her_flood_list': '10.0.0.1,10.0.0.2'
        }
        switch = cumulus.CumulusNVUE(device_cfg)
        self.assertEqual(
            switch._get_her_flood_list_for_physnet('physnet2'),
            ['10.0.0.1', '10.0.0.2'])

    def test_get_her_flood_list_for_physnet_default_none(self):
        """Test _get_her_flood_list_for_physnet defaults to None."""
        device_cfg = {'device_type': 'netmiko_cumulus_nvue'}
        switch = cumulus.CumulusNVUE(device_cfg)
        self.assertIsNone(
            switch._get_her_flood_list_for_physnet('physnet1'))

    # Plug/Unplug with HER Tests

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device',
                return_value='', autospec=True)
    def test_plug_switch_to_network_with_her_flood_list(self, mock_exec):
        """Test plug_switch_to_network with HER flood list."""
        device_cfg = {
            'device_type': 'netmiko_cumulus_nvue',
            'ngs_physnet_her_flood': 'physnet1:10.0.1.1,10.0.1.2'
        }
        switch = cumulus.CumulusNVUE(device_cfg)
        switch.plug_switch_to_network(10100, 100, physnet='physnet1')
        mock_exec.assert_called_with(
            switch,
            ['nv set bridge domain br_default vlan 100 vni 10100',
             'nv set nve vxlan flooding head-end-replication 10.0.1.1',
             'nv set nve vxlan flooding head-end-replication 10.0.1.2'])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device',
                return_value='', autospec=True)
    def test_plug_switch_to_network_without_her(self, mock_exec):
        """Test plug_switch_to_network without HER (EVPN only)."""
        device_cfg = {'device_type': 'netmiko_cumulus_nvue'}
        switch = cumulus.CumulusNVUE(device_cfg)
        switch.plug_switch_to_network(10100, 100, physnet='physnet1')
        # Should only have VXLAN map, no HER commands
        mock_exec.assert_called_with(
            switch,
            ['nv set bridge domain br_default vlan 100 vni 10100'])

    # EVPN Configuration Tests

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device',
                return_value='', autospec=True)
    def test_plug_switch_to_network_with_evpn_enabled(self, mock_exec):
        """Test plug_switch_to_network with EVPN VNI config enabled."""
        device_cfg = {
            'device_type': 'netmiko_cumulus_nvue',
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
             'nv set bridge domain br_default vlan 100 vni 10100'])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device',
                return_value='', autospec=True)
    def test_plug_switch_to_network_evpn_with_her(self, mock_exec):
        """Test plug_switch_to_network with EVPN and HER flood list."""
        device_cfg = {
            'device_type': 'netmiko_cumulus_nvue',
            'ngs_evpn_vni_config': 'true',
            'ngs_bgp_asn': '65000',
            'ngs_her_flood_list': '10.0.1.1,10.0.1.2'
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
             'nv set nve vxlan flooding head-end-replication 10.0.1.1',
             'nv set nve vxlan flooding head-end-replication 10.0.1.2'])

    def test_plug_switch_to_network_evpn_without_bgp_asn(self):
        """Test plug_switch_to_network fails when EVPN enabled, no ASN."""
        device_cfg = {
            'device_type': 'netmiko_cumulus_nvue',
            'ngs_evpn_vni_config': 'true'
        }
        switch = cumulus.CumulusNVUE(device_cfg)
        self.assertRaises(exc.GenericSwitchNetmikoConfigError,
                          switch.plug_switch_to_network, 10100, 100)

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device',
                return_value='', autospec=True)
    def test_unplug_switch_from_network_with_evpn_enabled(self, mock_exec):
        """Test unplug_switch_from_network with EVPN VNI config enabled."""
        device_cfg = {
            'device_type': 'netmiko_cumulus_nvue',
            'ngs_evpn_vni_config': 'true',
            'ngs_bgp_asn': '65000'
        }
        switch = cumulus.CumulusNVUE(device_cfg)
        switch.unplug_switch_from_network(10100, 100)
        expected_evpn_cmd = (
            'vtysh -c "configure terminal" '
            '-c "router bgp 65000" '
            '-c "address-family l2vpn evpn" '
            '-c "no vni 10100"')
        mock_exec.assert_called_with(
            switch,
            ['nv unset bridge domain br_default vlan 100 vni',
             expected_evpn_cmd])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device',
                return_value='', autospec=True)
    def test_unplug_switch_from_network_without_evpn(self, mock_exec):
        """Test unplug_switch_from_network without EVPN VNI config."""
        device_cfg = {'device_type': 'netmiko_cumulus_nvue'}
        switch = cumulus.CumulusNVUE(device_cfg)
        switch.unplug_switch_from_network(10100, 100)
        # Should only remove VXLAN map, no EVPN command
        mock_exec.assert_called_with(
            switch,
            ['nv unset bridge domain br_default vlan 100 vni'])

    def test_unplug_switch_from_network_evpn_without_bgp_asn(self):
        """Test unplug_switch_from_network fails when EVPN enabled, no ASN."""
        device_cfg = {
            'device_type': 'netmiko_cumulus_nvue',
            'ngs_evpn_vni_config': 'true'
        }
        switch = cumulus.CumulusNVUE(device_cfg)
        self.assertRaises(exc.GenericSwitchNetmikoConfigError,
                          switch.unplug_switch_from_network, 10100, 100)

    # vlan_has_ports() tests

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch._get_connection', autospec=True)
    def test_vlan_has_ports_true(self, mock_get_conn):
        """Test vlan_has_ports returns True when VLAN has ports."""
        device_cfg = {'device_type': 'netmiko_cumulus_nvue'}
        switch = cumulus.CumulusNVUE(device_cfg)

        mock_net_connect = mock.MagicMock()
        mock_get_conn.return_value.__enter__.return_value = mock_net_connect

        # Simulate output with ports
        output = '''{
  "multicast": {},
  "port": {
    "swp1": {},
    "swp2": {}
  }
}'''
        mock_net_connect.send_command.return_value = output

        result = switch.vlan_has_ports(100)
        self.assertTrue(result)
        mock_net_connect.send_command.assert_called_once_with(
            'nv show bridge domain br_default vlan 100 -o json')

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch._get_connection', autospec=True)
    def test_vlan_has_ports_false(self, mock_get_conn):
        """Test vlan_has_ports returns False when VLAN has no ports."""
        device_cfg = {'device_type': 'netmiko_cumulus_nvue'}
        switch = cumulus.CumulusNVUE(device_cfg)

        mock_net_connect = mock.MagicMock()
        mock_get_conn.return_value.__enter__.return_value = mock_net_connect

        # Simulate output without ports
        output = '''{
  "multicast": {},
  "port": {}
}'''
        mock_net_connect.send_command.return_value = output

        result = switch.vlan_has_ports(100)
        self.assertFalse(result)

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch._get_connection', autospec=True)
    def test_vlan_has_ports_invalid_json(self, mock_get_conn):
        """Test vlan_has_ports handles invalid JSON gracefully."""
        device_cfg = {'device_type': 'netmiko_cumulus_nvue'}
        switch = cumulus.CumulusNVUE(device_cfg)

        mock_net_connect = mock.MagicMock()
        mock_get_conn.return_value.__enter__.return_value = mock_net_connect

        # Simulate invalid JSON output
        output = 'not valid json'
        mock_net_connect.send_command.return_value = output

        result = switch.vlan_has_ports(100)
        self.assertFalse(result)

    # vlan_has_vni() tests

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch._get_connection', autospec=True)
    def test_vlan_has_vni_true(self, mock_get_conn):
        """Test vlan_has_vni returns True when VNI is configured."""
        device_cfg = {'device_type': 'netmiko_cumulus_nvue'}
        switch = cumulus.CumulusNVUE(device_cfg)

        mock_net_connect = mock.MagicMock()
        mock_get_conn.return_value.__enter__.return_value = mock_net_connect

        # Simulate output with matching VNI
        output = '''{
  "br_default": {
    "vlan-vni-map": {
      "100": {
        "vni": 5000
      },
      "200": {
        "vni": 6000
      }
    }
  }
}'''
        mock_net_connect.send_command.return_value = output

        result = switch.vlan_has_vni(100, 5000)
        self.assertTrue(result)
        mock_net_connect.send_command.assert_called_once_with(
            'nv show bridge domain br_default vlan-vni-map -o json')

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch._get_connection', autospec=True)
    def test_vlan_has_vni_false_wrong_vni(self, mock_get_conn):
        """Test vlan_has_vni returns False when VNI doesn't match."""
        device_cfg = {'device_type': 'netmiko_cumulus_nvue'}
        switch = cumulus.CumulusNVUE(device_cfg)

        mock_net_connect = mock.MagicMock()
        mock_get_conn.return_value.__enter__.return_value = mock_net_connect

        # Simulate output with wrong VNI for this VLAN
        output = '''{
  "br_default": {
    "vlan-vni-map": {
      "100": {
        "vni": 5000
      },
      "200": {
        "vni": 6000
      }
    }
  }
}'''
        mock_net_connect.send_command.return_value = output

        result = switch.vlan_has_vni(100, 9999)
        self.assertFalse(result)

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch._get_connection', autospec=True)
    def test_vlan_has_vni_false_vlan_not_found(self, mock_get_conn):
        """Test vlan_has_vni returns False when VLAN not in output."""
        device_cfg = {'device_type': 'netmiko_cumulus_nvue'}
        switch = cumulus.CumulusNVUE(device_cfg)

        mock_net_connect = mock.MagicMock()
        mock_get_conn.return_value.__enter__.return_value = mock_net_connect

        # Simulate output without the queried VLAN
        output = '''{
  "br_default": {
    "vlan-vni-map": {
      "200": {
        "vni": 6000
      },
      "300": {
        "vni": 7000
      }
    }
  }
}'''
        mock_net_connect.send_command.return_value = output

        result = switch.vlan_has_vni(100, 5000)
        self.assertFalse(result)

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch._get_connection', autospec=True)
    def test_vlan_has_vni_empty_output(self, mock_get_conn):
        """Test vlan_has_vni returns False with empty switch output."""
        device_cfg = {'device_type': 'netmiko_cumulus_nvue'}
        switch = cumulus.CumulusNVUE(device_cfg)

        mock_net_connect = mock.MagicMock()
        mock_get_conn.return_value.__enter__.return_value = mock_net_connect

        # Simulate empty output (no VNIs configured)
        output = '''{
  "br_default": {
    "vlan-vni-map": {}
  }
}'''
        mock_net_connect.send_command.return_value = output

        result = switch.vlan_has_vni(100, 5000)
        self.assertFalse(result)

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch._get_connection', autospec=True)
    def test_vlan_has_vni_invalid_json(self, mock_get_conn):
        """Test vlan_has_vni handles invalid JSON gracefully."""
        device_cfg = {'device_type': 'netmiko_cumulus_nvue'}
        switch = cumulus.CumulusNVUE(device_cfg)

        mock_net_connect = mock.MagicMock()
        mock_get_conn.return_value.__enter__.return_value = mock_net_connect

        # Simulate invalid JSON output
        output = 'not valid json'
        mock_net_connect.send_command.return_value = output

        result = switch.vlan_has_vni(100, 5000)
        self.assertFalse(result)
