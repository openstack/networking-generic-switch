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
import six
import stevedore

from networking_generic_switch import exceptions as gsw_exc

GENERIC_SWITCH_NAMESPACE = 'generic_switch.devices'
LOG = logging.getLogger(__name__)

# Internal ngs options will not be passed to driver.
NGS_INTERNAL_OPTS = [
    {'name': 'ngs_mac_address'},
    # Comma-separated list of names of interfaces to be added to each network.
    {'name': 'ngs_trunk_ports'},
    # Comma-separated list of physical networks to which this switch is mapped.
    {'name': 'ngs_physical_networks'},
    {'name': 'ngs_ssh_connect_timeout', 'default': 60},
    {'name': 'ngs_ssh_connect_interval', 'default': 10},
    {'name': 'ngs_max_connections', 'default': 1},
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


@six.add_metaclass(abc.ABCMeta)
class GenericSwitchDevice(object):

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

    def _get_trunk_ports(self):
        """Return a list of trunk ports on this switch."""
        trunk_ports = self.ngs_config.get('ngs_trunk_ports')
        if not trunk_ports:
            return []
        return trunk_ports.split(',')

    def _get_physical_networks(self):
        """Return a list of physical networks mapped to this switch."""
        physnets = self.ngs_config.get('ngs_physical_networks')
        if not physnets:
            return []
        return physnets.split(',')

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
