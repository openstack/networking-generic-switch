# Copyright 2022 EscherCloud.
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


class Pluribus(netmiko_devices.NetmikoSwitch):
    ADD_NETWORK = (
        'vlan-create id {segmentation_id} scope fabric\
 ports none description {network_name} auto-vxlan',
    )

    DELETE_NETWORK = (
        'vlan-delete id {segmentation_id}',
    )

    PLUG_PORT_TO_NETWORK = (
        'vlan-port-remove vlan-range all ports {port}',
        'port-vlan-add port {port} untagged-vlan {segmentation_id}',
    )

    DELETE_PORT = (
        'vlan-port-remove vlan-range all ports {port}',
    )
