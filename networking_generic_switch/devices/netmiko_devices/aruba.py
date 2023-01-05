# Copyright (c) 2022 VEXXHOST, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

from networking_generic_switch.devices import netmiko_devices


class ArubaOSCX(netmiko_devices.NetmikoSwitch):
    """Built for ArubaOS-CX"""

    ADD_NETWORK = (
        'vlan {segmentation_id}',
        'name {network_name}',
    )

    DELETE_NETWORK = (
        'no vlan {segmentation_id}',
    )

    PLUG_PORT_TO_NETWORK = (
        'interface {port}',
        'no routing',
        'vlan access {segmentation_id}',
    )

    DELETE_PORT = (
        'interface {port}',
        'no vlan access {segmentation_id}',
    )

    ADD_NETWORK_TO_TRUNK = (
        "interface {port}",
        "no routing",
        "vlan trunk allowed {segmentation_id}",
    )

    REMOVE_NETWORK_FROM_TRUNK = (
        "interface {port}",
        "no vlan trunk allowed {segmentation_id}",
    )

    ENABLE_PORT = (
        "interface {port}",
        "no shutdown",
    )

    DISABLE_PORT = (
        "interface {port}",
        "shutdown",
    )
