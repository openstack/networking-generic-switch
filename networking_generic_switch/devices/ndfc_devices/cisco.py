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

"""Cisco NDFC (Nexus Dashboard Fabric Controller) REST API Driver.

EXPERIMENTAL: This driver is experimental and based on publicly available
NDFC API documentation. It manages Cisco NX-OS switches through the NDFC
REST API. NDFC provides centralized fabric management with audit trails,
templating, and policy-based configuration.

API Documentation:
    Primary: https://developer.cisco.com/docs/
        nexus-dashboard-fabric-controller/latest/
    Getting Started: https://developer.cisco.com/docs/
        nexus-dashboard-fabric-controller/latest/
        getting-started/
    Reference Implementation:
        https://opendev.org/x/networking-cisco (ML2 driver)

The NDFC REST API follows OpenAPI 3.0 specification. API documentation
is also embedded in the NDFC UI (accessible via Swagger UI).

Authentication:
    POST /login - Returns JWT token used in Authorization header

Key API Endpoints Used (Modern NDFC API):
    Based on Cisco networking-cisco ML2 driver implementation.
    Uses modern ``/api/v1/manage/*`` paths
    (not legacy ``/appcenter/cisco/ndfc/*``).

    Switches/Inventory:
        GET  .../fabrics/{fabric}/switches

    Networks (VLANs and VXLANs):
        POST   .../fabrics/{fabric}/networks
        DELETE .../fabrics/{fabric}/networks/{network}
        POST   .../fabrics/{fabric}/networkAttachments
        POST   .../fabrics/{fabric}/networkActions/deploy

    Interfaces (legacy LAN Fabric REST API):
        PUT  /appcenter/cisco/ndfc/api/v1/lan-fabric/rest/interface
        POST /appcenter/cisco/ndfc/api/v1/lan-fabric/rest/interface/deploy

    Configuration Deployment:
        POST /appcenter/cisco/ndfc/api/v1/lan-fabric/rest/control/
             fabrics/{fabricName}/config-deploy/{switchId}
"""

import hashlib
import re
import threading

from oslo_log import log as logging
from oslo_utils import strutils
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from networking_generic_switch.devices import GenericSwitchDevice
from networking_generic_switch import exceptions as exc

LOG = logging.getLogger(__name__)

# NDFC-specific options. Extracted from device config and merged into
# self.ngs_config (following the pattern of NGS_INTERNAL_OPTS). Connection
# identity keys (host, port, username, password, ip) remain in self.config.
NDFC_OPTS = [
    # NDFC fabric that owns the managed switches.
    {'name': 'ndfc_fabric_name', 'default': 'default'},
    # Per-request timeout in seconds.
    {'name': 'ndfc_timeout', 'default': 30},
    # Switch identification within the NDFC inventory.
    {'name': 'ndfc_switch_serial'},
    {'name': 'ndfc_switch_hostname'},
    # Templates and policies used when creating networks and interfaces.
    {'name': 'ndfc_network_template', 'default': 'Default_Network_Universal'},
    {'name': 'ndfc_network_extension_template',
     'default': 'Default_Network_Extension_Universal'},
    {'name': 'ndfc_vrf', 'default': 'default'},
    {'name': 'ndfc_interface_policy', 'default': 'int_trunk_host'},
]


# Matches failure indicators as whole words to avoid false positives on
# benign fields such as "failoverEnabled" or "failsafe". NDFC embeds status
# strings like "FAILED" or human-readable "... failure ..." messages.
_FAILURE_RE = re.compile(r'\b(fail|failed|failure)\b', re.IGNORECASE)


def _find_failure_messages(data):
    """Recursively collect failure messages embedded in response data.

    NDFC can return HTTP 200 OK with failure messages embedded in the
    response body. This walks the structure and returns the string values
    that indicate a failure, so callers can surface a meaningful reason
    rather than a generic error.

    Matching is limited to whole-word failure tokens (see ``_FAILURE_RE``)
    to avoid false positives on unrelated fields that merely contain the
    substring "fail".

    Based on Cisco networking-cisco ML2 driver implementation.

    :param data: Response data (dict, list, str, or primitive)
    :returns: List of failure message strings (empty if none found)
    """
    messages = []
    if isinstance(data, dict):
        for value in data.values():
            messages.extend(_find_failure_messages(value))
    elif isinstance(data, list):
        for item in data:
            messages.extend(_find_failure_messages(item))
    elif isinstance(data, str) and _FAILURE_RE.search(data):
        messages.append(data)
    return messages


# Session pool for NDFC instances, one copy per worker process (a
# requests.Session and its token cannot be shared across a fork). We only
# guard against concurrency within a worker -- threads or eventlet
# greenthreads -- for which threading.Lock is correct in both cases.
# Key: hash of (host, port, username, password)
# Value: dict with 'session', 'token', 'lock' keys
_NDFC_SESSION_POOL = {}
# Guards creation of pool entries; each entry has its own 'lock' for its token.
_NDFC_POOL_LOCK = threading.Lock()


class CiscoNDFC(GenericSwitchDevice):
    """Cisco NDFC REST API-based switch driver.

    Manages Cisco NX-OS switches through Nexus Dashboard Fabric
    Controller (NDFC) REST API. Supports VLAN provisioning, port
    configuration, trunk management, and VXLAN L2VNI configuration
    via NDFC fabric controller.

    Port can be disabled: True

    Configuration Parameters
    ~~~~~~~~~~~~~~~~~~~~~~~~

    Required:
        - host: NDFC hostname or IP address
        - username: NDFC authentication username
        - password: NDFC authentication password
        - ndfc_fabric_name: NDFC fabric name (default: 'default')
        - ngs_network_name_format: Must contain ``{segmentation_id}``.
          Additional static text is permitted (e.g.
          ``neutron-{segmentation_id}``). The value ``{segmentation_id}``
          is appropriate for most deployments.

    Switch identification:
        The config section name (e.g. ``[genericswitch:leaf01]``) must match
        the switch hostname in NDFC. This aligns with Ironic ``switch_info``.

        Optional overrides:
        - ndfc_switch_serial: Explicit serial number (skips hostname lookup).
        - ndfc_switch_hostname: Override if hostname differs from section name.

    Optional NDFC Templates and Policies:
        - ndfc_network_template: Network template name
          (default: 'Default_Network_Universal')
        - ndfc_network_extension_template: Network extension template name
          (default: 'Default_Network_Extension_Universal')
        - ndfc_vrf: VRF name for network creation
          (default: 'default')
        - ndfc_interface_policy: Interface policy template name for
          trunk (uplink) ports configured via ``ngs_trunk_ports``
          (default: 'int_trunk_host'). Host-facing ports configured
          via ``plug_port_to_network`` always use ``int_access_host``.


    Optional Connection Settings:
        - port: NDFC HTTPS port (default: 443)
        - ngs_verify_tls: Verify the NDFC TLS certificate (default: True)
        - ndfc_timeout: Request timeout in seconds (default: 30)
        - ngs_max_connections: Session connection pool size, per NDFC
          controller (default: 1).

    NDFC Instance Sharing
    ~~~~~~~~~~~~~~~~~~~~~

    Multiple switch configurations pointing to the same NDFC instance
    automatically share a single authenticated session, pooled by hashed
    credentials. Token expiration is handled automatically with retry logic.

    VXLAN L2VNI Support
    ~~~~~~~~~~~~~~~~~~~

    Supports hierarchical port binding with VXLAN L2VNI. NDFC handles
    NVE interface configuration, BGP EVPN control plane, and VXLAN data
    plane based on the fabric template.

    Security Group Implementation
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Security groups are not currently implemented.
    """

    # Signal L2VNI support (methods implemented dynamically)
    PLUG_SWITCH_TO_NETWORK = True
    UNPLUG_SWITCH_FROM_NETWORK = True

    @property
    def support_trunk_on_ports(self):
        return True

    @property
    def support_trunk_on_bond_ports(self):
        return False

    def __init__(self, device_cfg, device_name=""):
        # Extract NDFC-specific options before the base class runs, mirroring
        # the pattern used by other drivers (e.g. Juniper). The base class only
        # strips ngs_* prefixed options from device_cfg; connection identity
        # keys (host, port, username, password, ip) are intentionally left in
        # self.config and read below.
        ndfc_cfg = {}
        for opt in NDFC_OPTS:
            opt_name = opt['name']
            if opt_name in device_cfg:
                ndfc_cfg[opt_name] = device_cfg.pop(opt_name)
            elif 'default' in opt:
                ndfc_cfg[opt_name] = opt['default']
        super(CiscoNDFC, self).__init__(device_cfg, device_name)
        self.ngs_config.update(ndfc_cfg)

        # NDFC connection configuration. `host` identifies the NDFC controller;
        # sessions are shared across all switches pointing to the same NDFC.
        self.ndfc_host = self.config.get('host')
        if not self.ndfc_host:
            LOG.error('NDFC host is required for the NDFC driver')
            raise exc.GenericSwitchNDFCConfigError()
        self.ndfc_port = self.config.get('port', 443)
        self.ndfc_username = self.config.get('username')
        self.ndfc_password = self.config.get('password')
        self.ndfc_fabric = self.ngs_config['ndfc_fabric_name']
        self.verify_tls = strutils.bool_from_string(
            self.ngs_config['ngs_verify_tls'])
        self.ndfc_timeout = int(self.ngs_config['ndfc_timeout'])
        # Session pool sized by ngs_max_connections, bounds per-NDFC not
        # per-switch since the session is shared across all switch sections.
        self.ndfc_max_connections = int(
            self.ngs_config['ngs_max_connections'])

        # Switch identification: serial or hostname (defaults to section name,
        # matching Ironic switch_info).
        self.ndfc_switch_serial = self.ngs_config.get('ndfc_switch_serial')
        self.ndfc_switch_hostname = (
            self.ngs_config.get('ndfc_switch_hostname') or self.device_name)
        if not (self.ndfc_switch_serial or self.ndfc_switch_hostname):
            LOG.error('A switch identifier (ndfc_switch_serial or '
                      'ndfc_switch_hostname) is required for the NDFC driver')
            raise exc.GenericSwitchNDFCConfigError()

        # Network name format must contain {segmentation_id} for consistency
        # across add_network, plug_port_to_network, and delete_port.
        name_format = self.ngs_config['ngs_network_name_format']
        if '{segmentation_id}' not in name_format:
            LOG.error(
                "ngs_network_name_format '%s' must contain {segmentation_id} "
                "for the NDFC driver.", name_format)
            raise exc.GenericSwitchNDFCConfigError()

        # NDFC template and policy configuration
        self.ndfc_network_template = self.ngs_config['ndfc_network_template']
        self.ndfc_network_extension_template = self.ngs_config[
            'ndfc_network_extension_template']
        self.ndfc_vrf = self.ngs_config['ndfc_vrf']
        self.ndfc_interface_policy = self.ngs_config['ndfc_interface_policy']

        # Generate session key from credentials (hashed)
        # This ensures password changes result in new sessions.
        # Note: Sessions with old passwords remain in the pool
        # but are never accessed since devices with new
        # passwords get different keys. Intentional - no
        # session cleanup needed.
        session_data = (
            "%s:%s:%s:%s" % (
                self.ndfc_host, self.ndfc_port,
                self.ndfc_username, self.ndfc_password)
        ).encode('utf-8')
        self._session_key = (
            hashlib.sha256(session_data).hexdigest()
        )

        # Cache for switch data (per-switch instance)
        self._switch_serial = None

        # API URL patterns (Cisco networking-cisco ML2 ref)
        # Using modern NDFC API (/api/v1/manage/* paths)
        # Modern API uses fabric NAME in URLs, not fabric ID
        self._api_base = (
            "api/v1/manage/fabrics/%s/" % self.ndfc_fabric
        )

    def _get_session_pool_entry(self):
        """Get or create the session pool entry for this NDFC instance.

        The returned dict is shared mutable state. Callers must only touch
        its ``token`` under the entry's ``lock``; the ``session`` object is
        created once and is never mutated afterwards (the auth header is
        passed per-request, see :meth:`_session_request`), so it is safe to
        use concurrently across threads.

        :returns: Dict with 'session', 'token', 'lock' keys
        """
        with _NDFC_POOL_LOCK:
            if self._session_key not in _NDFC_SESSION_POOL:
                LOG.info("Creating new shared NDFC session for %s:%s",
                         self.ndfc_host, self.ndfc_port)
                _NDFC_SESSION_POOL[self._session_key] = {
                    'session': self._create_session(),
                    'token': None,
                    'lock': threading.Lock()
                }
            return _NDFC_SESSION_POOL[self._session_key]

    def _ensure_authenticated(self, pool_entry):
        """Return a valid auth token, authenticating if needed.

        Thread-safe across all switch instances sharing the same NDFC
        credentials: the token is read and written only under the pool
        entry's lock.

        :param pool_entry: Session pool entry dict.
        :returns: A valid authentication token.
        """
        with pool_entry['lock']:
            if pool_entry['token'] is None:
                LOG.debug("No token in pool, authenticating to NDFC")
                self._authenticate(pool_entry)
            return pool_entry['token']

    def _reauthenticate(self, pool_entry, stale_token):
        """Force re-authentication and return a fresh token.

        Only re-authenticates if the token has not already been refreshed
        by another thread (compared against ``stale_token``), avoiding a
        thundering herd of logins when many concurrent requests see the
        same expiry. Thread-safe: all token access is under the pool
        entry's lock.

        :param pool_entry: Session pool entry dict.
        :param stale_token: The token the caller found to be invalid.
        :returns: A valid authentication token.
        """
        with pool_entry['lock']:
            if pool_entry['token'] in (stale_token, None):
                LOG.debug("Invalidating NDFC token for %s:%s and "
                          "re-authenticating", self.ndfc_host, self.ndfc_port)
                pool_entry['token'] = None
                self._authenticate(pool_entry)
            return pool_entry['token']

    def _create_session(self):
        """Create requests session with retry logic."""
        session = requests.Session()

        # Configure retry strategy.
        # 500 is intentionally excluded: it indicates a server-side error
        # with a meaningful response body that should be logged, not silently
        # retried. Retrying 500s on write operations also risks applying the
        # same change multiple times and swallows the error payload.
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "PUT", "POST", "DELETE"]
        )

        # All requests target a single NDFC host, so only pool_maxsize (the
        # number of connections kept for that one host) is meaningful here;
        # pool_connections (the number of distinct host pools cached) is left
        # at its default.
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_maxsize=self.ndfc_max_connections
        )

        session.mount("https://", adapter)
        session.mount("http://", adapter)

        # Set common headers. The Authorization header is intentionally not
        # set here; it is passed per-request so the shared session object is
        # never mutated after creation (see _session_request).
        session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })

        session.verify = self.verify_tls

        return session

    def _authenticate(self, pool_entry):
        """Authenticate with NDFC and store token in pool entry.

        Uses NDFC authentication endpoint to obtain JWT token.
        API Reference: POST /login

        Based on Cisco networking-cisco ML2 driver reference implementation.

        Request Payload:
            {
                "userName": "admin",
                "userPasswd": "password",
                "domain": "DefaultAuth",  # Can be "DefaultAuth" or domain name
                "expirationTime": 100000
            }

        Response:
            {
                "jwttoken": "eyJhbGci...",  # JWT token
                ...
            }

        The caller must hold ``pool_entry['lock']``.

        :param pool_entry: Session pool entry dict
        """
        auth_url = (
            f"https://{self.ndfc_host}:{self.ndfc_port}"
            "/login"
        )

        auth_data = {
            "userName": self.ndfc_username,
            "userPasswd": self.ndfc_password,
            "domain": "DefaultAuth",
            "expirationTime": 100000
        }

        try:
            response = pool_entry['session'].post(
                auth_url,
                json=auth_data,
                timeout=self.ndfc_timeout
            )
            response.raise_for_status()

            # Extract token from response (key is 'jwttoken' per Cisco ML2)
            token = response.json().get('jwttoken')
            if not token:
                LOG.error("NDFC authentication failed: no jwttoken in "
                          "response from %s", self.ndfc_host)
                raise exc.GenericSwitchNDFCConnectError(
                    error=("NDFC authentication to %s returned no token"
                           % self.ndfc_host))

            # Store the token only; the Authorization header is applied
            # per-request rather than mutated onto the shared session.
            pool_entry['token'] = token

            LOG.info("Successfully authenticated to NDFC at %s "
                     "(shared session)", self.ndfc_host)

        except requests.exceptions.RequestException as e:
            LOG.error("NDFC connection failed to %s:%s: %s",
                      self.ndfc_host, self.ndfc_port, e)
            raise exc.GenericSwitchNDFCConnectError(
                error=("NDFC connection failed to %s:%s: %s"
                       % (self.ndfc_host, self.ndfc_port, e))) from e

    def _parse_response(self, response, method, endpoint, url):
        """Parse an NDFC HTTP response, checking for embedded failures.

        :returns: Parsed JSON dict, or {} if no body.
        :raises: GenericSwitchNDFCConfigError on embedded failure.
        """
        if response.content:
            result = response.json()
            LOG.debug("NDFC response: %s %s status=%s body=%s",
                      method, url, response.status_code, result)
            failures = _find_failure_messages(result)
            if failures:
                detail = "; ".join(failures)
                LOG.error(
                    "NDFC API %s %s returned success status but "
                    "response indicates failure: %s",
                    method, endpoint, detail)
                raise exc.GenericSwitchNDFCConfigError(error=detail)
            return result
        LOG.debug("NDFC response: %s %s status=%s (no body)",
                  method, url, response.status_code)
        return {}

    @staticmethod
    def _http_error_detail(e):
        """Extract response body from an HTTPError for logging."""
        if e.response is not None:
            try:
                return e.response.json()
            except ValueError:
                pass
        return None

    @staticmethod
    def _is_auth_error(e):
        """Return True if HTTPError indicates an authentication failure."""
        # HTTPError raised by raise_for_status() always carries a response.
        status_code = e.response.status_code
        try:
            body = e.response.json()
        except ValueError:
            body = {}
        body_str = str(body).lower()
        return (
            status_code in (401, 403)
            or 'token has expired' in body_str
            or 'not authorized' in body_str
        )

    def _ndfc_request(self, method, endpoint, **kwargs):
        """Execute NDFC REST API request with error handling.

        Automatically handles token expiration by re-authenticating and
        retrying the request once on 401/403 errors. Uses shared session
        pool for efficiency across multiple switch instances.

        :param method: HTTP method (GET, POST, PUT, DELETE)
        :param endpoint: API endpoint path (no leading slash)
        :param kwargs: Additional requests arguments
        :returns: Response JSON data
        :raises: GenericSwitchNDFCConfigError on API errors
        """
        url = f"https://{self.ndfc_host}:{self.ndfc_port}/{endpoint}"

        LOG.debug("NDFC request: %s %s payload=%s",
                  method, url, kwargs.get('json'))

        # The session object is shared and never mutated; the token is
        # applied per-request by _session_request.
        pool_entry = self._get_session_pool_entry()
        session = pool_entry['session']
        token = self._ensure_authenticated(pool_entry)

        # First attempt
        try:
            response = self._session_request(
                session, method, url, token, **kwargs)
            response.raise_for_status()
            return self._parse_response(response, method, endpoint, url)

        except requests.exceptions.HTTPError as e:
            if not self._is_auth_error(e):
                detail = self._http_error_detail(e)
                LOG.error("NDFC API error: %s", detail if detail else e)
                raise exc.GenericSwitchNDFCConfigError(
                    error=str(detail) if detail else str(e)) from e

            # HTTPError from raise_for_status() always carries a response.
            status = e.response.status_code
            LOG.info("NDFC token expired (HTTP %s), "
                     "re-authenticating and retrying request", status)
            token = self._reauthenticate(pool_entry, token)

            LOG.debug("NDFC retry: %s %s payload=%s",
                      method, url, kwargs.get('json'))
            try:
                response = self._session_request(
                    session, method, url, token, **kwargs)
                response.raise_for_status()
                return self._parse_response(
                    response, method, endpoint, url)
            except requests.exceptions.HTTPError as retry_error:
                detail = self._http_error_detail(retry_error)
                LOG.error("NDFC API error after re-auth: %s",
                          detail if detail else retry_error)
                raise exc.GenericSwitchNDFCConfigError(
                    error=(str(detail) if detail
                           else str(retry_error))) from retry_error

        except requests.exceptions.RequestException as e:
            # Attempt to extract a response body from the cause chain
            # (e.g. RetryError wraps a ResponseError with a last response)
            error_detail = None
            cause = (getattr(e, 'reason', None)
                     or getattr(e, '__cause__', None))
            last_response = getattr(cause, 'response', None)
            if last_response is not None:
                try:
                    error_detail = last_response.json()
                except ValueError:
                    error_detail = last_response.text
            error_msg = (
                f"NDFC request failed: {error_detail}" if error_detail
                else f"NDFC request failed: {e}"
            )
            LOG.error(error_msg)
            raise exc.GenericSwitchNDFCConfigError(error=error_msg) from e

    def _session_request(self, session, method, url, token, **kwargs):
        """Send a request applying the auth token as a per-request header.

        The Authorization header is passed per-request rather than stored on
        the shared session, so the session object is never mutated after
        creation and remains safe for concurrent use across threads.

        :param session: Shared requests.Session from the pool.
        :param method: HTTP method.
        :param url: Fully-qualified request URL.
        :param token: Auth token to send, if any.
        :param kwargs: Additional requests arguments.
        :returns: The requests.Response.
        """
        headers = dict(kwargs.pop('headers', None) or {})
        if token:
            headers['Authorization'] = f'Bearer {token}'
        return session.request(
            method, url, headers=headers, timeout=self.ndfc_timeout, **kwargs)

    def _set_vlan_vni_mapping(self, switch_serial, segmentation_id, vni,
                              vni_value=None):
        """Configure or clear the vn-segment mapping for a VLAN.

        Uses the switch_freeform policy via the control policies API to
        push the vlan/vn-segment configuration at the global config level.
        This is necessary because vn-segment is a VLAN database command
        (under 'vlan <id>'), not an interface SVI command.

        LAN Fabric REST API:
        POST /lan-fabric/rest/control/policies - create/update freeform policy
        POST /lan-fabric/rest/control/fabrics/{f}/config-deploy/{s}

        :param switch_serial: Switch serial number
        :param segmentation_id: VLAN ID
        :param vni: VNI being configured (used only for logging)
        :param vni_value: VNI integer to configure, or None to clear.
        """
        _policies_base = (
            "appcenter/cisco/ndfc/api/v1/lan-fabric/rest/control/policies"
        )

        if vni_value:
            conf = f"vlan {segmentation_id}\n  vn-segment {vni}"
            action = "Configuring"
        else:
            conf = f"vlan {segmentation_id}\n  no vn-segment"
            action = "Clearing"

        LOG.info("%s VNI %s on VLAN %s via switch_freeform (serial %s)",
                 action, vni, segmentation_id, switch_serial)

        payload = {
            "serialNumber": switch_serial,
            "entityType": "SWITCH",
            "entityName": "SWITCH",
            "templateName": "switch_freeform",
            "nvPairs": {
                "CONF": conf,
            }
        }

        self._ndfc_request('POST', _policies_base, json=payload)
        self._deploy_config(switch_serial)

    def _get_interface_nvpairs(self, switch_serial, port):
        """Get the current nvPairs for an interface.

        LAN Fabric REST API:
        GET /appcenter/cisco/ndfc/api/v1/lan-fabric/rest/interface
            ?serialNumber={serial}&ifName={port}

        A query failure is deliberately not swallowed: callers use the
        returned nvPairs to compute the new interface configuration, so
        returning an empty dict on error would silently drop the port's
        existing VLANs when the updated config is written back.

        :param switch_serial: Switch serial number
        :param port: Interface name (e.g. 'Ethernet1/49')
        :returns: nvPairs dict, or empty dict if the interface is not found.
        :raises: GenericSwitchNDFCConfigError if the query fails.
        """
        _interface_base = (
            "appcenter/cisco/ndfc/api/v1/lan-fabric/rest/interface"
        )
        response = self._ndfc_request(
            'GET',
            f'{_interface_base}?serialNumber={switch_serial}'
            f'&ifName={port}'
        )
        # Response: [{'policy': ..., 'interfaces': [{'nvPairs': {...}}]}]
        for policy_obj in (response if isinstance(response, list) else []):
            for iface in policy_obj.get('interfaces', []):
                return iface.get('nvPairs', {})
        return {}

    def _get_interface_allowed_vlans(self, switch_serial, port):
        """Get the current ALLOWED_VLANS for a trunk interface as a set.

        :param switch_serial: Switch serial number
        :param port: Interface name (e.g. 'Ethernet1/49')
        :returns: Set of VLAN IDs (ints), empty set if not set or not found.
        """
        nv_pairs = self._get_interface_nvpairs(switch_serial, port)
        return self._parse_vlan_list(nv_pairs.get('ALLOWED_VLANS', ''))

    def _set_interface_policy(self, switch_serial, port,
                              policy, vlan_key, vlan_value=None,
                              extra_nv_pairs=None):
        """Set interface policy and VLAN configuration on a switch port.

        Configures the interface directly via the LAN Fabric REST interface
        API, bypassing the networkAttachments API which enforces fabric
        topology constraints (requires leaf/aggregation association).

        Uses the legacy LAN Fabric REST interface:
        PUT /appcenter/cisco/ndfc/api/v1/lan-fabric/rest/interface

        Followed by a deploy to push the configuration to the device:
        POST /appcenter/cisco/ndfc/api/v1/lan-fabric/rest/interface/deploy

        :param switch_serial: Switch serial number
        :param port: Interface name (e.g. 'Ethernet1/4')
        :param policy: NDFC interface policy template name
            (e.g. 'int_trunk_host', 'int_access_host')
        :param vlan_key: nvPairs key for VLAN assignment
            ('ALLOWED_VLANS' for trunk, 'ACCESS_VLAN' for access)
        :param vlan_value: VLAN value to set (e.g. '100', 'none').
            If None, the VLAN nvPair is not set.
        :param extra_nv_pairs: Optional dict of additional nvPairs to
            merge into the payload (e.g. {'NATIVE_VLAN': '100'}).
        """
        _interface_base = (
            "appcenter/cisco/ndfc/api/v1/lan-fabric/rest/interface"
        )

        nv_pairs = {
            "BPDUGUARD_ENABLED": "true",
            "PORTTYPE_FAST_ENABLED": "true",
            "MTU": "jumbo",
            "SPEED": "Auto"
        }
        if vlan_value is not None:
            nv_pairs[vlan_key] = vlan_value
        if extra_nv_pairs:
            nv_pairs.update(extra_nv_pairs)

        payload = {
            "policy": policy,
            "interfaces": [
                {
                    "serialNumber": switch_serial,
                    "ifName": port,
                    "nvPairs": nv_pairs
                }
            ]
        }

        LOG.debug("Setting interface policy '%s' on %s:%s %s=%s",
                  policy, switch_serial, port, vlan_key, vlan_value)

        self._ndfc_request('PUT', _interface_base, json=payload)

        # Deploy the interface configuration to the device
        deploy_payload = [{"serialNumber": switch_serial, "ifName": port}]
        self._ndfc_request(
            'POST',
            f'{_interface_base}/deploy',
            json=deploy_payload
        )

    def _set_port_admin_state(self, switch_serial, port, operation):
        """Administratively shut or enable a switch port.

        Checks the current admin state first and skips the API call if
        the port is already in the desired state.

        LAN Fabric REST API:
        GET  /appcenter/cisco/ndfc/api/v1/lan-fabric/rest/interface
        POST /appcenter/cisco/ndfc/api/v1/lan-fabric/rest/interface/adminstatus

        :param switch_serial: Switch serial number
        :param port: Interface name (e.g. 'Ethernet1/4')
        :param operation: 'shut' or 'noshut'
        """
        # ADMIN_STATE nvPair is 'true' when port is up, 'false' when shut
        desired_admin_state = 'true' if operation == 'noshut' else 'false'
        nv_pairs = self._get_interface_nvpairs(switch_serial, port)
        current_admin_state = nv_pairs.get('ADMIN_STATE')

        if current_admin_state == desired_admin_state:
            LOG.debug("Port %s:%s already in desired admin state (%s), "
                      "skipping %s", switch_serial, port,
                      current_admin_state, operation)
            return

        payload = {
            "operation": operation,
            "interfaces": [
                {"serialNumber": switch_serial, "ifName": port}
            ]
        }

        LOG.debug("Setting port admin state '%s' on %s:%s",
                  operation, switch_serial, port)

        _adminstatus = (
            "appcenter/cisco/ndfc/api/v1/lan-fabric/rest"
            "/interface/adminstatus"
        )
        self._ndfc_request(
            'POST',
            _adminstatus,
            json=payload
        )

    def _get_switch_serial(self):
        """Resolve this switch's serial number in NDFC (cached).

        A switch may be identified by an explicit serial number, its
        management IP (``ip``), or its hostname (``ndfc_switch_hostname``,
        which defaults to the config section name). An explicit serial needs
        no lookup; otherwise the NDFC inventory is queried and matched.

        Uses modern NDFC API: GET /api/v1/manage/fabrics/{fabric}/switches

        Response structure:
            {
                "switches": [
                    {
                        "serialNumber": "ABC123",
                        "fabricManagementIp": "10.1.1.1",
                        "hostname": "switch-1",
                        "switchRole": "leaf",
                        ...
                    }
                ]
            }
        """
        if self._switch_serial is not None:
            return self._switch_serial

        # An explicit serial number needs no inventory lookup.
        if self.ndfc_switch_serial:
            self._switch_serial = self.ndfc_switch_serial
            return self._switch_serial

        # Look up switch by hostname in NDFC inventory.
        response = self._ndfc_request('GET', f'{self._api_base}switches')

        # Modern API wraps switches in a "switches" key
        switches = response.get('switches', [])

        # Match by hostname.
        for switch in switches:
            if switch.get('hostname') == self.ndfc_switch_hostname:
                self._switch_serial = switch.get('serialNumber')
                LOG.debug("Resolved switch serial %s (hostname=%s)",
                          self._switch_serial, self.ndfc_switch_hostname)
                return self._switch_serial

        LOG.error("Switch (hostname=%s) not found in fabric '%s'",
                  self.ndfc_switch_hostname, self.ndfc_fabric)
        raise exc.GenericSwitchNDFCConfigError()

    def _deploy_config(self, switch_serial):
        """Deploy pending configuration changes to switch.

        Pushes staged intent from NDFC's database to the physical switch,
        clearing "Pending" sync status.

        :param switch_serial: Serial number of the switch to deploy to
        """
        _control_base = (
            "appcenter/cisco/ndfc/api/v1/lan-fabric/rest/control"
            f"/fabrics/{self.ndfc_fabric}"
        )

        LOG.debug("Deploying configuration to switch %s", switch_serial)

        self._ndfc_request(
            'POST',
            f"{_control_base}/config-deploy/{switch_serial}"
        )

    def _build_network_config(self, network_name, vlan_id, network_id):
        """Build the NDFC network payload shared by VLAN and L2VNI creation.

        The payload is identical for a pure VLAN network and a VXLAN L2VNI
        network except for the network identifier: for pure VLANs
        ``network_id`` equals ``vlan_id``; for VXLAN L2VNI ``network_id`` is
        the VNI while ``vlan_id`` is the local VLAN.

        :param network_name: Name used for both displayName and networkName.
        :param vlan_id: Local VLAN ID (segmentation_id).
        :param network_id: NDFC networkId (VLAN ID for pure VLANs, VNI for
            L2VNI).
        :returns: A dict describing a single NDFC network.
        """
        return {
            "displayName": network_name,
            "fabricName": self.ndfc_fabric,
            "networkName": network_name,
            "vlanId": vlan_id,
            "vrfName": self.ndfc_vrf,
            "networkId": network_id,
            "networkType": "vxlan",  # NDFC fabric type
            "l2Data": {
                "vlanName": "",
                "rtAuto": False
            },
            "l3Data": {
                "gatewayIp": "",
                "vlanInterfaceDescription": "",
                "arp": True,
                "mtu": {"protocol": {"layer2": 9216}},
                "ipv4Trm": False,
                "ipv6Trm": False,
                "fabricData": {
                    "gatewayOnBorder": False
                },
                "tag": 12345,
                "netflow": False,
                "igmpVersion": 2
            },
            "networkTemplateName": self.ndfc_network_template
        }

    def add_network(self, segmentation_id, network_id):
        """Create pure VLAN network in NDFC fabric.

        For VXLAN L2VNI networks, use plug_switch_to_network() instead.

        :param segmentation_id: VLAN ID
        :param network_id: Neutron network UUID
        """
        if not self._do_vlan_management():
            LOG.debug("VLAN management disabled, skipping network %s",
                      network_id)
            return

        network_name = self._get_network_name(
            segmentation_id=segmentation_id,
            network_id=segmentation_id
        )

        switch_serial = self._get_switch_serial()

        # Create pure VLAN network in NDFC (modern API).
        # For pure VLANs networkId == vlanId (segmentation_id).
        network_config = self._build_network_config(
            network_name, segmentation_id, segmentation_id)

        network_payload = {"networks": [network_config]}

        LOG.info("Creating VLAN network %s (VLAN %s) in fabric %s",
                 network_name, segmentation_id, self.ndfc_fabric)

        try:
            self._ndfc_request(
                'POST',
                f'{self._api_base}networks',
                json=network_payload
            )
        except exc.GenericSwitchNDFCConfigError as e:
            # NDFC has no cheap "does this network exist?" query, and a
            # concurrent NGS instance may be creating the same network, so
            # we always attempt creation and treat an expected "already
            # exists" failure as success. Any other failure is genuine.
            if "already exists" not in str(e).lower():
                LOG.error("Failed to create VLAN network %s: %s",
                          network_name, e)
                raise

        # Configure trunk ports with this VLAN (ngs_trunk_ports support)
        for trunk_port in self.get_trunk_ports():
            existing = self._get_interface_allowed_vlans(
                switch_serial, trunk_port)
            new_vlans = existing | {int(segmentation_id)}
            LOG.info("Adding VLAN %s to trunk port %s (was: %s, now: %s)",
                     segmentation_id, trunk_port, existing, new_vlans)
            self._set_interface_policy(
                switch_serial, trunk_port,
                policy=self.ndfc_interface_policy,
                vlan_key='ALLOWED_VLANS',
                vlan_value=self._vlan_list_to_str(new_vlans)
            )

        if self.get_trunk_ports():
            self._deploy_config(switch_serial)

    def del_network(self, segmentation_id, network_id):
        """Delete VLAN network from NDFC fabric.

        For VXLAN L2VNI networks, use unplug_switch_from_network() instead.

        :param segmentation_id: VLAN ID
        :param network_id: Neutron network UUID
        """
        if not self._do_vlan_management():
            LOG.debug("VLAN management disabled, skipping network %s",
                      network_id)
            return

        network_name = self._get_network_name(
            segmentation_id=segmentation_id,
            network_id=segmentation_id
        )

        switch_serial = self._get_switch_serial()

        LOG.info("Deleting VLAN network %s (VLAN %s) from fabric %s",
                 network_name, segmentation_id, self.ndfc_fabric)

        # Remove VLAN from trunk ports (ngs_trunk_ports support)
        for trunk_port in self.get_trunk_ports():
            existing = self._get_interface_allowed_vlans(
                switch_serial, trunk_port)
            new_vlans = existing - {int(segmentation_id)}
            LOG.info("Removing VLAN %s from trunk port %s (was: %s, now: %s)",
                     segmentation_id, trunk_port, existing, new_vlans)
            self._set_interface_policy(
                switch_serial, trunk_port,
                policy=self.ndfc_interface_policy,
                vlan_key='ALLOWED_VLANS',
                vlan_value=self._vlan_list_to_str(new_vlans)
            )

        if self.get_trunk_ports():
            self._deploy_config(switch_serial)

        # Detach switch from network (modern API uses attach=false).
        # A failure here is not ignored: leaving the attachment in place
        # can keep the node connected to the tenant network, so we surface
        # the error to the caller.
        detachment_entry = {
            "attach": False,
            "interfaces": [],
            "networkName": network_name,
            "switchId": switch_serial,
            "vlanId": segmentation_id
        }

        try:
            self._ndfc_request(
                'POST',
                f'{self._api_base}networkAttachments',
                json={"attachments": [detachment_entry]}
            )
        except exc.GenericSwitchNDFCConfigError as e:
            LOG.error("Failed to detach switch from network %s: %s",
                      network_name, e)
            raise

        # Delete the network object from the fabric.
        try:
            self._ndfc_request(
                'DELETE',
                f'{self._api_base}networks/{network_name}'
            )
        except exc.GenericSwitchNDFCConfigError as e:
            LOG.error("Failed to delete network %s: %s", network_name, e)
            raise

    def plug_port_to_network(self, port, segmentation_id,
                             trunk_details=None, default_vlan=None):
        """Configure switch port for network access.

        Configures access ports with int_access_host policy or trunk ports
        with int_trunk_host policy, setting VLANs appropriately.

        :param port: Port identifier (e.g., 'Ethernet1/1')
        :param segmentation_id: VLAN ID (native VLAN for trunk ports)
        :param trunk_details: Dict with 'sub_ports' list for trunk config
        :param default_vlan: Native VLAN override (access mode only)
        """
        if not self.is_allowed(port, segmentation_id):
            LOG.warning("Port %s / VLAN %s not in allowlist, skipping",
                        port, segmentation_id)
            return

        switch_serial = self._get_switch_serial()

        if trunk_details:
            # Trunk port: configure int_trunk_host with native VLAN and
            # all sub-port VLANs added to the existing ALLOWED_VLANS list.
            sub_port_vlans = [
                str(sp['segmentation_id'])
                for sp in trunk_details.get('sub_ports', [])
            ]
            LOG.debug("Configuring port %s as trunk: native VLAN %s, "
                      "sub-port VLANs %s on %s",
                      port, segmentation_id, sub_port_vlans, switch_serial)

            existing = self._get_interface_allowed_vlans(switch_serial, port)
            new_vlans = existing | {int(segmentation_id)}
            for vlan in sub_port_vlans:
                new_vlans = new_vlans | {int(vlan)}

            self._set_interface_policy(
                switch_serial, port,
                policy='int_trunk_host',
                vlan_key='ALLOWED_VLANS',
                vlan_value=self._vlan_list_to_str(new_vlans),
                extra_nv_pairs={'NATIVE_VLAN': str(segmentation_id)}
            )
        else:
            # Access port
            port_default_vlan = default_vlan or self._get_port_default_vlan()
            if port_default_vlan:
                LOG.debug("Replacing default VLAN %s on port %s with VLAN %s",
                          port_default_vlan, port, segmentation_id)

            LOG.info("Configuring port %s with VLAN %s on %s",
                     port, segmentation_id, switch_serial)

            self._set_interface_policy(
                switch_serial, port,
                policy='int_access_host',
                vlan_key='ACCESS_VLAN',
                vlan_value=str(segmentation_id)
            )

        if self._disable_inactive_ports():
            self._set_port_admin_state(switch_serial, port, 'noshut')

        self._deploy_config(switch_serial)

    def delete_port(self, port, segmentation_id,
                    trunk_details=None, default_vlan=None):
        """Remove port from network.

        Access ports: moves to default VLAN.
        Trunk ports: removes VLANs; reverts to access mode if no VLANs remain.

        :param port: Port identifier
        :param segmentation_id: VLAN ID
        :param trunk_details: Dict with 'sub_ports' list for trunk mode
        :param default_vlan: Default VLAN override (access mode only)
        """
        switch_serial = self._get_switch_serial()

        LOG.info("Removing VLAN %s from port %s on %s",
                 segmentation_id, port, switch_serial)

        if trunk_details:
            # Trunk port: remove native VLAN and all sub-port VLANs from
            # the existing ALLOWED_VLANS list.
            sub_port_vlans = [
                str(sp['segmentation_id'])
                for sp in trunk_details.get('sub_ports', [])
            ]
            LOG.debug("Removing trunk VLANs from port %s: native %s, "
                      "sub-ports %s on %s",
                      port, segmentation_id, sub_port_vlans, switch_serial)

            existing = self._get_interface_allowed_vlans(switch_serial, port)
            remaining = existing - {int(segmentation_id)}
            for vlan in sub_port_vlans:
                remaining = remaining - {int(vlan)}

            if not remaining:
                # No VLANs left — revert to access mode on default VLAN
                port_default_vlan = str(
                    default_vlan or self._get_port_default_vlan() or 1
                )
                LOG.debug("No trunk VLANs remain on port %s, "
                          "reverting to access mode (VLAN %s)",
                          port, port_default_vlan)
                self._set_interface_policy(
                    switch_serial, port,
                    policy='int_access_host',
                    vlan_key='ACCESS_VLAN',
                    vlan_value=port_default_vlan
                )
            else:
                self._set_interface_policy(
                    switch_serial, port,
                    policy='int_trunk_host',
                    vlan_key='ALLOWED_VLANS',
                    vlan_value=self._vlan_list_to_str(remaining),
                    extra_nv_pairs={'NATIVE_VLAN': ''}
                )
        else:
            # Access port: move to default VLAN
            # (int_access_host rejects ACCESS_VLAN=none)
            port_default_vlan = str(
                default_vlan or self._get_port_default_vlan() or 1
            )
            self._set_interface_policy(
                switch_serial, port,
                policy='int_access_host',
                vlan_key='ACCESS_VLAN',
                vlan_value=port_default_vlan
            )

        if self._disable_inactive_ports():
            self._set_port_admin_state(switch_serial, port, 'shut')

        self._deploy_config(switch_serial)

    def add_subports_on_trunk(self, binding_profile, port, subports):
        """Add subports to a trunk port via interface policy.

        Fetches the current ALLOWED_VLANS, appends all subport VLANs,
        and writes the updated list in a single PUT. Bond ports are not
        supported (support_trunk_on_bond_ports is False).

        LAN Fabric REST API:
            1. GET  /lan-fabric/rest/interface - Fetch current ALLOWED_VLANS
            2. PUT  /lan-fabric/rest/interface - Set updated ALLOWED_VLANS
            3. POST /lan-fabric/rest/interface/deploy - Push to device
            4. POST /lan-fabric/rest/control/fabrics/{f}/config-deploy/{s}

        :param binding_profile: Neutron binding profile (unused — bond
            ports are blocked upstream by support_trunk_on_bond_ports)
        :param port: Switch port identifier (e.g. 'Ethernet1/1')
        :param subports: List of subport dicts with 'segmentation_id'
        """
        switch_serial = self._get_switch_serial()

        existing = self._get_interface_allowed_vlans(switch_serial, port)
        new_vlans = existing | {int(sp.get('segmentation_id'))
                                for sp in subports}

        LOG.info("Adding subport VLANs %s to trunk port %s on %s",
                 [sp.get('segmentation_id') for sp in subports],
                 port, switch_serial)

        self._set_interface_policy(
            switch_serial, port,
            policy='int_trunk_host',
            vlan_key='ALLOWED_VLANS',
            vlan_value=self._vlan_list_to_str(new_vlans)
        )

        self._deploy_config(switch_serial)

    def del_subports_on_trunk(self, binding_profile, port, subports):
        """Remove subports from a trunk port via interface policy.

        Fetches the current ALLOWED_VLANS, removes all subport VLANs,
        and writes the updated list in a single PUT. If no VLANs remain,
        reverts the port to int_access_host on the default VLAN.

        LAN Fabric REST API:
            1. GET  /lan-fabric/rest/interface - Fetch current ALLOWED_VLANS
            2. PUT  /lan-fabric/rest/interface - Set updated ALLOWED_VLANS
            3. POST /lan-fabric/rest/interface/deploy - Push to device
            4. POST /lan-fabric/rest/control/fabrics/{f}/config-deploy/{s}

        :param binding_profile: Neutron binding profile (unused — bond
            ports are blocked upstream by support_trunk_on_bond_ports)
        :param port: Switch port identifier (e.g. 'Ethernet1/1')
        :param subports: List of subport dicts with 'segmentation_id'
        """
        switch_serial = self._get_switch_serial()

        existing = self._get_interface_allowed_vlans(switch_serial, port)
        remaining = existing - {int(sp.get('segmentation_id'))
                                for sp in subports}

        LOG.info("Removing subport VLANs %s from trunk port %s on %s",
                 [sp.get('segmentation_id') for sp in subports],
                 port, switch_serial)

        if not remaining:
            port_default_vlan = str(self._get_port_default_vlan() or 1)
            LOG.debug("No trunk VLANs remain on port %s, "
                      "reverting to access mode (VLAN %s)",
                      port, port_default_vlan)
            self._set_interface_policy(
                switch_serial, port,
                policy='int_access_host',
                vlan_key='ACCESS_VLAN',
                vlan_value=port_default_vlan
            )
        else:
            self._set_interface_policy(
                switch_serial, port,
                policy='int_trunk_host',
                vlan_key='ALLOWED_VLANS',
                vlan_value=self._vlan_list_to_str(remaining)
            )

        self._deploy_config(switch_serial)

    def plug_switch_to_network(self, vni,
                               segmentation_id,
                               physnet=None):
        """Configure L2VNI mapping in NDFC fabric.

        Creates VXLAN network with VNI-to-VLAN mapping. NDFC handles NVE
        interface configuration and BGP EVPN control plane setup.

        :param vni: VXLAN Network Identifier
        :param segmentation_id: VLAN ID to map to the VNI
        :param physnet: Physical network name (unused)
        """
        network_name = self._get_network_name(
            segmentation_id=vni,
            network_id=f"vni-{vni}"
        )

        switch_serial = self._get_switch_serial()

        # Create L2VNI network in NDFC (modern API).
        # For VXLAN L2VNI networkId is the VNI, vlanId is the local VLAN.
        network_config = self._build_network_config(
            network_name, segmentation_id, vni)

        network_payload = {"networks": [network_config]}

        LOG.info("Creating L2VNI network %s (VNI %s, VLAN %s) in fabric %s",
                 network_name, vni, segmentation_id, self.ndfc_fabric)

        try:
            self._ndfc_request(
                'POST',
                f'{self._api_base}networks',
                json=network_payload
            )
        except exc.GenericSwitchNDFCConfigError as e:
            # NDFC has no cheap "does this network exist?" query, and a
            # concurrent NGS instance may be creating the same network, so
            # we always attempt creation and treat an expected "already
            # exists" failure as success. Any other failure is genuine and
            # must be raised so the port binding does not proceed against a
            # network that was never created.
            if "already exists" not in str(e).lower():
                LOG.error("Failed to create L2VNI network %s: %s",
                          network_name, e)
                raise

        # Configure the VLAN-to-VNI mapping directly on the switch via
        # the interface policy API, using INTERFACE_VLAN (SVI).
        # This avoids networkAttachments which rejects Access/Aggregation
        # role switches without a leaf/spine association.
        self._set_vlan_vni_mapping(switch_serial, segmentation_id, vni,
                                   vni_value=vni)

    def unplug_switch_from_network(self, vni,
                                   segmentation_id,
                                   physnet=None):
        """Remove L2VNI mapping from NDFC fabric.

        Clears vn-segment configuration on the VLAN.

        :param vni: VXLAN Network Identifier to remove
        :param segmentation_id: VLAN ID
        :param physnet: Physical network name (unused)
        """
        network_name = self._get_network_name(
            segmentation_id=vni,
            network_id=f"vni-{vni}"
        )

        switch_serial = self._get_switch_serial()

        LOG.info("Removing L2VNI network %s (VNI %s, VLAN %s) from "
                 "switch %s in fabric %s",
                 network_name, vni, segmentation_id,
                 switch_serial, self.ndfc_fabric)

        try:
            self._set_vlan_vni_mapping(switch_serial, segmentation_id, vni,
                                       vni_value=None)
        except exc.GenericSwitchNDFCConfigError as e:
            LOG.debug("Failed to remove VNI %s from VLAN %s SVI: %s",
                      vni, segmentation_id, e)

    def vlan_has_vni(self, segmentation_id, vni):
        """Check if VLAN has VNI mapping configured in NDFC.

        Queries NDFC to check if a network with the given VNI exists
        and is attached to this switch with the specified VLAN.

        :param segmentation_id: VLAN ID
        :param vni: VNI to check for
        :returns: True if VNI is configured, False otherwise
        """
        network_name = self._get_network_name(
            segmentation_id=vni,
            network_id=f"vni-{vni}"
        )

        try:
            # Query network details
            network = self._ndfc_request(
                'GET',
                f'{self._api_base}networks/{network_name}'
            )

            # Check if network ID matches VNI and VLAN ID matches.
            # NDFC may return networkId/vlanId as int or string.
            # Since we use switch_freeform rather than networkAttachments,
            # there will be no attachment record — the existence of the
            # network object with matching VNI and VLAN is sufficient to
            # confirm the VNI is configured on this switch.
            if (str(network.get('networkId')) == str(vni)
                    and str(network.get('vlanId')) == str(segmentation_id)):
                LOG.debug("VNI %s already configured on VLAN %s",
                          vni, segmentation_id)
                return True

        except exc.GenericSwitchNDFCConfigError:
            # Network doesn't exist or query failed
            pass

        return False

    def vlan_has_ports(self, segmentation_id):
        """Check if VLAN has ports assigned in NDFC.

        Queries all interfaces on this switch and checks ACCESS_VLAN and
        ALLOWED_VLANS nvPairs to determine if any port carries the VLAN.

        LAN Fabric REST API:

        GET /appcenter/cisco/ndfc/api/v1/lan-fabric/rest/interface
            ?serialNumber={serial}

        Response: [{'policy': ..., 'interfaces': [{'nvPairs': {...}}]}]

        :param segmentation_id: VLAN ID to check
        :returns: True if VLAN has ports, False if empty
        """
        switch_serial = self._get_switch_serial()

        try:
            response = self._ndfc_request(
                'GET',
                "appcenter/cisco/ndfc/api/v1/lan-fabric/rest/interface"
                f"?serialNumber={switch_serial}"
            )

            # Response is a list of policy objects each wrapping interfaces:
            # [{'policy': ..., 'interfaces': [{'ifName': ..., 'nvPairs': {}}]}]
            for policy_obj in (response if isinstance(response, list) else []):
                for interface in policy_obj.get('interfaces', []):
                    nv_pairs = interface.get('nvPairs', {})

                    # Check access VLAN
                    access_vlan = nv_pairs.get('ACCESS_VLAN')
                    if access_vlan == str(segmentation_id):
                        LOG.debug("VLAN %s has access port %s",
                                  segmentation_id, interface.get('ifName'))
                        return True

                    # Check trunk allowed VLANs
                    allowed_vlans_str = nv_pairs.get('ALLOWED_VLANS', '')
                    if allowed_vlans_str and allowed_vlans_str != 'none':
                        allowed_vlans = self._parse_vlan_list(
                            allowed_vlans_str)
                        if segmentation_id in allowed_vlans:
                            LOG.debug("VLAN %s in trunk allowed list on %s",
                                      segmentation_id,
                                      interface.get('ifName'))
                            return True

        except exc.GenericSwitchNDFCConfigError as e:
            # Conservative: return True on error to prevent accidental removal
            LOG.warning("Failed to query VLAN %s ports: %s. "
                        "Assuming VLAN has ports (conservative)",
                        segmentation_id, e)
            return True

        LOG.debug("VLAN %s has no ports", segmentation_id)
        return False

    def _parse_vlan_list(self, vlan_str):
        """Parse a VLAN list string into a set of integers.

        Handles formats like: "1,10,20-25,30" and "none".

        :param vlan_str: VLAN list string
        :returns: Set of VLAN IDs as integers
        """
        vlans = set()
        for part in vlan_str.split(','):
            part = part.strip()
            if '-' in part:
                start, end = part.split('-')
                vlans.update(range(int(start), int(end) + 1))
            elif part.isdigit():
                vlans.add(int(part))
        return vlans

    def _vlan_list_to_str(self, vlans):
        """Serialise a set of VLAN IDs to a compact comma-separated string.

        Sequential VLANs are collapsed into range notation, e.g.
        {100, 200, 201, 202, 300} → '100,200-202,300'.

        :param vlans: Set of VLAN IDs as integers
        :returns: Compact sorted string, or 'none' if empty
        """
        if not vlans:
            return 'none'

        sorted_vlans = sorted(vlans)
        parts = []
        start = prev = sorted_vlans[0]

        for v in sorted_vlans[1:]:
            if v == prev + 1:
                prev = v
            else:
                parts.append(str(start) if start == prev
                             else f'{start}-{prev}')
                start = prev = v
        parts.append(str(start) if start == prev else f'{start}-{prev}')

        return ','.join(parts)

    # Security group methods - not implemented
    def add_security_group(self, sg_id, rules):
        """Create security group policy in NDFC."""
        LOG.warning("Security groups not implemented for NDFC driver")
        raise NotImplementedError(
            "NDFC security group support planned for future release"
        )

    def update_security_group(self, sg_id, rules):
        """Update security group policy."""
        raise NotImplementedError(
            "NDFC security group support planned for future release"
        )

    def del_security_group(self, sg_id):
        """Delete security group policy."""
        raise NotImplementedError(
            "NDFC security group support planned for future release"
        )

    def bind_security_group(self, sg_id, port):
        """Bind security group to port."""
        raise NotImplementedError(
            "NDFC security group support planned for future release"
        )

    def unbind_security_group(self, sg_id, port):
        """Unbind security group from port."""
        raise NotImplementedError(
            "NDFC security group support planned for future release"
        )
