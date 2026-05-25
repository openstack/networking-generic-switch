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
from xml.etree import ElementTree

from networking_generic_switch.netconf_models import constants as ncconst
from networking_generic_switch.netconf_models.openconfig.vlan import vlan
from networking_generic_switch.netconf_models import utils as ncutils


class InterfacesEthernetConfig:
    """OpenConfig interface ethernet configuration"""

    NAMESPACE = 'http://openconfig.net/yang/interfaces'
    PARENT = 'interface'
    TAG = 'config'

    def __init__(self, operation=ncconst.NetconfEditConfigOperation.MERGE):
        self.operation = operation
        self._aggregate_id = None
        self._aggregate_id_namespace = (
            'http://openconfig.net/yang/interfaces/aggregate')

    @property
    def operation(self):
        """RFC 6241 - <edit-config> operation attribute"""
        return self._operation.value if self._operation else None

    @operation.setter
    def operation(self, value):
        """RFC 6241 - <edit-config> operation attribute"""
        if isinstance(value, ncconst.NetconfEditConfigOperation):
            self._operation = value
        elif isinstance(value, str):
            self._operation = ncconst.NetconfEditConfigOperation(value)
        else:
            raise TypeError('Invalid type {} for config operation attribute.'
                            .format(type(value)))

    @operation.deleter
    def operation(self):
        self._operation = None

    @property
    def aggregate_id(self):
        """Logical aggregate interface for interface"""
        return self._aggregate_id

    @aggregate_id.setter
    def aggregate_id(self, value: str):
        """Set logical aggregate interface for interface"""
        if not isinstance(value, str):
            raise TypeError('aggregate_id must be string, got {}'
                            .format(type(value)))
        self._aggregate_id = value

    @aggregate_id.deleter
    def aggregate_id(self):
        self._aggregate_id = None

    def to_xml_element(self):
        """Create XML Element

        :return: ElementTree Element with SubElements
        """
        element = ElementTree.Element(self.TAG)
        if self.operation:
            element.set('operation', self.operation)
        if self.aggregate_id is not None:
            ncutils.txt_subelement(
                element, 'aggregate-id', self.aggregate_id,
                xmlns=self._aggregate_id_namespace)
        return element


class InterfacesEthernet:
    """Ethernet configuration and state"""
    NAMESPACE = 'http://openconfig.net/yang/interfaces/ethernet'
    PARENT = 'interface'
    TAG = 'ethernet'

    def __init__(self):
        self._switched_vlan = vlan.VlanSwitchedVlan()
        self._config = InterfacesEthernetConfig()

    @property
    def switched_vlan(self):
        return self._switched_vlan

    @switched_vlan.setter
    def switched_vlan(self, value):
        if not isinstance(value, vlan.VlanSwitchedVlan):
            raise TypeError('switched_vlan must be VlanSwitchedVlan, got {}'
                            .format(type(value)))
        self._switched_vlan = value

    @switched_vlan.deleter
    def switched_vlan(self):
        self._switched_vlan = None

    @property
    def config(self):
        """Configuration parameters for interface"""
        return self._config

    @config.setter
    def config(self, value):
        if not isinstance(value, InterfacesEthernetConfig):
            raise TypeError('config must be InterfacesEthernetConfig, got {}'
                            .format(type(value)))
        self._config = value

    @config.deleter
    def config(self):
        self._config = None

    def to_xml_element(self):
        """Create XML Element

        :return: ElementTree Element with SubElements
        """
        elem = ElementTree.Element(self.TAG)
        elem.set('xmlns', self.NAMESPACE)
        if self.config:
            elem.append(self.config.to_xml_element())
        if self.switched_vlan:
            elem.append(self.switched_vlan.to_xml_element())
        return elem
