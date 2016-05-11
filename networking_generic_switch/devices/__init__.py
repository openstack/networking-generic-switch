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

from networking_generic_switch._i18n import _LE
from networking_generic_switch import exceptions as gsw_exc


GENERIC_SWITCH_NAMESPACE = 'generic_switch.devices'
LOG = logging.getLogger(__name__)


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
    LOG.error(_LE("Driver manager %(manager)s failed to load device plugin "
                  "%(entrypoint)s: %(exp)s"),
              {'manager': manager, 'entrypoint': entrypoint, 'exp': exception})
    raise gsw_exc.GenericSwitchEntrypointLoadError(
        ep=entrypoint,
        err=exception)


@six.add_metaclass(abc.ABCMeta)
class GenericSwitchDevice(object):

    def __init__(self, device_cfg):
        self.config = device_cfg

    @abc.abstractmethod
    def add_network(self, segmentation_id, network_id):
        pass

    @abc.abstractmethod
    def del_network(self, segmentation_id):
        pass

    @abc.abstractmethod
    def plug_port_to_network(self, segmentation_id, port):
        pass
