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
import functools
import uuid

import netmiko
from oslo_config import cfg
from oslo_log import log as logging
import paramiko
import tenacity
from tooz import coordination

from networking_generic_switch import batching
from networking_generic_switch import devices
from networking_generic_switch.devices import utils as device_utils
from networking_generic_switch import exceptions as exc
from networking_generic_switch import locking as ngs_lock

LOG = logging.getLogger(__name__)
CONF = cfg.CONF


def check_output(operation):
    """Returns a decorator that checks the output of an operation.

    :param operation: Operation being attempted. One of 'add network',
        'delete network', 'plug port', 'unplug port'.
    """
    def decorator(func):
        """The real decorator."""

        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            """Wrapper that checks the output of an operation.

            :returns: The return value of the wrapped method.
            :raises: GenericSwitchNetmikoConfigError if the driver detects that
                an error has occurred.
            """
            output = func(self, *args, **kwargs)
            self.check_output(output, operation)
            return output

        return wrapper

    return decorator


class NetmikoSwitch(devices.GenericSwitchDevice):

    NETMIKO_DEVICE_TYPE = None

    ADD_NETWORK = None

    DELETE_NETWORK = None

    PLUG_PORT_TO_NETWORK = None

    DELETE_PORT = None

    PLUG_BOND_TO_NETWORK = None

    UNPLUG_BOND_FROM_NETWORK = None

    ADD_NETWORK_TO_TRUNK = None

    REMOVE_NETWORK_FROM_TRUNK = None

    ENABLE_PORT = None

    DISABLE_PORT = None

    ENABLE_BOND = None

    DISABLE_BOND = None

    SAVE_CONFIGURATION = None

    ERROR_MSG_PATTERNS = ()
    """Sequence of error message patterns.

    Sequence of re.RegexObject objects representing patterns to check for in
    device output that indicate a failure to apply configuration.
    """

    def __init__(self, device_cfg, *args, **kwargs):
        super(NetmikoSwitch, self).__init__(device_cfg, *args, **kwargs)
        if self.NETMIKO_DEVICE_TYPE:
            device_type = self.NETMIKO_DEVICE_TYPE
        else:
            device_type = self.config.get('device_type', '')
            # use part that is after 'netmiko_'
            device_type = device_type.partition('netmiko_')[2]
        if device_type not in netmiko.platforms:
            raise exc.GenericSwitchNetmikoNotSupported(
                device_type=device_type)
        self.config['device_type'] = device_type
        # Don't pass disabled_algorithms by default to keep compatibility
        # with older versions of Netmiko.
        disabled_algorithms = self._get_ssh_disabled_algorithms()
        if disabled_algorithms:
            self.config['disabled_algorithms'] = disabled_algorithms
        if CONF.ngs.session_log_file:
            self.config['session_log'] = CONF.ngs.session_log_file
            self.config['session_log_record_writes'] = True
            self.config['session_log_file_mode'] = 'append'

        _NUMERIC_CAST = {
            "port": int,
            "global_delay_factor": float,
            "conn_timeout": float,
            "auth_timeout": float,
            "banner_timeout": float,
            "blocking_timeout": float,
            "timeout": float,
            "session_timeout": float,
            "read_timeout_override": float,
            "keepalive": int,
        }

        for key, expected_type in _NUMERIC_CAST.items():
            value = self.config.get(key)
            if isinstance(value, str):
                try:
                    self.config[key] = expected_type(value)
                except ValueError:
                    LOG.error(
                        "Invalid value %s for %s; expected %s",
                        value, key, expected_type.__name__,
                    )
                    raise exc.GenericSwitchNetmikoConfigError()

        self.lock_kwargs = {
            'locks_pool_size': int(self.ngs_config['ngs_max_connections']),
            'locks_prefix': self.config.get(
                'host', '') or self.config.get('ip', ''),
            'timeout': CONF.ngs_coordination.acquire_timeout}

        self.locker = None
        self.batch_cmds = None
        if self._batch_requests():
            if not CONF.ngs_coordination.backend_url:
                raise exc.GenericSwitchNetmikoConfigError(
                    config=device_utils.sanitise_config(self.config),
                    error="ngs_batch_requests is true but [ngs_coordination] "
                          "backend_url is not provided")
            # NOTE: we skip the lock if we are batching requests
            self.locker = None
            switch_name = self.lock_kwargs['locks_prefix']
            self.batch_cmds = batching.SwitchBatch(
                switch_name, CONF.ngs_coordination.backend_url)
        elif CONF.ngs_coordination.backend_url:
            self.locker = coordination.get_coordinator(
                CONF.ngs_coordination.backend_url,
                ('ngs-' + device_utils.get_hostname()).encode('ascii'))
            self.locker.start()
            atexit.register(self.locker.stop)

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

        # If configured, batch up requests to the switch
        if self.batch_cmds is not None:
            return self.batch_cmds.do_batch(self, cmd_set)
        return self._send_commands_to_device(cmd_set)

    def _send_commands_to_device(self, cmd_set):
        try:
            with ngs_lock.PoolLock(self.locker, **self.lock_kwargs):
                with self._get_connection() as net_connect:
                    output = self.send_config_set(net_connect, cmd_set)
                    if self._get_save_configuration():
                        # Save configuration only if enabled in settings
                        # and when configuration is applied successfully.
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

    @check_output('add network')
    def add_network(self, segmentation_id, network_id):
        if not self._do_vlan_management():
            LOG.info(f"Skipping add network for {segmentation_id}")
            return ""

        # NOTE(zhenguo): Remove dashes from uuid as on most devices 32 chars
        # is the max length of vlan name.
        network_id = uuid.UUID(network_id).hex
        network_name = self._get_network_name(network_id, segmentation_id)
        # NOTE(mgoddard): Pass network_id and segmentation_id for drivers not
        # yet using network_name.
        cmds = self._format_commands(self.ADD_NETWORK,
                                     segmentation_id=segmentation_id,
                                     network_id=network_id,
                                     network_name=network_name)
        for port in self._get_trunk_ports():
            cmds += self._format_commands(self.ADD_NETWORK_TO_TRUNK,
                                          port=port,
                                          segmentation_id=segmentation_id)
        return self.send_commands_to_device(cmds)

    @check_output('delete network')
    def del_network(self, segmentation_id, network_id):
        if not self._do_vlan_management():
            LOG.info(f"Skipping delete network for {segmentation_id}")
            return ""

        # NOTE(zhenguo): Remove dashes from uuid as on most devices 32 chars
        # is the max length of vlan name.
        network_id = uuid.UUID(network_id).hex
        cmds = []
        for port in self._get_trunk_ports():
            cmds += self._format_commands(self.REMOVE_NETWORK_FROM_TRUNK,
                                          port=port,
                                          segmentation_id=segmentation_id)
        network_name = self._get_network_name(network_id, segmentation_id)
        # NOTE(mgoddard): Pass network_id and segmentation_id for drivers not
        # yet using network_name.
        cmds += self._format_commands(self.DELETE_NETWORK,
                                      segmentation_id=segmentation_id,
                                      network_id=network_id,
                                      network_name=network_name)
        return self.send_commands_to_device(cmds)

    @check_output('plug port')
    def plug_port_to_network(self, port, segmentation_id):
        cmds = []
        if self._disable_inactive_ports() and self.ENABLE_PORT:
            cmds += self._format_commands(self.ENABLE_PORT, port=port)
        ngs_port_default_vlan = self._get_port_default_vlan()
        if ngs_port_default_vlan:
            cmds += self._format_commands(
                self.DELETE_PORT,
                port=port,
                segmentation_id=ngs_port_default_vlan)
        cmds += self._format_commands(
            self.PLUG_PORT_TO_NETWORK,
            port=port,
            segmentation_id=segmentation_id)
        return self.send_commands_to_device(cmds)

    @check_output('unplug port')
    def delete_port(self, port, segmentation_id):
        cmds = self._format_commands(self.DELETE_PORT,
                                     port=port,
                                     segmentation_id=segmentation_id)
        ngs_port_default_vlan = self._get_port_default_vlan()
        if ngs_port_default_vlan:
            # NOTE(mgoddard): Pass network_id and segmentation_id for drivers
            # not yet using network_name.
            network_name = self._get_network_name(ngs_port_default_vlan,
                                                  ngs_port_default_vlan)
            cmds += self._format_commands(
                self.ADD_NETWORK,
                segmentation_id=ngs_port_default_vlan,
                network_id=ngs_port_default_vlan,
                network_name=network_name)
            cmds += self._format_commands(
                self.PLUG_PORT_TO_NETWORK,
                port=port,
                segmentation_id=ngs_port_default_vlan)
        if self._disable_inactive_ports() and self.DISABLE_PORT:
            cmds += self._format_commands(self.DISABLE_PORT, port=port)
        return self.send_commands_to_device(cmds)

    @check_output('plug bond')
    def plug_bond_to_network(self, bond, segmentation_id):
        # Fallback to regular plug port if no specialist PLUG_BOND_TO_NETWORK
        # commands set
        if not self.PLUG_BOND_TO_NETWORK:
            return self.plug_port_to_network(bond, segmentation_id)
        cmds = []
        if self._disable_inactive_ports() and self.ENABLE_BOND:
            cmds += self._format_commands(self.ENABLE_BOND, bond=bond)
        ngs_port_default_vlan = self._get_port_default_vlan()
        if ngs_port_default_vlan:
            cmds += self._format_commands(
                self.UNPLUG_BOND_FROM_NETWORK,
                bond=bond,
                segmentation_id=ngs_port_default_vlan)
        cmds += self._format_commands(
            self.PLUG_BOND_TO_NETWORK,
            bond=bond,
            segmentation_id=segmentation_id)
        return self.send_commands_to_device(cmds)

    @check_output('unplug bond')
    def unplug_bond_from_network(self, bond, segmentation_id):
        # Fallback to regular port delete if no specialist
        # UNPLUG_BOND_FROM_NETWORK commands set
        if not self.UNPLUG_BOND_FROM_NETWORK:
            return self.delete_port(bond, segmentation_id)
        cmds = self._format_commands(self.UNPLUG_BOND_FROM_NETWORK,
                                     bond=bond,
                                     segmentation_id=segmentation_id)
        ngs_port_default_vlan = self._get_port_default_vlan()
        if ngs_port_default_vlan:
            # NOTE(mgoddard): Pass network_id and segmentation_id for drivers
            # not yet using network_name.
            network_name = self._get_network_name(ngs_port_default_vlan,
                                                  ngs_port_default_vlan)
            cmds += self._format_commands(
                self.ADD_NETWORK,
                segmentation_id=ngs_port_default_vlan,
                network_id=ngs_port_default_vlan,
                network_name=network_name)
            cmds += self._format_commands(
                self.PLUG_BOND_TO_NETWORK,
                bond=bond,
                segmentation_id=ngs_port_default_vlan)
        if self._disable_inactive_ports() and self.DISABLE_BOND:
            cmds += self._format_commands(self.DISABLE_BOND, bond=bond)
        return self.send_commands_to_device(cmds)

    def send_config_set(self, net_connect, cmd_set):
        """Send a set of configuration lines to the device.

        :param net_connect: a netmiko connection object.
        :param cmd_set: a list of configuration lines to send.
        :returns: The output of the configuration commands.
        """
        net_connect.enable()
        return net_connect.send_config_set(config_commands=cmd_set,
                                           cmd_verify=False)

    def save_configuration(self, net_connect):
        """Try to save the device's configuration.

        :param net_connect: a netmiko connection object.
        """
        try:
            net_connect.save_config()
        except NotImplementedError:
            if self.SAVE_CONFIGURATION:
                for cmd in self.SAVE_CONFIGURATION:
                    net_connect.send_command(cmd)
            else:
                LOG.warning("Saving config is not supported for %s,"
                            " all changes will be lost after switch"
                            " reboot", self.config['device_type'])

    def check_output(self, output, operation):
        """Check the output from the device following an operation.

        Drivers should implement this method to handle output from devices and
        perform any checks necessary to validate that the configuration was
        applied successfully.

        :param output: Output from the device.
        :param operation: Operation being attempted. One of 'add network',
            'delete network', 'plug port', 'unplug port'.
        :raises: GenericSwitchNetmikoConfigError if the driver detects that an
            error has occurred.
        """
        if not output:
            return

        for pattern in self.ERROR_MSG_PATTERNS:
            if pattern.search(output):
                msg = ("Found invalid configuration in device response. "
                       "Operation: %(operation)s. Output: %(output)s" %
                       {'operation': operation, 'output': output})
                raise exc.GenericSwitchNetmikoConfigError(
                    config=device_utils.sanitise_config(self.config),
                    error=msg)
