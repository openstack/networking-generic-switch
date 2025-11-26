================================================
Cisco NDFC (Nexus Dashboard Fabric Controller)
================================================

.. warning::

   **HIGHLY EXPERIMENTAL**: The Cisco NDFC driver is in early development
   and should be considered experimental. It has **NOT** been extensively
   tested in production environments.

   * Modern NDFC API implementation (``/api/v1/manage/*`` endpoints)
   * Stateless operations (always queries NDFC for current state)
   * Uses declarative network attachment model
   * Limited real-world deployment testing

   **Recommendation:** Thorough testing in non-production environments is
   **strongly recommended** before deployment.

The Cisco NDFC driver manages NX-OS switches through NDFC's REST API
instead of direct SSH access. This provides centralized fabric management,
audit trails, and policy-based configuration. NDFC handles all underlying
switch configuration including BGP EVPN, NVE interfaces, and VXLAN data
plane setup.

Prerequisites
=============

* NDFC instance managing your VXLAN BGP EVPN fabric
* NDFC user account with permissions to manage networks and interfaces
* Switches added to NDFC fabric inventory
* For VXLAN: BGP EVPN configured in the fabric template
* Modern NDFC version supporting ``/api/v1/manage/*`` API endpoints

Configuration Parameters
========================

Required:

* ``device_type`` - Must be ``cisco_ndfc``
* ``host`` - NDFC hostname or IP address (the NDFC controller, not the
  managed switch)
* ``username`` - NDFC authentication username
* ``password`` - NDFC authentication password
* ``ndfc_fabric_name`` - NDFC fabric name (default: ``default``)

Switch identification:

The config section name (e.g. ``leaf01`` for ``[genericswitch:leaf01]``) must
match the switch hostname in NDFC. This aligns with the Ironic ``switch_info``
used to route ports to this section.

Optional:

* ``ndfc_switch_serial`` - Explicit switch serial number. When set, skips the
  hostname lookup (minor performance optimization).
* ``ndfc_switch_hostname`` - Override the hostname if it differs from the
  section name (rarely needed).

Optional:

* ``ndfc_network_template`` - Network template (default:
  ``Default_Network_Universal``)
* ``ndfc_vrf`` - VRF name (default: ``default``)
* ``ndfc_interface_policy`` - Interface policy template (default:
  ``int_trunk_host``)
* ``port`` - NDFC HTTPS port (default: ``443``)
* ``ngs_verify_tls`` - Verify the NDFC TLS certificate (default: ``True``)
* ``ndfc_timeout`` - Request timeout in seconds (default: ``30``)
* ``ngs_max_connections`` - Session connection pool size (default: ``1``).
  The requests session is shared across all sections pointing at the same
  NDFC, so this bounds connections per controller, not per switch.

Known Limitations
=================

* Security groups are not currently implemented. Support for NDFC policies
  and contracts is planned for a future release.

Configuration Example
=====================

.. code-block:: ini

   [genericswitch:leaf01]
   device_type = cisco_ndfc
   host = ndfc.example.com
   username = admin
   password = secure_password
   ndfc_fabric_name = prod-vxlan-fabric
   ngs_physical_networks = datacenter1

The section name ``leaf01`` automatically becomes the switch hostname for NDFC
lookups.
