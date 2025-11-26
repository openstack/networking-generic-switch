===================
VXLAN L2VNI Support
===================

Networking Generic Switch supports VXLAN Layer 2 VNI (L2VNI) configurations
for hierarchical port binding scenarios. This enables VXLAN overlay networks
with local VLAN mappings on each switch.

Overview
========

In VXLAN L2VNI scenarios:

* Neutron creates a VXLAN network (top segment) with a VNI (VXLAN Network
  Identifier)
* Each switch gets a dynamically allocated local VLAN (bottom segment)
* The driver maps the local VLAN to the global VNI on the switch fabric

This allows multiple switches to participate in the same VXLAN network using
their own local VLAN IDs, which are mapped to a common VNI for overlay traffic.

How It Works
============

When a baremetal port binds to a VXLAN network:

1. Neutron allocates a local VLAN for the switch
2. The driver configures the VNI-to-VLAN mapping on the switch
3. The port is added to the local VLAN
4. VXLAN encapsulation/decapsulation happens at the switch VTEP

When the last port is removed from a VLAN:

1. The port is removed from the VLAN
2. The driver checks if other ports remain on the VLAN
3. If empty, the VNI-to-VLAN mapping is automatically removed
4. The VLAN itself is removed by normal cleanup

Idempotency and Safety
------------------------

The L2VNI implementation includes several safety mechanisms:

* **Idempotency**: VNI mappings are only configured once, even when multiple
  ports bind to the same network
* **Reference checking**: VNI mappings are only removed when the last port
  is unplugged, verified by querying the switch
* **Graceful degradation**: Switches without L2VNI support log warnings but
  don't fail port binding
* **No locks on queries**: Read-only operations don't acquire locks for
  better performance

BUM Traffic Replication
========================

Control Plane vs Data Plane
-----------------------------

BGP EVPN serves as the control plane for MAC/IP address learning in all
modes. Type-2 routes advertise MAC addresses and IP bindings, allowing
switches to learn remote addresses without flooding.

The data plane handles BUM (Broadcast, Unknown unicast, Multicast) traffic
replication. Three modes are available, depending on the switch platform:

* **Ingress-replication**: BGP EVPN Type-3 IMET routes discover remote
  VTEPs; the head-end switch replicates BUM traffic to each VTEP
* **Multicast**: PIM multicast groups replicate BUM traffic through the
  network
* **Head-end-replication** (Cumulus only): Static VTEP lists for
  replication

Choosing a BUM Replication Mode
---------------------------------

**Use Ingress-Replication (default) when:**

* Simplicity is preferred - no PIM configuration required
* You have a small to medium-sized fabric
* Your switches have sufficient CPU for head-end replication
* You want to minimize infrastructure dependencies

**Use Multicast when:**

* You have an existing BGP EVPN VXLAN fabric with PIM already deployed
* You have a large-scale fabric with many endpoints
* Network-based replication (PIM) is preferred over head-end replication
* Your organization's standard is to use multicast for BUM traffic

**Use Head-End-Replication (Cumulus only) when:**

* You have a static list of VTEPs
* You don't want to run BGP EVPN
* You have a simple topology with few VTEPs

Multicast Group Assignment
----------------------------

For platforms that support multicast mode, the driver provides two methods
for assigning multicast groups to VNIs:

1. **Explicit mapping** (via ``ngs_mcast_group_map``): Pre-existing
   VNI-to-group assignments specified as comma-separated pairs. This is
   checked first.

2. **Automatic derivation** (via ``ngs_mcast_group_base``): For unmapped
   VNIs, calculated as ``ngs_mcast_group_base + (VNI % 256)``.

**Example:** With ``ngs_mcast_group_base = 239.1.1.0`` and VNI 10100:

``239.1.1.0 + (10100 % 256) = 239.1.1.0 + 116 = 239.1.1.116``

If a VNI is in the explicit map (e.g.,
``ngs_mcast_group_map = 10100:239.5.5.5``), that mapping takes precedence
over automatic derivation.

Supported Platforms
===================

.. toctree::
   :maxdepth: 1

   cisco-nxos
   cisco-ndfc
   arista-eos
   sonic
   cumulus-nvue
   juniper-junos

Unsupported Platforms
=====================

**OpenVSwitch (OVS)** - CI/Testing Only

.. warning::

   The OVS implementation does NOT configure actual VXLAN tunnels.
   It is designed exclusively for CI and testing purposes to
   exercise the hierarchical port binding workflow and L2VNI
   cleanup logic without requiring physical hardware switches.

The OVS implementation uses bridge external_ids to store
VNI-to-VLAN mappings as metadata, allowing the driver to track
and clean up VNI associations using the same logic as physical
switches.

.. code-block:: ini

   [genericswitch:ovs-switch]
   device_type = netmiko_ovs_linux
   ngs_ovs_bridge = genericswitch

The ``ngs_ovs_bridge`` parameter specifies the OVS bridge name
to use for VNI mapping storage. Defaults to ``genericswitch``.
Common values include ``brbm`` (Ironic CI) or ``genericswitch``
(devstack plugin).

For production VXLAN deployments, use physical switch
implementations (Cisco NX-OS, Arista EOS, SONiC, Cumulus NVUE,
or Juniper Junos).

**Cisco IOS** - Not Supported

Classic Cisco IOS does not support VXLAN. VXLAN is only available
in NX-OS and IOS-XE (Catalyst 9000 series and newer).

**Dell OS10** - Not Supported

Dell OS10 uses a different VXLAN configuration model that requires
a separate virtual-network ID (vn-id) as an intermediate
abstraction between VLANs and VNIs. This virtual-network model
requires independent numbering (vn-id 1-65535) that cannot be
automatically derived from the VLAN segmentation ID. The
configuration workflow (create virtual-network, assign vxlan-vni,
associate member interfaces) is incompatible with the direct
VLAN-to-VNI mapping model used by this driver.

Neutron Configuration
=====================

VXLAN L2VNI support requires the ``baremetal-l2vni`` mechanism
driver from the `networking-baremetal
<https://docs.openstack.org/networking-baremetal/latest/>`__
project. This driver handles hierarchical port binding, allocating
local VLAN segments that are mapped to VXLAN VNIs on the switch
fabric by networking-generic-switch.

For detailed Neutron ML2 configuration, mechanism driver ordering,
VLAN range planning, and deployment guidance, refer to the
`Ironic VXLAN Networking guide
<https://docs.openstack.org/ironic/latest/admin/vxlan.html>`__.
