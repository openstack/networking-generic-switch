# Copyright 2017 Servers.com
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


import re

from oslo_log import log as logging

from networking_generic_switch.devices import netmiko_devices


LOG = logging.getLogger(__name__)


class BrocadeFastIron(netmiko_devices.NetmikoSwitch):
    ADD_NETWORK = (
        'vlan {segmentation_id} by port',
        'name {network_name}',
    )

    DELETE_NETWORK = (
        'no vlan {segmentation_id}',
    )

    PLUG_PORT_TO_NETWORK = (
        'vlan {segmentation_id} by port',
        'untagged ether {port}',
    )

    DELETE_PORT = (
        'vlan {segmentation_id} by port',
        'no untagged ether {port}',
    )

    QUERY_PORT = (
        'show interfaces ether {port} | include VLAN',
    )

    @staticmethod
    def _process_raw_output(raw_output):
        PATTERN = "Member of L2 VLAN ID (\\d+), port is untagged"
        match = re.search(PATTERN, raw_output)
        if not match:
            return None
        return match.group(1)  # vlan_id

    def get_wrong_vlan(self, port):
        raw_output = self.send_commands_to_device(
            self._format_commands(self.QUERY_PORT, port=port)
        )
        return self._process_raw_output(str(raw_output))

    def clean_port_vlan_if_necessary(self, port):
        wrong_vlan = self.get_wrong_vlan(port)
        if not wrong_vlan:
            return
        if str(wrong_vlan) == '1':
            return
        LOG.warning(
            'Port %s is used in a wrong vlan %s, clean it',
            port,
            str(wrong_vlan)
        )
        self.delete_port(port, wrong_vlan)

    @netmiko_devices.check_output('plug port')
    def plug_port_to_network(self, port, segmentation_id):
        self.clean_port_vlan_if_necessary(port)
        return super(BrocadeFastIron, self).plug_port_to_network(
            port, segmentation_id)
