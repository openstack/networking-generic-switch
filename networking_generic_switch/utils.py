# Copyright 2025 Mirantis, Inc.
#
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

from neutron_lib.api.definitions import portbindings


def is_802_3ad(binding_profile):
    """Return whether a port binding profile is using 802.3ad link aggregation.

    :param binding_profile: The port binding_profile to check
    :returns: Whether the port is a port group using 802.3ad link
              aggregation.
    """
    binding_profile = binding_profile or {}
    local_group_information = binding_profile.get(
        'local_group_information')
    if not local_group_information:
        return False
    return local_group_information.get('bond_mode') in ['4', '802.3ad']


def is_port_supported(port):
    """Return whether a port is supported by this driver.

    Ports supported by this driver have a VNIC type of 'baremetal'.

    :param port: The port to check
    :returns: Whether the port is supported by the NGS driver
    """
    vnic_type = port[portbindings.VNIC_TYPE]
    return vnic_type == portbindings.VNIC_BAREMETAL


def is_port_bound(port):
    """Return whether a port is bound by this driver.

    Ports bound by this driver have their VIF type set to 'other'.

    :param port: The port to check
    :returns: Whether the port is bound by the NGS driver
    """
    if not is_port_supported(port):
        return False

    vif_type = port[portbindings.VIF_TYPE]
    return vif_type == portbindings.VIF_TYPE_OTHER
