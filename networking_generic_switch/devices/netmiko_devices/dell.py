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

    DELETE_AND_PLUG_PORT = (
        'interface vlan {wrong_segmentation_id}',
        'no untagged {port}',
        'interface vlan {segmentation_id}',
        'untagged {port}'
    )

    @staticmethod
    def _detect_plug_port_failure(raw_output, port, vlan):
        PATTERN = "Error: .* Port is untagged in another Vlan."
        match = re.search(PATTERN, raw_output)
        if match:
            raise exc.GenericSwitchPlugPortToNetworkError(port=port,
                                                          vlan=vlan,
                                                          error=match.group(0))

    def plug_port_to_network(self, port, segmentation_id):
        # get current vlan
        raw_output = self.send_commands_to_device(
            self._format_commands(self.QUERY_PORT, port=port)
        )
        PATTERN = "U\s*(\d+)"
        current_vlan = re.search(PATTERN, raw_output).group(1)

        if ( current_vlan == str(segmentation_id) ): # Already set as needed
            LOG.debug(
                'Port %s is used in VLAN %s, intended VLAN is %s, no action taken.',
                port,
                str(current_vlan),
                str(segmentation_id)
            )
            return

        if ( current_vlan == '1' ):             # Port is clean
            LOG.debug(
                'Port %s is clean!',
                port,
            )
            raw_output = self.send_commands_to_device(
                self._format_commands(self.PLUG_PORT_TO_NETWORK,
                                      port=port,
                                      segmentation_id=segmentation_id))
        else:                                   # Port has existing & incorrect VLAN
            LOG.warning(
                'Port %s is used in VLAN %s, attempting to clean it',
                port,
                current_vlan
            )
            raw_output = self.send_commands_to_device(
                self._format_commands(self.DELETE_AND_PLUG_PORT,
                                      port=port,
                                      wrong_segmentation_id=current_vlan,
                                      segmentation_id=segmentation_id))

        self._detect_plug_port_failure(str(raw_output), port, segmentation_id)

