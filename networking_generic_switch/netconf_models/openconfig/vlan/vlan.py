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
from networking_generic_switch.netconf_models.openconfig.vlan import types
from networking_generic_switch.netconf_models import utils as ncutils


class TrunkVlans(abc.Collection):

    def __init__(self):
        self._trunk_vlans = []
        self._removals = []

    def __iter__(self):
        return iter(self._trunk_vlans)

    def __len__(self):
        return len(self._trunk_vlans)

    def __contains__(self, item):
        return item in self._trunk_vlans

    def add(self, value):
        """Add vlan or range of vlans (range: 100..200)"""
        try:
            value = int(value)
            if value not in self._trunk_vlans:
                self._trunk_vlans.append(types.VlanId(value).vlan_id)
        except ValueError:
            if value not in self._trunk_vlans:
                self._trunk_vlans.append(types.VlanRange(value).vlan_range)

    def remove(self, value):
        """Mark vlan or range for removal (range: 100..200)"""
        try:
            value = int(value)
            if value not in self._removals:
                self._removals.append(types.VlanId(value).vlan_id)
        except ValueError:
            if value not in self._removals:
                self._removals.append(types.VlanRange(value).vlan_range)


class VlanSwitchedConfig:
    """Ethernet interface VLAN config

    VLAN related configuration that is part of the physical
    Ethernet interface.
    """
    NAMESPACE = 'http://openconfig.net/yang/vlan'
    PARENT = 'switched-vlan'
    TAG = 'config'

    def __init__(self,
                 operation: str = ncconst.NetconfEditConfigOperation.MERGE,
                 interface_mode: Optional[str] = None,
                 native_vlan: Optional[int] = None,
                 access_vlan: Optional[int] = None):

        self.operation = operation
        self._interface_mode = None
        self._native_vlan = None
        self._access_vlan = None
        self._trunk_vlans = TrunkVlans()
        if interface_mode:
            self.interface_mode = interface_mode
        if native_vlan:
            self.native_vlan = native_vlan
        if access_vlan:
            self.access_vlan = access_vlan

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
    def interface_mode(self):
        """Get the interface to access or trunk mode for VLANs"""
        return self._interface_mode.value if self._interface_mode else None

    @interface_mode.setter
    def interface_mode(self, value):
        """Set the interface to access or trunk mode for VLANs"""
        self._interface_mode = types.VlanInterfaceMode(value)

    @interface_mode.deleter
    def interface_mode(self):
        """Delete the interface to access or trunk mode for VLANs"""
        self._interface_mode = None

    @property
    def native_vlan(self):
        """Native VLAN

         is valid for trunk mode interfaces
         """
        return self._native_vlan.vlan_id if self._native_vlan else None

    # TODO(hjensas): Only allow if interface_mode == trunk
    @native_vlan.setter
    def native_vlan(self, value: int):
        """Set native VLAN

        is valid for trunk mode interfaces
        """
        self._native_vlan = types.VlanId(value)

    @native_vlan.deleter
    def native_vlan(self):
        """Delete native VLAN"""
        self._native_vlan = None

    # TODO(hjensas): Only allow if interface_mode == access
    @property
    def access_vlan(self):
        """Access VLAN assigned to the interfaces"""
        return self._access_vlan.vlan_id if self._access_vlan else None

    @access_vlan.setter
    def access_vlan(self, value: int):
        """Set access VLAN assigned to the interfaces"""
        self._access_vlan = types.VlanId(value)

    @access_vlan.deleter
    def access_vlan(self):
        """Unset access VLAN assigned to the interfaces"""
        self._access_vlan = None

    @property
    def trunk_vlans(self):
        """Allowed VLANs may be specified for trunk mode interfaces"""
        return self._trunk_vlans

    # TODO(hjensas): Only allow if interface_mode == trunk
    @trunk_vlans.setter
    def trunk_vlans(self, value: str):
        """Set allowed VLANs may be specified for trunk mode interfaces"""
        self._trunk_vlans.add(value)

    @trunk_vlans.deleter
    def trunk_vlans(self):
        self._trunk_vlans = TrunkVlans()

    def to_xml_element(self):
        """Create XML Element

        :return: ElementTree Element with SubElements
        """
        elem = ElementTree.Element(self.TAG)
        if self.operation:
            elem.set('operation', self.operation)
        if self.access_vlan is not None:
            ncutils.txt_subelement(elem, 'access-vlan', str(self.access_vlan))
        if self.native_vlan is not None:
            ncutils.txt_subelement(elem, 'native-vlan', str(self.native_vlan))
        if self.trunk_vlans is not None:
            for item in self.trunk_vlans:
                ncutils.txt_subelement(
                    elem, 'trunk-vlans', str(item))
            for item in self.trunk_vlans._removals:
                ncutils.txt_subelement(
                    elem, 'trunk-vlans', str(item),
                    attrib={
                        'operation':
                            ncconst.NetconfEditConfigOperation.REMOVE.value})
        if self.interface_mode:
            ncutils.txt_subelement(
                elem, 'interface-mode', self.interface_mode)
        return elem


class VlanSwitchedVlan:
    """VLAN interface-specific data on Ethernet interfaces.

    Enclosing container for VLAN interface-specific
    data on Ethernet interfaces. These are for standard
    L2, switched-style VLANs.
    """
    NAMESPACE = 'http://openconfig.net/yang/vlan'
    PARENT = 'ethernet'
    TAG = 'switched-vlan'

    def __init__(self):
        self._config = VlanSwitchedConfig()

    @property
    def config(self):
        """Configuration parameters for VLANs"""
        return self._config

    @config.setter
    def config(self, value):
        if not isinstance(value, VlanSwitchedConfig):
            raise TypeError('config must be VlanSwitchedConfig, got {}'
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
        return elem


class VlanConfig:
    """OpenConfig VLAN configuration"""

    NAMESPACE = 'http://openconfig.net/yang/vlan'
    PARENT = 'vlan'
    TAG = 'config'

    def __init__(self,
                 operation=ncconst.NetconfEditConfigOperation.MERGE,
                 vlan_id: int = None,
                 name: str = None,
                 status: str = None):
        self.operation = operation
        self._vlan_id = None
        self._name = None
        self._status = None
        if vlan_id:
            self.vlan_id = vlan_id
        if name:
            self.name = name
        if status:
            self.status = status

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
    def vlan_id(self):
        """The id of the VLAN"""
        return self._vlan_id.vlan_id if self._vlan_id else None

    @vlan_id.setter
    def vlan_id(self, value: int):
        self._vlan_id = types.VlanId(value)

    @vlan_id.deleter
    def vlan_id(self):
        self._vlan_id = None

    @property
    def name(self):
        """Interface VLAN name."""
        return self._name

    @name.setter
    def name(self, value: str):
        if not isinstance(value, str):
            raise TypeError('name must be string, got {}'
                            .format(type(value)))
        self._name = value

    @name.deleter
    def name(self):
        self._name = None

    @property
    def status(self):
        """Admin state of the VLAN"""
        return self._status.value if self._status else None

    @status.setter
    def status(self, value: str):
        """Admin state of the VLAN"""
        self._status = types.VlanStatus(value)

    @status.deleter
    def status(self):
        self._status = None

    def to_xml_element(self):
        """Create XML Element

        :return: ElementTree Element with SubElements
        """
        elem = ElementTree.Element(self.TAG)
        elem.set('operation', self.operation)
        if self.vlan_id is not None:
            ncutils.txt_subelement(elem, 'vlan-id', str(self.vlan_id))
        if self.name is not None:
            ncutils.txt_subelement(elem, 'name', self.name)
        if self.status is not None:
            ncutils.txt_subelement(elem, 'status', self.status)
        return elem


class Vlan:
    """Base vlan"""

    NAMESPACE = 'http://openconfig.net/yang/vlan'
    PARENT = 'vlans'
    TAG = 'vlan'

    def __init__(self, vlan_id: int,
                 operation=ncconst.NetconfEditConfigOperation.MERGE):
        self.operation = operation
        self.vlan_id = vlan_id
        self._config = VlanConfig(vlan_id=self.vlan_id)

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
            raise TypeError('Invalid type {} for config operation '
                            'attribute.'.format(type(value)))

    @property
    def vlan_id(self):
        """The id of the VLAN"""
        return self._vlan_id.vlan_id

    @vlan_id.setter
    def vlan_id(self, value: int):
        if not isinstance(value, int):
            raise TypeError(f'vlan_id must be integer, got {type(value)}')
        self._vlan_id = types.VlanId(value)

    @vlan_id.deleter
    def vlan_id(self):
        self._vlan_id = None

    @property
    def config(self):
        """Configuration parameters for VLAN"""
        return self._config

    @config.setter
    def config(self, value):
        """Configuration parameters for VLAN"""
        if not isinstance(value, VlanConfig):
            raise TypeError('config must be VlanConfig, got {}'
                            .format(type(value)))
        self._config = value
        if self.vlan_id:
            self.config.vlan_id = self.vlan_id

    @config.deleter
    def config(self):
        self._config = None

    def to_xml_element(self):
        """Create XML Element

        :return: ElementTree Element with SubElements
        """
        elem = ElementTree.Element(self.TAG)
        if self.vlan_id:
            ncutils.txt_subelement(
                elem, 'vlan-id', str(self.vlan_id),
                attrib={'operation': self.operation})
        if self.config:
            elem.append(self.config.to_xml_element())
        return elem


class Vlans(abc.Collection):
    """Group/List of VLANs"""

    NAMESPACE = 'http://openconfig.net/yang/vlan'
    TAG = 'vlans'

    def __init__(self):
        # List of vlans of type OpenconfigVlan
        self._vlans = list()

    def __iter__(self):
        return iter(self._vlans)

    def __len__(self):
        return len(self._vlans)

    def __contains__(self, item):
        return item in self._vlans

    @property
    def vlans(self):
        """List of VLANs"""
        return self._vlans

    def add(self, vlan_id: int):
        """Add VLAN

        :param vlan_id: VLAN ID
        :type: int
        :Keyword arguments: VLAN configuration
        """
        vlan = Vlan(vlan_id)
        self._vlans.append(vlan)
        return vlan

    def remove(self, vlan_id: int):
        """Remove VLAN

        :param vlan_id: VLAN ID
        :type: int
        """
        vlan = Vlan(vlan_id)
        vlan.operation = ncconst.NetconfEditConfigOperation.REMOVE
        self._vlans.append(vlan)
        return vlan

    def to_xml_element(self):
        """Create XML Element

        :return: ElementTree Element with SubElements
        """
        elem = ElementTree.Element(self.TAG)
        elem.set('xmlns', self.NAMESPACE)
        for vlan in self.vlans:
            elem.append(vlan.to_xml_element())
        return elem
