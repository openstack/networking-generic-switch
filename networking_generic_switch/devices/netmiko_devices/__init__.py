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

import atexit
import contextlib
import uuid

import netmiko
from oslo_config import cfg
from oslo_log import log as logging
import paramiko
import tenacity
from tooz import coordination

from networking_generic_switch import devices
from networking_generic_switch.devices import utils as device_utils
from networking_generic_switch import exceptions as exc
from networking_generic_switch import locking as ngs_lock

LOG = logging.getLogger(__name__)
CONF = cfg.CONF


class NetmikoSwitch(devices.GenericSwitchDevice):

    ADD_NETWORK = None

    DELETE_NETWORK = None

    PLUG_PORT_TO_NETWORK = None

    DELETE_PORT = None

    ADD_NETWORK_TO_TRUNK = None

    REMOVE_NETWORK_FROM_TRUNK = None

    SAVE_CONFIGURATION = None

    def __init__(self, device_cfg):
        super(NetmikoSwitch, self).__init__(device_cfg)
        device_type = self.config.get('device_type', '')
        # use part that is after 'netmiko_'
        device_type = device_type.partition('netmiko_')[2]
        if device_type not in netmiko.platforms:
            raise exc.GenericSwitchNetmikoNotSupported(
                device_type=device_type)
        self.config['device_type'] = device_type

        self.locker = None
        if CONF.ngs_coordination.backend_url:
            self.locker = coordination.get_coordinator(
                CONF.ngs_coordination.backend_url,
                ('ngs-' + CONF.host).encode('ascii'))
            self.locker.start()
            atexit.register(self.locker.stop)

        self.lock_kwargs = {
            'locks_pool_size': int(self.ngs_config['ngs_max_connections']),
            'locks_prefix': self.config.get(
                'host', '') or self.config.get('ip', ''),
            'timeout': CONF.ngs_coordination.acquire_timeout}

    def _format_commands(self, commands, **kwargs):
        if not commands:
            return []
        if not all(kwargs.values()):
            raise exc.GenericSwitchNetmikoMethodError(cmds=commands,
                                                      args=kwargs)
        try:
            cmd_set = [cmd.format(**kwargs) for cmd in commands]
        except (KeyError, TypeError):
            raise exc.GenericSwitchNetmikoMethodError(cmds=commands,
                                                      args=kwargs)
        return cmd_set

    @contextlib.contextmanager
    def _get_connection(self):
        """Context manager providing a netmiko SSH connection object.

        This function hides the complexities of gracefully handling retrying
        failed connection attempts.
        """
        retry_exc_types = (paramiko.SSHException, EOFError)

        # Use tenacity to handle retrying.
        @tenacity.retry(
            # Log a message after each failed attempt.
            after=tenacity.after_log(LOG, logging.DEBUG),
            # Reraise exceptions if our final attempt fails.
            reraise=True,
            # Retry on SSH connection errors.
            retry=tenacity.retry_if_exception_type(retry_exc_types),
            # Stop after the configured timeout.
            stop=tenacity.stop_after_delay(
                int(self.ngs_config['ngs_ssh_connect_timeout'])),
            # Wait for the configured interval between attempts.
            wait=tenacity.wait_fixed(
                int(self.ngs_config['ngs_ssh_connect_interval'])),
        )
        def _create_connection():
            return netmiko.ConnectHandler(**self.config)

        # First, create a connection.
        try:
            net_connect = _create_connection()
        except tenacity.RetryError as e:
            LOG.error("Reached maximum SSH connection attempts, not retrying")
            raise exc.GenericSwitchNetmikoConnectError(
                config=device_utils.sanitise_config(self.config), error=e)
        except Exception as e:
            LOG.error("Unexpected exception during SSH connection")
            raise exc.GenericSwitchNetmikoConnectError(
                config=device_utils.sanitise_config(self.config), error=e)

        # Now yield the connection to the caller.
        with net_connect:
            yield net_connect

    def send_commands_to_device(self, cmd_set):
        if not cmd_set:
            LOG.debug("Nothing to execute")
            return

        try:
            with ngs_lock.PoolLock(self.locker, **self.lock_kwargs):
                with self._get_connection() as net_connect:
                    output = self.send_config_set(net_connect, cmd_set)
                    # NOTE (vsaienko) always save configuration
                    # when configuration is applied successfully.
                    self.save_configuration(net_connect)
        except exc.GenericSwitchException:
            # Reraise without modification exceptions originating from this
            # module.
            raise
        except Exception as e:
            raise exc.GenericSwitchNetmikoConnectError(
                config=device_utils.sanitise_config(self.config), error=e)

        LOG.debug(output)
        return output

    def add_network(self, segmentation_id, network_id):
        # NOTE(zhenguo): Remove dashes from uuid as on most devices 32 chars
        # is the max length of vlan name.
        network_id = uuid.UUID(network_id).hex
        cmds = self._format_commands(self.ADD_NETWORK,
                                     segmentation_id=segmentation_id,
                                     network_id=network_id)
        for port in self._get_trunk_ports():
            cmds += self._format_commands(self.ADD_NETWORK_TO_TRUNK,
                                          port=port,
                                          segmentation_id=segmentation_id)
        self.send_commands_to_device(cmds)

    def del_network(self, segmentation_id, network_id):
        # NOTE(zhenguo): Remove dashes from uuid as on most devices 32 chars
        # is the max length of vlan name.
        network_id = uuid.UUID(network_id).hex
        cmds = []
        for port in self._get_trunk_ports():
            cmds += self._format_commands(self.REMOVE_NETWORK_FROM_TRUNK,
                                          port=port,
                                          segmentation_id=segmentation_id)
        cmds += self._format_commands(self.DELETE_NETWORK,
                                      segmentation_id=segmentation_id,
                                      network_id=network_id)
        self.send_commands_to_device(cmds)

    def plug_port_to_network(self, port, segmentation_id):
        self.send_commands_to_device(
            self._format_commands(self.PLUG_PORT_TO_NETWORK,
                                  port=port,
                                  segmentation_id=segmentation_id))

    def delete_port(self, port, segmentation_id):
        self.send_commands_to_device(
            self._format_commands(self.DELETE_PORT,
                                  port=port,
                                  segmentation_id=segmentation_id))

    def send_config_set(self, net_connect, cmd_set):
        """Send a set of configuration lines to the device.

        :param net_connect: a netmiko connection object.
        :param cmd_set: a list of configuration lines to send.
        :returns: The output of the configuration commands.
        """
        net_connect.enable()
        return net_connect.send_config_set(config_commands=cmd_set)

    def save_configuration(self, net_connect):
        """Save the device's configuration.

        :param net_connect: a netmiko connection object.
        """
        if self.SAVE_CONFIGURATION:
            for cmd in self.SAVE_CONFIGURATION:
                net_connect.send_command(cmd)
