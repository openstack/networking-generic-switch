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

import netmiko
from neutron.i18n import _LI
from oslo_log import log as logging
from oslo_utils import importutils

from networking_generic_switch import config as gsw_conf
from networking_generic_switch import exceptions as exc

LOG = logging.getLogger(__name__)


def get_device(device_id):
    conn_info = gsw_conf.get_config_for_device(device_id)
    device_type = conn_info.get('device_type')
    # NOTE(pas-ha) fail early if given device type is not supported
    # by installed Netmiko library at all
    if device_type not in netmiko.platforms:
        raise exc.GenericSwitchNotSupported(
            device_type=device_type, lib="netmiko")
    module_path = '.'.join((__name__, device_type))
    device_module = importutils.try_import(module_path)
    if not device_module:
        raise exc.GenericSwitchNotSupported(
            device_type=device_type, lib='networking-generic-switch')
    return device_module.generic_switch_device(conn_info)


class GenericSwitch(object):

    ADD_NETWORK = None

    DELETE_NETWORK = None

    PLUG_PORT_TO_NETWORK = None

    def __init__(self, conn_info):
        self.conn_info = conn_info

    def _exec_commands(self, commands, **kwargs):
        if not commands:
            LOG.debug("Nothing to execute")
            return
        cmd_set = self._format_commands(commands, **kwargs)
        net_connect = netmiko.ConnectHandler(**self.conn_info)
        net_connect.enable()
        output = net_connect.send_config_set(config_commands=cmd_set)
        LOG.debug(output)

    def _format_commands(self, commands, **kwargs):
        if not all(kwargs.values()):
            raise exc.GenericSwitchMethodError(cmds=commands, args=kwargs)
        try:
            cmd_set = [cmd.format(**kwargs) for cmd in commands]
        except KeyError:
            raise exc.GenericSwitchMethodError(cmds=commands, args=kwargs)
        except TypeError:
            raise exc.GenericSwitchMethodError(cmds=commands, args=kwargs)
        return cmd_set

    def add_network(self, segmentation_id, network_id):
        self._exec_commands(
            self.ADD_NETWORK,
            segmentation_id=segmentation_id,
            network_id=network_id)
        LOG.info(_LI('Network %s has been added'), network_id)

    def del_network(self, segmentation_id):
        self._exec_commands(
            self.DELETE_NETWORK,
            segmentation_id=segmentation_id)
        LOG.info(_LI('Network %s has been deleted'), segmentation_id)

    def plug_port_to_network(self, port, segmentation_id):
        self._exec_commands(
            self.PLUG_PORT_TO_NETWORK,
            port=port,
            segmentation_id=segmentation_id)
        LOG.info(_LI("Port %(port)s has been added to vlan "
                     "%(segmentation_id)d"),
                 {'port': port, 'segmentation_id': segmentation_id})
