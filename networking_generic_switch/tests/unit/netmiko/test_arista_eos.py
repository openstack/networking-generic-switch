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

from unittest import mock

from oslo_utils import uuidutils

from networking_generic_switch.devices.netmiko_devices import arista
from networking_generic_switch import exceptions as exc
from networking_generic_switch.tests.unit.netmiko import test_netmiko_base


class TestNetmikoAristaEos(test_netmiko_base.NetmikoSwitchTestBase):

    def _make_switch_device(self):
        device_cfg = {'device_type': 'netmiko_arista_eos'}
        return arista.AristaEos(device_cfg)

    def test_constants(self):
        self.assertIsNone(self.switch.SAVE_CONFIGURATION)

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device', autospec=True)
    def test_add_network(self, m_exec):
        self.switch.add_network(33, '0ae071f5-5be9-43e4-80ea-e41fefe85b21')
        m_exec.assert_called_with(
            self.switch,
            ['vlan 33', 'name 0ae071f55be943e480eae41fefe85b21'])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device', autospec=True)
    def test_del_network(self, mock_exec):
        self.switch.del_network(33, '0ae071f5-5be9-43e4-80ea-e41fefe85b21')
        mock_exec.assert_called_with(self.switch, ['no vlan 33'])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device', autospec=True)
    def test_plug_port_to_network(self, mock_exec):
        self.switch.plug_port_to_network(3333, 33)
        mock_exec.assert_called_with(
            self.switch,
            ['interface 3333', 'switchport mode access',
             'switchport access vlan 33'])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device', autospec=True)
    def test_delete_port(self, mock_exec):
        self.switch.delete_port(3333, 33)
        mock_exec.assert_called_with(
            self.switch,
            ['interface 3333', 'no switchport access vlan 33',
             'no switchport mode trunk',
             'switchport trunk allowed vlan none'])

    def test__format_commands(self):
        cmd_set = self.switch._format_commands(
            arista.AristaEos.ADD_NETWORK,
            segmentation_id=22,
            network_id=22,
            network_name='vlan-22')
        self.assertEqual(cmd_set, ['vlan 22', 'name vlan-22'])

        cmd_set = self.switch._format_commands(
            arista.AristaEos.DELETE_NETWORK,
            segmentation_id=22)
        self.assertEqual(cmd_set, ['no vlan 22'])

        cmd_set = self.switch._format_commands(
            arista.AristaEos.PLUG_PORT_TO_NETWORK,
            port=3333,
            segmentation_id=33)
        plug_exp = ['interface 3333', 'switchport mode access',
                    'switchport access vlan 33']
        self.assertEqual(plug_exp, cmd_set)

        cmd_set = self.switch._format_commands(
            arista.AristaEos.DELETE_PORT,
            port=3333,
            segmentation_id=33)
        del_exp = ['interface 3333', 'no switchport access vlan 33',
                   'no switchport mode trunk',
                   'switchport trunk allowed vlan none']
        self.assertEqual(del_exp, cmd_set)

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device', autospec=True)
    def test_plug_port_to_network_subports(self, mock_exec):
        trunk_details = {"sub_ports": [{"segmentation_id": "tag1"},
                                       {"segmentation_id": "tag2"}]}
        self.switch.plug_port_to_network(4444, 44, trunk_details=trunk_details)
        mock_exec.assert_called_with(
            self.switch,
            ['interface 4444',
             'switchport mode trunk',
             'switchport trunk native vlan 44',
             'switchport trunk allowed vlan add 44',
             'interface 4444',
             'switchport trunk allowed vlan add tag1',
             'interface 4444',
             'switchport trunk allowed vlan add tag2'])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device', autospec=True)
    def test_delete_port_subports(self, mock_exec):
        trunk_details = {"sub_ports": [{"segmentation_id": "tag1"},
                                       {"segmentation_id": "tag2"}]}
        self.switch.delete_port(4444, 44, trunk_details=trunk_details)
        mock_exec.assert_called_with(
            self.switch,
            ['interface 4444',
             'no switchport access vlan 44',
             'no switchport mode trunk',
             'switchport trunk allowed vlan none',
             'interface 4444',
             'no switchport trunk native vlan 44',
             'switchport trunk allowed vlan remove 44',
             'interface 4444',
             'switchport trunk allowed vlan remove tag1',
             'interface 4444',
             'switchport trunk allowed vlan remove tag2'])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device', autospec=True)
    def test_plug_bond_to_network_subports(self, mock_exec):
        trunk_details = {"sub_ports": [{"segmentation_id": "tag1"},
                                       {"segmentation_id": "tag2"}]}
        self.switch.plug_bond_to_network(4444, 44, trunk_details=trunk_details)
        mock_exec.assert_called_with(
            self.switch,
            ['interface 4444',
             'switchport mode trunk',
             'switchport trunk native vlan 44',
             'switchport trunk allowed vlan add 44',
             'interface 4444',
             'switchport trunk allowed vlan add tag1',
             'interface 4444',
             'switchport trunk allowed vlan add tag2'])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device', autospec=True)
    def test_unplug_bond_from_network_subports(self, mock_exec):
        trunk_details = {"sub_ports": [{"segmentation_id": "tag1"},
                                       {"segmentation_id": "tag2"}]}
        self.switch.unplug_bond_from_network(
            4444, 44, trunk_details=trunk_details)
        mock_exec.assert_called_with(
            self.switch,
            ['interface 4444',
             'no switchport access vlan 44',
             'no switchport mode trunk',
             'switchport trunk allowed vlan none',
             'interface 4444',
             'no switchport trunk native vlan 44',
             'switchport trunk allowed vlan remove 44',
             'interface 4444',
             'switchport trunk allowed vlan remove tag1',
             'interface 4444',
             'switchport trunk allowed vlan remove tag2'])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device', autospec=True)
    def test_add_subports_on_trunk_no_subports(self, mock_exec):
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
    def test_add_subports_on_trunk_subports(self, mock_exec):
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
            ['interface 44',
             'switchport trunk allowed vlan add tag1',
             'interface 44',
             'switchport trunk allowed vlan add tag2'])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device', autospec=True)
    def test_del_subports_on_trunk_no_subports(self, mock_exec):
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
    def test_del_subports_on_trunk_subports(self, mock_exec):
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
            ['interface 44',
             'switchport trunk allowed vlan remove tag1',
             'interface 44',
             'switchport trunk allowed vlan remove tag2'])

    def test__parse_vlan_ports_with_ports(self):
        output = '''VLAN  Name                             Status    Ports
----- -------------------------------- --------- ------
100   VLAN0100                         active    Et1, Et2'''
        result = self.switch._parse_vlan_ports(output, 100)
        self.assertTrue(result)

    def test__parse_vlan_ports_without_ports(self):
        output = '''VLAN  Name                             Status    Ports
----- -------------------------------- --------- ------
100   VLAN0100                         active'''
        result = self.switch._parse_vlan_ports(output, 100)
        self.assertFalse(result)

    def test__parse_vlan_ports_vlan_not_found(self):
        output = '''VLAN  Name                             Status    Ports
----- -------------------------------- --------- ------
200   VLAN0200                         active    Et1'''
        result = self.switch._parse_vlan_ports(output, 100)
        self.assertFalse(result)

    def test__parse_vlan_vni_match(self):
        output = '''Vxlan1 is up, line protocol is up (connected)
  Hardware is Vxlan
  Source interface is Loopback1 and is active with 10.0.0.1
  Replication/Flood Mode is headend with Flood List Source: EVPN
  Remote MAC learning via EVPN
  VNI mapping to VLANs
  Static VLAN to VNI mapping is [100, 5000] [200, 6000]
  Dynamic VLAN to VNI mapping for 'evpn' is
    [300, 7000]'''
        result = self.switch._parse_vlan_vni(output, 100, 5000)
        self.assertTrue(result)

    def test__parse_vlan_vni_no_match(self):
        output = '''Vxlan1 is up, line protocol is up (connected)
  Hardware is Vxlan
  Source interface is Loopback1 and is active with 10.0.0.1
  Replication/Flood Mode is headend with Flood List Source: EVPN
  Remote MAC learning via EVPN
  VNI mapping to VLANs
  Static VLAN to VNI mapping is [100, 5000] [200, 6000]
  Dynamic VLAN to VNI mapping for 'evpn' is
    [300, 7000]'''
        result = self.switch._parse_vlan_vni(output, 100, 9999)
        self.assertFalse(result)

    def test__parse_vlan_vni_vlan_not_found(self):
        output = '''Vxlan1 is up, line protocol is up (connected)
  Hardware is Vxlan
  Source interface is Loopback1 and is active with 10.0.0.1
  Replication/Flood Mode is headend with Flood List Source: EVPN
  Remote MAC learning via EVPN
  VNI mapping to VLANs
  Static VLAN to VNI mapping is [100, 5000] [200, 6000]
  Dynamic VLAN to VNI mapping for 'evpn' is
    [300, 7000]'''
        result = self.switch._parse_vlan_vni(output, 400, 5000)
        self.assertFalse(result)

    # Configuration Tests

    def test_init_default_vxlan_config(self):
        """Test __init__ with default VXLAN configuration."""
        device_cfg = {'device_type': 'netmiko_arista_eos'}
        switch = arista.AristaEos(device_cfg)
        self.assertEqual(switch.vxlan_interface, 'Vxlan1')
        self.assertIsNone(switch.bgp_asn)

    def test_init_custom_vxlan_interface(self):
        """Test __init__ with custom VXLAN interface."""
        device_cfg = {
            'device_type': 'netmiko_arista_eos',
            'vxlan_interface': 'Vxlan2'
        }
        switch = arista.AristaEos(device_cfg)
        self.assertEqual(switch.vxlan_interface, 'Vxlan2')

    def test_init_with_bgp_asn(self):
        """Test __init__ with BGP ASN configuration."""
        device_cfg = {
            'device_type': 'netmiko_arista_eos',
            'ngs_bgp_asn': '65000'
        }
        switch = arista.AristaEos(device_cfg)
        self.assertEqual(switch.bgp_asn, '65000')

    def test_init_with_custom_route_target(self):
        """Test __init__ with custom route-target configuration."""
        device_cfg = {
            'device_type': 'netmiko_arista_eos',
            'ngs_bgp_asn': '65000',
            'ngs_evpn_route_target': '65000:100'
        }
        switch = arista.AristaEos(device_cfg)
        self.assertEqual(switch.evpn_route_target, '65000:100')

    def test_init_default_route_target(self):
        """Test __init__ with default route-target."""
        device_cfg = {
            'device_type': 'netmiko_arista_eos'
        }
        switch = arista.AristaEos(device_cfg)
        self.assertEqual(switch.evpn_route_target, 'auto')

    # EVPN Plug/Unplug Tests

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device',
                return_value='', autospec=True)
    def test_plug_switch_to_network(self, mock_exec):
        """Test plug_switch_to_network with default route-target."""
        device_cfg = {
            'device_type': 'netmiko_arista_eos',
            'ngs_bgp_asn': '65000'
        }
        switch = arista.AristaEos(device_cfg)
        switch.plug_switch_to_network(10100, 100)
        mock_exec.assert_called_with(
            switch,
            ['router bgp 65000', 'vlan 100', 'rd auto',
             'route-target both auto', 'interface Vxlan1',
             'vxlan vlan 100 vni 10100'])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device',
                return_value='', autospec=True)
    def test_plug_switch_to_network_custom_interface(self, mock_exec):
        """Test plug_switch_to_network with custom VXLAN interface."""
        device_cfg = {
            'device_type': 'netmiko_arista_eos',
            'ngs_bgp_asn': '65000',
            'vxlan_interface': 'Vxlan2'
        }
        switch = arista.AristaEos(device_cfg)
        switch.plug_switch_to_network(10100, 100)
        mock_exec.assert_called_with(
            switch,
            ['router bgp 65000', 'vlan 100', 'rd auto',
             'route-target both auto', 'interface Vxlan2',
             'vxlan vlan 100 vni 10100'])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device',
                return_value='', autospec=True)
    def test_plug_switch_to_network_custom_route_target(self, mock_exec):
        """Test plug_switch_to_network with custom route-target."""
        device_cfg = {
            'device_type': 'netmiko_arista_eos',
            'ngs_bgp_asn': '65000',
            'ngs_evpn_route_target': '65000:100'
        }
        switch = arista.AristaEos(device_cfg)
        switch.plug_switch_to_network(10100, 100)
        mock_exec.assert_called_with(
            switch,
            ['router bgp 65000', 'vlan 100', 'rd auto',
             'route-target both 65000:100', 'interface Vxlan1',
             'vxlan vlan 100 vni 10100'])

    def test_plug_switch_to_network_without_bgp_asn(self):
        """Test plug_switch_to_network fails without BGP ASN."""
        device_cfg = {'device_type': 'netmiko_arista_eos'}
        switch = arista.AristaEos(device_cfg)
        self.assertRaises(exc.GenericSwitchNetmikoConfigError,
                          switch.plug_switch_to_network, 10100, 100)

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device',
                return_value='', autospec=True)
    def test_unplug_switch_from_network(self, mock_exec):
        """Test unplug_switch_from_network with BGP EVPN."""
        device_cfg = {
            'device_type': 'netmiko_arista_eos',
            'ngs_bgp_asn': '65000'
        }
        switch = arista.AristaEos(device_cfg)
        switch.unplug_switch_from_network(10100, 100)
        mock_exec.assert_called_with(
            switch,
            ['interface Vxlan1', 'no vxlan vlan 100',
             'router bgp 65000', 'no vlan 100'])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device',
                return_value='', autospec=True)
    def test_unplug_switch_from_network_custom_interface(self, mock_exec):
        """Test unplug_switch_from_network with custom VXLAN interface."""
        device_cfg = {
            'device_type': 'netmiko_arista_eos',
            'ngs_bgp_asn': '65000',
            'vxlan_interface': 'Vxlan2'
        }
        switch = arista.AristaEos(device_cfg)
        switch.unplug_switch_from_network(10100, 100)
        mock_exec.assert_called_with(
            switch,
            ['interface Vxlan2', 'no vxlan vlan 100',
             'router bgp 65000', 'no vlan 100'])

    def test_unplug_switch_from_network_without_bgp_asn(self):
        """Test unplug_switch_from_network fails without BGP ASN."""
        device_cfg = {'device_type': 'netmiko_arista_eos'}
        switch = arista.AristaEos(device_cfg)
        self.assertRaises(exc.GenericSwitchNetmikoConfigError,
                          switch.unplug_switch_from_network, 10100, 100)
