# Copyright (c) 2018 StackHPC Ltd.
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

from oslo_log import log as logging
import tenacity

from networking_generic_switch.devices import netmiko_devices
from networking_generic_switch.devices import utils as device_utils
from networking_generic_switch import exceptions as exc

LOG = logging.getLogger(__name__)

# Internal ngs options will not be passed to driver.
JUNIPER_INTERNAL_OPTS = [
    # Timeout (seconds) for committing configuration changes.
    {'name': 'ngs_commit_timeout', 'default': 60},
    # Interval (seconds) between attempts to commit configuration changes.
    {'name': 'ngs_commit_interval', 'default': 5},
]


class Juniper(netmiko_devices.NetmikoSwitch):

    ADD_NETWORK = (
        'set vlans {network_name} vlan-id {segmentation_id}',
    )

    DELETE_NETWORK = (
        'delete vlans {network_name}',
    )

    PLUG_PORT_TO_NETWORK = (
        # Delete any existing VLAN associations - only one VLAN may be
        # associated with an access mode port.
        'delete interface {port} unit 0 family ethernet-switching '
        'vlan members',
        'set interface {port} unit 0 family ethernet-switching '
        'vlan members {segmentation_id}',
    )

    DELETE_PORT = (
        'delete interface {port} unit 0 family ethernet-switching '
        'vlan members',
    )

    ENABLE_PORT = (
        'delete interface {port} disable',
    )

    DISABLE_PORT = (
        'set interface {port} disable',
    )

    ADD_NETWORK_TO_TRUNK = (
        'set interface {port} unit 0 family ethernet-switching '
        'vlan members {segmentation_id}',
    )

    REMOVE_NETWORK_FROM_TRUNK = (
        'delete interface {port} unit 0 family ethernet-switching '
        'vlan members {segmentation_id}',
    )

    def __init__(self, device_cfg):
        super(Juniper, self).__init__(device_cfg)

        # Do not expose Juniper internal options to device config.
        for opt in JUNIPER_INTERNAL_OPTS:
            opt_name = opt['name']
            if opt_name in self.config:
                self.ngs_config[opt_name] = self.config.pop(opt_name)
            elif 'default' in opt:
                self.ngs_config[opt_name] = opt['default']

    def send_config_set(self, net_connect, cmd_set):
        """Send a set of configuration lines to the device.

        :param net_connect: a netmiko connection object.
        :param cmd_set: a list of configuration lines to send.
        :returns: The output of the configuration commands.
        """
        # We use the private configuration mode, which hides the configuration
        # changes of concurrent sessions from us, and discards uncommitted
        # changes on termination of the session. See
        # https://www.juniper.net/documentation/en_US/junos/topics/concept/junos-cli-multiple-users-usage-overview.html.
        net_connect.config_mode(config_command='configure private')

        # Don't exit configuration mode, as we still need to commit the changes
        # in save_configuration().
        return net_connect.send_config_set(config_commands=cmd_set,
                                           exit_config_mode=False)

    def save_configuration(self, net_connect):
        """Save the device's configuration.

        :param net_connect: a netmiko connection object.
        :raises: GenericSwitchNetmikoConfigError if saving the
                 configuration fails.
        """
        # Junos configuration is transactional, and requires an explicit commit
        # of changes in order for them to be applied. Since committing requires
        # an exclusive lock on the configuration database, it can fail if
        # another session has a lock. We use a retry mechanism to work around
        # this.

        class BaseRetryable(Exception):
            """Base class for retryable exceptions."""

        class DBLocked(BaseRetryable):
            """Switch configuration DB is locked by another user."""

        class WarningStmtExists(BaseRetryable):
            """Attempting to add a statement that already exists."""

        class WarningStmtNotExist(BaseRetryable):
            """Attempting to remove a statement that does not exist."""

        @tenacity.retry(
            # Log a message after each failed attempt.
            after=tenacity.after_log(LOG, logging.DEBUG),
            # Reraise exceptions if our final attempt fails.
            reraise=True,
            # Retry on certain failures.
            retry=(tenacity.retry_if_exception_type(BaseRetryable)),
            # Stop after the configured timeout.
            stop=tenacity.stop_after_delay(
                int(self.ngs_config['ngs_commit_timeout'])),
            # Wait for the configured interval between attempts.
            wait=tenacity.wait_fixed(
                int(self.ngs_config['ngs_commit_interval'])),
        )
        def commit():
            try:
                net_connect.commit()
            except ValueError as e:
                # Netmiko raises ValueError on commit failure, and appends the
                # CLI output to the exception message.

                # Certain strings indicate a temporary failure, or a harmless
                # warning. In these cases we should retry the operation. We
                # don't ignore warning messages, in case there is some other
                # less benign cause for the failure.
                retryable_msgs = {
                    # Concurrent access to the switch can lead to contention
                    # for the configuration database lock, and potentially
                    # failure to commit changes with the following message.
                    "error: configuration database locked": DBLocked,
                    # Can be caused by concurrent configuration if two sessions
                    # attempt to remove the same statement.
                    "warning: statement does not exist": WarningStmtNotExist,
                    # Can be caused by concurrent configuration if two sessions
                    # attempt to add the same statement.
                    "warning: statement already exists": WarningStmtExists,
                }
                for msg in retryable_msgs:
                    if msg in str(e):
                        raise retryable_msgs[msg](e)
                raise

        try:
            commit()
        except DBLocked as e:
            msg = ("Reached timeout waiting for switch configuration DB lock. "
                   "Configuration might not be committed. Error: %s" % str(e))
            LOG.error(msg)
            raise exc.GenericSwitchNetmikoConfigError(
                config=device_utils.sanitise_config(self.config), error=msg)
        except (WarningStmtNotExist, WarningStmtExists) as e:
            msg = ("Reached timeout while attempting to apply configuration. "
                   "This is likely to be caused by multiple sessions "
                   "configuring the device concurrently. Error: %s" % str(e))
            LOG.error(msg)
            raise exc.GenericSwitchNetmikoConfigError(
                config=device_utils.sanitise_config(self.config), error=msg)
        except ValueError as e:
            msg = "Failed to commit configuration: %s" % e
            LOG.error(msg)
            raise exc.GenericSwitchNetmikoConfigError(
                config=device_utils.sanitise_config(self.config), error=msg)
