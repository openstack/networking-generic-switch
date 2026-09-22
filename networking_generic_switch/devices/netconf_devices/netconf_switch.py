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
from urllib.parse import parse_qs as urlparse_qs
from urllib.parse import urlparse
import uuid
from xml.etree import ElementTree

from ncclient import manager
from ncclient.operations.rpc import RPCError
from ncclient.transport.errors import AuthenticationError
from ncclient.transport.errors import SessionCloseError
from ncclient.transport.errors import SSHError
from oslo_config import cfg
from oslo_log import log as logging
from oslo_utils import strutils
import tenacity
from tooz import coordination

from networking_generic_switch import devices
from networking_generic_switch.devices.netconf_devices import (
    constants as ncconst)
from networking_generic_switch.devices import utils as device_utils
from networking_generic_switch import exceptions as exc
from networking_generic_switch import locking as ngs_lock
from networking_generic_switch.yang_models import utils as yutils

LOG = logging.getLogger(__name__)
CONF = cfg.CONF


class NetconfSwitch(devices.GenericSwitchDevice):
    """Base class for NETCONF-based switch drivers.

    Provides ncclient transport, NETCONF locking, candidate/running
    datastore dispatch, confirmed-commit, and retry on lock-denied.

    Subclasses must assign callable class variables (ADD_NETWORK, etc.)
    that build OpenConfig model objects.  The dispatch methods in this
    class invoke those callables, serialize the result to XML via
    ``yutils.config_to_xml``, and push to the device.
    """

    ADD_NETWORK_TO_TRUNK = None
    REMOVE_NETWORK_FROM_TRUNK = None
    ADD_SUBPORTS_ON_TRUNK = None
    DEL_SUBPORTS_ON_TRUNK = None
    ENABLE_PORT = None
    DISABLE_PORT = None

    @property
    def trunk_vlans_converge(self):
        return True

    VALID_NETCONF_TARGETS = ('candidate', 'running')

    def __init__(self, device_cfg, *args, **kwargs):
        super().__init__(device_cfg, *args, **kwargs)

        self.capabilities = set()

        self._ncclient_args = self._build_ncclient_args()
        self._netconf_target = self.ngs_config.get('ngs_netconf_target')
        if (self._netconf_target
                and self._netconf_target not in self.VALID_NETCONF_TARGETS):
            raise exc.GenericSwitchConfigException(
                option='ngs_netconf_target',
                allowed_options=', '.join(self.VALID_NETCONF_TARGETS))
        self._netconf_save_config = self.ngs_config.get(
            'ngs_netconf_save_config')

        self._confirmed_commit = strutils.bool_from_string(
            self.ngs_config.get('ngs_netconf_confirmed_commit', True))
        self._confirmed_commit_timeout = int(
            self.ngs_config.get('ngs_netconf_confirmed_commit_timeout', 5))
        if (self._confirmed_commit_timeout < 1
                or self._confirmed_commit_timeout > 30):
            raise exc.GenericSwitchConfigException(
                option='ngs_netconf_confirmed_commit_timeout',
                allowed_options='integer between 1 and 30')

        netconf_logger = logging.getLogger('ncclient')
        netconf_logger.setLevel(logging.WARNING)

        self.lock_kwargs = {
            'locks_pool_size': int(
                self.ngs_config.get('ngs_max_connections', 1)),
            'locks_prefix': self.config.get('host', ''),
            'timeout': CONF.ngs_coordination.acquire_timeout,
        }
        self.locker = None
        if CONF.ngs_coordination.backend_url:
            self.locker = coordination.get_coordinator(
                CONF.ngs_coordination.backend_url,
                ('ngs-' + device_utils.get_hostname()).encode('ascii'))
            self.locker.start()
            atexit.register(self.locker.stop)
        else:
            LOG.warning(
                "Switch %s: [ngs_coordination] backend_url is not "
                "configured. The ngs_max_connections is ignored.",
                self.lock_kwargs['locks_prefix'])

    def _build_ncclient_args(self):
        """Build keyword arguments for ``ncclient.manager.connect``.

        :returns: dict of keyword arguments suitable for
            ``ncclient.manager.connect``.
        """
        args = dict(
            host=self.config.get('host'),
            port=int(self.config.get('port', 830)),
            username=self.config.get('username'),
            hostkey_verify=self.config.get(
                'hostkey_verify', 'true').lower() in ('true', '1', 'yes'),
            device_params=self._parse_device_params(),
            allow_agent=self.config.get(
                'allow_agent', 'true').lower() in ('true', '1', 'yes'),
            use_libssh=True,
        )
        key_filename = self.config.get('key_filename')
        if key_filename:
            args['key_filename'] = key_filename
        password = self.config.get('password')
        if password:
            args['password'] = password

        return args

    def _parse_device_params(self):
        """Parse the ``device_params`` config value for ncclient.

        :returns: dict for the ncclient ``device_params`` keyword argument.
        """
        raw = self.config.get('device_params', '')
        if isinstance(raw, dict):
            return raw
        if not raw:
            return {'name': 'default'}
        # INI value looks like "name:default" or "name:nexus"
        parts = raw.split(':')
        if len(parts) == 2:
            return {parts[0].strip(): parts[1].strip()}
        return {'name': raw.strip()}

    @staticmethod
    def process_capabilities(server_capabilities):
        """Map NETCONF server capability URIs to short names.

        Matches IANA NETCONF capability URIs and OpenConfig YANG module
        names from the server's hello message.

        :param server_capabilities: Iterable of capability URI strings
            from the NETCONF hello message.
        :returns: set of short capability names.
        """
        capabilities = set()
        for capability in server_capabilities:
            for k, v in ncconst.IANA_NETCONF_CAPABILITIES.items():
                if v in capability:
                    capabilities.add(k)
            if capability.startswith('http://openconfig.net/yang'):
                module_list = urlparse_qs(
                    urlparse(capability).query).get('module')
                if module_list:
                    capabilities.add(module_list[0])

        return capabilities

    def get_capabilities(self):
        """Connect to the device and return its processed capabilities.

        :returns: set of short capability names.
        :raises: GenericSwitchNetconfConnectError on SSH or authentication
            failure.
        """
        # https://github.com/ncclient/ncclient/issues/525
        _ignore_close_issue_525 = False
        try:
            with manager.connect(**self._ncclient_args) as nc_client:
                server_capabilities = nc_client.server_capabilities
                _ignore_close_issue_525 = True
        except SessionCloseError as e:
            if not _ignore_close_issue_525:
                raise e
        except (SSHError, AuthenticationError) as e:
            raise exc.GenericSwitchNetconfConnectError(
                device=self.device_name, error=e)

        return self.process_capabilities(server_capabilities)

    def get_from_device(self, query):
        """Read-only <get> RPC.

        :param query: An OpenConfig model object with a
            ``to_xml_element()`` method.
        :returns: XML string of the reply data.
        """
        # https://github.com/ncclient/ncclient/issues/525
        _ignore_close_issue_525 = False

        q_filter = ElementTree.tostring(
            query.to_xml_element()).decode('utf-8')
        try:
            with manager.connect(**self._ncclient_args) as client:
                reply = client.get(filter=('subtree', q_filter))
                _ignore_close_issue_525 = True
        except SessionCloseError as e:
            if not _ignore_close_issue_525:
                raise e
        except RPCError as e:
            LOG.error('Netconf XML: %s', q_filter)
            raise e

        return reply.data_xml

    @tenacity.retry(
        reraise=True,
        retry=tenacity.retry_if_exception_type(
            (exc.GenericSwitchNetconfLockDenied,
             exc.GenericSwitchNetconfOperationFailed)),
        wait=tenacity.wait_exponential(multiplier=1, min=2, max=5),
        stop=tenacity.stop_after_attempt(10))
    def _lock_and_configure(self, client, source, config):
        """Lock *source* datastore, edit-config, and commit.

        Retries with exponential back-off (2s, 4s, 5s, 5s, ...) on
        lock-denied and operation-failed errors.

        :param client: An active ``ncclient.manager.Manager`` session.
        :param source: Datastore name (``candidate`` or ``running``).
        :param config: List of configuration model objects, each with a
            ``to_xml_element()`` method.
        :raises: GenericSwitchNetconfLockDenied if the datastore lock
            cannot be acquired (triggers tenacity retry).
        :raises: GenericSwitchNetconfOperationFailed if the device
            returns operation-failed (triggers tenacity retry).
        """
        try:
            with client.locked(source):
                xml_config = yutils.config_to_xml(config)
                LOG.debug(
                    'Sending configuration to Netconf device %(dev)s: '
                    '%(conf)s',
                    {'dev': self.device_name, 'conf': xml_config})
                if source == ncconst.CANDIDATE:
                    client.discard_changes()
                    client.edit_config(target=source, config=xml_config)
                    if (':validate' in self.capabilities
                            or ':validate:1.1' in self.capabilities):
                        client.validate(source='candidate')
                    if (self._confirmed_commit
                            and (':confirmed-commit' in self.capabilities
                                 or ':confirmed-commit:1.1'
                                 in self.capabilities)):
                        client.commit(confirmed=True,
                                      timeout=str(
                                          self._confirmed_commit_timeout))
                    client.commit()
                elif source == ncconst.RUNNING:
                    client.edit_config(target=source, config=xml_config)
                    if self._get_save_configuration():
                        self._save_running_config(client)
        except RPCError as err:
            if err.tag == ncconst.LOCK_DENIED_TAG:
                if (source == ncconst.CANDIDATE
                        and self._get_lock_session_id(err.info) == '0'):
                    client.discard_changes()
                raise exc.GenericSwitchNetconfLockDenied()
            elif err.tag == ncconst.OPERATION_FAILED_TAG:
                LOG.warning(
                    'Netconf device %(dev)s returned operation-failed, '
                    'retrying: %(msg)s',
                    {'dev': self.device_name, 'msg': err.message})
                raise exc.GenericSwitchNetconfOperationFailed()
            else:
                LOG.error('Netconf XML: %s', yutils.config_to_xml(config))
                raise err

    def _save_running_config(self, client):
        """Persist running configuration after a direct edit.

        Tries the configured ``ngs_netconf_save_config`` first (sent as
        an ``edit-config`` to the running datastore), then falls back to
        ``copy-config`` to the startup datastore if the device advertises
        the ``:startup`` capability.

        :param client: An active ``ncclient.manager.Manager`` session.
        """
        if self._netconf_save_config:
            LOG.debug('Saving configuration on Netconf device %s '
                      'via edit-config', self.device_name)
            client.edit_config(target=ncconst.RUNNING,
                               config=self._netconf_save_config)
        elif ':startup' in self.capabilities:
            LOG.info('Copying running to startup on Netconf device %s',
                     self.device_name)
            client.copy_config(
                source=ncconst.RUNNING,
                target=ncconst.STARTUP)
        else:
            LOG.warning(
                'Cannot persist running config on Netconf device %s: '
                'no ngs_netconf_save_config configured and device does '
                'not advertise :startup capability', self.device_name)

    def _get_datastore_target(self):
        """Determine the NETCONF datastore target.

        Uses ``ngs_netconf_target`` if configured, otherwise auto-detects
        from server capabilities (preferring candidate over
        writable-running).

        :returns: Datastore name string or ``None`` if no usable
            target is available.
        """
        if self._netconf_target:
            return self._netconf_target
        if ':candidate' in self.capabilities:
            return ncconst.CANDIDATE
        if ':writable-running' in self.capabilities:
            return ncconst.RUNNING
        return None

    def send_config_to_device(self, config):
        """Edit configuration on the device.

        :param config: Configuration object or list of configuration objects.
            Each must implement ``to_xml_element()``.
        """
        # https://github.com/ncclient/ncclient/issues/525
        _ignore_close_issue_525 = False

        if not isinstance(config, list):
            config = [config]

        try:
            with ngs_lock.PoolLock(self.locker, **self.lock_kwargs):
                with manager.connect(**self._ncclient_args) as client:
                    self.capabilities = self.process_capabilities(
                        client.server_capabilities)
                    target = self._get_datastore_target()
                    if target:
                        self._lock_and_configure(client, target, config)
                        _ignore_close_issue_525 = True
        except SessionCloseError as e:
            if not _ignore_close_issue_525:
                raise e

    @staticmethod
    def _get_lock_session_id(err_info):
        """Parse session-id from a lock-denied error [RFC6241].

        :param err_info: XML string from the RPCError ``info`` attribute.
        :returns: Session ID string that holds the conflicting lock.
        """
        root = ElementTree.fromstring(err_info)
        session_id = root.find(
            "./{urn:ietf:params:xml:ns:netconf:base:1.0}session-id").text
        return session_id

    def add_network(self, segmentation_id, network_id, physnet_vlans=None):
        """Create a VLAN on the device.

        Delegates to the ``ADD_NETWORK`` callable set by the subclass.
        If trunk ports are configured and ``ADD_NETWORK_TO_TRUNK`` is
        defined, the trunk tagging is included in the same edit-config.

        :param segmentation_id: VLAN ID of the network.
        :param network_id: UUID of the Neutron network.
        :param physnet_vlans: Complete set of VLAN segmentation IDs on
            the physical network, or None if convergence is not active.
        """
        if not self._do_vlan_management():
            LOG.debug("Skipping add network for %s", segmentation_id)
            return
        network_id = uuid.UUID(network_id).hex
        network_name = self._get_network_name(network_id, segmentation_id)
        config = self.ADD_NETWORK(
            self,
            segmentation_id=segmentation_id,
            network_name=network_name,
        ) or []
        trunk_ports = self.get_trunk_ports()
        if trunk_ports and self.ADD_NETWORK_TO_TRUNK:
            trunk_config = self.ADD_NETWORK_TO_TRUNK(
                self,
                segmentation_id=segmentation_id,
                trunk_ports=trunk_ports,
                physnet_vlans=physnet_vlans,
            )
            if trunk_config:
                config.extend(trunk_config)
        if config:
            self.send_config_to_device(config)

    def del_network(self, segmentation_id, network_id, physnet_vlans=None):
        """Remove a VLAN from the device.

        Delegates to the ``DELETE_NETWORK`` callable set by the subclass.
        If trunk ports are configured and ``REMOVE_NETWORK_FROM_TRUNK`` is
        defined, the trunk untagging is included in the same edit-config
        (before the VLAN delete).

        :param segmentation_id: VLAN ID of the network.
        :param network_id: UUID of the Neutron network.
        :param physnet_vlans: Complete set of VLAN segmentation IDs on
            the physical network, or None if convergence is not active.
        """
        if not self._do_vlan_management():
            LOG.info("Skipping delete network for %s", segmentation_id)
            return
        config = []
        trunk_ports = self.get_trunk_ports()
        if trunk_ports and self.REMOVE_NETWORK_FROM_TRUNK:
            trunk_config = self.REMOVE_NETWORK_FROM_TRUNK(
                self,
                segmentation_id=segmentation_id,
                trunk_ports=trunk_ports,
                physnet_vlans=physnet_vlans,
            )
            if trunk_config:
                config.extend(trunk_config)
        network_id = uuid.UUID(network_id).hex
        network_name = self._get_network_name(network_id, segmentation_id)
        delete_config = self.DELETE_NETWORK(
            self,
            segmentation_id=segmentation_id,
            network_name=network_name,
        )
        if delete_config:
            config.extend(delete_config)
        if config:
            self.send_config_to_device(config)

    def plug_port_to_network(self, port_id, segmentation_id,
                             trunk_details=None, default_vlan=None):
        """Plug a port into a network.

        Collects enable, default-VLAN removal, and plug config into a
        single edit-config RPC.

        :param port_id: Name of the switch interface.
        :param segmentation_id: VLAN ID of the network.
        :param trunk_details: Trunk information if port is part of a trunk.
        :param default_vlan: Default VLAN ID when port is unconfigured.
        """
        config = []
        if self._disable_inactive_ports() and self.ENABLE_PORT:
            enable_config = self.ENABLE_PORT(self, port_id=port_id)
            if enable_config:
                config.extend(enable_config)
        port_default_vlan = default_vlan or self._get_port_default_vlan()
        if port_default_vlan:
            clear_config = self.DELETE_PORT(
                self,
                port_id=port_id,
                segmentation_id=port_default_vlan,
            )
            if clear_config:
                config.extend(clear_config)
        plug_config = self.PLUG_PORT_TO_NETWORK(
            self,
            port_id=port_id,
            segmentation_id=segmentation_id,
            trunk_details=trunk_details,
        )
        if plug_config:
            config.extend(plug_config)
        if config:
            self.send_config_to_device(config)

    def delete_port(self, port_id, segmentation_id, trunk_details=None,
                    default_vlan=None):
        """Delete a port from a network.

        Collects unplug, default-VLAN restoration, and disable config
        into a single edit-config RPC.

        :param port_id: Name of the switch interface.
        :param segmentation_id: VLAN ID of the network.
        :param trunk_details: Trunk information if port is part of a trunk.
        :param default_vlan: Default VLAN ID when port is unconfigured.
        """
        config = []
        unplug_config = self.DELETE_PORT(
            self,
            port_id=port_id,
            segmentation_id=segmentation_id,
            trunk_details=trunk_details,
        )
        if unplug_config:
            config.extend(unplug_config)
        port_default_vlan = default_vlan or self._get_port_default_vlan()
        if port_default_vlan:
            network_name = self._get_network_name(
                port_default_vlan, port_default_vlan)
            restore_net = self.ADD_NETWORK(
                self,
                segmentation_id=port_default_vlan,
                network_name=network_name,
            )
            if restore_net:
                config.extend(restore_net)
            restore_port = self.PLUG_PORT_TO_NETWORK(
                self,
                port_id=port_id,
                segmentation_id=port_default_vlan,
            )
            if restore_port:
                config.extend(restore_port)
        if self._disable_inactive_ports() and self.DISABLE_PORT:
            disable_config = self.DISABLE_PORT(self, port_id=port_id)
            if disable_config:
                config.extend(disable_config)
        if config:
            self.send_config_to_device(config)

    #
    # L2VNI — unsupported for now
    #

    def plug_switch_to_network(self, vni, segmentation_id, physnet=None):
        """Configure L2VNI mapping on the switch.

        Not yet supported by NETCONF devices; logs a debug message.

        :param vni: VXLAN Network Identifier.
        :param segmentation_id: VLAN ID to map to the VNI.
        :param physnet: Physical network name (optional).
        """
        LOG.debug("plug_switch_to_network not supported for NETCONF device "
                  "%s", self.device_name)

    def unplug_switch_from_network(self, vni, segmentation_id, physnet=None):
        """Remove L2VNI mapping from the switch.

        Not yet supported by NETCONF devices; logs a debug message.

        :param vni: VXLAN Network Identifier.
        :param segmentation_id: VLAN ID from which to remove the VNI mapping.
        :param physnet: Physical network name (optional).
        """
        LOG.debug("unplug_switch_from_network not supported for NETCONF "
                  "device %s", self.device_name)

    def vlan_has_ports(self, segmentation_id):
        """Check if a VLAN has any ports assigned.

        Returns ``True`` (conservative default) to prevent premature
        VNI cleanup.

        :param segmentation_id: VLAN ID to check.
        :returns: Always ``True``.
        """
        return True

    def vlan_has_vni(self, segmentation_id, vni):
        """Check if a VLAN has a specific VNI mapping.

        Returns ``False`` since L2VNI is not supported.

        :param segmentation_id: VLAN ID to check.
        :param vni: VNI to check for.
        :returns: Always ``False``.
        """
        return False

    #
    # Trunks — dispatch to subclass callables
    #

    def add_subports_on_trunk(self, binding_profile, port_id, subports,
                              trunk_details=None):
        """Allow subports on trunk.

        :param binding_profile: Binding profile of the parent port.
        :param port_id: Name of the switch port.
        :param subports: List of subport objects.
        :param trunk_details: Full trunk details dict from the parent port.
        :raises: GenericSwitchNotSupported if not implemented by subclass.
        """
        if not self.ADD_SUBPORTS_ON_TRUNK:
            raise exc.GenericSwitchNotSupported(
                feature='trunk subports',
                switch=self.device_name,
                error='NETCONF driver does not support trunk subports')
        config = self.ADD_SUBPORTS_ON_TRUNK(
            self, binding_profile=binding_profile, port_id=port_id,
            subports=subports, trunk_details=trunk_details)
        if config:
            self.send_config_to_device(config)

    def del_subports_on_trunk(self, binding_profile, port_id, subports,
                              trunk_details=None):
        """Remove subports from trunk.

        :param binding_profile: Binding profile of the parent port.
        :param port_id: Name of the switch port.
        :param subports: List of subport objects.
        :param trunk_details: Full trunk details dict from the parent port.
        :raises: GenericSwitchNotSupported if not implemented by subclass.
        """
        if not self.DEL_SUBPORTS_ON_TRUNK:
            raise exc.GenericSwitchNotSupported(
                feature='trunk subports',
                switch=self.device_name,
                error='NETCONF driver does not support trunk subports')
        config = self.DEL_SUBPORTS_ON_TRUNK(
            self, binding_profile=binding_profile, port_id=port_id,
            subports=subports, trunk_details=trunk_details)
        if config:
            self.send_config_to_device(config)

    #
    # Security groups — gated by ngs_security_groups_enabled (default False)
    #

    def add_security_group(self, sg):
        """Add a security group to the switch.

        :param sg: Security group object including rules.
        """
        pass

    def update_security_group(self, sg):
        """Update an existing security group on the switch.

        :param sg: Security group object including rules.
        """
        pass

    def del_security_group(self, sg_id):
        """Delete a security group from the switch.

        :param sg_id: Security group ID.
        """
        pass

    def bind_security_group(self, sg, port_id, port_ids):
        """Apply a security group to a port.

        :param sg: Security group object including rules.
        :param port_id: Name of switch port to bind group to.
        :param port_ids: Names of all switch ports currently bound to
            this group.
        """
        pass

    def unbind_security_group(self, sg_id, port_id, port_ids):
        """Remove a bound security group from a port.

        :param sg_id: ID of security group to unbind.
        :param port_id: Name of switch port to unbind group from.
        :param port_ids: Names of all switch ports currently bound to
            this group.
        """
        pass
