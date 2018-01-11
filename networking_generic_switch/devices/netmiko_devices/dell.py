# Copyright 2016 Mirantis, Inc.
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

from networking_generic_switch.devices import netmiko_devices
from networking_generic_switch import exceptions as exc

from oslo_log import log as logging
LOG = logging.getLogger(__name__)

class DellNos(netmiko_devices.NetmikoSwitch):
    PLUG_PORT_TO_NETWORK = (
        'interface vlan {segmentation_id}',
        'untagged {port}'
    )

    DELETE_PORT = (
        'interface vlan {segmentation_id}',
        'no untagged {port}',
    )

    QUERY_PORT = (
        'end',
        'show interfaces switchport {port} | grep ^U',
    )

    @staticmethod
    def _detect_plug_port_failure(raw_output, port, vlan):
        PATTERN = "Error: .* Port is untagged in another Vlan."
        match = re.search(PATTERN, raw_output)
        if match:
            raise exc.GenericSwitchPlugPortToNetworkError(port=port,
                                                          vlan=vlan,
                                                          error=match.group(0))
    def _get_wrong_vlan(self, port):
        raw_output = self.send_commands_to_device(
            self._format_commands(self.QUERY_PORT, port=port)
        )
        PATTERN = "U\s*(\d+)"
        match = re.search(PATTERN, raw_output)
        current_vlan = match.group(1)
        if not match:
            return None
        return current_vlan  # vlan_id

    def _clean_port_vlan_if_necessary(self, port):
        wrong_vlan = self._get_wrong_vlan(port)
        if not wrong_vlan:
            return
        if str(wrong_vlan) == '1':
            return
        LOG.warning(
            'Port %s is used in VLAN %s, attempting to clean it',
            port,
            str(wrong_vlan)
        )
        self.delete_port(port, wrong_vlan)

    def plug_port_to_network(self, port, segmentation_id):
        self._clean_port_vlan_if_necessary(port)
        raw_output = self.send_commands_to_device(
            self._format_commands(self.PLUG_PORT_TO_NETWORK,
                                  port=port,
                                  segmentation_id=segmentation_id))
        self._detect_plug_port_failure(str(raw_output), port, segmentation_id)

