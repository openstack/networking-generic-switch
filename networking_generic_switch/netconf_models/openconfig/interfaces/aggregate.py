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
from networking_generic_switch.netconf_models.openconfig.interfaces import (
    types)
from networking_generic_switch.netconf_models.openconfig.vlan import vlan
from networking_generic_switch.netconf_models import utils as ncutils


class InterfacesAggregationConfig:

    NAMESPACE = 'http://openconfig.net/yang/interfaces/aggregate'
    PARENT = 'aggregation'
    TAG = 'config'

    def __init__(self,
                 operation: str = ncconst.NetconfEditConfigOperation.MERGE):
        self.operation = operation
        self._lag_type = None
        self._min_links = None

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
    def lag_type(self):
        return self._lag_type.value if self._lag_type else None

    @lag_type.setter
    def lag_type(self, value: str):
        """the type of LAG, i.e., how it is configured / maintained"""
        self._lag_type = types.AggregationType(value)

    @lag_type.deleter
    def lag_type(self):
        self._lag_type = None

    @property
    def min_links(self):
        return self._min_links

    @min_links.setter
    def min_links(self, value: int):
        self._min_links = value

    @min_links.deleter
    def min_links(self):
        self._min_links = None

    def to_xml_element(self):
        """Create XML Element

        :return: ElementTree Element with SubElements
        """
        elem = ElementTree.Element(self.TAG)
        if self.operation:
            elem.set('operation', self.operation)
        if self.lag_type is not None:
            ncutils.txt_subelement(elem, 'lag-type', self.lag_type)
        if self.min_links is not None:
            ncutils.txt_subelement(elem, 'min-links', str(self.min_links))
        return elem


class InterfacesAggregation:
    """Options for logical interfaces representing aggregates"""

    NAMESPACE = 'http://openconfig.net/yang/interfaces/aggregate'
    PARENT = 'interface'
    TAG = 'aggregation'

    def __init__(self):
        self._switched_vlan = vlan.VlanSwitchedVlan()
        self._config = InterfacesAggregationConfig()

    @property
    def switched_vlan(self):
        return self._switched_vlan

    @switched_vlan.setter
    def switched_vlan(self, value):
        if not isinstance(value, vlan.VlanSwitchedVlan):
            raise TypeError('switched_vlan must be '
                            'OpenConfigVlanSwitchedVlan, got {}'
                            .format(type(value)))
        self._switched_vlan = value

    @switched_vlan.deleter
    def switched_vlan(self):
        self._switched_vlan = None

    @property
    def config(self):
        return self._config

    @config.setter
    def config(self, value):
        if not isinstance(value, InterfacesAggregationConfig):
            raise TypeError('config must be InterfacesAggregationConfig, got '
                            '{}'.format(type(value)))
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
