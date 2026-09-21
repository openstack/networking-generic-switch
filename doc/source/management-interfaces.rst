.. _management-interfaces:

=====================
Management Interfaces
=====================

Networking-generic-switch supports multiple management interfaces for
configuring network switches. Each interface uses a different protocol and
library to communicate with the device.

SSH/CLI (Netmiko)
=================

The SSH/CLI interface uses `Netmiko <https://github.com/ktbyers/netmiko>`_
(which in turn uses `Paramiko <https://www.paramiko.org/>`_) to open an SSH
session to the switch and execute CLI commands. This is the original and
most widely used management interface.

Configuration commands are defined as class-variable tuples in each device
driver and sent sequentially over the SSH session. See the
:doc:`netmiko-device-commands` page for the full list of CLI commands per
device.

Connection parameters (``ip``, ``port``, ``username``, ``password``,
``secret``, ``key_file``) are passed directly to Netmiko. Any parameter
not prefixed with ``ngs_`` is forwarded to the underlying Netmiko
connection. See `Netmiko documentation
<https://ktbyers.github.io/netmiko/docs/netmiko/index.html>`_ for the
full list of connection options.

For coordination and synchronization of concurrent SSH sessions, see the
:ref:`synchronization` section of the administration guide.

.. _netconf-management-interface:

NETCONF
=======

The NETCONF interface uses `ncclient <https://github.com/ncclient/ncclient>`_
to communicate with switches via the NETCONF protocol
(`RFC 6241 <https://datatracker.ietf.org/doc/html/rfc6241>`_). Configuration
payloads are structured XML documents built from OpenConfig YANG models and
pushed to the device using ``edit-config`` RPCs. See the
:doc:`netconf-device-commands` page for rendered XML examples per device and
operation.

Datastore Selection
-------------------

The driver automatically detects which NETCONF datastore to use based on
the capabilities advertised in the server's hello message:

1. If the switch advertises the ``:candidate`` capability, the driver uses
   the candidate datastore with lock, discard, edit-config, validate,
   confirmed-commit, and commit.
2. If only ``:writable-running`` is available, the driver edits the running
   datastore directly with lock and edit-config.

For details on datastore override and configuration persistence, see
:ref:`netconf-datastore-selection` and :ref:`netconf-persistence` in the
configuration guide.

Confirmed Commit
----------------

When the switch supports the ``:confirmed-commit`` capability, the driver
uses a two-phase commit: first a confirmed commit with a configurable
timeout (default 5 seconds), then a confirming commit. If the confirming
commit never arrives (e.g. the process crashes), the switch automatically
rolls back the candidate configuration after the timeout.

Confirmed commit can be disabled entirely by setting
``ngs_netconf_confirmed_commit`` to ``false``, and the timeout can be tuned
with ``ngs_netconf_confirmed_commit_timeout``. See
:ref:`netconf-specific-options` for details.

.. note::

   Some switches (e.g. Cisco NX-OS) hold their config backend busy for the
   entire confirmed-commit timeout window, blocking other NETCONF sessions
   with ``operation-failed``. If you see frequent retry warnings during
   concurrent operations, reduce the timeout or disable confirmed commit.

Lock Retry
----------

If another NETCONF session holds a lock on the target datastore, or the
device returns ``operation-failed`` (e.g. due to a concurrent confirmed
commit), the driver retries with exponential back-off (2 s, 4 s, 5 s,
5 s, ..., up to 10 attempts). This handles transient lock contention from
concurrent Neutron threads or other management sessions.

Coordination
------------

The NETCONF driver uses the same ``PoolLock`` coordination mechanism as the
Netmiko drivers. Configure the coordination backend and
``ngs_max_connections`` as described in the :ref:`synchronization` section
of the administration guide.

ncclient Connection Options
---------------------------

These options are passed directly to ``ncclient.manager.connect()`` and do
**not** use the ``ngs_`` prefix:

.. list-table::
   :header-rows: 1
   :widths: 25 15 60

   * - Option
     - Default
     - Description
   * - ``host``
     - *(required)*
     - Hostname or IP address of the switch NETCONF subsystem.
   * - ``port``
     - ``830``
     - NETCONF TCP port.
   * - ``username``
     - *(required)*
     - SSH username for NETCONF authentication.
   * - ``password``
     -
     - SSH password. Either ``password`` or ``key_filename`` must be
       provided.
   * - ``key_filename``
     -
     - Path to an SSH private key file for key-based authentication.
   * - ``hostkey_verify``
     - ``true``
     - Whether to verify the switch's SSH host key. Set to ``false`` in
       lab environments where host keys are not managed.
   * - ``device_params``
     - ``name:default``
     - ncclient device handler. Format is ``name:<handler>`` (e.g.
       ``name:nexus`` for Cisco NX-OS or ``name:junos`` for Juniper).
       See `ncclient documentation
       <https://ncclient.readthedocs.io/en/latest/>`_ for available
       handlers.
   * - ``allow_agent``
     - ``true``
     - Allow use of the local SSH agent for key-based authentication.
   * - ``look_for_keys``
     - ``true``
     - Look for SSH keys in ``~/.ssh/`` if no explicit key is provided.

.. _restconf-management-interface:

RESTCONF
========

The RESTCONF interface uses the `requests <https://requests.readthedocs.io/>`_
library to communicate with switches via the RESTCONF protocol
(`RFC 8040 <https://datatracker.ietf.org/doc/html/rfc8040>`_). Configuration
payloads are structured JSON documents (RFC 7951) built from OpenConfig YANG
models and sent to the device using HTTP PATCH (merge), GET (read), and
DELETE (remove) operations. See the :doc:`restconf-device-commands` page for
rendered JSON examples per device and operation.

RESTCONF is a lightweight alternative to NETCONF for devices that expose an
HTTPS-based management API. It provides the same OpenConfig model coverage
as the NETCONF driver but uses JSON over HTTP instead of XML over SSH.

Transport Overview
------------------

The RESTCONF driver sends configuration to the device as one HTTP PATCH
request per top-level YANG container. Each PATCH targets the container's
own resource URL (e.g.
``https://<host>:<port>/restconf/data/openconfig-interfaces:interfaces``)
and the request body contains only the container's children — the
module-prefixed container name is conveyed by the URL, not repeated in the
body. The body is a JSON document conforming to RFC 7951 encoding rules:

- Nested elements use bare names (e.g. ``interface``, ``config``)
- Augmented elements use module-prefixed names
  (e.g. ``openconfig-if-ethernet:ethernet``)
- Lists become JSON arrays
- Leaf values map to native JSON types (string, number, boolean)

Example PATCH to
``/restconf/data/openconfig-interfaces:interfaces`` setting an interface
to access VLAN 100:

.. code-block:: json

   {
     "interface": [
       {
         "name": "Ethernet1/31",
         "openconfig-if-ethernet:ethernet": {
           "openconfig-vlan:switched-vlan": {
             "config": {
               "interface-mode": "ACCESS",
               "access-vlan": 100
             }
           }
         }
       }
     ]
   }

Retry and Error Handling
------------------------

The RESTCONF driver retries requests that receive transient error responses:

- **HTTP 409 Conflict** — typically caused by concurrent configuration
  changes on the device.
- **HTTP 503 Service Unavailable** — the device is temporarily busy
  (e.g. during an internal commit or restart).
- **Connection errors** — network-level failures.

Retries use exponential back-off (2 s, 4 s, 5 s, ..., up to 10 attempts).
Non-transient errors (4xx other than 409, 5xx other than 503) raise
immediately without retry.

Coordination
------------

The RESTCONF driver uses the same ``PoolLock`` coordination mechanism as the
Netmiko and NETCONF drivers. Configure the coordination backend and
``ngs_max_connections`` as described in the :ref:`synchronization` section
of the administration guide.

RESTCONF vs NETCONF
-------------------

.. list-table::
   :header-rows: 1
   :widths: 30 35 35

   * - Aspect
     - NETCONF
     - RESTCONF
   * - Transport
     - SSH (port 830)
     - HTTPS (port 443)
   * - Encoding
     - XML
     - JSON (RFC 7951)
   * - Library
     - ncclient
     - requests
   * - Locking
     - Protocol-level lock/unlock
     - Coordination backend (Tooz)
   * - Atomic commit
     - Candidate + commit
     - Per-request PATCH (merge)
   * - Confirmed commit
     - Supported
     - Not applicable
   * - Operation mapping
     - edit-config with operation attributes
     - HTTP methods (PATCH, PUT, DELETE)

Choose RESTCONF when:

- The device does not support NETCONF or has a more mature RESTCONF
  implementation.
- You prefer JSON-based configuration for debugging and automation.
- The device's NETCONF candidate datastore is unreliable.

Choose NETCONF when:

- You need atomic multi-resource commits (candidate + commit).
- You need confirmed commit with automatic rollback.
- The device has a mature NETCONF implementation with proper locking.

Connection Options
------------------

These options configure the RESTCONF HTTP transport and are documented
in detail at :ref:`restconf-specific-options`.

.. list-table::
   :header-rows: 1
   :widths: 30 15 55

   * - Option
     - Default
     - Description
   * - ``host``
     - *(required)*
     - Hostname or IP address of the switch RESTCONF endpoint.
   * - ``username``
     - *(required)*
     - Username for HTTP Basic authentication.
   * - ``password``
     -
     - Password for HTTP Basic authentication.
   * - ``ngs_restconf_scheme``
     - ``https``
     - URL scheme (``https`` or ``http``).
   * - ``port``
     - ``443``
     - TCP port for the RESTCONF endpoint.
   * - ``ngs_restconf_content_type``
     - ``application/yang-data+json``
     - Media type for Content-Type and Accept headers.
   * - ``ngs_restconf_base_path``
     - ``/restconf/data``
     - Base path for RESTCONF data resources.
   * - ``ngs_verify_ssl``
     - ``True``
     - Whether to verify the server's TLS certificate.
   * - ``ngs_openconfig_network_instance``
     - ``default``
     - OpenConfig network-instance for VLAN management.
   * - ``ngs_port_id_re_sub``
     -
     - JSON regex substitution for port IDs (e.g.
       ``{"pattern": "^Eth", "repl": "Ethernet"}``).
   * - ``ngs_openconfig_disabled_properties``
     -
     - Comma-separated list of properties to omit.
