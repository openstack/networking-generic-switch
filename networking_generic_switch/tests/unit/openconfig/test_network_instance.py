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
