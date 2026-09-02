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

from networking_generic_switch.netconf_models.openconfig.interfaces import (
    aggregate)
from networking_generic_switch.netconf_models.openconfig.interfaces import (
    ethernet)
from networking_generic_switch.netconf_models.openconfig.interfaces import (
    interfaces)
from networking_generic_switch.netconf_models.openconfig.lacp import lacp
from networking_generic_switch.netconf_models.openconfig.network_instance \
    import network_instance
from networking_generic_switch.netconf_models.openconfig.vlan import vlan
from networking_generic_switch.netconf_models import utils as ncutils


class TestConfigToRestconfJsonMergeOrder(unittest.TestCase):
    """Focused tests for config_to_restconf_json() payload merge and order."""

    def test_single_interfaces_payload(self):
        ifaces = interfaces.Interfaces()
        iface = ifaces.add('eth1/31')
        iface.ethernet.switched_vlan.config.interface_mode = 'ACCESS'
        iface.ethernet.switched_vlan.config.access_vlan = 100
        result = ncutils.config_to_restconf_json([ifaces])
        self.assertIn('openconfig-interfaces:interfaces', result)
        self.assertEqual(1, len(result))
        iface_list = (
            result['openconfig-interfaces:interfaces']['interface'])
        self.assertEqual(1, len(iface_list))
        self.assertEqual('eth1/31', iface_list[0]['name'])

    def test_single_network_instances_payload(self):
        nis = network_instance.NetworkInstances()
        ni = nis.add('default')
        ni.vlans.add(100)
        result = ncutils.config_to_restconf_json([nis])
        self.assertIn(
            'openconfig-network-instance:network-instances', result)
        self.assertEqual(1, len(result))

    def test_merge_interfaces_and_network_instances(self):
        """Verify two different top-level containers merge into one dict."""
        ifaces = interfaces.Interfaces()
        iface = ifaces.add('eth1/1')
        iface.ethernet.switched_vlan.config.interface_mode = 'ACCESS'
        iface.ethernet.switched_vlan.config.access_vlan = 10

        nis = network_instance.NetworkInstances()
        ni = nis.add('default')
        ni.vlans.add(10)

        result = ncutils.config_to_restconf_json([ifaces, nis])
        self.assertEqual(2, len(result))
        self.assertIn('openconfig-interfaces:interfaces', result)
        self.assertIn(
            'openconfig-network-instance:network-instances', result)

    def test_merge_preserves_both_payloads(self):
        """Verify merge doesn't lose data from either model."""
        ifaces = interfaces.Interfaces()
        iface = ifaces.add('eth1/5')
        iface.ethernet.switched_vlan.config.interface_mode = 'TRUNK'
        iface.ethernet.switched_vlan.config.trunk_vlans.add(100)
        iface.ethernet.switched_vlan.config.trunk_vlans.add(200)

        nis = network_instance.NetworkInstances()
        ni = nis.add('default')
        v1 = ni.vlans.add(100)
        v1.config.name = 'Vlan100'
        v2 = ni.vlans.add(200)
        v2.config.name = 'Vlan200'

        result = ncutils.config_to_restconf_json([ifaces, nis])

        iface_list = (
            result['openconfig-interfaces:interfaces']['interface'])
        self.assertEqual(1, len(iface_list))
        trunk_vlans = (
            iface_list[0]['openconfig-if-ethernet:ethernet']
            ['openconfig-vlan:switched-vlan']['config']['trunk-vlans'])
        self.assertEqual([100, 200], trunk_vlans)

        ni_list = (
            result['openconfig-network-instance:network-instances']
            ['network-instance'])
        self.assertEqual(1, len(ni_list))
        vlan_list = ni_list[0]['openconfig-vlan:vlans']['vlan']
        self.assertEqual(2, len(vlan_list))

    def test_later_model_overwrites_same_key(self):
        """When two models produce the same top-level key, last one wins."""
        ifaces1 = interfaces.Interfaces()
        ifaces1.add('eth1/1')

        ifaces2 = interfaces.Interfaces()
        ifaces2.add('eth1/2')

        result = ncutils.config_to_restconf_json([ifaces1, ifaces2])
        iface_list = (
            result['openconfig-interfaces:interfaces']['interface'])
        self.assertEqual(1, len(iface_list))
        self.assertEqual('eth1/2', iface_list[0]['name'])

    def test_empty_config_list(self):
        result = ncutils.config_to_restconf_json([])
        self.assertEqual({}, result)

    def test_three_way_merge(self):
        """Merge interfaces, network-instances, and LACP."""
        ifaces = interfaces.Interfaces()
        ifaces.add('eth1/1')

        nis = network_instance.NetworkInstances()
        nis.add('default')

        oc_lacp = lacp.LACP()
        oc_lacp.interfaces.add('po10')

        result = ncutils.config_to_restconf_json([ifaces, nis])
        self.assertEqual(2, len(result))
        self.assertIn('openconfig-interfaces:interfaces', result)
        self.assertIn(
            'openconfig-network-instance:network-instances', result)


class TestRestconfPathGeneration(unittest.TestCase):
    """Tests for to_restconf_path() and restconf_resource_path()."""

    def test_all_model_path_segments(self):
        """Verify to_restconf_path() on every model class.

        Each case is a 2-tuple: (model_instance, expected_path_segment)
        """
        cases = [
            (interfaces.Interfaces(), 'openconfig-interfaces:interfaces'),
            (interfaces.BaseInterface('eth0'), 'interface=eth0'),
            (interfaces.InterfaceEthernet('eth1/31'), 'interface=eth1%2F31'),
            (interfaces.InterfaceAggregate('po10'), 'interface=po10'),
            (interfaces.InterfaceEthernet('Ethernet1/2/3'),
             'interface=Ethernet1%2F2%2F3'),
            (interfaces.InterfaceConfig(), 'config'),
            (ethernet.InterfacesEthernet(),
             'openconfig-if-ethernet:ethernet'),
            (ethernet.InterfacesEthernetConfig(), 'config'),
            (aggregate.InterfacesAggregation(),
             'openconfig-if-aggregate:aggregation'),
            (aggregate.InterfacesAggregationConfig(), 'config'),
            (vlan.VlanSwitchedVlan(), 'openconfig-vlan:switched-vlan'),
            (vlan.VlanSwitchedConfig(), 'config'),
            (vlan.Vlans(), 'openconfig-vlan:vlans'),
            (vlan.Vlan(100), 'vlan=100'),
            (vlan.VlanConfig(vlan_id=10), 'config'),
            (network_instance.NetworkInstances(),
             'openconfig-network-instance:network-instances'),
            (network_instance.NetworkInstance('default'),
             'network-instance=default'),
            (network_instance.NetworkInstance('my/instance'),
             'network-instance=my%2Finstance'),
            (lacp.LACP(), 'openconfig-lacp:lacp'),
            (lacp.LACPInterfaces(), 'interfaces'),
            (lacp.LACPInterface('po10'), 'interface=po10'),
            (lacp.LACPInterfaceConfig('po10'), 'config'),
        ]
        for obj, expected in cases:
            with self.subTest(cls=type(obj).__name__, expected=expected):
                self.assertEqual(expected, obj.to_restconf_path())

    def test_resource_path_composition(self):
        """Verify restconf_resource_path() composes URL paths correctly.

        Each case is a 3-tuple:
        (label, {segments, base_path (optional)}, expected_url)
        """
        base = '/restconf/data'
        cases = [
            ('single segment',
             dict(segments=('openconfig-interfaces:interfaces',)),
             base + '/openconfig-interfaces:interfaces'),
            ('multiple segments',
             dict(segments=(
                 'openconfig-interfaces:interfaces',
                 'interface=eth1%2F31',
                 'openconfig-if-ethernet:ethernet',
                 'openconfig-vlan:switched-vlan',
                 'config')),
             base + '/openconfig-interfaces:interfaces'
             '/interface=eth1%2F31'
             '/openconfig-if-ethernet:ethernet'
             '/openconfig-vlan:switched-vlan'
             '/config'),
            ('custom base path',
             dict(segments=('openconfig-interfaces:interfaces',),
                  base_path='/rests/data'),
             '/rests/data/openconfig-interfaces:interfaces'),
            ('trailing slash stripped',
             dict(segments=('openconfig-interfaces:interfaces',),
                  base_path='/restconf/data/'),
             base + '/openconfig-interfaces:interfaces'),
            ('no segments', dict(segments=()), base),
            ('empty segments skipped',
             dict(segments=(
                 'openconfig-interfaces:interfaces', '',
                 'interface=eth0')),
             base + '/openconfig-interfaces:interfaces/interface=eth0'),
            ('network-instance path',
             dict(segments=(
                 'openconfig-network-instance:network-instances',
                 'network-instance=default', 'openconfig-vlan:vlans',
                 'vlan=100')),
             base + '/openconfig-network-instance:network-instances'
             '/network-instance=default/openconfig-vlan:vlans/vlan=100'),
        ]
        for label, kwargs, expected in cases:
            with self.subTest(label):
                segs = kwargs.pop('segments')
                self.assertEqual(
                    expected,
                    ncutils.restconf_resource_path(*segs, **kwargs))

    def test_composed_interface_path_from_models(self):
        ifaces = interfaces.Interfaces()
        iface = ifaces.add('eth1/31')
        path = ncutils.restconf_resource_path(
            ifaces.to_restconf_path(),
            iface.to_restconf_path(),
            iface.ethernet.to_restconf_path(),
            iface.ethernet.switched_vlan.to_restconf_path(),
            iface.ethernet.switched_vlan.config.to_restconf_path())
        self.assertEqual(
            '/restconf/data/openconfig-interfaces:interfaces'
            '/interface=eth1%2F31'
            '/openconfig-if-ethernet:ethernet'
            '/openconfig-vlan:switched-vlan'
            '/config',
            path)

    def test_composed_network_instance_path_from_models(self):
        nis = network_instance.NetworkInstances()
        ni = nis.add('default')
        v = ni.vlans.add(100)
        path = ncutils.restconf_resource_path(
            nis.to_restconf_path(),
            ni.to_restconf_path(),
            ni.vlans.to_restconf_path(),
            v.to_restconf_path())
        self.assertEqual(
            '/restconf/data/openconfig-network-instance:network-instances'
            '/network-instance=default'
            '/openconfig-vlan:vlans'
            '/vlan=100',
            path)
