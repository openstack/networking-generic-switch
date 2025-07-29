# Copyright 2016 Huawei Technologies Co., Ltd.
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


class Huawei(netmiko_devices.NetmikoSwitch):
    """Device Name: Huawei (VRP V3 and V5)

    For Huawei Network Operating System VRP V3 and V5.
    """
    ADD_NETWORK = (
        'vlan {segmentation_id}',
    )

    DELETE_NETWORK = (
        'undo vlan {segmentation_id}',
    )

    PLUG_PORT_TO_NETWORK = (
        'interface {port}',
        'port link-type access',
        'port default vlan {segmentation_id}',
    )

    DELETE_PORT = (
        'interface {port}',
        'undo port default vlan {segmentation_id}',
    )
