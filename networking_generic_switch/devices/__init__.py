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

import abc

from oslo_log import log as logging
from oslo_utils import strutils
import stevedore

from networking_generic_switch import exceptions as gsw_exc

GENERIC_SWITCH_NAMESPACE = 'generic_switch.devices'
LOG = logging.getLogger(__name__)

# Internal ngs options will not be passed to driver.
NGS_INTERNAL_OPTS = [
    {'name': 'ngs_mac_address'},
    # Comma-separated list of names of interfaces to be added to each network.
    {'name': 'ngs_trunk_ports'},
    {'name': 'ngs_port_default_vlan'},
    # Comma-separated list of physical networks to which this switch is mapped.
    {'name': 'ngs_physical_networks'},
    {'name': 'ngs_ssh_connect_timeout', 'default': 60},
    {'name': 'ngs_ssh_connect_interval', 'default': 10},
    {'name': 'ngs_max_connections', 'default': 1},
    {'name': 'ngs_switchport_mode', 'default': 'access'},
    # If True, disable switch ports that are not in use.
    {'name': 'ngs_disable_inactive_ports', 'default': False},
    # String format for network name to configure on switches.
    # Accepts {network_id} and {segmentation_id} formatting options.
    {'name': 'ngs_network_name_format', 'default': '{network_id}'},
]


def device_manager(device_cfg):
    device_type = device_cfg.get('device_type', '')
    try:
        mgr = stevedore.driver.DriverManager(
            namespace=GENERIC_SWITCH_NAMESPACE,
            name=device_type,
            invoke_on_load=True,
            invoke_args=(device_cfg,),
            on_load_failure_callback=_load_failure_hook
        )
    except stevedore.exception.NoUniqueMatch as exc:
        raise gsw_exc.GenericSwitchEntrypointLoadError(
            ep='.'.join((GENERIC_SWITCH_NAMESPACE, device_type)),
            err=exc)
    return mgr.driver


def _load_failure_hook(manager, entrypoint, exception):
    LOG.error("Driver manager %(manager)s failed to load device plugin "
              "%(entrypoint)s: %(exp)s",
              {'manager': manager, 'entrypoint': entrypoint, 'exp': exception})
    raise gsw_exc.GenericSwitchEntrypointLoadError(
        ep=entrypoint,
        err=exception)


class GenericSwitchDevice(object, metaclass=abc.ABCMeta):

    def __init__(self, device_cfg):
        self.ngs_config = {}
        self.config = {}
        # Do not expose NGS internal options to device config.
        for opt in NGS_INTERNAL_OPTS:
            opt_name = opt['name']
            if opt_name in device_cfg.keys():
                self.ngs_config[opt_name] = device_cfg.pop(opt_name)
            elif 'default' in opt:
                self.ngs_config[opt_name] = opt['default']
        self.config = device_cfg

        self._validate_network_name_format()

    def _validate_network_name_format(self):
        """Validate the network name format configuration option."""
        network_name_format = self.ngs_config['ngs_network_name_format']
        # The format can include '{network_id}' and '{segmentation_id}'.
        try:
            network_name_format.format(network_id='dummy',
                                       segmentation_id='dummy')
        except (IndexError, KeyError):
            raise gsw_exc.GenericSwitchNetworkNameFormatInvalid(
                name_format=network_name_format)

    def _get_trunk_ports(self):
        """Return a list of trunk ports on this switch."""
        trunk_ports = self.ngs_config.get('ngs_trunk_ports')
        if not trunk_ports:
            return []
        return trunk_ports.split(',')

    def _get_port_default_vlan(self):
        """Return a default vlan of switch's interface if you specify."""
        return self.ngs_config.get('ngs_port_default_vlan', None)

    def _get_physical_networks(self):
        """Return a list of physical networks mapped to this switch."""
        physnets = self.ngs_config.get('ngs_physical_networks')
        if not physnets:
            return []
        return physnets.split(',')

    def _disable_inactive_ports(self):
        """Return whether inactive ports should be disabled."""
        return strutils.bool_from_string(
            self.ngs_config['ngs_disable_inactive_ports'])

    def _get_network_name(self, network_id, segmentation_id):
        """Return a network name to configure on switches.

        :param network_id: ID of the network.
        :param segmentation_id: segmentation ID of the network.
        :returns: a formatted network name.
        """
        network_name_format = self.ngs_config['ngs_network_name_format']
        return network_name_format.format(network_id=network_id,
                                          segmentation_id=segmentation_id)

    @abc.abstractmethod
    def add_network(self, segmentation_id, network_id):
        pass

    @abc.abstractmethod
    def del_network(self, segmentation_id, network_id):
        pass

    @abc.abstractmethod
    def plug_port_to_network(self, port_id, segmentation_id):
        pass

    @abc.abstractmethod
    def delete_port(self, port_id, segmentation_id):
        pass
