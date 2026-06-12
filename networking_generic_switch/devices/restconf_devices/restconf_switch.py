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
from urllib.parse import urlunsplit
import uuid

from oslo_config import cfg
from oslo_log import log as logging
from oslo_utils import netutils
from oslo_utils import strutils
import requests
import tenacity
from tooz import coordination

from networking_generic_switch import devices
from networking_generic_switch.devices import utils as device_utils
from networking_generic_switch import exceptions as exc
from networking_generic_switch import locking as ngs_lock
from networking_generic_switch.yang_models import utils as yutils

LOG = logging.getLogger(__name__)
CONF = cfg.CONF


class RestconfSwitch(devices.GenericSwitchDevice):
    """Base class for RESTCONF-based switch drivers.

    Provides HTTP session management, RESTCONF JSON serialization
    (RFC 8040 / RFC 7951), URL construction, retry logic, and
    coordination locking.

    Subclasses must assign callable class variables (ADD_NETWORK, etc.)
    that build YANG model objects.  The dispatch methods in this class
    invoke those callables, serialize the result to JSON via
    ``yutils.config_to_restconf_json``, and send to the device over
    HTTPS.
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

    def __init__(self, device_cfg, *args, **kwargs):
        super().__init__(device_cfg, *args, **kwargs)

        self._restconf_scheme = self.ngs_config.get(
            'ngs_restconf_scheme', 'https')
        self._restconf_port = int(self.config.get('port', 443))
        self._content_type = self.ngs_config.get(
            'ngs_restconf_content_type', 'application/yang-data+json')
        self._base_path = self.ngs_config.get(
            'ngs_restconf_base_path', '/restconf/data')
        self._verify_ssl = strutils.bool_from_string(
            self.ngs_config.get('ngs_verify_tls', True))

        self._base_url = self._build_base_url()

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

        # Initialize and cache the session for connection pooling and reuse
        self._session = self._configure_session()
        atexit.register(self._close_session)

    def _build_base_url(self):
        """Build the base URL for RESTCONF requests.

        :returns: Base URL string (e.g. ``https://switch:443`` or
            ``https://[2001:db8::1]:443`` for IPv6).
        """
        netloc = '{}:{}'.format(
            netutils.escape_ipv6(self.config.get('host')),
            self._restconf_port)
        return urlunsplit((self._restconf_scheme, netloc, '', '', ''))

    def _resource_url(self, path=''):
        """Build a full RESTCONF resource URL.

        :param path: Resource path to append after the base path.
            When empty, returns the RESTCONF data root URL.
        :returns: Full URL string.
        """
        base = self._base_url + self._base_path
        if not path:
            return base
        return '{}/{}'.format(base.rstrip('/'), path.lstrip('/'))

    def _configure_session(self):
        """Configure a ``requests.Session`` with auth, headers, and TLS.

        Creates a session with settings from device config.
        The session is cached on the instance for connection pooling
        and reuse across multiple requests.

        :returns: A configured ``requests.Session``.
        """
        session = requests.Session()
        username = self.config.get('username')
        password = self.config.get('password')
        if username:
            session.auth = (username, password or '')
        session.headers.update({
            'Content-Type': self._content_type,
            'Accept': self._content_type,
        })
        session.verify = self._verify_ssl
        return session

    def _close_session(self):
        """Close the cached session and cleanup connection pool."""
        if hasattr(self, '_session') and self._session:
            self._session.close()
            self._session = None

    @tenacity.retry(
        reraise=True,
        retry=tenacity.retry_if_exception_type(
            exc.GenericSwitchRestconfRetryable),
        wait=tenacity.wait_exponential(multiplier=1, min=2, max=5),
        stop=tenacity.stop_after_attempt(10))
    def _send_request(self, session, method, url, **kwargs):
        """Send an HTTP request with retry on transient failures.

        Retries with exponential back-off on HTTP 409 Conflict,
        HTTP 503 Service Unavailable, and connection errors.

        :param session: A ``requests.Session`` instance.
        :param method: HTTP method string (``GET``, ``PATCH``, etc.).
        :param url: Full URL to send the request to.
        :param kwargs: Additional keyword arguments passed to
            ``session.request``.
        :returns: ``requests.Response`` on success.
        :raises: GenericSwitchRestconfRetryable on transient errors
            (triggers tenacity retry).
        :raises: GenericSwitchRestconfError on non-transient HTTP errors.
        """
        try:
            response = session.request(method, url, **kwargs)
        except requests.exceptions.ConnectionError as e:
            LOG.warning(
                'RESTCONF connection error on device %(dev)s: %(err)s',
                {'dev': self.device_name, 'err': e})
            raise exc.GenericSwitchRestconfRetryable(
                device=self.device_name, error=e)

        if response.status_code == 409:
            LOG.warning(
                'RESTCONF device %(dev)s returned 409 Conflict, '
                'retrying: %(body)s',
                {'dev': self.device_name, 'body': response.text[:200]})
            raise exc.GenericSwitchRestconfRetryable(
                device=self.device_name,
                error='HTTP 409 Conflict')
        if response.status_code == 503:
            LOG.warning(
                'RESTCONF device %(dev)s returned 503 Service Unavailable, '
                'retrying: %(body)s',
                {'dev': self.device_name, 'body': response.text[:200]})
            raise exc.GenericSwitchRestconfRetryable(
                device=self.device_name,
                error='HTTP 503 Service Unavailable')

        if response.status_code >= 400:
            LOG.error(
                'RESTCONF %(method)s to %(url)s on device %(dev)s '
                'failed with status %(status)s: %(body)s',
                {'method': method, 'url': url, 'dev': self.device_name,
                 'status': response.status_code,
                 'body': response.text[:500]})
            raise exc.GenericSwitchRestconfError(
                device=self.device_name,
                error='HTTP {} {}'.format(
                    response.status_code, response.reason))

        return response

    # -----------------------------------------------------------------
    # Transport methods
    # -----------------------------------------------------------------

    def send_config_to_device(self, config, method='PATCH'):
        """Send configuration to the device via RESTCONF.

        Serializes model objects to RESTCONF JSON (RFC 7951) and sends
        one request per top-level container key.  NX-OS does not
        support PATCH to the bare ``/restconf/data`` root with multiple
        containers, so each key is sent to its own resource URL.

        :param config: Configuration object or list of configuration
            objects.  Each must implement ``to_restconf_dict()``.
        :param method: HTTP method to use (default ``PATCH``).
            Use ``PUT`` for operations that replace the resource
            entirely (e.g. interface trunk-vlan convergence).
        """
        if not isinstance(config, list):
            config = [config]

        payload = yutils.config_to_restconf_json(config)
        if not payload:
            return

        with ngs_lock.PoolLock(self.locker, **self.lock_kwargs):
            for container_key, container_data in payload.items():
                url = self._resource_url(container_key)
                LOG.debug(
                    'Sending RESTCONF %(method)s to device %(dev)s: '
                    '%(url)s payload: %(payload)s',
                    {'method': method, 'dev': self.device_name,
                     'url': url, 'payload': container_data})
                self._send_request(self._session, method, url,
                                   json=container_data)

    def get_from_device(self, path):
        """Read data from the device via RESTCONF GET.

        :param path: RESTCONF resource path (appended to the base URL).
        :returns: Parsed JSON response as a dict.
        """
        url = self._resource_url(path)
        LOG.debug(
            'Sending RESTCONF GET to device %(dev)s: %(url)s',
            {'dev': self.device_name, 'url': url})
        response = self._send_request(self._session, 'GET', url)
        return response.json()

    def delete_from_device(self, path):
        """Delete a resource from the device via RESTCONF DELETE.

        :param path: RESTCONF resource path to delete.
        """
        url = self._resource_url(path)
        LOG.debug(
            'Sending RESTCONF DELETE to device %(dev)s: %(url)s',
            {'dev': self.device_name, 'url': url})
        with ngs_lock.PoolLock(self.locker, **self.lock_kwargs):
            self._send_request(self._session, 'DELETE', url)

    # -----------------------------------------------------------------
    # Dispatch methods — delegate to subclass callables
    # -----------------------------------------------------------------

    def add_network(self, segmentation_id, network_id, physnet_vlans=None):
        """Create a VLAN on the device.

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
        if config:
            self.send_config_to_device(config)
        trunk_ports = self.get_trunk_ports()
        if trunk_ports and self.ADD_NETWORK_TO_TRUNK:
            trunk_config = self.ADD_NETWORK_TO_TRUNK(
                self,
                segmentation_id=segmentation_id,
                trunk_ports=trunk_ports,
                physnet_vlans=physnet_vlans,
            )
            if trunk_config:
                self.send_config_to_device(trunk_config, method='PUT')

    def del_network(self, segmentation_id, network_id, physnet_vlans=None):
        """Remove a VLAN from the device.

        :param segmentation_id: VLAN ID of the network.
        :param network_id: UUID of the Neutron network.
        :param physnet_vlans: Complete set of VLAN segmentation IDs on
            the physical network, or None if convergence is not active.
        """
        if not self._do_vlan_management():
            LOG.info("Skipping delete network for %s", segmentation_id)
            return
        trunk_ports = self.get_trunk_ports()
        if trunk_ports and self.REMOVE_NETWORK_FROM_TRUNK:
            trunk_config = self.REMOVE_NETWORK_FROM_TRUNK(
                self,
                segmentation_id=segmentation_id,
                trunk_ports=trunk_ports,
                physnet_vlans=physnet_vlans,
            )
            if trunk_config:
                self.send_config_to_device(trunk_config, method='PUT')
        network_id = uuid.UUID(network_id).hex
        network_name = self._get_network_name(network_id, segmentation_id)
        delete_config = self.DELETE_NETWORK(
            self,
            segmentation_id=segmentation_id,
            network_name=network_name,
        )
        if delete_config:
            self.send_config_to_device(delete_config)

    def plug_port_to_network(self, port_id, segmentation_id,
                             trunk_details=None, default_vlan=None):
        """Plug a port into a network.

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
            self.send_config_to_device(config, method='PUT')

    def delete_port(self, port_id, segmentation_id, trunk_details=None,
                    default_vlan=None):
        """Delete a port from a network.

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
            self.send_config_to_device(config, method='PUT')

    # -----------------------------------------------------------------
    # L2VNI — unsupported for now
    # -----------------------------------------------------------------

    def plug_switch_to_network(self, vni, segmentation_id, physnet=None):
        LOG.debug("plug_switch_to_network not supported for RESTCONF device "
                  "%s", self.device_name)

    def unplug_switch_from_network(self, vni, segmentation_id, physnet=None):
        LOG.debug("unplug_switch_from_network not supported for RESTCONF "
                  "device %s", self.device_name)

    def vlan_has_ports(self, segmentation_id):
        return True

    def vlan_has_vni(self, segmentation_id, vni):
        return False

    # -----------------------------------------------------------------
    # Trunks — dispatch to subclass callables
    # -----------------------------------------------------------------

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
                error='RESTCONF driver does not support trunk subports')
        config = self.ADD_SUBPORTS_ON_TRUNK(
            self, binding_profile=binding_profile, port_id=port_id,
            subports=subports, trunk_details=trunk_details)
        if config:
            self.send_config_to_device(config, method='PUT')

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
                error='RESTCONF driver does not support trunk subports')
        config = self.DEL_SUBPORTS_ON_TRUNK(
            self, binding_profile=binding_profile, port_id=port_id,
            subports=subports, trunk_details=trunk_details)
        if config:
            self.send_config_to_device(config, method='PUT')

    # -----------------------------------------------------------------
    # Security groups — stubs
    # -----------------------------------------------------------------

    def add_security_group(self, sg):
        pass

    def update_security_group(self, sg):
        pass

    def del_security_group(self, sg_id):
        pass

    def bind_security_group(self, sg, port_id, port_ids):
        pass

    def unbind_security_group(self, sg_id, port_id, port_ids):
        pass
