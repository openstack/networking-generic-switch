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
from networking_generic_switch.netconf_models.openconfig.interfaces import (
    aggregate)
from networking_generic_switch.netconf_models.openconfig.interfaces import (
    ethernet)
from networking_generic_switch.netconf_models.openconfig.interfaces import (
    interfaces)
from networking_generic_switch.netconf_models.openconfig.vlan import vlan


class TestInterfaces(unittest.TestCase):

    @mock.patch.object(ethernet, 'InterfacesEthernetConfig', autospec=True)
    @mock.patch.object(vlan, 'VlanSwitchedVlan', autospec=True)
    def test_interfaces_ethernet(self, mock_sw_vlan, mock_eth_conf):
        mock_sw_vlan.return_value.to_xml_element.return_value = (
            ElementTree.Element('fake-switched-vlan'))
        mock_eth_conf.return_value.to_xml_element.return_value = (
            ElementTree.Element('fake-ethernet-config'))
        if_eth = ethernet.InterfacesEthernet()
        mock_sw_vlan.assert_called_with()
        element = if_eth.to_xml_element()
        xml_str = ElementTree.tostring(element).decode("utf-8")
        expected = (f'<ethernet xmlns="{if_eth.NAMESPACE}">'
                    '<fake-ethernet-config />'
                    '<fake-switched-vlan />'
                    '</ethernet>')
        self.assertEqual(expected, xml_str)

    @mock.patch.object(aggregate, 'InterfacesAggregationConfig', autospec=True)
    @mock.patch.object(vlan, 'VlanSwitchedVlan', autospec=True)
    def test_interfaces_aggregate(self, mock_sw_vlan, mock_agg_conf):
        mock_sw_vlan.return_value.to_xml_element.return_value = (
            ElementTree.Element('fake-switched-vlan'))
        mock_agg_conf.return_value.to_xml_element.return_value = (
            ElementTree.Element('fake-aggregate-config'))
        if_aggregate = aggregate.InterfacesAggregation()
        mock_sw_vlan.assert_called_with()
        element = if_aggregate.to_xml_element()
        xml_str = ElementTree.tostring(element).decode("utf-8")
        expected = (f'<aggregation xmlns="{if_aggregate.NAMESPACE}">'
                    '<fake-aggregate-config />'
                    '<fake-switched-vlan />'
                    '</aggregation>')
        self.assertEqual(expected, xml_str)

    @mock.patch.object(interfaces, 'InterfaceAggregate', autospec=True)
    @mock.patch.object(interfaces, 'InterfaceEthernet', autospec=True)
    def test_interfaces_interfaces(self, mock_iface_eth, mock_iface_aggregate):
        mock_iface_eth.return_value.to_xml_element.return_value = (
            ElementTree.Element('fake-ethernet'))
        mock_iface_aggregate.return_value.to_xml_element.return_value = (
            ElementTree.Element('fake-aggregate'))
        ifaces = interfaces.Interfaces()
        iface = ifaces.add('eth0/1')
        iface2 = ifaces.add('po10', interface_type='aggregate')
        mock_iface_eth.assert_called_with('eth0/1')
        mock_iface_aggregate.assert_called_with('po10')
        self.assertEqual([iface, iface2], ifaces.interfaces)
        element = ifaces.to_xml_element()
        xml_str = ElementTree.tostring(element).decode("utf-8")
        expected = (f'<interfaces xmlns="{ifaces.NAMESPACE}">'
                    '<fake-ethernet />'
                    '<fake-aggregate />'
                    '</interfaces>')
        self.assertEqual(expected, xml_str)

    @mock.patch.object(ethernet, 'InterfacesEthernet', autospec=True)
    @mock.patch.object(interfaces, 'InterfaceConfig', autospec=True)
    def test_interfaces_interface_ethernet(self, mock_if_conf, mock_if_eth):
        mock_if_conf.return_value.to_xml_element.return_value = (
            ElementTree.Element('fake_config'))
        mock_if_eth.return_value.to_xml_element.return_value = (
            ElementTree.Element('fake_ethernet'))
        interface = interfaces.InterfaceEthernet('eth0/1')
        mock_if_conf.assert_called_with()
        mock_if_eth.assert_called_with()
        self.assertEqual('eth0/1', interface.name)
        self.assertEqual(mock_if_conf(), interface.config)
        self.assertEqual(mock_if_eth(), interface.ethernet)
        element = interface.to_xml_element()
        xml_str = ElementTree.tostring(element).decode("utf-8")
        expected = ('<interface>'
                    '<name>eth0/1</name>'
                    '<fake_config />'
                    '<fake_ethernet />'
                    '</interface>')
        self.assertEqual(expected, xml_str)
        not_string = 10
        self.assertRaises(TypeError,
                          interfaces.InterfaceEthernet, not_string)

    @mock.patch.object(aggregate, 'InterfacesAggregation', autospec=True)
    @mock.patch.object(interfaces, 'InterfaceConfig', autospec=True)
    def test_interfaces_interface_aggregate(self, mock_if_conf, mock_if_aggr):
        mock_if_conf.return_value.to_xml_element.return_value = (
            ElementTree.Element('fake_config'))
        mock_if_aggr.return_value.to_xml_element.return_value = (
            ElementTree.Element('fake_aggregation'))
        interface = interfaces.InterfaceAggregate('po10')
        mock_if_conf.assert_called_with()
        mock_if_aggr.assert_called_with()
        self.assertEqual('po10', interface.name)
        self.assertEqual(mock_if_conf(), interface.config)
        self.assertEqual(mock_if_aggr(), interface.aggregation)
        element = interface.to_xml_element()
        xml_str = ElementTree.tostring(element).decode("utf-8")
        expected = ('<interface operation="merge">'
                    '<name>po10</name>'
                    '<fake_config />'
                    '<fake_aggregation />'
                    '</interface>')
        self.assertEqual(expected, xml_str)
        not_string = 10
        self.assertRaises(TypeError,
                          interfaces.InterfaceEthernet, not_string)

    def test_interfaces_interface_config(self):
        if_conf = interfaces.InterfaceConfig()
        self.assertEqual(ncconst.NetconfEditConfigOperation.MERGE.value,
                         if_conf.operation)
        self.assertRaises(ValueError, interfaces.InterfaceConfig,
                          **dict(operation='invalid'))
        self.assertRaises(TypeError, interfaces.InterfaceConfig,
                          **dict(enabled='not_bool'))
        self.assertRaises(TypeError, interfaces.InterfaceConfig,
                          **dict(description=10))  # Not string
        self.assertRaises(TypeError, interfaces.InterfaceConfig,
                          **dict(mtu='not_int'))
        if_conf.name = 'test1'
        if_conf.enabled = True
        if_conf.description = 'Description'
        if_conf.mtu = 9000
        element = if_conf.to_xml_element()
        xml_str = ElementTree.tostring(element).decode("utf-8")
        expected = ('<config>'
                    '<name operation="merge">test1</name>'
                    '<description operation="merge">Description</description>'
                    '<enabled operation="merge">true</enabled>'
                    '<mtu operation="merge">9000</mtu>'
                    '</config>')
        self.assertEqual(expected, xml_str)
        del if_conf.name
        if_conf.operation = 'remove'
        if_conf.description = ''
        if_conf.mtu = 0
        if_conf.enabled = False
        element = if_conf.to_xml_element()
        xml_str = ElementTree.tostring(element).decode("utf-8")
        expected = ('<config>'
                    '<description operation="remove" />'
                    '<enabled operation="remove">false</enabled>'
                    '<mtu operation="remove">0</mtu>'
                    '</config>')
        self.assertEqual(expected, xml_str)

    def test_interfaces_interface_ethernet_config(self):
        eth_conf = ethernet.InterfacesEthernetConfig()
        self.assertEqual(ncconst.NetconfEditConfigOperation.MERGE.value,
                         eth_conf.operation)
        self.assertRaises(ValueError,
                          ethernet.InterfacesEthernetConfig,
                          **dict(operation='invalid'))
        eth_conf.aggregate_id = 'po100'
        element = eth_conf.to_xml_element()
        xml_str = ElementTree.tostring(element).decode("utf-8")
        expected = ('<config operation="merge">'
                    '<aggregate-id '
                    'xmlns="http://openconfig.net/yang/interfaces/aggregate"'
                    '>po100</aggregate-id>'
                    '</config>')
        self.assertEqual(expected, xml_str)
        eth_conf = ethernet.InterfacesEthernetConfig()
        eth_conf.operation = 'remove'
        element = eth_conf.to_xml_element()
        xml_str = ElementTree.tostring(element).decode("utf-8")
        expected = '<config operation="remove" />'
        self.assertEqual(expected, xml_str)
