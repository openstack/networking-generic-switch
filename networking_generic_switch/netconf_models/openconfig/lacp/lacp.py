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
from xml.etree import ElementTree

from networking_generic_switch.netconf_models import constants as ncconst
from networking_generic_switch.netconf_models.openconfig.lacp import types
from networking_generic_switch.netconf_models import utils as ncutils


class LACP:
    """LACP Top level

    LACP configuration and state variable containers
    """

    NAMESPACE = 'http://openconfig.net/yang/lacp'
    TAG = 'lacp'

    def __init__(self):
        self._config = None
        self._interfaces = LACPInterfaces()

    @property
    def interfaces(self):
        return self._interfaces

    @interfaces.setter
    def interfaces(self, value):
        if not isinstance(value, LACPInterfaces):
            raise TypeError('interfaces must be OpenConfigLACPInterfaces,'
                            'got {}'.format(type(value)))
        self._interfaces = value

    @interfaces.deleter
    def interfaces(self):
        self._interfaces = None

    def to_xml_element(self):
        """Create XML Element

        :return: ElementTree Element with SubElements
        """
        elem = ElementTree.Element(self.TAG)
        elem.set('xmlns', self.NAMESPACE)
        if self.interfaces:
            elem.append(self.interfaces.to_xml_element())
        return elem


class LACPInterfaces(abc.Collection):
    """Top-level grouping for LACP-enabled interfaces"""

    NAMESPACE = 'http://openconfig.net/yang/lacp'
    PARENT = 'lacp'
    TAG = 'interfaces'

    def __init__(self):
        # List of interfaces of type OpenconfigInterface
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

    def add(self, name: str):
        """Add interface

        :param name: Interface name
        :type: str
        """
        interface = LACPInterface(name)
        self._interfaces.append(interface)
        return interface

    def to_xml_element(self):
        """Create XML Element

        :return: ElementTree Element with SubElements
        """
        elem = ElementTree.Element(self.TAG)
        for interface in self.interfaces:
            elem.append(interface.to_xml_element())
        return elem


class LACPInterface:
    """Base LACP aggregate interface"""

    NAMESPACE = 'http://openconfig.net/yang/lacp'
    PARENT = 'interfaces'
    TAG = 'interface'

    def __init__(self, name: str,
                 operation=ncconst.NetconfEditConfigOperation.MERGE):
        self.operation = operation
        self._config = LACPInterfaceConfig(name)
        self.name = name

    @property
    def operation(self):
        """RFC 6241 - <edit-config> operation attribute"""
        return self._operation.value

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

    @property
    def name(self):
        """The name of the LACP aggregate interface."""
        return self._name

    @name.setter
    def name(self, value: str):
        """The name of the LACP aggregate interface."""
        if not isinstance(value, str):
            raise TypeError('name must be string, got {}'.format(type(value)))
        self._name = value
        # 'name' in the configuration is leaf-ref, should match.
        if self.config is not None:
            self.config.name = self.name

    @name.deleter
    def name(self):
        self._name = None

    @property
    def config(self):
        """Configuration data for each LACP aggregate interface"""
        return self._config

    @config.setter
    def config(self, value):
        if not isinstance(value, LACPInterfaceConfig):
            raise TypeError('config must be LACPInterfaceConfig,'
                            'got {}'.format(type(value)))
        self._config = value

    @config.deleter
    def config(self):
        self._config = None

    def to_xml_element(self):
        """Create XML Element

        :return: ElementTree Element with SubElements
        """
        elem = ElementTree.Element(self.TAG)
        elem.set('operation', self.operation)
        if self.name:
            ncutils.txt_subelement(elem, 'name', self.name)
        if self.config:
            elem.append(self.config.to_xml_element())
        return elem


class LACPInterfaceConfig:
    """OpenConfig LACP aggregate interface configuration"""

    NAMESPACE = 'http://openconfig.net/yang/lacp'
    PARENT = 'interface'
    TAG = 'config'

    def __init__(self, name: str,
                 operation=ncconst.NetconfEditConfigOperation.MERGE,
                 interval=types.LACPPeriod.SLOW,
                 lacp_mode=types.LACPActivity.ACTIVE):
        self._name = name
        self.operation = operation
        self.interval = interval
        self.lacp_mode = lacp_mode

    @property
    def operation(self):
        """RFC 6241 - <edit-config> operation attribute"""
        return self._operation.value

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

    @property
    def name(self):
        """The name of the interface."""
        return self._name

    @name.setter
    def name(self, value: str):
        if not isinstance(value, str):
            raise TypeError('name must be string, got {}'.format(type(value)))
        self._name = value

    @name.deleter
    def name(self):
        self._name = None

    @property
    def interval(self):
        """The period between LACP messages"""
        return self._interval.value if self._interval else None

    @interval.setter
    def interval(self, value: str):
        """Set the period between LACP messages (SLOW or FAST)"""
        if isinstance(value, types.LACPPeriod):
            self._interval = value
        elif isinstance(value, str):
            self._interval = types.LACPPeriod(value)
        else:
            raise TypeError('Invalid type {} for LACP interface interval.'
                            .format(type(value)))

    @interval.deleter
    def interval(self):
        self._interval = None

    @property
    def lacp_mode(self):
        """The LACP mode if the aggregate interface"""
        return self._lacp_mode.value

    @lacp_mode.setter
    def lacp_mode(self, value: str):
        """Set the LACP mode if the aggregate interface

        ACTIVE:  is to initiate the transmission of LACP packets.
        PASSIVE: is to wait for peer to initiate the transmission of
                 LACP packets
        """
        if isinstance(value, types.LACPActivity):
            self._lacp_mode = value
        elif isinstance(value, str):
            self._lacp_mode = types.LACPActivity(value)
        else:
            raise TypeError('Invalid type {} for LACP interface mode.'
                            .format(type(value)))

    @lacp_mode.deleter
    def lacp_mode(self):
        self._lacp_mode = None

    def to_xml_element(self):
        """Create XML Element

        :return: ElementTree Element with SubElements
        """
        elem = ElementTree.Element(self.TAG)
        elem.set('operation', self.operation)
        if self.name is not None:
            ncutils.txt_subelement(elem, 'name', self.name)
        if self.interval is not None:
            ncutils.txt_subelement(elem, 'interval', self.interval)
        if self.lacp_mode is not None:
            ncutils.txt_subelement(elem, 'lacp-mode', self.lacp_mode)
        return elem
