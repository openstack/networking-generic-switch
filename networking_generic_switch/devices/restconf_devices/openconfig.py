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

import json

from oslo_log import log as logging

from networking_generic_switch.devices.openconfig_mixin import (
    OpenConfigModelMixin)
from networking_generic_switch.devices.restconf_devices.restconf_switch \
    import RestconfSwitch
from networking_generic_switch.devices import utils as device_utils

LOG = logging.getLogger(__name__)


class RestconfOpenConfigSwitch(OpenConfigModelMixin, RestconfSwitch):
    """RESTCONF OpenConfig switch driver.

    Manages network and port operations using OpenConfig YANG models
    over RESTCONF transport (RFC 8040).  Callable class variables
    build OpenConfig model objects that the base class serialises to
    JSON (RFC 7951) and sends via HTTP PATCH.
    """

    def __init__(self, device_cfg, *args, **kwargs):
        super().__init__(device_cfg, *args, **kwargs)

        self._network_instance = self.ngs_config.get(
            'ngs_openconfig_network_instance', 'default')

        port_id_re_sub_raw = self.ngs_config.get(
            'ngs_port_id_re_sub', '')
        if isinstance(port_id_re_sub_raw, dict):
            self._port_id_re_sub = port_id_re_sub_raw
        elif port_id_re_sub_raw:
            self._port_id_re_sub = json.loads(port_id_re_sub_raw)
        else:
            self._port_id_re_sub = {}

        disabled_raw = self.ngs_config.get(
            'ngs_openconfig_disabled_properties', '')
        if isinstance(disabled_raw, list):
            self._disabled_properties = disabled_raw
        elif disabled_raw:
            self._disabled_properties = [
                p.strip() for p in disabled_raw.split(',')]
        else:
            self._disabled_properties = []

    def _port_id_resub(self, port_id):
        """Apply configured regex substitution to a port ID.

        :param port_id: Original port identifier from local link info.
        :returns: Possibly modified port identifier.
        """
        return device_utils.port_id_resub(port_id, self._port_id_re_sub)

    @property
    def support_trunk_on_ports(self):
        return True

    ADD_NETWORK = staticmethod(OpenConfigModelMixin._add_network)
    DELETE_NETWORK = staticmethod(OpenConfigModelMixin._delete_network)
    ADD_NETWORK_TO_TRUNK = staticmethod(
        OpenConfigModelMixin._add_network_to_trunk)
    REMOVE_NETWORK_FROM_TRUNK = staticmethod(
        OpenConfigModelMixin._remove_network_from_trunk)
    PLUG_PORT_TO_NETWORK = staticmethod(
        OpenConfigModelMixin._plug_port_to_network)
    DELETE_PORT = staticmethod(OpenConfigModelMixin._delete_port)
    ENABLE_PORT = staticmethod(OpenConfigModelMixin._enable_port)
    DISABLE_PORT = staticmethod(OpenConfigModelMixin._disable_port)
    ADD_SUBPORTS_ON_TRUNK = staticmethod(
        OpenConfigModelMixin._add_subports_on_trunk)
    DEL_SUBPORTS_ON_TRUNK = staticmethod(
        OpenConfigModelMixin._del_subports_on_trunk)
