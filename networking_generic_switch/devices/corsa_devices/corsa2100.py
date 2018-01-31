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

from oslo_log import log as logging

from networking_generic_switch.devices import corsa_devices
from networking_generic_switch import exceptions as exc

LOG = logging.getLogger(__name__)

class CorsaDP2100(corsa_devices.CorsaSwitch):
    PLUG_PORT_TO_NETWORK = (
        'interface vlan {segmentation_id}',
        'untagged {port}'
    )

    DELETE_PORT = (
        'interface vlan {segmentation_id}',
        'no untagged {port}'
    )

    @staticmethod
    def _detect_plug_port_failure(raw_output, port, vlan):
	LOG.info('PRUTH: in _detect_plug_port_failure(raw_output, port, vlan) ') 


        PATTERN = "Error: .* Port is untagged in another Vlan."
        match = re.search(PATTERN, raw_output)
        if match:
            raise exc.GenericSwitchPlugPortToNetworkError(port=port,
                                                          vlan=vlan,
                                                          error=match.group(0))

#    def plug_port_to_network(self, port, segmentation_id):
#	LOG.info('PRUTH: in plug_port_to_network(self, port, segmentation_id) ')
#
#        raw_output = self.send_commands_to_device(
#            self._format_commands(self.PLUG_PORT_TO_NETWORK,
#                                  port=port,
#                                  segmentation_id=segmentation_id))
#        self._detect_plug_port_failure(str(raw_output), port, segmentation_id)
