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
from collections import abc
from typing import Optional
from xml.etree import ElementTree

from networking_generic_switch.netconf_models import constants as ncconst
from networking_generic_switch.netconf_models.openconfig import (
    constants as oc_constants)
from networking_generic_switch.netconf_models.openconfig.interfaces import (
    aggregate)
from networking_generic_switch.netconf_models.openconfig.interfaces import (
    ethernet)
from networking_generic_switch.netconf_models import utils as ncutils


class InterfaceConfig:
    """OpenConfig interface configuration"""

    NAMESPACE = 'http://openconfig.net/yang/interfaces'
    PARENT = 'interface'
    TAG = 'config'

    def __init__(self,
                 operation=ncconst.NetconfEditConfigOperation.MERGE,
                 name: Optional[str] = None,
                 description: Optional[str] = None,
                 enabled: Optional[bool] = None,
                 mtu: Optional[int] = None):
        self.operation = operation
        self._name = name
        self._description = None
        self._enabled = None
        self._mtu = None
        if description:
            self.description = description
        if enabled is not None:
            self.enabled = enabled
        if mtu:
            self.mtu = mtu

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
        """RFC 6241 - <edit-config> operation attribute"""
        self._operation = None

    @property
    def name(self):
        """The name of the interface."""
        return self._name

    @name.setter
    def name(self, value: str):
        """The name of the interface."""
        if not isinstance(value, str):
            raise TypeError('name must be string, got {}'.format(type(value)))
        self._name = value

    @name.deleter
    def name(self):
        """The name of the interface."""
        self._name = None

    @property
    def description(self):
        """A textual description of the interface"""
        return self._description

    @description.setter
    def description(self, value: str):
        """A textual description of the interface"""
        if not isinstance(value, str):
            raise TypeError('description must be string, got {}'
                            .format(type(value)))
        self._description = value

    @description.deleter
    def description(self):
        self._description = None

    @property
    def enabled(self):
        """The configured, desired state of the interface"""
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool):
        """The configured, desired state of the interface"""
        if not isinstance(value, bool):
            raise TypeError('enabled must be boolean, got {}'
                            .format(type(value)))
        self._enabled = value

    @enabled.deleter
    def enabled(self):
        self._enabled = None

    @property
    def mtu(self):
        """The max transmission unit size in octets"""
        return self._mtu

    @mtu.setter
    def mtu(self, value: int):
        """Set the max transmission unit size in octets"""
        if not isinstance(value, int):
            raise TypeError(f'mtu must be integer, got {type(value)}')
        self._mtu = value

    @mtu.deleter
    def mtu(self):
        self._mtu = None

    def to_xml_element(self):
        """Create XML Element

        :return: ElementTree Element with SubElements
        """
        elem = ElementTree.Element(self.TAG)
        if self.name is not None:
            ncutils.txt_subelement(
                elem, 'name', self.name,
                attrib={'operation': self.operation})
        if self.description is not None:
            ncutils.txt_subelement(
                elem, 'description', self.description,
                attrib={'operation': self.operation})
        if self.enabled is not None:
            ncutils.txt_subelement(
                elem, 'enabled', str(self.enabled).lower(),
                attrib={'operation': self.operation})
        if self.mtu is not None:
            ncutils.txt_subelement(
                elem, 'mtu', str(self.mtu),
                attrib={'operation': self.operation})
        return elem


class BaseInterface:
    """Base interface"""

    NAMESPACE = 'http://openconfig.net/yang/interfaces'
    PARENT = 'interfaces'
    TAG = 'interface'

    def __init__(self, name: str):
        self.name = name
        self._config = InterfaceConfig()

    @property
    def name(self):
        """The name of the interface."""
        return self._name

    @name.setter
    def name(self, value: str):
        """The name of the interface."""
        if not isinstance(value, str):
            raise TypeError('name must be string, got {}'.format(type(value)))
        self._name = value

    @name.deleter
    def name(self):
        self._name = None

    @property
    def config(self):
        """Configuration parameters for interface"""
        return self._config

    @config.setter
    def config(self, value):
        if not isinstance(value, InterfaceConfig):
            raise TypeError('config must be InterfaceConfig, got {}'
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
        ncutils.txt_subelement(elem, 'name', self.name)
        if self._config:
            elem.append(self.config.to_xml_element())
        return elem


class InterfaceEthernet(BaseInterface):

    def __init__(self, name: str):
        super(InterfaceEthernet, self).__init__(name)
        self._ethernet = ethernet.InterfacesEthernet()

    @property
    def ethernet(self):
        """Ethernet configuration and state"""
        return self._ethernet

    @ethernet.setter
    def ethernet(self, value):
        if not isinstance(value, ethernet.InterfacesEthernet):
            raise TypeError('ethernet must be InterfacesEthernet, got {}'
                            .format(type(value)))
        self._ethernet = value

    @ethernet.deleter
    def ethernet(self):
        self._ethernet = None

    def to_xml_element(self):
        """Create XML Element

        :return: ElementTree Element with SubElements
        """
        elem = ElementTree.Element(self.TAG)
        ncutils.txt_subelement(elem, 'name', self.name)
        if self.config:
            elem.append(self.config.to_xml_element())
        if self.ethernet:
            elem.append(self.ethernet.to_xml_element())
        return elem


class InterfaceAggregate(BaseInterface):

    def __init__(self, name: str,
                 operation: str = ncconst.NetconfEditConfigOperation.MERGE):
        super(InterfaceAggregate, self).__init__(name)
        self.operation = operation
        self._aggregation = aggregate.InterfacesAggregation()

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
    def aggregation(self):
        """Ethernet configuration and state"""
        return self._aggregation

    @aggregation.setter
    def aggregation(self, value):
        if not isinstance(value, aggregate.InterfacesAggregation):
            raise TypeError('ethernet must be OpenConfigInterfacesAggregation,'
                            'got {}'.format(type(value)))
        self._aggregation = value

    @aggregation.deleter
    def aggregation(self):
        self._aggregation = None

    def to_xml_element(self):
        """Create XML Element

        :return: ElementTree Element with SubElements
        """
        elem = ElementTree.Element(self.TAG)
        if self.operation:
            elem.set('operation', self.operation)
        ncutils.txt_subelement(elem, 'name', self.name)
        if self.config:
            elem.append(self.config.to_xml_element())
        if self.aggregation:
            elem.append(self.aggregation.to_xml_element())
        return elem


class Interfaces(abc.Collection):
    """Group/List of interfaces"""

    NAMESPACE = 'http://openconfig.net/yang/interfaces'
    TAG = 'interfaces'

    def __init__(self):
        # List of interfaces of type Interface
        self._interfaces = list()

    def __iter__(self):
        return iter(self._interfaces)

    def __len__(self):
        return len(self._interfaces)

    def __contains__(self, item):
        return item in self._interfaces

    @property
    def interfaces(self):
        """List of interfaces"""
        return self._interfaces

    def add(self, name: str,
            interface_type: str = oc_constants.IFACE_TYPE_ETHERNET):
        """Add interface

        :param name: Interface name
        :type: str
        :param interface_type: Interface type ('ethernet', 'aggregate', 'base')
        :type: str
        """
        if interface_type == oc_constants.IFACE_TYPE_ETHERNET:
            interface = InterfaceEthernet(name)
        elif interface_type == oc_constants.IFACE_TYPE_AGGREGATE:
            interface = InterfaceAggregate(name)
        elif interface_type == oc_constants.IFACE_TYPE_BASE:
            interface = BaseInterface(name)
        else:
            raise ValueError('Invalid interface type {}'.format(type(name)))
        self._interfaces.append(interface)
        return interface

    def to_xml_element(self):
        """Create XML Element

        :return: ElementTree Element with SubElements
        """
        eleme = ElementTree.Element(self.TAG)
        eleme.set('xmlns', self.NAMESPACE)
        for interface in self.interfaces:
            eleme.append(interface.to_xml_element())
        return eleme
