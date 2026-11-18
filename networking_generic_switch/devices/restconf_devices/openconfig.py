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
from urllib.parse import quote

from oslo_log import log as logging

from networking_generic_switch.devices.openconfig_mixin import (
    OpenConfigModelMixin)
from networking_generic_switch.devices.restconf_devices.restconf_switch \
    import RestconfSwitch
from networking_generic_switch.devices import utils as device_utils
from networking_generic_switch import exceptions as exc

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

    def get_port_vlans(self, port_id):
        """Return the VLANs currently configured on a switch port.

        Reads the OpenConfig switched-vlan container for the port via
        a read-only RESTCONF GET, covering the access, native and
        trunk VLANs. The path is composed directly rather than built
        from model objects: a read needs only the resource path, and
        building a model to serialize it back into a URL would be
        ceremony.

        A trunk with no trunk-vlans entries has no per-port VLAN
        forwarding rule, so it consumes no per-port VLAN capacity and
        adds nothing to the count; an explicit range such as
        ``1..4094`` does count.

        :param port_id: Name of the switch interface.
        :returns: A sorted list of VLAN IDs configured on the port, or
                  None when the query fails or the response is not
                  recognised, in which case per-port VLAN limits
                  cannot be enforced on the port.
        """
        port = self._port_id_resub(port_id)
        path = (
            'openconfig-interfaces:interfaces'
            f'/interface={quote(port, safe="")}'
            '/openconfig-if-ethernet:ethernet'
            '/openconfig-vlan:switched-vlan'
        )
        try:
            response = self.get_from_device(path)
        except exc.GenericSwitchRestconfError as e:
            LOG.warning("Failed to query VLANs on port %(port)s of "
                        "switch %(dev)s: %(err)s",
                        {'port': port_id, 'dev': self.device_name, 'err': e})
            return None
        return self._parse_port_vlans(response)

    @staticmethod
    def _parse_port_vlans(response):
        """Parse a switched-vlan RESTCONF response into VLAN IDs.

        :param response: Parsed JSON response dict.
        :returns: A sorted list of VLAN IDs, or None when the response
                  does not carry a switched-vlan container.
        """
        if not isinstance(response, dict):
            return None
        # The container is an openconfig-vlan augmentation; servers
        # namespace it with its defining module, but tolerate an
        # unprefixed key and a missing module name.
        switched = None
        for key, value in response.items():
            if isinstance(value, dict) and key.endswith('switched-vlan'):
                switched = value
                break
        if switched is None:
            return None
        config = switched.get('config', switched)
        if not isinstance(config, dict):
            return None
        vlans = set()
        for leaf in ('access-vlan', 'native-vlan'):
            value = config.get(leaf)
            if isinstance(value, int) and not isinstance(value, bool):
                vlans.add(value)
        trunk_vlans = config.get('trunk-vlans', [])
        if isinstance(trunk_vlans, list):
            vlans.update(device_utils.expand_openconfig_trunk_vlans(
                trunk_vlans))
        return sorted(vlans)

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
