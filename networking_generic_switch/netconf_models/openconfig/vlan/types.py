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
import enum
import re

from networking_generic_switch.netconf_models.openconfig import constants


class VlanStatus(enum.Enum):
    """VLAN Admin state

    ACTIVE: VLAN is active
    SUSPENDED: VLAN is inactive / suspended
    """
    ACTIVE = constants.VLAN_ACTIVE
    SUSPENDED = constants.VLAN_SUSPENDED


class VlanInterfaceMode(enum.Enum):
    """VLAN interface mode (trunk or access)"""
    TRUNK = constants.VLAN_MODE_TRUNK
    ACCESS = constants.VLAN_MODE_ACCESS


class VlanId:
    """Type definition representing a single-tagged VLAN"""

    def __init__(self, vlan_id: int):
        if not isinstance(vlan_id, int):
            raise TypeError('vlan_id must be integer, got {}'
                            .format(type(vlan_id)))
        if vlan_id not in constants.VLAN_RANGE:
            raise ValueError('Invalid vlan id: {vlan_id} not in {range}'
                             .format(vlan_id=vlan_id,
                                     range=constants.VLAN_RANGE))
        self._vlan_id = vlan_id

    @property
    def vlan_id(self):
        return self._vlan_id


class VlanRange:
    """Type definition representing a range of single-tagged VLANs.

    A range is specified as x..y where x and y are
    valid VLAN IDs (1 <= vlan-id <= 4094). The range is
    assumed to be inclusive, such that any VLAN-ID matching
    x <= VLAN-ID <= y falls within the range."
    """
    # range specified as [lower]..[upper]
    pattern = re.compile(
        ('^(409[0-4]|40[0-8][0-9]|[1-3][0-9]{3}|'
         '[1-9][0-9]{1,2}|[1-9])\\.\\.(409[0-4]|'
         '40[0-8][0-9]|[1-3][0-9]{3}|[1-9][0-9]{1,2}|'
         '[1-9])$'))

    def __init__(self, vlan_range: str):
        if not isinstance(vlan_range, str):
            raise TypeError('vlan_range must be string, got {}'
                            .format(type(vlan_range)))
        if not self.pattern.match(vlan_range):
            raise ValueError('Invalid VLAN range {}'.format(vlan_range))
        lower, _, upper = vlan_range.partition('..')
        if not int(lower) <= int(upper):
            raise ValueError('Invalid VLAN range {}'.format(vlan_range))
        self._vlan_range = vlan_range

    @property
    def vlan_range(self):
        return self._vlan_range
