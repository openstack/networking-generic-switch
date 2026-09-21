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

import json
import unittest
from unittest import mock

from networking_generic_switch.devices.netconf_devices import openconfig
from networking_generic_switch.yang_models.openconfig import (
    constants as oc_constants)
from networking_generic_switch.yang_models.openconfig.interfaces \
    .interfaces import Interfaces
from networking_generic_switch.yang_models.openconfig \
    .network_instance.network_instance import NetworkInstances


DEVICE_CFG = {
    'device_type': 'netconf_openconfig',
    'host': 'switch.example.com',
    'username': 'admin',
    'port': '830',
    'password': 'secret',
    'hostkey_verify': 'false',
    'device_params': {'name': 'default'},
    'ngs_manage_vlans': True,
    'ngs_network_name_format': '{network_id}',
    'ngs_max_connections': 1,
}

NETWORK_UUID = 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee'
NETWORK_UUID_HEX = 'aaaaaaaabbbbccccddddeeeeeeeeeeee'


def _make_switch(extra_cfg=None):
    cfg = dict(DEVICE_CFG)
    if extra_cfg:
        cfg.update(extra_cfg)
    return openconfig.NetconfOpenConfigSwitch(cfg, device_name='test-switch')


class TestNetconfOpenConfigSwitchInit(unittest.TestCase):

    def test_defaults(self):
        switch = _make_switch()
        self.assertEqual('default', switch._network_instance)
        self.assertEqual({}, switch._port_id_re_sub)
        self.assertEqual([], switch._disabled_properties)

    def test_custom_network_instance(self):
        switch = _make_switch({'ngs_openconfig_network_instance': 'my-vrf'})
        self.assertEqual('my-vrf', switch._network_instance)

    def test_port_id_re_sub_json_string(self):
        re_sub = json.dumps({'pattern': 'Ethernet', 'repl': 'eth'})
        switch = _make_switch({'ngs_port_id_re_sub': re_sub})
        self.assertEqual('Ethernet', switch._port_id_re_sub['pattern'])
        self.assertEqual('eth', switch._port_id_re_sub['repl'])

    def test_port_id_re_sub_dict(self):
        re_sub = {'pattern': 'Ethernet', 'repl': 'eth'}
        switch = _make_switch({'ngs_port_id_re_sub': re_sub})
        self.assertEqual('Ethernet', switch._port_id_re_sub['pattern'])
        self.assertEqual('eth', switch._port_id_re_sub['repl'])

    def test_disabled_properties_csv(self):
        switch = _make_switch(
            {'ngs_openconfig_disabled_properties': 'port_mtu'})
        self.assertEqual(['port_mtu'], switch._disabled_properties)

    def test_disabled_properties_list(self):
        switch = _make_switch(
            {'ngs_openconfig_disabled_properties': ['port_mtu']})
        self.assertEqual(['port_mtu'], switch._disabled_properties)


class TestPortIdResub(unittest.TestCase):

    def test_no_config(self):
        switch = _make_switch()
        self.assertEqual('Ethernet1/1', switch._port_id_resub('Ethernet1/1'))

    def test_substitution(self):
        re_sub = {'pattern': 'Ethernet', 'repl': 'eth'}
        switch = _make_switch({'ngs_port_id_re_sub': re_sub})
        self.assertEqual('eth1/1', switch._port_id_resub('Ethernet1/1'))

    def test_no_match(self):
        re_sub = {'pattern': 'GigabitEthernet', 'repl': 'ge-'}
        switch = _make_switch({'ngs_port_id_re_sub': re_sub})
        self.assertEqual('Ethernet1/1', switch._port_id_resub('Ethernet1/1'))


class TestAddNetwork(unittest.TestCase):

    def test_returns_network_instances(self):
        switch = _make_switch()
        result = switch._add_network(
            segmentation_id=100, network_name='testnet')
        self.assertEqual(1, len(result))
        self.assertIsInstance(result[0], NetworkInstances)

    def test_vlan_properties(self):
        switch = _make_switch()
        result = switch._add_network(
            segmentation_id=200, network_name='mynet')
        net_instances = result[0]
        net_inst = list(net_instances)[0]
        self.assertEqual('default', net_inst.name)
        vlans = list(net_inst.vlans)
        self.assertEqual(1, len(vlans))
        self.assertEqual(200, vlans[0].vlan_id)
        self.assertEqual('mynet', vlans[0].config.name)
        self.assertEqual(oc_constants.VLAN_ACTIVE, vlans[0].config.status)

    def test_custom_network_instance(self):
        switch = _make_switch({'ngs_openconfig_network_instance': 'prod-vrf'})
        result = switch._add_network(
            segmentation_id=100, network_name='testnet')
        net_inst = list(result[0])[0]
        self.assertEqual('prod-vrf', net_inst.name)


class TestDeleteNetwork(unittest.TestCase):

    def test_returns_network_instances(self):
        switch = _make_switch()
        result = switch._delete_network(
            segmentation_id=100, network_name='testnet')
        self.assertEqual(1, len(result))
        self.assertIsInstance(result[0], NetworkInstances)

    def test_vlan_marked_for_removal(self):
        switch = _make_switch()
        result = switch._delete_network(
            segmentation_id=300, network_name='oldnet')
        net_inst = list(result[0])[0]
        vlans = list(net_inst.vlans)
        self.assertEqual(1, len(vlans))
        vlan_obj = vlans[0]
        self.assertEqual(300, vlan_obj.vlan_id)
        self.assertEqual('remove', vlan_obj.operation)
        self.assertEqual('neutron-DELETED-300', vlan_obj.config.name)
        self.assertEqual(oc_constants.VLAN_SUSPENDED, vlan_obj.config.status)


class TestAddNetworkToTrunk(unittest.TestCase):

    def test_returns_interfaces(self):
        switch = _make_switch()
        result = switch._add_network_to_trunk(
            segmentation_id=100, trunk_ports=['Ethernet1/48', 'Ethernet1/49'])
        self.assertEqual(1, len(result))
        self.assertIsInstance(result[0], Interfaces)

    def test_trunk_ports_created(self):
        switch = _make_switch()
        result = switch._add_network_to_trunk(
            segmentation_id=200,
            trunk_ports=['Ethernet1/48', 'Ethernet1/49'])
        ifaces = result[0]
        iface_list = list(ifaces)
        self.assertEqual(2, len(iface_list))
        for iface in iface_list:
            sv = iface.ethernet.switched_vlan
            self.assertEqual(oc_constants.VLAN_MODE_TRUNK,
                             sv.config.interface_mode)
            self.assertIn(200, sv.config.trunk_vlans)

    def test_port_id_resub_applied(self):
        re_sub = {'pattern': 'Ethernet', 'repl': 'eth'}
        switch = _make_switch({'ngs_port_id_re_sub': re_sub})
        result = switch._add_network_to_trunk(
            segmentation_id=100, trunk_ports=['Ethernet1/48'])
        iface = list(result[0])[0]
        self.assertEqual('eth1/48', iface.name)

    def test_physnet_vlans_replace_operation(self):
        switch = _make_switch()
        result = switch._add_network_to_trunk(
            segmentation_id=100,
            trunk_ports=['Ethernet1/48', 'Ethernet1/49'],
            physnet_vlans={100, 200, 300})
        ifaces = result[0]
        for iface in ifaces:
            sv = iface.ethernet.switched_vlan
            self.assertEqual('replace', sv.config.operation)
            self.assertEqual(oc_constants.VLAN_MODE_TRUNK,
                             sv.config.interface_mode)
            self.assertIn(100, sv.config.trunk_vlans)
            self.assertIn(200, sv.config.trunk_vlans)
            self.assertIn(300, sv.config.trunk_vlans)
            self.assertEqual(3, len(sv.config.trunk_vlans))

    def test_physnet_vlans_none_uses_merge(self):
        switch = _make_switch()
        result = switch._add_network_to_trunk(
            segmentation_id=100,
            trunk_ports=['Ethernet1/48'],
            physnet_vlans=None)
        iface = list(result[0])[0]
        sv = iface.ethernet.switched_vlan
        self.assertEqual('merge', sv.config.operation)
        self.assertIn(100, sv.config.trunk_vlans)
        self.assertEqual(1, len(sv.config.trunk_vlans))

    def test_physnet_vlans_empty_set_replace(self):
        switch = _make_switch()
        result = switch._add_network_to_trunk(
            segmentation_id=100,
            trunk_ports=['Ethernet1/48'],
            physnet_vlans=set())
        iface = list(result[0])[0]
        sv = iface.ethernet.switched_vlan
        self.assertEqual('replace', sv.config.operation)
        self.assertEqual(0, len(sv.config.trunk_vlans))


class TestRemoveNetworkFromTrunk(unittest.TestCase):

    def test_returns_interfaces(self):
        switch = _make_switch()
        result = switch._remove_network_from_trunk(
            segmentation_id=100, trunk_ports=['Ethernet1/48'])
        self.assertEqual(1, len(result))
        self.assertIsInstance(result[0], Interfaces)

    def test_trunk_vlan_marked_for_removal(self):
        switch = _make_switch()
        result = switch._remove_network_from_trunk(
            segmentation_id=200,
            trunk_ports=['Ethernet1/48', 'Ethernet1/49'])
        ifaces = result[0]
        iface_list = list(ifaces)
        self.assertEqual(2, len(iface_list))
        for iface in iface_list:
            sv = iface.ethernet.switched_vlan
            self.assertEqual(oc_constants.VLAN_MODE_TRUNK,
                             sv.config.interface_mode)
            self.assertIn(200, sv.config.trunk_vlans._removals)

    def test_port_id_resub_applied(self):
        re_sub = {'pattern': 'Ethernet', 'repl': 'eth'}
        switch = _make_switch({'ngs_port_id_re_sub': re_sub})
        result = switch._remove_network_from_trunk(
            segmentation_id=100, trunk_ports=['Ethernet1/48'])
        iface = list(result[0])[0]
        self.assertEqual('eth1/48', iface.name)

    def test_physnet_vlans_replace_operation(self):
        switch = _make_switch()
        result = switch._remove_network_from_trunk(
            segmentation_id=100,
            trunk_ports=['Ethernet1/48', 'Ethernet1/49'],
            physnet_vlans={200, 300})
        ifaces = result[0]
        for iface in ifaces:
            sv = iface.ethernet.switched_vlan
            self.assertEqual('replace', sv.config.operation)
            self.assertEqual(oc_constants.VLAN_MODE_TRUNK,
                             sv.config.interface_mode)
            self.assertIn(200, sv.config.trunk_vlans)
            self.assertIn(300, sv.config.trunk_vlans)
            self.assertNotIn(100, sv.config.trunk_vlans)
            self.assertEqual(2, len(sv.config.trunk_vlans))
            self.assertEqual(0, len(sv.config.trunk_vlans._removals))

    def test_physnet_vlans_none_uses_per_element_remove(self):
        switch = _make_switch()
        result = switch._remove_network_from_trunk(
            segmentation_id=200,
            trunk_ports=['Ethernet1/48'],
            physnet_vlans=None)
        iface = list(result[0])[0]
        sv = iface.ethernet.switched_vlan
        self.assertEqual('merge', sv.config.operation)
        self.assertIn(200, sv.config.trunk_vlans._removals)

    def test_physnet_vlans_empty_set_replace(self):
        switch = _make_switch()
        result = switch._remove_network_from_trunk(
            segmentation_id=100,
            trunk_ports=['Ethernet1/48'],
            physnet_vlans=set())
        iface = list(result[0])[0]
        sv = iface.ethernet.switched_vlan
        self.assertEqual('replace', sv.config.operation)
        self.assertEqual(0, len(sv.config.trunk_vlans))
        self.assertEqual(0, len(sv.config.trunk_vlans._removals))


class TestPlugPortToNetwork(unittest.TestCase):

    def test_returns_interfaces(self):
        switch = _make_switch()
        result = switch._plug_port_to_network(
            port_id='Ethernet1/1', segmentation_id=100)
        self.assertEqual(1, len(result))
        self.assertIsInstance(result[0], Interfaces)

    def test_interface_properties(self):
        switch = _make_switch()
        result = switch._plug_port_to_network(
            port_id='Ethernet1/1', segmentation_id=200)
        ifaces = result[0]
        iface_list = list(ifaces)
        self.assertEqual(1, len(iface_list))
        iface = iface_list[0]
        self.assertEqual('Ethernet1/1', iface.name)
        self.assertIsNone(iface.config.enabled)

    def test_switched_vlan_access(self):
        switch = _make_switch()
        result = switch._plug_port_to_network(
            port_id='Ethernet1/1', segmentation_id=150)
        iface = list(result[0])[0]
        sv = iface.ethernet.switched_vlan
        self.assertEqual('replace', sv.config.operation)
        self.assertEqual(oc_constants.VLAN_MODE_ACCESS,
                         sv.config.interface_mode)
        self.assertEqual(150, sv.config.access_vlan)

    def test_trunk_details_sets_trunk_mode(self):
        switch = _make_switch()
        trunk_details = {
            'sub_ports': [
                {'segmentation_id': 200},
                {'segmentation_id': 300},
            ],
        }
        result = switch._plug_port_to_network(
            port_id='Ethernet1/1', segmentation_id=100,
            trunk_details=trunk_details)
        iface = list(result[0])[0]
        sv = iface.ethernet.switched_vlan
        self.assertEqual('replace', sv.config.operation)
        self.assertEqual(oc_constants.VLAN_MODE_TRUNK,
                         sv.config.interface_mode)
        self.assertEqual(100, sv.config.native_vlan)
        self.assertIn(200, sv.config.trunk_vlans)
        self.assertIn(300, sv.config.trunk_vlans)
        self.assertEqual(2, len(sv.config.trunk_vlans))

    def test_trunk_details_empty_subports(self):
        switch = _make_switch()
        trunk_details = {
            'sub_ports': [],
        }
        result = switch._plug_port_to_network(
            port_id='Ethernet1/1', segmentation_id=100,
            trunk_details=trunk_details)
        iface = list(result[0])[0]
        sv = iface.ethernet.switched_vlan
        self.assertEqual('replace', sv.config.operation)
        self.assertEqual(oc_constants.VLAN_MODE_TRUNK,
                         sv.config.interface_mode)
        self.assertEqual(100, sv.config.native_vlan)
        self.assertEqual(0, len(sv.config.trunk_vlans))

    def test_trunk_details_none_uses_access_mode(self):
        switch = _make_switch()
        result = switch._plug_port_to_network(
            port_id='Ethernet1/1', segmentation_id=100,
            trunk_details=None)
        iface = list(result[0])[0]
        sv = iface.ethernet.switched_vlan
        self.assertEqual(oc_constants.VLAN_MODE_ACCESS,
                         sv.config.interface_mode)
        self.assertEqual(100, sv.config.access_vlan)

    def test_port_id_resub_applied(self):
        re_sub = {'pattern': 'Ethernet', 'repl': 'eth'}
        switch = _make_switch({'ngs_port_id_re_sub': re_sub})
        result = switch._plug_port_to_network(
            port_id='Ethernet1/1', segmentation_id=100)
        iface = list(result[0])[0]
        self.assertEqual('eth1/1', iface.name)

    def test_port_id_resub_applied_with_trunk_details(self):
        re_sub = {'pattern': 'Ethernet', 'repl': 'eth'}
        switch = _make_switch({'ngs_port_id_re_sub': re_sub})
        trunk_details = {
            'sub_ports': [{'segmentation_id': 200}],
        }
        result = switch._plug_port_to_network(
            port_id='Ethernet1/1', segmentation_id=100,
            trunk_details=trunk_details)
        iface = list(result[0])[0]
        self.assertEqual('eth1/1', iface.name)


class TestDeletePort(unittest.TestCase):

    def test_returns_interfaces(self):
        switch = _make_switch()
        result = switch._delete_port(
            port_id='Ethernet1/1', segmentation_id=100)
        self.assertEqual(1, len(result))
        self.assertIsInstance(result[0], Interfaces)

    def test_interface_config_remove(self):
        switch = _make_switch()
        result = switch._delete_port(
            port_id='Ethernet1/1', segmentation_id=100)
        iface = list(result[0])[0]
        self.assertEqual('remove', iface.config.operation)
        self.assertEqual('', iface.config.description)
        self.assertIsNone(iface.config.enabled)

    def test_switched_vlan_remove(self):
        switch = _make_switch()
        result = switch._delete_port(
            port_id='Ethernet1/1', segmentation_id=100)
        iface = list(result[0])[0]
        sv = iface.ethernet.switched_vlan
        self.assertEqual('remove', sv.config.operation)

    def test_port_id_resub_applied(self):
        re_sub = {'pattern': 'Ethernet', 'repl': 'eth'}
        switch = _make_switch({'ngs_port_id_re_sub': re_sub})
        result = switch._delete_port(
            port_id='Ethernet1/1', segmentation_id=100)
        iface = list(result[0])[0]
        self.assertEqual('eth1/1', iface.name)


class TestEnablePort(unittest.TestCase):

    def test_returns_interfaces(self):
        switch = _make_switch()
        result = switch._enable_port(port_id='Ethernet1/1')
        self.assertEqual(1, len(result))
        self.assertIsInstance(result[0], Interfaces)

    def test_enabled_true(self):
        switch = _make_switch()
        result = switch._enable_port(port_id='Ethernet1/1')
        iface = list(result[0])[0]
        self.assertTrue(iface.config.enabled)

    def test_port_id_resub_applied(self):
        re_sub = {'pattern': 'Ethernet', 'repl': 'eth'}
        switch = _make_switch({'ngs_port_id_re_sub': re_sub})
        result = switch._enable_port(port_id='Ethernet1/1')
        iface = list(result[0])[0]
        self.assertEqual('eth1/1', iface.name)


class TestDisablePort(unittest.TestCase):

    def test_returns_interfaces(self):
        switch = _make_switch()
        result = switch._disable_port(port_id='Ethernet1/1')
        self.assertEqual(1, len(result))
        self.assertIsInstance(result[0], Interfaces)

    def test_enabled_false(self):
        switch = _make_switch()
        result = switch._disable_port(port_id='Ethernet1/1')
        iface = list(result[0])[0]
        self.assertFalse(iface.config.enabled)

    def test_port_id_resub_applied(self):
        re_sub = {'pattern': 'Ethernet', 'repl': 'eth'}
        switch = _make_switch({'ngs_port_id_re_sub': re_sub})
        result = switch._disable_port(port_id='Ethernet1/1')
        iface = list(result[0])[0]
        self.assertEqual('eth1/1', iface.name)


class TestSupportTrunkOnPorts(unittest.TestCase):

    def test_returns_true(self):
        switch = _make_switch()
        self.assertTrue(switch.support_trunk_on_ports)


class TestAddSubportsOnTrunk(unittest.TestCase):

    BINDING_PROFILE = {
        'local_link_information': [
            {'port_id': 'Ethernet1/1', 'switch_info': 'test-switch'}
        ]
    }

    def test_returns_interfaces(self):
        switch = _make_switch()
        result = switch._add_subports_on_trunk(
            binding_profile=self.BINDING_PROFILE,
            port_id='Ethernet1/1',
            subports=[{'segmentation_id': 200}])
        self.assertEqual(1, len(result))
        self.assertIsInstance(result[0], Interfaces)

    def test_delta_merge_without_trunk_details(self):
        switch = _make_switch()
        result = switch._add_subports_on_trunk(
            binding_profile=self.BINDING_PROFILE,
            port_id='Ethernet1/1',
            subports=[{'segmentation_id': 200},
                      {'segmentation_id': 300}])
        iface = list(result[0])[0]
        sv = iface.ethernet.switched_vlan
        self.assertEqual(oc_constants.VLAN_MODE_TRUNK,
                         sv.config.interface_mode)
        self.assertEqual('merge', sv.config.operation)
        self.assertIn(200, sv.config.trunk_vlans)
        self.assertIn(300, sv.config.trunk_vlans)
        self.assertEqual(2, len(sv.config.trunk_vlans))

    def test_converge_replace_with_trunk_details(self):
        switch = _make_switch()
        trunk_details = {
            'segmentation_id': 100,
            'sub_ports': [
                {'segmentation_id': 200},
                {'segmentation_id': 300},
                {'segmentation_id': 400},
            ],
        }
        result = switch._add_subports_on_trunk(
            binding_profile=self.BINDING_PROFILE,
            port_id='Ethernet1/1',
            subports=[{'segmentation_id': 400}],
            trunk_details=trunk_details)
        iface = list(result[0])[0]
        sv = iface.ethernet.switched_vlan
        self.assertEqual('replace', sv.config.operation)
        self.assertEqual(oc_constants.VLAN_MODE_TRUNK,
                         sv.config.interface_mode)
        self.assertEqual(100, sv.config.native_vlan)
        self.assertIn(200, sv.config.trunk_vlans)
        self.assertIn(300, sv.config.trunk_vlans)
        self.assertIn(400, sv.config.trunk_vlans)
        self.assertEqual(3, len(sv.config.trunk_vlans))

    def test_converge_no_native_vlan(self):
        switch = _make_switch()
        trunk_details = {
            'sub_ports': [{'segmentation_id': 200}],
        }
        result = switch._add_subports_on_trunk(
            binding_profile=self.BINDING_PROFILE,
            port_id='Ethernet1/1',
            subports=[{'segmentation_id': 200}],
            trunk_details=trunk_details)
        iface = list(result[0])[0]
        sv = iface.ethernet.switched_vlan
        self.assertEqual('replace', sv.config.operation)
        self.assertIsNone(sv.config.native_vlan)
        self.assertIn(200, sv.config.trunk_vlans)

    def test_port_id_resub_applied(self):
        re_sub = {'pattern': 'Ethernet', 'repl': 'eth'}
        switch = _make_switch({'ngs_port_id_re_sub': re_sub})
        result = switch._add_subports_on_trunk(
            binding_profile=self.BINDING_PROFILE,
            port_id='Ethernet1/1',
            subports=[{'segmentation_id': 200}])
        iface = list(result[0])[0]
        self.assertEqual('eth1/1', iface.name)


class TestDelSubportsOnTrunk(unittest.TestCase):

    BINDING_PROFILE = {
        'local_link_information': [
            {'port_id': 'Ethernet1/1', 'switch_info': 'test-switch'}
        ]
    }

    def test_returns_interfaces(self):
        switch = _make_switch()
        result = switch._del_subports_on_trunk(
            binding_profile=self.BINDING_PROFILE,
            port_id='Ethernet1/1',
            subports=[{'segmentation_id': 200}])
        self.assertEqual(1, len(result))
        self.assertIsInstance(result[0], Interfaces)

    def test_delta_remove_without_trunk_details(self):
        switch = _make_switch()
        result = switch._del_subports_on_trunk(
            binding_profile=self.BINDING_PROFILE,
            port_id='Ethernet1/1',
            subports=[{'segmentation_id': 200},
                      {'segmentation_id': 300}])
        iface = list(result[0])[0]
        sv = iface.ethernet.switched_vlan
        self.assertEqual(oc_constants.VLAN_MODE_TRUNK,
                         sv.config.interface_mode)
        self.assertEqual('merge', sv.config.operation)
        self.assertIn(200, sv.config.trunk_vlans._removals)
        self.assertIn(300, sv.config.trunk_vlans._removals)

    def test_converge_replace_with_remaining_subports(self):
        switch = _make_switch()
        trunk_details = {
            'segmentation_id': 100,
            'sub_ports': [
                {'segmentation_id': 300},
                {'segmentation_id': 400},
            ],
        }
        result = switch._del_subports_on_trunk(
            binding_profile=self.BINDING_PROFILE,
            port_id='Ethernet1/1',
            subports=[{'segmentation_id': 200}],
            trunk_details=trunk_details)
        iface = list(result[0])[0]
        sv = iface.ethernet.switched_vlan
        self.assertEqual('replace', sv.config.operation)
        self.assertEqual(oc_constants.VLAN_MODE_TRUNK,
                         sv.config.interface_mode)
        self.assertEqual(100, sv.config.native_vlan)
        self.assertIn(300, sv.config.trunk_vlans)
        self.assertIn(400, sv.config.trunk_vlans)
        self.assertNotIn(200, sv.config.trunk_vlans)
        self.assertEqual(2, len(sv.config.trunk_vlans))

    def test_converge_remove_all_reverts_to_access(self):
        switch = _make_switch()
        trunk_details = {
            'segmentation_id': 100,
            'sub_ports': [],
        }
        result = switch._del_subports_on_trunk(
            binding_profile=self.BINDING_PROFILE,
            port_id='Ethernet1/1',
            subports=[{'segmentation_id': 200}],
            trunk_details=trunk_details)
        iface = list(result[0])[0]
        sv = iface.ethernet.switched_vlan
        self.assertEqual('replace', sv.config.operation)
        self.assertEqual(oc_constants.VLAN_MODE_ACCESS,
                         sv.config.interface_mode)
        self.assertEqual(100, sv.config.access_vlan)
        self.assertEqual(0, len(sv.config.trunk_vlans))

    def test_converge_remove_all_no_native_vlan(self):
        switch = _make_switch()
        trunk_details = {
            'sub_ports': [],
        }
        result = switch._del_subports_on_trunk(
            binding_profile=self.BINDING_PROFILE,
            port_id='Ethernet1/1',
            subports=[{'segmentation_id': 200}],
            trunk_details=trunk_details)
        iface = list(result[0])[0]
        sv = iface.ethernet.switched_vlan
        self.assertEqual('replace', sv.config.operation)
        self.assertEqual(oc_constants.VLAN_MODE_ACCESS,
                         sv.config.interface_mode)
        self.assertIsNone(sv.config.access_vlan)

    def test_port_id_resub_applied(self):
        re_sub = {'pattern': 'Ethernet', 'repl': 'eth'}
        switch = _make_switch({'ngs_port_id_re_sub': re_sub})
        result = switch._del_subports_on_trunk(
            binding_profile=self.BINDING_PROFILE,
            port_id='Ethernet1/1',
            subports=[{'segmentation_id': 200}])
        iface = list(result[0])[0]
        self.assertEqual('eth1/1', iface.name)


class TestDispatchIntegration(unittest.TestCase):
    """Test end-to-end dispatch through base class methods."""

    def test_add_network_dispatch(self):
        switch = _make_switch()
        with mock.patch.object(switch, 'send_config_to_device',
                               autospec=True) as mock_send:
            switch.add_network(100, NETWORK_UUID)
        mock_send.assert_called_once()
        config = mock_send.call_args[0][0]
        self.assertIsInstance(config[0], NetworkInstances)

    def test_del_network_dispatch(self):
        switch = _make_switch()
        with mock.patch.object(switch, 'send_config_to_device',
                               autospec=True) as mock_send:
            switch.del_network(100, NETWORK_UUID)
        mock_send.assert_called_once()
        config = mock_send.call_args[0][0]
        self.assertIsInstance(config[0], NetworkInstances)

    def test_plug_port_to_network_dispatch(self):
        switch = _make_switch()
        with mock.patch.object(switch, 'send_config_to_device',
                               autospec=True) as mock_send:
            switch.plug_port_to_network('Ethernet1/1', 100)
        mock_send.assert_called_once()
        config = mock_send.call_args[0][0]
        self.assertIsInstance(config[0], Interfaces)

    def test_delete_port_dispatch(self):
        switch = _make_switch()
        with mock.patch.object(switch, 'send_config_to_device',
                               autospec=True) as mock_send:
            switch.delete_port('Ethernet1/1', 100)
        mock_send.assert_called_once()
        config = mock_send.call_args[0][0]
        self.assertIsInstance(config[0], Interfaces)

    def test_add_network_skips_without_vlan_management(self):
        switch = _make_switch({'ngs_manage_vlans': 'false'})
        with mock.patch.object(switch, 'send_config_to_device',
                               autospec=True) as mock_send:
            switch.add_network(100, NETWORK_UUID)
        mock_send.assert_not_called()

    def test_add_network_vlan_name_from_hex_uuid(self):
        switch = _make_switch()
        with mock.patch.object(switch, 'send_config_to_device',
                               autospec=True) as mock_send:
            switch.add_network(100, NETWORK_UUID)
        config = mock_send.call_args[0][0]
        net_inst = list(config[0])[0]
        vlan_obj = list(net_inst.vlans)[0]
        self.assertEqual(NETWORK_UUID_HEX, vlan_obj.config.name)

    def test_del_network_has_deleted_name(self):
        switch = _make_switch()
        with mock.patch.object(switch, 'send_config_to_device',
                               autospec=True) as mock_send:
            switch.del_network(100, NETWORK_UUID)
        config = mock_send.call_args[0][0]
        net_inst = list(config[0])[0]
        vlan_obj = list(net_inst.vlans)[0]
        self.assertEqual('neutron-DELETED-100', vlan_obj.config.name)

    def test_add_network_with_trunk_ports(self):
        switch = _make_switch({'ngs_trunk_ports': 'Ethernet1/48,Ethernet1/49'})
        with mock.patch.object(switch, 'send_config_to_device',
                               autospec=True) as mock_send:
            switch.add_network(100, NETWORK_UUID)
        mock_send.assert_called_once()
        config = mock_send.call_args[0][0]
        self.assertEqual(2, len(config))
        self.assertIsInstance(config[0], NetworkInstances)
        self.assertIsInstance(config[1], Interfaces)
        iface_list = list(config[1])
        self.assertEqual(2, len(iface_list))
        for iface in iface_list:
            sv = iface.ethernet.switched_vlan
            self.assertEqual(oc_constants.VLAN_MODE_TRUNK,
                             sv.config.interface_mode)
            self.assertIn(100, sv.config.trunk_vlans)

    def test_del_network_with_trunk_ports(self):
        switch = _make_switch({'ngs_trunk_ports': 'Ethernet1/48,Ethernet1/49'})
        with mock.patch.object(switch, 'send_config_to_device',
                               autospec=True) as mock_send:
            switch.del_network(100, NETWORK_UUID)
        mock_send.assert_called_once()
        config = mock_send.call_args[0][0]
        self.assertEqual(2, len(config))
        self.assertIsInstance(config[0], Interfaces)
        self.assertIsInstance(config[1], NetworkInstances)
        iface_list = list(config[0])
        self.assertEqual(2, len(iface_list))
        for iface in iface_list:
            sv = iface.ethernet.switched_vlan
            self.assertIn(100, sv.config.trunk_vlans._removals)

    def test_add_network_with_trunk_ports_physnet_vlans(self):
        switch = _make_switch({'ngs_trunk_ports': 'Ethernet1/48,Ethernet1/49'})
        with mock.patch.object(switch, 'send_config_to_device',
                               autospec=True) as mock_send:
            switch.add_network(100, NETWORK_UUID,
                               physnet_vlans={100, 200, 300})
        mock_send.assert_called_once()
        config = mock_send.call_args[0][0]
        self.assertEqual(2, len(config))
        self.assertIsInstance(config[0], NetworkInstances)
        self.assertIsInstance(config[1], Interfaces)
        iface_list = list(config[1])
        self.assertEqual(2, len(iface_list))
        for iface in iface_list:
            sv = iface.ethernet.switched_vlan
            self.assertEqual('replace', sv.config.operation)
            self.assertEqual(oc_constants.VLAN_MODE_TRUNK,
                             sv.config.interface_mode)
            self.assertIn(100, sv.config.trunk_vlans)
            self.assertIn(200, sv.config.trunk_vlans)
            self.assertIn(300, sv.config.trunk_vlans)

    def test_del_network_with_trunk_ports_physnet_vlans(self):
        switch = _make_switch({'ngs_trunk_ports': 'Ethernet1/48,Ethernet1/49'})
        with mock.patch.object(switch, 'send_config_to_device',
                               autospec=True) as mock_send:
            switch.del_network(100, NETWORK_UUID,
                               physnet_vlans={200, 300})
        mock_send.assert_called_once()
        config = mock_send.call_args[0][0]
        self.assertEqual(2, len(config))
        self.assertIsInstance(config[0], Interfaces)
        self.assertIsInstance(config[1], NetworkInstances)
        iface_list = list(config[0])
        self.assertEqual(2, len(iface_list))
        for iface in iface_list:
            sv = iface.ethernet.switched_vlan
            self.assertEqual('replace', sv.config.operation)
            self.assertIn(200, sv.config.trunk_vlans)
            self.assertIn(300, sv.config.trunk_vlans)
            self.assertNotIn(100, sv.config.trunk_vlans)
            self.assertEqual(0, len(sv.config.trunk_vlans._removals))

    def test_plug_port_with_disable_inactive(self):
        switch = _make_switch({'ngs_disable_inactive_ports': 'true'})
        with mock.patch.object(switch, 'send_config_to_device',
                               autospec=True) as mock_send:
            switch.plug_port_to_network('Ethernet1/1', 100)
        mock_send.assert_called_once()
        config = mock_send.call_args[0][0]
        self.assertEqual(2, len(config))
        enable_iface = list(config[0])[0]
        self.assertTrue(enable_iface.config.enabled)
        plug_iface = list(config[1])[0]
        sv = plug_iface.ethernet.switched_vlan
        self.assertEqual(oc_constants.VLAN_MODE_ACCESS,
                         sv.config.interface_mode)

    def test_plug_port_no_enable_without_disable_inactive(self):
        switch = _make_switch()
        with mock.patch.object(switch, 'send_config_to_device',
                               autospec=True) as mock_send:
            switch.plug_port_to_network('Ethernet1/1', 100)
        config = mock_send.call_args[0][0]
        self.assertEqual(1, len(config))

    def test_plug_port_clears_default_vlan(self):
        switch = _make_switch({'ngs_port_default_vlan': '1'})
        with mock.patch.object(switch, 'send_config_to_device',
                               autospec=True) as mock_send:
            switch.plug_port_to_network('Ethernet1/1', 100)
        mock_send.assert_called_once()
        config = mock_send.call_args[0][0]
        self.assertEqual(2, len(config))
        clear_iface = list(config[0])[0]
        self.assertEqual('remove',
                         clear_iface.ethernet.switched_vlan.config.operation)

    def test_delete_port_restores_default_vlan(self):
        switch = _make_switch({'ngs_port_default_vlan': '1'})
        with mock.patch.object(switch, 'send_config_to_device',
                               autospec=True) as mock_send:
            switch.delete_port('Ethernet1/1', 100)
        mock_send.assert_called_once()
        config = mock_send.call_args[0][0]
        self.assertEqual(3, len(config))
        self.assertIsInstance(config[0], Interfaces)
        self.assertIsInstance(config[1], NetworkInstances)
        self.assertIsInstance(config[2], Interfaces)

    def test_delete_port_with_disable_inactive(self):
        switch = _make_switch({'ngs_disable_inactive_ports': 'true'})
        with mock.patch.object(switch, 'send_config_to_device',
                               autospec=True) as mock_send:
            switch.delete_port('Ethernet1/1', 100)
        mock_send.assert_called_once()
        config = mock_send.call_args[0][0]
        self.assertEqual(2, len(config))
        disable_iface = list(config[1])[0]
        self.assertFalse(disable_iface.config.enabled)

    def test_delete_port_no_disable_without_disable_inactive(self):
        switch = _make_switch()
        with mock.patch.object(switch, 'send_config_to_device',
                               autospec=True) as mock_send:
            switch.delete_port('Ethernet1/1', 100)
        config = mock_send.call_args[0][0]
        self.assertEqual(1, len(config))

    def test_plug_port_with_trunk_details(self):
        switch = _make_switch()
        trunk_details = {
            'sub_ports': [
                {'segmentation_id': 200},
                {'segmentation_id': 300},
            ],
        }
        with mock.patch.object(switch, 'send_config_to_device',
                               autospec=True) as mock_send:
            switch.plug_port_to_network(
                'Ethernet1/1', 100, trunk_details=trunk_details)
        mock_send.assert_called_once()
        config = mock_send.call_args[0][0]
        iface = list(config[0])[0]
        sv = iface.ethernet.switched_vlan
        self.assertEqual('replace', sv.config.operation)
        self.assertEqual(oc_constants.VLAN_MODE_TRUNK,
                         sv.config.interface_mode)
        self.assertEqual(100, sv.config.native_vlan)
        self.assertIn(200, sv.config.trunk_vlans)
        self.assertIn(300, sv.config.trunk_vlans)

    def test_plug_port_with_trunk_details_and_default_vlan(self):
        switch = _make_switch({'ngs_port_default_vlan': '1'})
        trunk_details = {
            'sub_ports': [
                {'segmentation_id': 200},
            ],
        }
        with mock.patch.object(switch, 'send_config_to_device',
                               autospec=True) as mock_send:
            switch.plug_port_to_network(
                'Ethernet1/1', 100, trunk_details=trunk_details)
        mock_send.assert_called_once()
        config = mock_send.call_args[0][0]
        self.assertEqual(2, len(config))
        clear_iface = list(config[0])[0]
        self.assertEqual('remove',
                         clear_iface.ethernet.switched_vlan.config.operation)
        plug_iface = list(config[1])[0]
        sv = plug_iface.ethernet.switched_vlan
        self.assertEqual(oc_constants.VLAN_MODE_TRUNK,
                         sv.config.interface_mode)
        self.assertEqual(100, sv.config.native_vlan)
        self.assertIn(200, sv.config.trunk_vlans)

    def test_delete_port_with_trunk_details(self):
        switch = _make_switch()
        trunk_details = {
            'sub_ports': [
                {'segmentation_id': 200},
                {'segmentation_id': 300},
            ],
        }
        with mock.patch.object(switch, 'send_config_to_device',
                               autospec=True) as mock_send:
            switch.delete_port(
                'Ethernet1/1', 100, trunk_details=trunk_details)
        mock_send.assert_called_once()
        config = mock_send.call_args[0][0]
        self.assertEqual(1, len(config))
        iface = list(config[0])[0]
        sv = iface.ethernet.switched_vlan
        self.assertEqual('remove', sv.config.operation)

    def test_delete_port_with_trunk_details_restores_default_vlan(self):
        switch = _make_switch({'ngs_port_default_vlan': '1'})
        trunk_details = {
            'sub_ports': [
                {'segmentation_id': 200},
            ],
        }
        with mock.patch.object(switch, 'send_config_to_device',
                               autospec=True) as mock_send:
            switch.delete_port(
                'Ethernet1/1', 100, trunk_details=trunk_details)
        mock_send.assert_called_once()
        config = mock_send.call_args[0][0]
        self.assertEqual(3, len(config))
        self.assertIsInstance(config[0], Interfaces)
        self.assertIsInstance(config[1], NetworkInstances)
        self.assertIsInstance(config[2], Interfaces)
        restore_iface = list(config[2])[0]
        sv = restore_iface.ethernet.switched_vlan
        self.assertEqual(oc_constants.VLAN_MODE_ACCESS,
                         sv.config.interface_mode)

    def test_add_subports_on_trunk_dispatch(self):
        switch = _make_switch()
        binding_profile = {
            'local_link_information': [
                {'port_id': 'Ethernet1/1', 'switch_info': 'test-switch'}
            ]
        }
        with mock.patch.object(switch, 'send_config_to_device',
                               autospec=True) as mock_send:
            switch.add_subports_on_trunk(
                binding_profile, 'Ethernet1/1',
                [{'segmentation_id': 200}])
        mock_send.assert_called_once()
        config = mock_send.call_args[0][0]
        self.assertIsInstance(config[0], Interfaces)

    def test_del_subports_on_trunk_dispatch(self):
        switch = _make_switch()
        binding_profile = {
            'local_link_information': [
                {'port_id': 'Ethernet1/1', 'switch_info': 'test-switch'}
            ]
        }
        with mock.patch.object(switch, 'send_config_to_device',
                               autospec=True) as mock_send:
            switch.del_subports_on_trunk(
                binding_profile, 'Ethernet1/1',
                [{'segmentation_id': 200}])
        mock_send.assert_called_once()
        config = mock_send.call_args[0][0]
        self.assertIsInstance(config[0], Interfaces)

    def test_add_subports_on_trunk_dispatch_with_trunk_details(self):
        switch = _make_switch()
        binding_profile = {
            'local_link_information': [
                {'port_id': 'Ethernet1/1', 'switch_info': 'test-switch'}
            ]
        }
        trunk_details = {
            'segmentation_id': 100,
            'sub_ports': [
                {'segmentation_id': 200},
                {'segmentation_id': 300},
            ],
        }
        with mock.patch.object(switch, 'send_config_to_device',
                               autospec=True) as mock_send:
            switch.add_subports_on_trunk(
                binding_profile, 'Ethernet1/1',
                [{'segmentation_id': 300}],
                trunk_details=trunk_details)
        mock_send.assert_called_once()
        config = mock_send.call_args[0][0]
        iface = list(config[0])[0]
        sv = iface.ethernet.switched_vlan
        self.assertEqual('replace', sv.config.operation)
        self.assertEqual(100, sv.config.native_vlan)
        self.assertIn(200, sv.config.trunk_vlans)
        self.assertIn(300, sv.config.trunk_vlans)

    def test_del_subports_on_trunk_dispatch_with_trunk_details(self):
        switch = _make_switch()
        binding_profile = {
            'local_link_information': [
                {'port_id': 'Ethernet1/1', 'switch_info': 'test-switch'}
            ]
        }
        trunk_details = {
            'segmentation_id': 100,
            'sub_ports': [
                {'segmentation_id': 300},
            ],
        }
        with mock.patch.object(switch, 'send_config_to_device',
                               autospec=True) as mock_send:
            switch.del_subports_on_trunk(
                binding_profile, 'Ethernet1/1',
                [{'segmentation_id': 200}],
                trunk_details=trunk_details)
        mock_send.assert_called_once()
        config = mock_send.call_args[0][0]
        iface = list(config[0])[0]
        sv = iface.ethernet.switched_vlan
        self.assertEqual('replace', sv.config.operation)
        self.assertEqual(100, sv.config.native_vlan)
        self.assertIn(300, sv.config.trunk_vlans)
        self.assertNotIn(200, sv.config.trunk_vlans)
