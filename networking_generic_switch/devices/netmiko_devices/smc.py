# Copyright 2024 Nscale.
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

from networking_generic_switch.devices import netmiko_devices


class SupermicroSmis(netmiko_devices.NetmikoSwitch):
    """A class to represent a Supermicro SMIS switch"""
    """
    Inherits from:
    --------------
    netmiko_devices.NetmikoSwitch

    Class Attributes:
    -----------------
    ADD_NETWORK : tuple
        A tuple of command strings used to add a VLAN
        with a specific segmentation ID
        and name the VLAN.

    DELETE_NETWORK : tuple
        A tuple of command strings used to delete a VLAN
        by its segmentation ID.

    PLUG_PORT_TO_NETWORK : tuple
        A tuple of command strings used to configure a port
        to connect to a specific VLAN.
        This sets the port to access mode and assigns it
        to the specified VLAN.

    DELETE_PORT : tuple
        A tuple of command strings used to remove a port
        from the VLAN. This removes
        any trunking configuration and clears VLAN assignments.
    """
    ADD_NETWORK = (
        'vlan {segmentation_id}',
        'name {network_name}',
    )

    DELETE_NETWORK = (
        'no vlan {segmentation_id}',
    )

    PLUG_PORT_TO_NETWORK = (
        'interface {port}',
        'switchport mode access',
        'switchport access vlan {segmentation_id}',
    )

    DELETE_PORT = (
        'interface {port}',
        'no switchport access vlan {segmentation_id}',
        'no switchport mode trunk',
        'switchport trunk allowed vlan none'
    )
