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

from networking_generic_switch.devices.restconf_devices import openconfig
from networking_generic_switch.yang_models.openconfig import (
    constants as oc_constants)


DEVICE_CFG = {
    'device_type': 'restconf_openconfig',
    'host': 'switch.example.com',
    'username': 'admin',
    'password': 'secret',
    'ngs_manage_vlans': True,
    'ngs_network_name_format': '{network_id}',
    'ngs_max_connections': 1,
}


def _make_switch(extra_cfg=None):
    cfg = dict(DEVICE_CFG)
    if extra_cfg:
        cfg.update(extra_cfg)
    return openconfig.RestconfOpenConfigSwitch(cfg, device_name='test-switch')


class TestRestconfOpenConfigSwitchInit(unittest.TestCase):

    def test_default_network_instance(self):
        switch = _make_switch()
        self.assertEqual('default', switch._network_instance)

    def test_custom_network_instance(self):
        switch = _make_switch({'ngs_openconfig_network_instance': 'PROD'})
        self.assertEqual('PROD', switch._network_instance)

    def test_port_id_re_sub_empty(self):
        switch = _make_switch()
        self.assertEqual({}, switch._port_id_re_sub)

    def test_port_id_re_sub_json_string(self):
        switch = _make_switch(
            {'ngs_port_id_re_sub': '{"pattern":"Eth","repl":"eth"}'})
        self.assertEqual({'pattern': 'Eth', 'repl': 'eth'},
                         switch._port_id_re_sub)

    def test_port_id_re_sub_dict(self):
        switch = _make_switch(
            {'ngs_port_id_re_sub': {'pattern': 'X', 'repl': 'Y'}})
        self.assertEqual({'pattern': 'X', 'repl': 'Y'},
                         switch._port_id_re_sub)

    def test_port_id_resub_applies_regex(self):
        switch = _make_switch(
            {'ngs_port_id_re_sub':
             '{"pattern":"Ethernet","repl":"Eth"}'})
        self.assertEqual('Eth1/1', switch._port_id_resub('Ethernet1/1'))

    def test_port_id_resub_noop_when_empty(self):
        switch = _make_switch()
        self.assertEqual('eth1/1', switch._port_id_resub('eth1/1'))

    def test_support_trunk_on_ports(self):
        switch = _make_switch()
        self.assertTrue(switch.support_trunk_on_ports)

    def test_trunk_vlans_converge(self):
        switch = _make_switch()
        self.assertTrue(switch.trunk_vlans_converge)

    def test_callables_assigned(self):
        switch = _make_switch()
        self.assertIsNotNone(switch.ADD_NETWORK)
        self.assertIsNotNone(switch.DELETE_NETWORK)
        self.assertIsNotNone(switch.ADD_SUBPORTS_ON_TRUNK)
        self.assertIsNotNone(switch.DEL_SUBPORTS_ON_TRUNK)


class TestAddSubportsOnTrunkConvergence(unittest.TestCase):
    """Test trunk_details-based convergence (replace operation)."""

    def test_add_subports_with_trunk_details_uses_replace(self):
        switch = _make_switch()
        binding_profile = {'local_link_information': [
            {'port_id': 'eth1/1', 'switch_info': 'test-switch'}]}
        subports = [{'segmentation_id': 200}]
        trunk_details = {
            'segmentation_id': 100,
            'sub_ports': [
                {'segmentation_id': 200},
                {'segmentation_id': 300},
            ],
        }
        config = switch.ADD_SUBPORTS_ON_TRUNK(
            switch, binding_profile=binding_profile, port_id='eth1/1',
            subports=subports, trunk_details=trunk_details)
        self.assertEqual(1, len(config))
        ifaces = config[0]
        iface = ifaces._interfaces[0]
        sv_config = iface.ethernet.switched_vlan.config
        self.assertEqual('replace', sv_config.operation)
        self.assertEqual(oc_constants.VLAN_MODE_TRUNK,
                         sv_config.interface_mode)
        self.assertEqual(100, sv_config.native_vlan)
        self.assertEqual([200, 300], list(sv_config._trunk_vlans))

    def test_add_subports_without_trunk_details_merge_fallback(self):
        switch = _make_switch()
        binding_profile = {'local_link_information': [
            {'port_id': 'eth1/1', 'switch_info': 'test-switch'}]}
        subports = [
            {'segmentation_id': 200},
            {'segmentation_id': 300},
        ]
        config = switch.ADD_SUBPORTS_ON_TRUNK(
            switch, binding_profile=binding_profile, port_id='eth1/1',
            subports=subports, trunk_details=None)
        self.assertEqual(1, len(config))
        ifaces = config[0]
        iface = ifaces._interfaces[0]
        sv_config = iface.ethernet.switched_vlan.config
        self.assertEqual('merge', sv_config.operation)
        self.assertEqual([200, 300], list(sv_config._trunk_vlans))

    def test_add_subports_converge_sorted_vlans(self):
        switch = _make_switch()
        trunk_details = {
            'segmentation_id': 10,
            'sub_ports': [
                {'segmentation_id': 500},
                {'segmentation_id': 200},
                {'segmentation_id': 300},
            ],
        }
        config = switch.ADD_SUBPORTS_ON_TRUNK(
            switch, binding_profile={}, port_id='eth1/1',
            subports=[{'segmentation_id': 500}],
            trunk_details=trunk_details)
        iface = config[0]._interfaces[0]
        sv_config = iface.ethernet.switched_vlan.config
        self.assertEqual([200, 300, 500], list(sv_config._trunk_vlans))


class TestDelSubportsOnTrunkConvergence(unittest.TestCase):
    """Test trunk_details-based convergence for subport removal."""

    def test_del_subports_with_trunk_details_uses_replace(self):
        switch = _make_switch()
        binding_profile = {'local_link_information': [
            {'port_id': 'eth1/1', 'switch_info': 'test-switch'}]}
        subports = [{'segmentation_id': 200}]
        trunk_details = {
            'segmentation_id': 100,
            'sub_ports': [{'segmentation_id': 300}],
        }
        config = switch.DEL_SUBPORTS_ON_TRUNK(
            switch, binding_profile=binding_profile, port_id='eth1/1',
            subports=subports, trunk_details=trunk_details)
        self.assertEqual(1, len(config))
        ifaces = config[0]
        iface = ifaces._interfaces[0]
        sv_config = iface.ethernet.switched_vlan.config
        self.assertEqual('replace', sv_config.operation)
        self.assertEqual(oc_constants.VLAN_MODE_TRUNK,
                         sv_config.interface_mode)
        self.assertEqual(100, sv_config.native_vlan)
        self.assertEqual([300], list(sv_config._trunk_vlans))

    def test_del_subports_without_trunk_details_remove_fallback(self):
        switch = _make_switch()
        binding_profile = {'local_link_information': [
            {'port_id': 'eth1/1', 'switch_info': 'test-switch'}]}
        subports = [
            {'segmentation_id': 200},
            {'segmentation_id': 300},
        ]
        config = switch.DEL_SUBPORTS_ON_TRUNK(
            switch, binding_profile=binding_profile, port_id='eth1/1',
            subports=subports, trunk_details=None)
        self.assertEqual(1, len(config))
        ifaces = config[0]
        iface = ifaces._interfaces[0]
        sv_config = iface.ethernet.switched_vlan.config
        self.assertEqual('merge', sv_config.operation)
        self.assertEqual([200, 300],
                         list(sv_config._trunk_vlans._removals))

    def test_del_all_subports_switches_to_access_mode(self):
        switch = _make_switch()
        trunk_details = {
            'segmentation_id': 100,
            'sub_ports': [],
        }
        config = switch.DEL_SUBPORTS_ON_TRUNK(
            switch, binding_profile={}, port_id='eth1/1',
            subports=[{'segmentation_id': 200}],
            trunk_details=trunk_details)
        iface = config[0]._interfaces[0]
        sv_config = iface.ethernet.switched_vlan.config
        self.assertEqual(oc_constants.VLAN_MODE_ACCESS,
                         sv_config.interface_mode)
        self.assertEqual(100, sv_config.access_vlan)

    def test_del_subports_converge_sorted_remaining(self):
        switch = _make_switch()
        trunk_details = {
            'segmentation_id': 10,
            'sub_ports': [
                {'segmentation_id': 500},
                {'segmentation_id': 200},
            ],
        }
        config = switch.DEL_SUBPORTS_ON_TRUNK(
            switch, binding_profile={}, port_id='eth1/1',
            subports=[{'segmentation_id': 300}],
            trunk_details=trunk_details)
        iface = config[0]._interfaces[0]
        sv_config = iface.ethernet.switched_vlan.config
        self.assertEqual([200, 500], list(sv_config._trunk_vlans))


class TestEndToEndDispatch(unittest.TestCase):
    """Test that dispatch methods properly call send_config_to_device."""

    def test_add_subports_dispatches(self):
        switch = _make_switch()
        binding_profile = {'local_link_information': [
            {'port_id': 'eth1/1', 'switch_info': 'test-switch'}]}
        subports = [{'segmentation_id': 200}]
        trunk_details = {
            'segmentation_id': 100,
            'sub_ports': [{'segmentation_id': 200}],
        }
        with mock.patch.object(switch, 'send_config_to_device',
                               autospec=True) as mock_send:
            switch.add_subports_on_trunk(
                binding_profile, 'eth1/1', subports,
                trunk_details=trunk_details)
        mock_send.assert_called_once()
        config = mock_send.call_args[0][0]
        self.assertEqual(1, len(config))

    def test_del_subports_dispatches(self):
        switch = _make_switch()
        binding_profile = {'local_link_information': [
            {'port_id': 'eth1/1', 'switch_info': 'test-switch'}]}
        subports = [{'segmentation_id': 200}]
        trunk_details = {
            'segmentation_id': 100,
            'sub_ports': [{'segmentation_id': 300}],
        }
        with mock.patch.object(switch, 'send_config_to_device',
                               autospec=True) as mock_send:
            switch.del_subports_on_trunk(
                binding_profile, 'eth1/1', subports,
                trunk_details=trunk_details)
        mock_send.assert_called_once()
        config = mock_send.call_args[0][0]
        self.assertEqual(1, len(config))

    def test_add_network_dispatches(self):
        switch = _make_switch()
        with mock.patch.object(switch, 'send_config_to_device',
                               autospec=True) as mock_send:
            switch.add_network(100, 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee')
        mock_send.assert_called_once()

    def test_plug_port_to_network_dispatches(self):
        switch = _make_switch()
        with mock.patch.object(switch, 'send_config_to_device',
                               autospec=True) as mock_send:
            switch.plug_port_to_network('eth1/1', 100)
        mock_send.assert_called_once()

    def test_port_id_resub_applied_in_subports(self):
        switch = _make_switch(
            {'ngs_port_id_re_sub':
             '{"pattern":"Ethernet","repl":"Eth"}'})
        trunk_details = {
            'segmentation_id': 100,
            'sub_ports': [{'segmentation_id': 200}],
        }
        config = switch.ADD_SUBPORTS_ON_TRUNK(
            switch, binding_profile={}, port_id='Ethernet1/1',
            subports=[{'segmentation_id': 200}],
            trunk_details=trunk_details)
        iface = config[0]._interfaces[0]
        self.assertEqual('Eth1/1', iface.name)
