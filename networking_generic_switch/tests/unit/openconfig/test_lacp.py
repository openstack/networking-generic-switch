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
from networking_generic_switch.netconf_models.openconfig import (
    constants as oc_constants)
from networking_generic_switch.netconf_models.openconfig.lacp import lacp


class TestOpenConfigLACP(unittest.TestCase):

    @mock.patch.object(lacp, 'LACPInterfaces', autospec=True)
    def test_openconfig_lacp(self, mock_lcap_ifaces):
        mock_lcap_ifaces.return_value.to_xml_element.return_value = (
            ElementTree.Element('fake-lacp-interfaces'))
        oc_lacp = lacp.LACP()
        mock_lcap_ifaces.assert_called_with()
        mock_lcap_ifaces.return_value.__len__.return_value = 1
        element = oc_lacp.to_xml_element()
        xml_str = ElementTree.tostring(element).decode("utf-8")
        expected = (f'<lacp xmlns="{oc_lacp.NAMESPACE}">'
                    '<fake-lacp-interfaces />'
                    '</lacp>')
        self.assertEqual(expected, xml_str)

    @mock.patch.object(lacp, 'LACPInterface', autospec=True)
    def test_openconfig_lacp_interfaces(self, mock_lacp_iface):
        mock_lacp_iface.return_value.to_xml_element.return_value = (
            ElementTree.Element('fake-lacp-interface'))
        oc_lacp_ifaces = lacp.LACPInterfaces()
        self.assertEqual([], oc_lacp_ifaces.interfaces)
        oc_lacp_iface = oc_lacp_ifaces.add('lacp-iface-name')
        mock_lacp_iface.assert_called_with('lacp-iface-name')
        self.assertEqual([oc_lacp_iface], oc_lacp_ifaces.interfaces)
        element = oc_lacp_ifaces.to_xml_element()
        xml_str = ElementTree.tostring(element).decode("utf-8")
        expected = ('<interfaces>'
                    '<fake-lacp-interface />'
                    '</interfaces>')
        self.assertEqual(expected, xml_str)

    @mock.patch.object(lacp, 'LACPInterfaceConfig', autospec=True)
    def test_openconfig_lacp_interface(self, mock_lacp_if_conf):
        mock_lacp_if_conf.return_value.to_xml_element.return_value = (
            ElementTree.Element('fake-lacp-interface-config'))
        self.assertRaises(TypeError, lacp.LACPInterface, int(20))
        oc_lacp_iface = lacp.LACPInterface('lacp-iface-name')
        self.assertEqual('lacp-iface-name', oc_lacp_iface.name)
        element = oc_lacp_iface.to_xml_element()
        xml_str = ElementTree.tostring(element).decode("utf-8")
        expected = ('<interface operation="merge">'
                    '<name>lacp-iface-name</name>'
                    '<fake-lacp-interface-config />'
                    '</interface>')
        self.assertEqual(expected, xml_str)
        oc_lacp_iface.operation = ncconst.NetconfEditConfigOperation.REMOVE
        element = oc_lacp_iface.to_xml_element()
        xml_str = ElementTree.tostring(element).decode("utf-8")
        expected = ('<interface operation="remove">'
                    '<name>lacp-iface-name</name>'
                    '<fake-lacp-interface-config />'
                    '</interface>')
        self.assertEqual(expected, xml_str)

    def test_openconfig_lacp_interface_config(self):
        self.assertRaises(ValueError,
                          lacp.LACPInterfaceConfig, 'name',
                          **dict(operation='invalid'))
        self.assertRaises(ValueError, lacp.LACPInterfaceConfig,
                          'name', **dict(interval='invalid'))
        self.assertRaises(ValueError, lacp.LACPInterfaceConfig,
                          'name', **dict(lacp_mode='invalid'))
        lacp_if_conf = lacp.LACPInterfaceConfig('lacp-iface-name')
        element = lacp_if_conf.to_xml_element()
        xml_str = ElementTree.tostring(element).decode("utf-8")
        expected = ('<config operation="merge">'
                    '<name>lacp-iface-name</name>'
                    '<interval>SLOW</interval>'
                    '<lacp-mode>ACTIVE</lacp-mode>'
                    '</config>')
        self.assertEqual(expected, xml_str)
        lacp_if_conf.interval = oc_constants.LACP_PERIOD_FAST
        lacp_if_conf.lacp_mode = oc_constants.LACP_ACTIVITY_PASSIVE
        element = lacp_if_conf.to_xml_element()
        xml_str = ElementTree.tostring(element).decode("utf-8")
        expected = ('<config operation="merge">'
                    '<name>lacp-iface-name</name>'
                    '<interval>FAST</interval>'
                    '<lacp-mode>PASSIVE</lacp-mode>'
                    '</config>')
        self.assertEqual(expected, xml_str)
