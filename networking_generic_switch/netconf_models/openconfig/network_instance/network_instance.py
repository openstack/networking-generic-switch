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

from networking_generic_switch.netconf_models.openconfig.vlan import vlan
from networking_generic_switch.netconf_models import utils as ncutils


class NetworkInstances(abc.Collection):
    """Top-level grouping containing a list of network instances."""

    NAMESPACE = 'http://openconfig.net/yang/network-instance'
    TAG = 'network-instances'

    def __init__(self):
        self._network_instances = list()

    def __iter__(self):
        return iter(self._network_instances)

    def __len__(self):
        return len(self._network_instances)

    def __contains__(self, item):
        return item in self._network_instances

    @property
    def network_instances(self):
        return self._network_instances

    def add(self, name: str):
        """Add network instance

        :param name: A unique name identifying the network instance
        :type: str
        :Keyword arguments: Network instance arguments
        """
        network_instance = NetworkInstance(name)
        self._network_instances.append(network_instance)
        return network_instance

    def to_xml_element(self):
        """Create XML Element

        :return: ElementTree Element with SubElements
        """
        elem = ElementTree.Element(self.TAG)
        elem.set('xmlns', self.NAMESPACE)
        for instance in self.network_instances:
            elem.append(instance.to_xml_element())
        return elem


class NetworkInstance:
    """An OpenConfig description of a network_instance.

    This may be a Layer 3 forwarding construct such as a virtual
    routing and forwarding (VRF) instance, or a Layer 2 instance
    such as a virtual switch instance (VSI). Mixed Layer 2 and
    Layer 3 instances are also supported.
    """
    NAMESPACE = 'http://openconfig.net/yang/network-instance'
    TAG = 'network-instance'

    def __init__(self, name):
        self.name = name
        self._vlans = vlan.Vlans()

    @property
    def name(self):
        """A unique name identifying the network instance"""
        return self._name

    @name.setter
    def name(self, value: str):
        """A unique name identifying the network instance"""
        if not isinstance(value, str):
            raise TypeError('name must be string, got {}'.format(type(value)))
        self._name = value

    @name.deleter
    def name(self):
        self._name = None

    @property
    def vlans(self):
        """Group/List of VLANs - keyed by id"""
        return self._vlans

    @vlans.setter
    def vlans(self, value):
        if not isinstance(value, vlan.Vlans):
            raise TypeError('vlans must be Vlans, got {}'.format(type(value)))
        self._vlans = value

    @vlans.deleter
    def vlans(self):
        self._vlans = None

    def to_xml_element(self):
        """Create XML Element

        :return: ElementTree Element with SubElements
        """
        elem = ElementTree.Element(self.TAG)
        if self.name:
            ncutils.txt_subelement(elem, 'name', self.name)
        if self.vlans:
            elem.append(self.vlans.to_xml_element())
        return elem
