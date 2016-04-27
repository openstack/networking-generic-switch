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
from oslo_log import log as logging

from networking_generic_switch._i18n import _
from networking_generic_switch._i18n import _LI
from networking_generic_switch import devices
from networking_generic_switch import exceptions as exc

LOG = logging.getLogger(__name__)


class GenericSwitchNetmikoMethodError(exc.GenericSwitchException):
    message = _("Can not parse arguments: commands %(cmds)s, args %(args)s")


class GenericSwitchNetmikoNotSupported(exc.GenericSwitchException):
    message = _("Netmiko does not support device type %(device_type)s")


class GenericSwitchNetmikoConnectError(exc.GenericSwitchException):
    message = _("Netmiko connected error: %(config)s")


class NetmikoSwitch(devices.GenericSwitchDevice):

    ADD_NETWORK = None

    DELETE_NETWORK = None

    PLUG_PORT_TO_NETWORK = None

    def __init__(self, device_cfg):
        super(NetmikoSwitch, self).__init__(device_cfg)
        device_type = self.config.get('device_type', '')
        # use part that is after 'netmiko_'
        device_type = device_type.partition('netmiko_')[2]
        if device_type not in netmiko.platforms:
            raise GenericSwitchNetmikoNotSupported(
                device_type=device_type)
        self.config['device_type'] = device_type

    def _exec_commands(self, commands, **kwargs):
        if not commands:
            LOG.debug("Nothing to execute")
            return
        cmd_set = self._format_commands(commands, **kwargs)
        try:
            net_connect = netmiko.ConnectHandler(**self.config)
        except Exception:
            raise GenericSwitchNetmikoConnectError(config=self.config)
        net_connect.enable()
        output = net_connect.send_config_set(config_commands=cmd_set)
        LOG.debug(output)

    def _format_commands(self, commands, **kwargs):
        if not all(kwargs.values()):
            raise GenericSwitchNetmikoMethodError(cmds=commands, args=kwargs)
        try:
            cmd_set = [cmd.format(**kwargs) for cmd in commands]
        except (KeyError, TypeError):
            raise GenericSwitchNetmikoMethodError(cmds=commands, args=kwargs)
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
