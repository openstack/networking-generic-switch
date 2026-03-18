====================
Administration Guide
====================

This guide covers operational aspects of managing networking-generic-switch
deployments, including performance tuning, advanced features, and
switch-specific configuration scenarios.

.. _synchronization:

Synchronization
===============

Some devices are limited in the number of concurrent SSH sessions that they can
support, or do not support concurrent configuration database updates. In these
cases it can be useful to use an external service to synchronize access to the
managed devices. This synchronization is provided by the `Tooz library
<https://docs.openstack.org/tooz/latest/>`__, which provides support for a
number of different backends, including Etcd, ZooKeeper, and others. A
connection URL for the backend should be configured as follows::

    [ngs_coordination]
    backend_url = <backend URL>

The backend URL format includes the Tooz driver as the scheme, with driver
options passed using query string parameters. For example, to use the
``etcd3gw`` driver with an API version of ``v3`` and a path to a CA
certificate::

    [ngs_coordination]
    backend_url = etcd3+https://etcd.example.com?api_version=v3,ca_cert=/path/to/ca/cert.crt

The default behaviour is to limit the number of concurrent active connections
to each device to one, but the number may be configured per-device as follows::

    [genericswitch:device-hostname]
    ngs_max_connections = <max connections>

When synchronization is used, each Neutron thread executing the
networking-generic-switch plugin will attempt to acquire a lock, with a default
timeout of 60 seconds before failing. This timeout can be configured as follows
(setting it to 0 means no timeout)::

    [ngs_coordination]
    ...
    acquire_timeout = <timeout in seconds>

.. _batching:

Batching
========

For many network devices there is a significant SSH connection overhead which
is incurred for each network or port configuration change. In a large scale
system with many concurrent changes, this overhead adds up quickly. Since the
Antelope release, the Generic Switch driver includes support to batch up switch
configuration changes and apply them together using a single SSH connection.

This is implemented using etcd as a queueing system. Commands are added
to an input key, then a worker thread processes the available commands
for a particular switch device. We pull off the queue using the version
at which the keys were added, giving a FIFO style queue. The result of
each command set are added to an output key, which the original request
thread is watching. Distributed locks are used to serialise the
processing of commands for each switch device.

The etcd endpoint is configured using the same ``[ngs_coordination]
backend_url`` option used in :ref:`synchronization`, with the limitation that
only ``etcd3gw`` is supported.

Additionally, each device that will use batched configuration should include
the following option::

    [genericswitch:device-hostname]
    ngs_batch_requests = True

Disabling Inactive Ports
========================

By default, switch interfaces remain administratively enabled when not in use,
and the access VLAN association is removed. On most devices, this will cause
the interface to be a member of the default VLAN, usually VLAN 1. This could
be a security issue, with unallocated ports having access to a shared network.

To resolve this issue, it is possible to configure interfaces as
administratively down when not in use. This is done on a per-device basis,
using the ``ngs_disable_inactive_ports`` flag::

    [genericswitch:device-hostname]
    ngs_disable_inactive_ports = <optional boolean>

This is currently compatible with the following devices:

.. netmiko-device-commands::
  :output-type: devices-supporting-port-disable

Network Name Format
===================

By default, when a network is created on a switch, if the switch supports
assigning names to VLANs, they are assigned a name of the neutron network UUID.
For example::

    8f60256e4b6343bf873026036606ce5e

It is possible to use a different format for the network name using the
``ngs_network_name_format`` option. This option uses Python string formatting
syntax, and accepts the parameters ``{network_id}`` and ``{segmentation_id}``.
For example::

    [genericswitch:device-hostname]
    ngs_network_name_format = neutron-{network_id}-{segmentation_id}

Some switches have issues assigning VLANs a name that starts with a number,
and this configuration option can be used to avoid this.

.. _manage-vlans:

Manage VLANs
============

By default, on network creation VLANs are added to all switches. In a similar
way, VLANs are removed when it seems they are no longer required.
However, in some cases only a subset of the ports are managed by Neutron.
In a similar way, when multiple switches are used, it is very common that
the network administrator restricts the VLANs allowed. In these cases, there
is little utility in adding and removing vlans on the switches. This process
takes time, so not doing this can speed up a number of common operations.
A particular case where this can cause problems is when a VLAN used for
the switch management interface, or any other port not managed by Neutron,
is removed by this Neutron driver.

To stop networking generic switch trying to add or remove VLANs on the switch,
administrator are expected to pre-add all enabled VLANs as well as tagging
these VLANs on trunk ports.
Once those VLANs and trunk ports are preconfigured on the switch, you can
use the following configuration to stop networking generic switch adding or
removing any VLANs::

    [genericswitch:device-hostname]
    ngs_manage_vlans = False

Saving configuration on devices
===============================

By default, all configuration changes are saved on persistent storage of the
devices, using model-specific commands.  This occurs after each change.

This may be undesirable for performance reasons, or if you have external means
of saving configuration on a regular basis.  In this case, configuration saving
can be disabled::

    [genericswitch:device-hostname]
    ngs_save_configuration = False

Trunk ports
===========

When VLANs are created on the switches, it is common to want to tag these
VLANS on one or more trunk ports.  To do this, you need to declare a
comma-separated list of trunk ports that can be managed by Networking Generic
Switch.  It will then dynamically tag and untag VLANs on these ports whenever
it creates and deletes VLANs.  For example::

    [genericswitch:device-hostname]
    ngs_trunk_ports = Ethernet1/48, Port-channel1

This is useful when managing several switches in the same physical network,
because they are likely to be interconnected with trunk links.
Another important use-case is to connect the DHCP agent with a trunk port,
because the agent needs access to all active VLANs.

Note that this option is only used if ``ngs_manage_vlans = True``.

.. _physicalnetworks:

Multiple physical networks
==========================

It is possible to use Networking Generic Switch to manage several physical
networks.  The desired physical network is selected by the Neutron API client
when it creates the network object.

In this case, you may want to only create VLANs on switches that belong to the
requested physical network, especially because VLAN ranges from separate
physical networks may overlap.  This also improves reconfiguration performance
because fewer switches will need to be configured whenever a network is
created/deleted.

To this end, each switch can be configured with a list of physical networks
it belongs to::

    [genericswitch:device-hostname]
    ngs_physical_networks = physnet1, physnet2

Physical network names should match the names defined in the ML2 configuration.

If no physical network is declared in a switch configuration, then VLANs for
all physical networks will be created on this switch.

Note that this option is only used if ``ngs_manage_vlans = True``.

SSH algorithm configuration
===========================

You may need to tune the SSH negotiation process for some devices.  Reasons
include using a faster key exchange algorithm, disabling an algorithm that
has a buggy implementation on the target device, or working around limitations
related to FIPS requirements.

The ``ngs_ssh_disabled_algorithms`` configuration parameter allows to selectively
disable algorithms of a given type (key exchange, cipher, MAC, etc). It is based
on `Paramiko's disabled_algorithms setting
<https://docs.paramiko.org/en/stable/api/transport.html#paramiko.transport.Transport.__init__>`__.

The format is a list of ``<type>:<algorithm>`` entries to disable. The same type
can be repeated several times with different algorithms. Here is an example configuration::

    [genericswitch:device-hostname]
    ngs_ssh_disabled_algorithms = kex:diffie-hellman-group-exchange-sha1, ciphers:blowfish-cbc, ciphers:3des-cbc

As of Paramiko 2.9.1, the valid types are ``ciphers``, ``macs``, ``keys``, ``pubkeys``,
``kex``, ``gsskex``.  However, this might change depending on the version of Paramiko.
Check Paramiko source code or documentation to determine the accepted algorithm types.

Advanced Netmiko configuration
==============================

It is sometimes necessary to perform advanced configuration of Netmiko, for instance
to tune connection timeout or other low-level SSH parameters.

Any device configuration parameter that does not start with the ``ngs_`` prefix will
be passed directly to Netmiko.  Well-known Netmiko parameters are passed through a
type conversion step to ensure compatibility with Netmiko.

Here is an example configuration with a float, a boolean and a string::

    [genericswitch:device-hostname]
    conn_timeout = 1.5
    alt_host_keys = True
    alt_key_file = /path/to/host_keys

A list and description of available parameters can be consulted in the `Netmiko documentation
<https://ktbyers.github.io/netmiko/docs/netmiko/index.html#netmiko.BaseConnection>`__.

VXLAN L2VNI Support
===================

Networking Generic Switch supports VXLAN Layer 2 VNI (L2VNI) configurations
for hierarchical port binding scenarios. This enables VXLAN overlay networks
with local VLAN mappings on each switch.

Overview
--------

In VXLAN L2VNI scenarios:

* Neutron creates a VXLAN network (top segment) with a VNI (VXLAN Network Identifier)
* Each switch gets a dynamically allocated local VLAN (bottom segment)
* The driver maps the local VLAN to the global VNI on the switch fabric

This allows multiple switches to participate in the same VXLAN network using
their own local VLAN IDs, which are mapped to a common VNI for overlay traffic.

Supported Switches
------------------

**Cisco Nexus (NX-OS)** - Full L2VNI support
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The Cisco Nexus implementation is production-ready and fully tested. It supports
two modes for BUM (Broadcast, Unknown unicast, Multicast) traffic replication:

1. **Ingress-replication** (default) - Uses BGP EVPN for BUM traffic replication
2. **Multicast** - Uses ASM multicast groups with PIM Sparse Mode

Switch prerequisites:

* VXLAN and NV overlay features must be enabled
* Switch must be configured as a VTEP (VXLAN Tunnel Endpoint)
* For multicast mode: PIM Sparse Mode and Anycast RP must be configured

Example Cisco NX-OS switch configuration:

.. code-block:: text

   ! Enable VXLAN features (Cisco NX-OS specific)
   feature vxlan
   feature nv overlay

   ! Configure NVE interface (pre-configured by admin)
   interface nve1
     no shutdown
     source-interface loopback0
     host-reachability protocol bgp

NVE Configuration Parameters
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Configuration parameters:

* ``ngs_nve_interface`` - NVE interface name (default: ``nve1``)
* ``ngs_bum_replication_mode`` - BUM traffic replication mode (default:
  ``ingress-replication``). Options: ``ingress-replication``, ``multicast``
* ``ngs_mcast_group_map`` - Explicit VNI-to-multicast-group mappings as
  comma-separated ``VNI:group`` pairs. Used for pre-existing multicast group
  assignments. Example: ``10100:239.1.1.100, 10200:239.1.1.200``
* ``ngs_mcast_group_base`` - Base ASM multicast group address for automatic
  derivation of unmapped VNIs (optional when ``ngs_mcast_group_map`` is used,
  required otherwise when ``ngs_bum_replication_mode=multicast``).
  Example: ``239.1.1.0``
* ``ngs_mcast_group_increment`` - Multicast group derivation method (default:
  ``vni_last_octet``)

Configuration Example (Ingress-Replication Mode):

.. code-block:: ini

   [genericswitch:leaf01]
   device_type = netmiko_cisco_nxos
   ip = 192.0.2.10
   username = admin
   password = password
   ngs_physical_networks = datacenter1,datacenter2

   # NVE interface (optional, default: nve1)
   ngs_nve_interface = nve1

   # BUM replication mode (optional, default: ingress-replication)
   ngs_bum_replication_mode = ingress-replication

Configuration Example (Multicast Mode):

.. code-block:: ini

   [genericswitch:leaf02]
   device_type = netmiko_cisco_nxos
   ip = 192.0.2.11
   username = admin
   password = password
   ngs_physical_networks = datacenter1,datacenter2

   # BUM replication mode set to multicast
   ngs_bum_replication_mode = multicast

   # Base multicast group (required for multicast mode)
   ngs_mcast_group_base = 239.1.1.0

   # NVE interface (optional, default: nve1)
   ngs_nve_interface = nve1

Configuration Example (Multicast Mode with Explicit VNI Mapping):

.. code-block:: ini

   [genericswitch:leaf03]
   device_type = netmiko_cisco_nxos
   ip = 192.0.2.12
   username = admin
   password = password
   ngs_physical_networks = datacenter1,datacenter2

   # BUM replication mode set to multicast
   ngs_bum_replication_mode = multicast

   # Explicit VNI-to-multicast-group mappings for pre-existing assignments
   ngs_mcast_group_map = 10100:239.1.1.100, 10200:239.1.1.200, 5000:239.2.2.50

   # Optional: Base for automatic derivation of unmapped VNIs
   ngs_mcast_group_base = 239.1.1.0

   # NVE interface (optional, default: nve1)
   ngs_nve_interface = nve1

Prerequisites for Ingress-Replication Mode
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Your Cisco NX-OS switches must have BGP EVPN configured. This is required
for the ingress-replication data plane to function correctly.

Example switch configuration:

.. code-block:: text

   ! Enable required features
   feature bgp
   feature vxlan
   feature nv overlay

   ! Configure BGP EVPN
   router bgp 65000
     neighbor 192.0.2.1 remote-as 65000
     address-family l2vpn evpn
       neighbor 192.0.2.1 activate
       advertise-pip

   ! Configure NVE interface
   interface nve1
     no shutdown
     source-interface loopback0
     host-reachability protocol bgp

Prerequisites for Multicast Mode
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

For multicast mode, in addition to BGP EVPN (used for MAC/IP learning), your
fabric must have PIM Sparse Mode with Anycast RP configured across all switches.

Example switch configuration for multicast mode:

.. code-block:: text

   ! Enable required features
   feature bgp
   feature pim
   feature vxlan
   feature nv overlay

   ! Configure PIM on underlay interfaces
   interface Ethernet1/1-48
     ip pim sparse-mode

   ! Loopback for VTEP
   interface loopback0
     ip address 10.0.0.1/32
     ip pim sparse-mode

   ! Anycast RP configuration (same on all RP switches)
   ip pim rp-address 10.255.255.254 group-list 239.0.0.0/8

   ! Configure Anycast RP set (repeat for each RP)
   ip pim anycast-rp 10.255.255.254 10.0.0.1
   ip pim anycast-rp 10.255.255.254 10.0.0.2

   ! Configure BGP EVPN (still used for MAC/IP learning)
   router bgp 65000
     neighbor 192.0.2.1 remote-as 65000
     address-family l2vpn evpn
       neighbor 192.0.2.1 activate
       advertise-pip

   ! Configure NVE interface
   interface nve1
     no shutdown
     source-interface loopback0
     host-reachability protocol bgp

Generated Configuration
^^^^^^^^^^^^^^^^^^^^^^^

**Ingress-Replication Mode** (default)

For each VXLAN network, the driver automatically configures:

.. code-block:: text

   ! BGP EVPN control plane
   evpn
     vni 10100 l2
     rd auto
     route-target both auto

   ! Data plane with ingress-replication
   vlan 100
     vn-segment 10100
   interface nve1
     member vni 10100
       ingress-replication protocol bgp

**Multicast Mode**

For each VXLAN network with multicast mode enabled, the driver automatically
configures:

.. code-block:: text

   ! BGP EVPN control plane (used for MAC/IP learning)
   evpn
     vni 10100 l2
     rd auto
     route-target both auto

   ! Data plane with multicast group
   vlan 100
     vn-segment 10100
   interface nve1
     member vni 10100
       mcast-group 239.1.1.116

**Multicast Group Assignment**

The driver supports two methods for assigning multicast groups to VNIs:

1. **Explicit mapping** (via ``ngs_mcast_group_map``): Pre-existing VNI-to-group
   assignments are specified as comma-separated pairs. This is checked first.

2. **Automatic derivation** (via ``ngs_mcast_group_base``): For unmapped VNIs,
   the group is calculated as ``ngs_mcast_group_base + (VNI % 256)``.

For example, with ``ngs_mcast_group_base = 239.1.1.0`` and VNI 10100:
``239.1.1.0 + (10100 % 256) = 239.1.1.0 + 116 = 239.1.1.116``

If a VNI is in the explicit map (e.g., ``ngs_mcast_group_map = 10100:239.5.5.5``),
that mapping takes precedence over automatic derivation.

The driver handles both configuration and cleanup automatically based on
port binding operations. VNI mappings are only removed when the last port
is unplugged from a VLAN.

Choosing Between Ingress-Replication and Multicast
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

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

Both modes use BGP EVPN for MAC/IP learning (control plane). The difference
is only in how BUM traffic is replicated (data plane):

* **Ingress-replication**: Head-end switch replicates to each remote VTEP
* **Multicast**: Network (PIM) replicates using multicast groups

**SONiC** - Full L2VNI support
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The SONiC implementation uses BGP EVPN with ingress-replication for BUM
(Broadcast, Unknown unicast, Multicast) traffic handling. This approach
relies on EVPN Type-3 IMET routes for dynamic VTEP discovery and avoids
the scaling issues associated with static flood lists.

SONiC Configuration Parameters
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Configuration parameters:

* ``vtep_name`` - VXLAN tunnel endpoint interface name (required)
* ``ngs_bgp_asn`` - BGP AS number (required)

Configuration Example:

.. code-block:: ini

   [genericswitch:sonic-switch]
   device_type = netmiko_sonic
   ip = 192.0.2.20
   username = admin
   password = password
   ngs_physical_networks = datacenter1,datacenter2

   # VTEP interface name (required)
   vtep_name = vtep

   # BGP AS number (required)
   ngs_bgp_asn = 65000

Generated Configuration
^^^^^^^^^^^^^^^^^^^^^^^

For each VXLAN network, the driver automatically configures:

.. code-block:: text

   # BGP EVPN control plane (via FRR vtysh)
   vtysh -c "configure terminal" \
         -c "router bgp 65000" \
         -c "address-family l2vpn evpn" \
         -c "vni 10100" \
         -c "rd auto" \
         -c "route-target import auto" \
         -c "route-target export auto"

   # VXLAN map
   config vxlan map add vtep 100 10100

Prerequisites
^^^^^^^^^^^^^

Your SONiC switches must have BGP EVPN pre-configured with
``advertise-all-vni`` enabled in FRR.

**Arista EOS** - Full L2VNI support
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The Arista EOS implementation is production-ready and fully tested. It supports
two modes for BUM (Broadcast, Unknown unicast, Multicast) traffic replication:

1. **Ingress-replication** (default) - Uses BGP EVPN for BUM traffic replication
2. **Multicast** - Uses ASM multicast groups with PIM Sparse Mode

Switch prerequisites:

* BGP EVPN must be configured
* VXLAN interface must be configured as a VTEP
* For multicast mode: PIM Sparse Mode and Anycast RP must be configured

Arista EOS Configuration Parameters
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Configuration parameters:

* ``vxlan_interface`` - VXLAN interface name (default: ``Vxlan1``)
* ``ngs_bgp_asn`` - BGP AS number (required)
* ``ngs_evpn_route_target`` - Route-target value (default: ``auto``)
* ``ngs_bum_replication_mode`` - BUM traffic replication mode (default:
  ``ingress-replication``). Options: ``ingress-replication``, ``multicast``
* ``ngs_mcast_group_map`` - Explicit VNI-to-multicast-group mappings as
  comma-separated ``VNI:group`` pairs. Used for pre-existing multicast group
  assignments. Example: ``10100:239.1.1.100, 10200:239.1.1.200``
* ``ngs_mcast_group_base`` - Base ASM multicast group address for automatic
  derivation of unmapped VNIs (optional when ``ngs_mcast_group_map`` is used,
  required otherwise when ``ngs_bum_replication_mode=multicast``).
  Example: ``239.1.1.0``
* ``ngs_mcast_group_increment`` - Multicast group derivation method (default:
  ``vni_last_octet``)

Configuration Example (Ingress-Replication Mode):

.. code-block:: ini

   [genericswitch:arista-switch]
   device_type = netmiko_arista_eos
   ip = 192.0.2.30
   username = admin
   password = password
   ngs_physical_networks = datacenter1,datacenter2

   # VXLAN interface name (optional, default: Vxlan1)
   vxlan_interface = Vxlan1

   # BGP AS number (required)
   ngs_bgp_asn = 65000

   # BUM replication mode (optional, default: ingress-replication)
   ngs_bum_replication_mode = ingress-replication

Configuration Example (Multicast Mode):

.. code-block:: ini

   [genericswitch:arista-leaf02]
   device_type = netmiko_arista_eos
   ip = 192.0.2.31
   username = admin
   password = password
   ngs_physical_networks = datacenter1,datacenter2

   # BUM replication mode set to multicast
   ngs_bum_replication_mode = multicast

   # Base multicast group (required for multicast mode)
   ngs_mcast_group_base = 239.1.1.0

   # VXLAN interface (optional, default: Vxlan1)
   vxlan_interface = Vxlan1

   # BGP AS number (required)
   ngs_bgp_asn = 65000

Configuration Example (Multicast Mode with Explicit VNI Mapping):

.. code-block:: ini

   [genericswitch:arista-leaf03]
   device_type = netmiko_arista_eos
   ip = 192.0.2.32
   username = admin
   password = password
   ngs_physical_networks = datacenter1,datacenter2

   # BUM replication mode set to multicast
   ngs_bum_replication_mode = multicast

   # Explicit VNI-to-multicast-group mappings for pre-existing assignments
   ngs_mcast_group_map = 10100:239.1.1.100, 10200:239.1.1.200, 5000:239.2.2.50

   # Optional: Base for automatic derivation of unmapped VNIs
   ngs_mcast_group_base = 239.1.1.0

   # BGP AS number (required)
   ngs_bgp_asn = 65000

Prerequisites for Ingress-Replication Mode
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Your Arista EOS switches must have BGP EVPN configured. This is required
for the ingress-replication data plane to function correctly.

Example switch configuration:

.. code-block:: text

   ! Configure BGP EVPN
   router bgp 65000
     router-id 10.0.0.1
     neighbor 10.0.0.2 remote-as 65000
     neighbor 10.0.0.2 update-source Loopback0
     address-family evpn
       neighbor 10.0.0.2 activate

   ! Configure VXLAN interface
   interface Vxlan1
     vxlan source-interface Loopback0
     vxlan udp-port 4789

Prerequisites for Multicast Mode
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

For multicast mode, in addition to BGP EVPN (used for MAC/IP learning), your
fabric must have PIM Sparse Mode with Anycast RP configured across all switches.

Example switch configuration for multicast mode:

.. code-block:: text

   ! Configure PIM on underlay interfaces
   interface Ethernet1-48
     ip pim sparse-mode

   ! Loopback for VTEP
   interface Loopback0
     ip address 10.0.0.1/32
     ip pim sparse-mode

   ! Anycast RP configuration (same on all RP switches)
   ip pim rp-address 10.255.255.254 239.0.0.0/8

   ! Configure Anycast RP set (repeat for each RP)
   ip pim anycast-rp 10.255.255.254 10.0.0.1
   ip pim anycast-rp 10.255.255.254 10.0.0.2

   ! Configure BGP EVPN (still used for MAC/IP learning)
   router bgp 65000
     router-id 10.0.0.1
     neighbor 10.0.0.2 remote-as 65000
     neighbor 10.0.0.2 update-source Loopback0
     address-family evpn
       neighbor 10.0.0.2 activate

   ! Configure VXLAN interface
   interface Vxlan1
     vxlan source-interface Loopback0
     vxlan udp-port 4789

Generated Configuration
^^^^^^^^^^^^^^^^^^^^^^^

**Ingress-Replication Mode** (default)

For each VXLAN network, the driver automatically configures:

.. code-block:: text

   ! BGP EVPN control plane
   router bgp 65000
     vlan 100
       rd auto
       route-target both auto

   ! Data plane with ingress-replication
   interface Vxlan1
     vxlan vlan 100 vni 10100

**Multicast Mode**

For each VXLAN network with multicast mode enabled, the driver automatically
configures:

.. code-block:: text

   ! BGP EVPN control plane (used for MAC/IP learning)
   router bgp 65000
     vlan 100
       rd auto
       route-target both auto

   ! Data plane with multicast group
   interface Vxlan1
     vxlan vlan 100 vni 10100
     vxlan vlan 100 flood vtep 239.1.1.116

**Multicast Group Assignment**

The driver supports two methods for assigning multicast groups to VNIs:

1. **Explicit mapping** (via ``ngs_mcast_group_map``): Pre-existing VNI-to-group
   assignments are specified as comma-separated pairs. This is checked first.

2. **Automatic derivation** (via ``ngs_mcast_group_base``): For unmapped VNIs,
   the group is calculated as ``ngs_mcast_group_base + (VNI % 256)``.

For example, with ``ngs_mcast_group_base = 239.1.1.0`` and VNI 10100:
``239.1.1.0 + (10100 % 256) = 239.1.1.0 + 116 = 239.1.1.116``

If a VNI is in the explicit map (e.g., ``ngs_mcast_group_map = 10100:239.5.5.5``),
that mapping takes precedence over automatic derivation.

The driver handles both configuration and cleanup automatically based on
port binding operations. VNI mappings are only removed when the last port
is unplugged from a VLAN.

Choosing Between Ingress-Replication and Multicast
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

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

Both modes use BGP EVPN for MAC/IP learning (control plane). The difference
is only in how BUM traffic is replicated (data plane):

* **Ingress-replication**: Head-end switch replicates to each remote VTEP
* **Multicast**: Network (PIM) replicates using multicast groups

**Cumulus NVUE** - Full L2VNI support
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The Cumulus NVUE implementation supports L2VNI configuration on the default
bridge domain ``br_default``. It includes support for Head-End Replication
(HER) flood lists for BUM traffic handling and EVPN control plane
configuration.

Configuration Parameters
^^^^^^^^^^^^^^^^^^^^^^^^

- ``device_type``: ``netmiko_cumulus_nvue``
- ``ngs_her_flood_list``: Global HER flood list (comma-separated VTEP IPs)
- ``ngs_physnet_her_flood``: Per-physnet HER flood lists (format:
  ``physnet1:ip1,ip2;physnet2:ip3,ip4``)
- ``ngs_evpn_vni_config``: Enable EVPN VNI control plane configuration
  (default: false)
- ``ngs_bgp_asn``: BGP AS number (required when ``ngs_evpn_vni_config`` is
  enabled)

HER Flood List Resolution
^^^^^^^^^^^^^^^^^^^^^^^^^

When configuring HER flood lists, the driver uses a three-tier resolution:

1. Check ``ngs_physnet_her_flood`` for a per-physnet mapping
2. Fall back to ``ngs_her_flood_list`` for a global configuration
3. Default to EVPN-only (no static flood list)

EVPN VNI Control Plane Configuration
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

When ``ngs_evpn_vni_config=true`` and ``ngs_bgp_asn`` is set, the driver
configures per-VNI EVPN in FRRouting (FRR) using vtysh commands:

.. code-block:: bash

   vtysh -c "configure terminal" \
         -c "router bgp <asn>" \
         -c "address-family l2vpn evpn" \
         -c "vni <vni>" \
         -c "rd auto" \
         -c "route-target import auto" \
         -c "route-target export auto"

Configuration Examples
^^^^^^^^^^^^^^^^^^^^^^

**Scenario 1: Basic L2VNI (EVPN-only, no static flood list)**

.. code-block:: ini

   [genericswitch:cumulus-switch]
   device_type = netmiko_cumulus_nvue

Generated commands:

.. code-block:: bash

   nv set bridge domain br_default vlan 100 vni 10100

**Scenario 2: L2VNI with Global HER Flood List**

.. code-block:: ini

   [genericswitch:cumulus-switch]
   device_type = netmiko_cumulus_nvue
   ngs_her_flood_list = 10.0.1.1,10.0.1.2

Generated commands:

.. code-block:: bash

   nv set bridge domain br_default vlan 100 vni 10100
   nv set nve vxlan flooding head-end-replication 10.0.1.1
   nv set nve vxlan flooding head-end-replication 10.0.1.2

**Scenario 3: L2VNI with Per-Physnet HER Flood Lists**

.. code-block:: ini

   [genericswitch:cumulus-switch]
   device_type = netmiko_cumulus_nvue
   ngs_physnet_her_flood = physnet1:10.0.1.1,10.0.1.2;physnet2:10.0.2.1

For physnet1, generated commands:

.. code-block:: bash

   nv set bridge domain br_default vlan 100 vni 10100
   nv set nve vxlan flooding head-end-replication 10.0.1.1
   nv set nve vxlan flooding head-end-replication 10.0.1.2

**Scenario 4: L2VNI with EVPN VNI Configuration**

.. code-block:: ini

   [genericswitch:cumulus-switch]
   device_type = netmiko_cumulus_nvue
   ngs_evpn_vni_config = true
   ngs_bgp_asn = 65000

Generated commands:

.. code-block:: bash

   vtysh -c "configure terminal" \
         -c "router bgp 65000" \
         -c "address-family l2vpn evpn" \
         -c "vni 10100" \
         -c "rd auto" \
         -c "route-target import auto" \
         -c "route-target export auto"
   nv set bridge domain br_default vlan 100 vni 10100

Without ``ngs_evpn_vni_config``, the EVPN block is omitted and only the
VXLAN map configuration is applied.

**Juniper Junos** - Full L2VNI support
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The Juniper Junos implementation supports L2VNI configuration on QFX and EX
series switches with EVPN control plane support. VLANs are referenced by name
(automatically created during network setup), and VNI mappings use the
``vxlan vni`` command.

Configuration Parameters
^^^^^^^^^^^^^^^^^^^^^^^^

- ``device_type``: ``netmiko_juniper``
- ``ngs_evpn_vni_config``: Enable EVPN VRF target configuration (default:
  false)
- ``ngs_bgp_asn``: BGP AS number (required when ``ngs_evpn_vni_config`` is
  enabled)

The driver automatically queries the switch to map VLAN IDs to VLAN names for
VNI configuration.

EVPN VRF Target Configuration
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

When ``ngs_evpn_vni_config=true`` and ``ngs_bgp_asn`` is set, the driver
configures per-VLAN VRF targets for EVPN Type-2 route import/export:

.. code-block:: bash

   set vlans <vlan-name> vrf-target target:<asn>:<vni>

Configuration Examples
^^^^^^^^^^^^^^^^^^^^^^

**Scenario 1: Basic L2VNI (no EVPN VRF target)**

.. code-block:: ini

   [genericswitch:juniper-switch]
   device_type = netmiko_juniper

Generated commands:

.. code-block:: bash

   set vlans vlan100 vxlan vni 10100

**Scenario 2: L2VNI with EVPN VRF Target**

.. code-block:: ini

   [genericswitch:juniper-switch]
   device_type = netmiko_juniper
   ngs_evpn_vni_config = true
   ngs_bgp_asn = 65000

Generated commands:

.. code-block:: bash

   set vlans vlan100 vxlan vni 10100
   set vlans vlan100 vrf-target target:65000:10100

Without ``ngs_evpn_vni_config``, the VRF target configuration is omitted and
only the VXLAN map is applied.

**OpenVSwitch (OVS)** - Not Supported - CI/Testing Only
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. warning::

   **IMPORTANT**: The OVS implementation does NOT configure actual VXLAN
   tunnels. It is designed exclusively for CI and testing purposes to exercise
   the hierarchical port binding workflow and L2VNI cleanup logic without
   requiring physical hardware switches.

The OVS implementation uses bridge external_ids to store VNI-to-VLAN mappings
as metadata, allowing the driver to track and clean up VNI associations using
the same logic as physical switches.

Configuration:

.. code-block:: ini

   [genericswitch:ovs-switch]
   device_type = netmiko_ovs_linux
   ngs_ovs_bridge = genericswitch

The ``ngs_ovs_bridge`` parameter specifies the OVS bridge name to use for VNI
mapping storage. Defaults to ``genericswitch``. Common values include ``brbm``
(Ironic CI) or ``genericswitch`` (devstack plugin).

For production VXLAN deployments, use physical switch implementations (Cisco
NX-OS, Arista EOS, SONiC, Cumulus NVUE, or Juniper Junos).

**Cisco IOS** - Not supported
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Classic Cisco IOS does not support VXLAN. VXLAN is only available in NX-OS
and IOS-XE (Catalyst 9000 series and newer).

**Dell OS10** - Not supported
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Dell OS10 uses a different VXLAN configuration model that requires a separate
virtual-network ID (vn-id) as an intermediate abstraction between VLANs and
VNIs. This virtual-network model requires independent numbering (vn-id 1-65535)
that cannot be automatically derived from the VLAN segmentation ID. The
configuration workflow (create virtual-network → assign vxlan-vni → associate
member interfaces) is incompatible with the direct VLAN-to-VNI mapping model
used by this driver.

How It Works
------------

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
----------------------

The L2VNI implementation includes several safety mechanisms:

* **Idempotency**: VNI mappings are only configured once, even when multiple
  ports bind to the same network
* **Reference checking**: VNI mappings are only removed when the last port
  is unplugged, verified by querying the switch
* **Graceful degradation**: Switches without L2VNI support log warnings but
  don't fail port binding
* **No locks on queries**: Read-only operations don't acquire locks for better
  performance

Cisco Nexus Example
-------------------

For a VXLAN network with VNI 5000 mapped to local VLAN 100, the driver
automatically generates:

.. code-block:: text

   ! BGP EVPN control plane
   evpn
     vni 5000 l2
     rd auto
     route-target both auto

   ! Data plane with ingress-replication
   vlan 100
     vn-segment 5000
   interface nve1
     member vni 5000
       ingress-replication protocol bgp

The driver automatically creates this mapping during port binding and removes
it during cleanup when the last port is unplugged from the VLAN.

Neutron Configuration
---------------------

**Prerequisites**: This feature requires the ``networking-baremetal`` plugin
with the ``baremetal-l2vni`` mechanism driver. The ``baremetal-l2vni`` driver
handles hierarchical port binding (top segment = VXLAN, bottom segment = VLAN)
and allocates local VLAN segments that are mapped to VXLAN VNIs on the switch
fabric.

Install networking-baremetal and configure it in your ML2 configuration:

.. code-block:: ini

   [ml2]
   type_drivers = vlan,vxlan
   tenant_network_types = vxlan
   mechanism_drivers = baremetal_l2vni,genericswitch

   [ml2_type_vxlan]
   vni_ranges = 4001:8000

   [ml2_type_vlan]
   network_vlan_ranges = physnet1:100:200

The ``baremetal-l2vni`` mechanism driver must be listed before
``genericswitch`` in the ``mechanism_drivers`` list to ensure proper
hierarchical port binding.
