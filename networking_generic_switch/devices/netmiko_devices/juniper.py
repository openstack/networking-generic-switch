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

from networking_generic_switch._i18n import _
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
    """Device Name: Juniper Junos OS

    Port can be disabled: True

    VXLAN L2VNI Support
    ~~~~~~~~~~~~~~~~~~~

    Juniper Junos supports VXLAN L2VNI configuration on QFX and EX series
    switches. VLANs are referenced by name (created during add_network), and
    the VNI is mapped using the ``vxlan vni`` command.
    """
    ADD_NETWORK = (
        'set vlans {network_name} vlan-id {segmentation_id}',
    )

    DELETE_NETWORK = (
        'delete vlans {network_name}',
    )

    PLUG_SWITCH_TO_NETWORK = (
        'set vlans {vlan_name} vxlan vni {vni}',
    )

    UNPLUG_SWITCH_FROM_NETWORK = (
        'delete vlans {vlan_name} vxlan vni',
    )

    SHOW_VLANS = ('show vlans',)

    PLUG_PORT_TO_NETWORK = (
        # Delete any existing VLAN associations - only one VLAN may be
        # associated with an access mode port.
        'delete interfaces {port} unit 0 family ethernet-switching '
        'vlan members',
        'set interfaces {port} unit 0 family ethernet-switching '
        'vlan members {segmentation_id}',
    )

    DELETE_PORT = (
        'delete interfaces {port} unit 0 family ethernet-switching '
        'vlan members',
    )

    ENABLE_PORT = (
        'delete interfaces {port} disable',
    )

    DISABLE_PORT = (
        'set interfaces {port} disable',
    )

    ADD_NETWORK_TO_TRUNK = (
        'set interfaces {port} unit 0 family ethernet-switching '
        'vlan members {segmentation_id}',
    )

    REMOVE_NETWORK_FROM_TRUNK = (
        'delete interfaces {port} unit 0 family ethernet-switching '
        'vlan members {segmentation_id}',
    )

    def __init__(self, device_cfg, *args, **kwargs):
        """Initialize Juniper Junos with EVPN configuration support.

        Extracts EVPN-related configuration before parent __init__ removes
        all ngs_* options.
        """
        # Extract EVPN configuration before parent removes ngs_* options
        evpn_config = device_cfg.get('ngs_evpn_vni_config', 'false')
        self.evpn_vni_config = evpn_config.lower() in ('true', 'yes', '1')
        self.bgp_asn = device_cfg.get('ngs_bgp_asn')

        # Do not expose Juniper internal options to device config.
        juniper_cfg = {}
        for opt in JUNIPER_INTERNAL_OPTS:
            opt_name = opt['name']
            if opt_name in device_cfg:
                juniper_cfg[opt_name] = device_cfg.pop(opt_name)
            elif 'default' in opt:
                juniper_cfg[opt_name] = opt['default']
        super(Juniper, self).__init__(device_cfg, *args, **kwargs)
        self.ngs_config.update(juniper_cfg)

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
            msg = _("Reached timeout waiting for switch configuration "
                    "DB lock. Configuration might not be committed. "
                    "Device: %(device)s, error: %(error)s") % {
                        'device': device_utils.sanitise_config(self.config),
                        'error': e}
            LOG.error(msg)
            raise exc.GenericSwitchNetmikoConfigError()
        except (WarningStmtNotExist, WarningStmtExists) as e:
            msg = _("Reached timeout while attempting to apply "
                    "configuration. This is likely to be caused by multiple "
                    "sessions configuring the device concurrently. "
                    "Device: %(device)s, error: %(error)s") % {
                        'device': device_utils.sanitise_config(self.config),
                        'error': e}
            LOG.error(msg)
            raise exc.GenericSwitchNetmikoConfigError()
        except ValueError as e:
            msg = _("Failed to commit configuration: Device: %(device)s, "
                    "error: %(error)s") % {
                        'device': device_utils.sanitise_config(self.config),
                        'error': e}
            LOG.error(msg)
            raise exc.GenericSwitchNetmikoConfigError()

    def _get_vlan_name_by_id(self, segmentation_id: int) -> str:
        """Get VLAN name from segmentation ID by querying the switch.

        :param segmentation_id: VLAN identifier
        :returns: VLAN name
        :raises: GenericSwitchNetmikoConfigError if VLAN not found
        """
        with self._get_connection() as net_connect:
            output = net_connect.send_command(self.SHOW_VLANS[0])
            vlan_name = self._parse_vlan_name(output, segmentation_id)
            if not vlan_name:
                msg = _("VLAN %(vlan)s not found on device %(device)s") % {
                    'vlan': segmentation_id,
                    'device': device_utils.sanitise_config(self.config)}
                LOG.error(msg)
                raise exc.GenericSwitchNetmikoConfigError()
            return vlan_name

    def _parse_vlan_name(self, output: str, segmentation_id: int):
        """Parse 'show vlans' output to find VLAN name by vlan-id.

        :param output: Command output from switch
        :param segmentation_id: VLAN identifier to find
        :returns: VLAN name if found, None otherwise
        """
        # Junos output format:
        # Routing instance        VLAN name           Tag     Interfaces
        # default-switch          default             1
        # default-switch          vlan100             100     xe-0/0/1.0*
        # default-switch          vlan200             200
        lines = output.strip().split('\n')
        for line in lines:
            # Skip header lines and empty lines
            if not line.strip() or 'Routing instance' in line or \
               'VLAN name' in line:
                continue
            parts = line.split()
            # Need at least routing-instance, vlan-name, and tag
            if len(parts) >= 3:
                # Format: routing-instance, vlan-name, tag, [interfaces...]
                vlan_name = parts[1]
                try:
                    vlan_id = int(parts[2])
                    if vlan_id == segmentation_id:
                        return vlan_name
                except (ValueError, IndexError):
                    continue
        return None

    def _parse_vlan_ports(self, output: str, segmentation_id: int) -> bool:
        """Parse 'show vlans' output for ports.

        :param output: Command output from switch
        :param segmentation_id: VLAN identifier being checked
        :returns: True if VLAN has ports, False otherwise
        """
        # Junos output format:
        # Routing instance        VLAN name           Tag     Interfaces
        # default-switch          vlan100             100     xe-0/0/1.0*
        lines = output.strip().split('\n')
        for line in lines:
            if not line.strip() or 'Routing instance' in line or \
               'VLAN name' in line:
                continue
            parts = line.split()
            if len(parts) >= 3:
                try:
                    vlan_id = int(parts[2])
                    if vlan_id == segmentation_id:
                        # If there are 4+ parts, interfaces are listed
                        return len(parts) >= 4
                except (ValueError, IndexError):
                    continue
        return False

    def _parse_vlan_vni(self, output: str, segmentation_id: int,
                        vni: int) -> bool:
        """Parse 'show vlans' output to check for VNI.

        :param output: Command output from switch
        :param segmentation_id: VLAN identifier being checked
        :param vni: VNI to check for
        :returns: True if VLAN has this VNI, False otherwise
        """
        # Junos extended output format for VXLAN-enabled VLANs:
        # Routing instance        VLAN name           Tag     Interfaces
        # default-switch          vlan100             100
        #   VNI: 5000
        lines = output.strip().split('\n')
        found_vlan = False
        for line in lines:
            # Look for the VLAN line
            if not found_vlan:
                if not line.strip() or 'Routing instance' in line or \
                   'VLAN name' in line:
                    continue
                parts = line.split()
                if len(parts) >= 3:
                    try:
                        vlan_id = int(parts[2])
                        if vlan_id == segmentation_id:
                            found_vlan = True
                    except (ValueError, IndexError):
                        continue
            else:
                # Found the VLAN, now look for VNI on following lines
                if 'VNI:' in line:
                    try:
                        vni_value = int(line.split('VNI:')[1].strip())
                        return vni_value == vni
                    except (ValueError, IndexError):
                        return False
                # If we hit another VLAN or non-indented line, stop looking
                if line and not line.startswith(' '):
                    return False
        return False

    @netmiko_devices.check_output('plug vni')
    def plug_switch_to_network(self, vni: int, segmentation_id: int,
                               physnet: str = None):
        """Configure L2VNI mapping with EVPN on the Juniper switch.

        Dynamically generates commands based on configuration:
        1. Map VLAN to VNI
        2. Configure EVPN VRF target (if ngs_evpn_vni_config enabled)

        :param vni: VXLAN Network Identifier
        :param segmentation_id: VLAN identifier
        :param physnet: Physical network name (unused but kept for signature)
        :returns: Command output
        """
        # Get the VLAN name from segmentation_id
        vlan_name = self._get_vlan_name_by_id(segmentation_id)

        # Step 1: Map VLAN to VNI
        cmds = self._format_commands(
            self.PLUG_SWITCH_TO_NETWORK,
            vni=vni,
            segmentation_id=segmentation_id,
            vlan_name=vlan_name)

        # Step 2: Configure EVPN VRF target if enabled
        if self.evpn_vni_config:
            if not self.bgp_asn:
                raise exc.GenericSwitchNetmikoConfigError(
                    switch=self.device_name,
                    error='ngs_bgp_asn configuration parameter is '
                          'required when ngs_evpn_vni_config is enabled')
            # Configure VRF target for EVPN Type-2 routes
            evpn_cmd = (f'set vlans {vlan_name} vrf-target '
                        f'target:{self.bgp_asn}:{vni}')
            cmds.append(evpn_cmd)

        return self.send_commands_to_device(cmds)

    @netmiko_devices.check_output('unplug vni')
    def unplug_switch_from_network(self, vni: int, segmentation_id: int,
                                   physnet: str = None):
        """Remove L2VNI mapping and EVPN configuration from Juniper switch.

        Removes configuration in reverse order of creation:
        1. Remove VXLAN VNI map
        2. Remove EVPN VRF target (if enabled)

        :param vni: VXLAN Network Identifier
        :param segmentation_id: VLAN identifier
        :param physnet: Physical network name (unused but kept for signature)
        :returns: Command output
        """
        # Get the VLAN name from segmentation_id
        vlan_name = self._get_vlan_name_by_id(segmentation_id)

        # Step 1: Remove VXLAN VNI map
        cmds = self._format_commands(
            self.UNPLUG_SWITCH_FROM_NETWORK,
            vni=vni,
            segmentation_id=segmentation_id,
            vlan_name=vlan_name)

        # Step 2: Remove EVPN VRF target if it was configured
        if self.evpn_vni_config:
            if not self.bgp_asn:
                raise exc.GenericSwitchNetmikoConfigError(
                    switch=self.device_name,
                    error='ngs_bgp_asn configuration parameter is '
                          'required when ngs_evpn_vni_config is enabled')
            # Remove VRF target
            evpn_cmd = f'delete vlans {vlan_name} vrf-target'
            cmds.append(evpn_cmd)

        return self.send_commands_to_device(cmds)

    def vlan_has_ports(self, segmentation_id: int) -> bool:
        """Check if a VLAN has any switch ports currently assigned.

        :param segmentation_id: VLAN identifier
        :returns: True if VLAN has ports, False otherwise
        """
        with self._get_connection() as net_connect:
            output = net_connect.send_command(self.SHOW_VLANS[0])
            return self._parse_vlan_ports(output, segmentation_id)

    def vlan_has_vni(self, segmentation_id: int, vni: int) -> bool:
        """Check if a VLAN already has a specific VNI mapping configured.

        :param segmentation_id: VLAN identifier
        :param vni: VNI to check for
        :returns: True if VLAN has this VNI, False otherwise
        """
        with self._get_connection() as net_connect:
            output = net_connect.send_command(self.SHOW_VLANS[0])
            return self._parse_vlan_vni(output, segmentation_id, vni)
