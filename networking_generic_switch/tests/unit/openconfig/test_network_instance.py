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
from xml.etree import ElementTree

from networking_generic_switch.netconf_models.openconfig.network_instance \
    import network_instance
from networking_generic_switch.netconf_models.openconfig.vlan import vlan
from networking_generic_switch.netconf_models import utils as ncutils


class TestNetworkInstance(unittest.TestCase):

    @mock.patch.object(network_instance, 'NetworkInstance', autospec=True)
    def test_network_instances(self, mock_net_instance):
        mock_net_instance.return_value.to_xml_element.return_value = (
            ElementTree.Element('fake-net-instance'))
        net_instances = network_instance.NetworkInstances()
        net_instance = net_instances.add('default')
        self.assertEqual([net_instance], net_instances.network_instances)
        element = net_instances.to_xml_element()
        xml_str = ElementTree.tostring(element).decode("utf-8")
        expected = (f'<network-instances xmlns="{net_instances.NAMESPACE}">'
                    '<fake-net-instance />'
                    '</network-instances>')
        self.assertEqual(expected, xml_str)

    @mock.patch.object(vlan, 'Vlans', autospec=True)
    def test_network_instance(self, mock_oc_vlans):
        mock_oc_vlans.return_value.to_xml_element.return_value = (
            ElementTree.Element('fake-oc-vlans'))
        mock_oc_vlans.return_value.__len__.return_value = 1
        net_instance = network_instance.NetworkInstance('default')
        self.assertEqual(mock_oc_vlans(), net_instance.vlans)
        element = net_instance.to_xml_element()
        xml_str = ElementTree.tostring(element).decode("utf-8")
        expected = ('<network-instance>'
                    '<name>default</name>'
                    '<fake-oc-vlans />'
                    '</network-instance>')
        self.assertEqual(expected, xml_str)


class TestNetworkInstanceRestconf(unittest.TestCase):

    def test_network_instance_restconf_dict(self):
        ni = network_instance.NetworkInstance('default')
        v = ni.vlans.add(100)
        v.config.name = 'Production'
        v.config.status = 'ACTIVE'
        result = ni.to_restconf_dict()
        expected = {
            'name': 'default',
            'openconfig-vlan:vlans': {
                'vlan': [
                    {
                        'vlan-id': 100,
                        'config': {
                            'vlan-id': 100,
                            'name': 'Production',
                            'status': 'ACTIVE',
                        }
                    }
                ]
            }
        }
        self.assertEqual(expected, result)

    def test_network_instance_restconf_dict_multiple_vlans(self):
        ni = network_instance.NetworkInstance('default')
        v1 = ni.vlans.add(10)
        v1.config.name = 'Management'
        v2 = ni.vlans.add(20)
        v2.config.name = 'Data'
        result = ni.to_restconf_dict()
        self.assertEqual('default', result['name'])
        vlan_list = result['openconfig-vlan:vlans']['vlan']
        self.assertEqual(2, len(vlan_list))
        self.assertEqual(10, vlan_list[0]['vlan-id'])
        self.assertEqual(20, vlan_list[1]['vlan-id'])

    def test_network_instance_restconf_dict_no_vlans(self):
        ni = network_instance.NetworkInstance('default')
        result = ni.to_restconf_dict()
        expected = {'name': 'default'}
        self.assertEqual(expected, result)

    def test_network_instances_restconf_dict(self):
        nis = network_instance.NetworkInstances()
        ni = nis.add('default')
        v = ni.vlans.add(100)
        v.config.name = 'Vlan100'
        v.config.status = 'ACTIVE'
        result = nis.to_restconf_dict()
        expected = {
            'openconfig-network-instance:network-instances': {
                'network-instance': [
                    {
                        'name': 'default',
                        'openconfig-vlan:vlans': {
                            'vlan': [
                                {
                                    'vlan-id': 100,
                                    'config': {
                                        'vlan-id': 100,
                                        'name': 'Vlan100',
                                        'status': 'ACTIVE',
                                    }
                                }
                            ]
                        }
                    }
                ]
            }
        }
        self.assertEqual(expected, result)

    def test_config_to_restconf_json_network_instance(self):
        nis = network_instance.NetworkInstances()
        ni = nis.add('default')
        ni.vlans.add(100)
        result = ncutils.config_to_restconf_json([nis])
        self.assertIn(
            'openconfig-network-instance:network-instances', result)
        ni_list = (
            result['openconfig-network-instance:network-instances']
            ['network-instance'])
        self.assertEqual(1, len(ni_list))
        self.assertEqual('default', ni_list[0]['name'])
