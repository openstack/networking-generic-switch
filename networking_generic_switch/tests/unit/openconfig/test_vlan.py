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

from networking_generic_switch.netconf_models import constants as ncconst
from networking_generic_switch.netconf_models.openconfig.vlan import vlan


class TestVlan(unittest.TestCase):

    @mock.patch.object(vlan, 'Vlan', autospec=True)
    def test_vlans(self, mock_vlan):
        mock_vlan.return_value.to_xml_element.side_effect = [
            ElementTree.Element('fake-vlan-10'),
            ElementTree.Element('fake-vlan-20')
        ]
        oc_vlans = vlan.Vlans()
        oc_vlan = oc_vlans.add(10)
        mock_vlan.assert_called_with(10)
        self.assertEqual([oc_vlan], oc_vlans.vlans)
        remove_vlan = oc_vlans.remove(20)
        self.assertEqual([oc_vlan, remove_vlan], oc_vlans.vlans)
        element = oc_vlans.to_xml_element()
        xml_str = ElementTree.tostring(element).decode("utf-8")
        expected = (f'<vlans xmlns="{oc_vlans.NAMESPACE}">'
                    '<fake-vlan-10 />'
                    '<fake-vlan-20 />'
                    '</vlans>')
        self.assertEqual(expected, xml_str)

    @mock.patch.object(vlan, 'VlanConfig', autospec=True)
    def test_vlan(self, mock_vlan_conf):
        mock_vlan_conf.return_value.to_xml_element.return_value = (
            ElementTree.Element('fake-vlan-conf'))
        oc_vlan = vlan.Vlan(10)
        self.assertEqual(ncconst.NetconfEditConfigOperation.MERGE.value,
                         oc_vlan.operation)
        self.assertEqual(10, oc_vlan.vlan_id)
        self.assertRaises(TypeError,
                          vlan.Vlan, 'not-int')
        self.assertRaises(ValueError, vlan.Vlan, 20,
                          **dict(operation='invalid'))
        element = oc_vlan.to_xml_element()
        xml_str = ElementTree.tostring(element).decode("utf-8")
        expected = ('<vlan>'
                    '<vlan-id operation="merge">10</vlan-id>'
                    '<fake-vlan-conf />'
                    '</vlan>')
        self.assertEqual(expected, xml_str)
        oc_vlan.operation = 'remove'
        element = oc_vlan.to_xml_element()
        xml_str = ElementTree.tostring(element).decode("utf-8")
        expected = ('<vlan>'
                    '<vlan-id operation="remove">10</vlan-id>'
                    '<fake-vlan-conf />'
                    '</vlan>')
        self.assertEqual(expected, xml_str)

    def test_vlan_config(self):
        vlan_conf = vlan.VlanConfig()
        self.assertEqual(ncconst.NetconfEditConfigOperation.MERGE.value,
                         vlan_conf.operation)
        self.assertRaises(ValueError, vlan.VlanConfig,
                          **dict(operation='invalid'))
        self.assertRaises(TypeError, vlan.VlanConfig,
                          **dict(vlan_id='not-int'))
        self.assertRaises(TypeError, vlan.VlanConfig,
                          **dict(name=20))  # Not str
        self.assertRaises(ValueError, vlan.VlanConfig,
                          **dict(status='invalid'))
        vlan_conf.vlan_id = 10
        vlan_conf.name = 'Vlan10'
        vlan_conf.status = 'ACTIVE'
        element = vlan_conf.to_xml_element()
        xml_str = ElementTree.tostring(element).decode("utf-8")
        expected = ('<config operation="merge">'
                    '<vlan-id>10</vlan-id>'
                    '<name>Vlan10</name>'
                    '<status>ACTIVE</status>'
                    '</config>')
        self.assertEqual(expected, xml_str)
        vlan_conf.operation = 'delete'
        vlan_conf.status = 'SUSPENDED'
        element = vlan_conf.to_xml_element()
        xml_str = ElementTree.tostring(element).decode("utf-8")
        expected = ('<config operation="delete">'
                    '<vlan-id>10</vlan-id>'
                    '<name>Vlan10</name>'
                    '<status>SUSPENDED</status>'
                    '</config>')
        self.assertEqual(expected, xml_str)

    @mock.patch.object(vlan, 'VlanSwitchedConfig', autospec=True)
    def test_switched_vlan(self, mock_switched_vlan_conf):
        mock_switched_vlan_conf.return_value.to_xml_element.return_value = (
            ElementTree.Element('fake-switched-vlan-config'))
        switched_vlan = vlan.VlanSwitchedVlan()
        element = switched_vlan.to_xml_element()
        xml_str = ElementTree.tostring(element).decode("utf-8")
        expected = (f'<switched-vlan xmlns="{switched_vlan.NAMESPACE}">'
                    '<fake-switched-vlan-config />'
                    '</switched-vlan>')
        self.assertEqual(expected, xml_str)

    def test_switched_vlan_config(self):
        swithced_vlan_conf = vlan.VlanSwitchedConfig()
        self.assertEqual(ncconst.NetconfEditConfigOperation.MERGE.value,
                         swithced_vlan_conf.operation)
        self.assertRaises(ValueError, vlan.VlanSwitchedConfig,
                          **dict(operation='invalid'))
        self.assertRaises(ValueError, vlan.VlanSwitchedConfig,
                          **dict(interface_mode='invalid'))
        self.assertRaises(TypeError, vlan.VlanSwitchedConfig,
                          **dict(native_vlan='not-int'))
        self.assertRaises(TypeError, vlan.VlanSwitchedConfig,
                          **dict(access_vlan='not-int'))
        swithced_vlan_conf.interface_mode = 'ACCESS'
        swithced_vlan_conf.access_vlan = 20
        element = swithced_vlan_conf.to_xml_element()
        xml_str = ElementTree.tostring(element).decode("utf-8")
        expected = ('<config operation="merge">'
                    '<access-vlan>20</access-vlan>'
                    '<interface-mode>ACCESS</interface-mode>'
                    '</config>')
        self.assertEqual(expected, xml_str)
        del swithced_vlan_conf.access_vlan
        swithced_vlan_conf.interface_mode = 'TRUNK'
        swithced_vlan_conf.native_vlan = 30
        swithced_vlan_conf.trunk_vlans.add('10..50')
        swithced_vlan_conf.trunk_vlans.add('99')
        swithced_vlan_conf.trunk_vlans.add(88)
        swithced_vlan_conf.trunk_vlans.add('200..300')
        element = swithced_vlan_conf.to_xml_element()
        xml_str = ElementTree.tostring(element).decode("utf-8")
        expected = ('<config operation="merge">'
                    '<native-vlan>30</native-vlan>'
                    '<trunk-vlans>10..50</trunk-vlans>'
                    '<trunk-vlans>99</trunk-vlans>'
                    '<trunk-vlans>88</trunk-vlans>'
                    '<trunk-vlans>200..300</trunk-vlans>'
                    '<interface-mode>TRUNK</interface-mode>'
                    '</config>')
        self.assertEqual(expected, xml_str)

    def test_switched_vlan_config_trunk_vlans_remove(self):
        conf = vlan.VlanSwitchedConfig(interface_mode='TRUNK')
        conf.trunk_vlans.add(100)
        conf.trunk_vlans.add(200)
        conf.trunk_vlans.remove(50)
        conf.trunk_vlans.remove('300..400')
        element = conf.to_xml_element()
        xml_str = ElementTree.tostring(element).decode("utf-8")
        expected = ('<config operation="merge">'
                    '<trunk-vlans>100</trunk-vlans>'
                    '<trunk-vlans>200</trunk-vlans>'
                    '<trunk-vlans operation="remove">50</trunk-vlans>'
                    '<trunk-vlans operation="remove">300..400</trunk-vlans>'
                    '<interface-mode>TRUNK</interface-mode>'
                    '</config>')
        self.assertEqual(expected, xml_str)

    def test_switched_vlan_config_trunk_vlans_remove_only(self):
        conf = vlan.VlanSwitchedConfig(interface_mode='TRUNK')
        conf.trunk_vlans.remove(100)
        element = conf.to_xml_element()
        xml_str = ElementTree.tostring(element).decode("utf-8")
        expected = ('<config operation="merge">'
                    '<trunk-vlans operation="remove">100</trunk-vlans>'
                    '<interface-mode>TRUNK</interface-mode>'
                    '</config>')
        self.assertEqual(expected, xml_str)

    def test_trunk_vlans_remove_dedup(self):
        trunk_vlans = vlan.TrunkVlans()
        trunk_vlans.remove(100)
        trunk_vlans.remove(100)
        self.assertEqual([100], trunk_vlans._removals)
