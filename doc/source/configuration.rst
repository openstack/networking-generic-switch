=============
Configuration
=============

In order to use this mechanism driver the Neutron configuration file needs to
be created/updated with the appropriate configuration information.

Switch configuration format::

    [genericswitch:<switch name>]
    device_type = <netmiko device type>
    ngs_mac_address = <switch mac address>
    ip = <IP address of switch>
    port = <ssh port>
    username = <credential username>
    password = <credential password>
    use_keys = <set to True when key_file is set>
    key_file = <ssh key file>
    secret = <enable secret>
    ngs_allowed_vlans = <comma-separated list of allowed vlans for switch>
    ngs_allowed_ports = <comma-separated list of allowed ports for switch>

    # If set ngs_port_default_vlan to default_vlan, switch's
    # interface will restore the default_vlan.
    ngs_port_default_vlan = <port default vlan>

The ``device_type`` entry is mandatory.  Most other configuration entries
are optional, see below.

The two new optional configuration parameters ``ngs_allowed_vlans`` and
``ngs_allowed_ports`` have been introduced to manage allowed VLANs and ports
on switches. If not set, all ports or VLANS are allowed.

.. note::

    Switch will be selected by local_link_connection/switch_info
    or ngs_mac_address. So, you can use the switch MAC address to identify
    switches if local_link_connection/switch_info is not set.

Examples
========

These example device configuration snippets are assumed to be part to a
specific file ``/etc/neutron/plugins/ml2/ml2_conf_genericswitch.ini``, but
they could also be added directly to ``/etc/neutron/plugins/ml2/ml2_conf.ini``.

Here is an example for the Cisco 300 series device::

    [genericswitch:sw-hostname]
    device_type = netmiko_cisco_s300
    ngs_mac_address = <switch mac address>
    username = admin
    password = password
    ip = <switch mgmt ip address>

for the Cisco IOS device::

    [genericswitch:sw-hostname]
    device_type = netmiko_cisco_ios
    ngs_mac_address = <switch mac address>
    username = admin
    password = password
    secret = secret
    ip = <switch mgmt ip address>

for the Cisco NX-OS device::

    [genericswitch:sw-hostname]
    device_type = netmiko_cisco_nxos
    ngs_mac_address = <switch mac address>
    # if security group support is required
    ngs_security_groups_enabled = True
    ip = <switch mgmt ip address>
    username = admin
    password = password
    secret = secret

for the Huawei VRPV3 or VRPV5 device::

    [genericswitch:sw-hostname]
    device_type = netmiko_huawei
    ngs_mac_address = <switch mac address>
    username = admin
    password = password
    port = 8222
    secret = secret
    ip = <switch mgmt ip address>

for the Huawei VRPV8 device::

    [genericswitch:sw-hostname]
    device_type = netmiko_huawei_vrpv8
    ngs_mac_address = <switch mac address>
    username = admin
    password = password
    port = 8222
    secret = secret
    ip = <switch mgmt ip address>

for the Arista EOS device::

    [genericswitch:arista-hostname]
    device_type = netmiko_arista_eos
    ngs_mac_address = <switch mac address>
    ip = <switch mgmt ip address>
    username = admin
    key_file = /opt/data/arista_key

for the Dell Force10 device::

    [genericswitch:dell-hostname]
    device_type = netmiko_dell_force10
    ngs_mac_address = <switch mac address>
    ip = <switch mgmt ip address>
    username = admin
    password = password
    secret = secret

for the Dell OS10 device::

    [genericswitch:dell-hostname]
    device_type = netmiko_dell_os10
    ngs_mac_address = <switch mac address>
    ip = <switch mgmt ip address>
    username = admin
    password = password
    secret = secret

for the Dell PowerConnect device::

    [genericswitch:dell-hostname]
    device_type = netmiko_dell_powerconnect
    ip = <switch mgmt ip address>
    username = admin
    password = password
    secret = secret

    # You can set ngs_switchport_mode according to switchmode you have set on
    # the switch. The following options are supported: general, access. It
    # will default to access mode if left unset. In general mode, the port
    # be set to transmit untagged packets.
    ngs_switchport_mode = access

Dell PowerConnect devices have been seen to have issues with multiple
concurrent configuration sessions. See :ref:`synchronization` and
:ref:`batching` for details on how to limit the number of concurrent active
connections to each device.

for the Brocade FastIron (ICX) device::

    [genericswitch:hostname-for-fast-iron]
    device_type = netmiko_brocade_fastiron
    ngs_mac_address = <switch mac address>
    ip = <switch mgmt ip address>
    username = admin
    password = password

for the Ruijie device::

    [genericswitch:sw-hostname]
    device_type = netmiko_ruijie
    ngs_mac_address = <switch mac address>
    username = admin
    password = password
    secret = secret
    ip = <switch mgmt ip address>

for the HPE 5900 Series device::

    [genericswitch:sw-hostname]
    device_type = netmiko_hp_comware
    username = admin
    password = password
    ip = <switch mgmt ip address>

for the Juniper Junos OS device::

    [genericswitch:hostname-for-juniper]
    device_type = netmiko_juniper
    ip = <switch mgmt ip address>
    username = admin
    password = password
    ngs_commit_timeout = <optional commit timeout (seconds)>
    ngs_commit_interval = <optional commit interval (seconds)>

for a Cumulus Linux device::

    [genericswitch:hostname-for-cumulus]
    device_type = netmiko_cumulus
    ip = <switch mgmt_ip address>
    username = admin
    password = password
    secret = secret
    ngs_mac_address = <switch mac address>

for a Cumulus NVUE Linux device::

    [genericswitch:hostname-for-cumulus]
    device_type = netmiko_cumulus_nvue
    ip = <switch mgmt_ip address>
    username = admin
    password = password
    secret = secret
    ngs_mac_address = <switch mac address>

for the Nokia SRL series device::

    [genericswitch:sw-hostname]
    device_type = netmiko_nokia_srl
    username = admin
    password = password
    ip = <switch mgmt ip address>

for a Pluribus switch::

    [genericswitch:sw-hostname]
    device_type = netmiko_pluribus
    username = admin
    password = password
    ip = <switch mgmt ip address>

for an ArubaOS-CX switch::

    [genericswitch:aruba-hostname]
    device_type = netmiko_aruba_aoscx
    username = admin
    password = password
    ip = <switch mgmt ip address>

for the Supermicro device::

    [genericswitch:sw-hostname]
    device_type = netmiko_supermicro_smis
    ngs_mac_address = <switch mac address>
    ip = <switch mgmt ip address>
    username = admin
    password = password
    secret = secret

General configuration
=====================

Additionally the ``GenericSwitch`` mechanism driver needs to be enabled from
the ml2 config file ``/etc/neutron/plugins/ml2/ml2_conf.ini``::

   [ml2]
   tenant_network_types = vlan
   type_drivers = local,flat,vlan,gre,vxlan
   mechanism_drivers = openvswitch,genericswitch
   ...

Physical networks need to be declared in the ML2 config as well, with a range
of VLANs that can be allocated to tenant networks.  Several physical networks
can coexist, possibly with overlapping VLAN ranges: in that case, each switch
configuration needs to include its physical network, see :ref:`physicalnetworks`.
Example of ``/etc/neutron/plugins/ml2/ml2_conf.ini`` with two physical networks::

   [ml2_type_vlan]
   network_vlan_ranges = physnet1:700:799,physnet2:600:850

For a given physical network, it is possible to specify several disjoint
ranges of VLANs by simply repeating the physical network name multiple times::

   [ml2_type_vlan]
   network_vlan_ranges = physnet1:700:720,physnet1:750:760

If drivers support security groups then ``genericswitch_security_group`` can be appended
to the list of ``service_plugins`` (this also needs to be enabled per switch configuration)::

    [DEFAULT]
    service_plugins = qos,ovn-router,trunk,segments,port_forwarding,log,genericswitch_security_group

(Re)start ``neutron-server`` specifying the additional configuration file
containing switch configuration::

    neutron-server \
        --config-file /etc/neutron/neutron.conf \
        --config-file /etc/neutron/plugins/ml2/ml2_conf.ini \
        --config-file /etc/neutron/plugins/ml2/ml2_conf_genericswitch.ini

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

The Cisco Nexus implementation is production-ready and fully tested.

Switch prerequisites:

* VXLAN and NV overlay features must be enabled
* Switch must be configured as a VTEP (VXLAN Tunnel Endpoint)

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

The Cisco NX-OS driver uses BGP EVPN with ingress-replication for all VXLAN
deployments. This approach aligns with Cisco best practices and avoids
multicast group scaling issues that occur with Neutron's dynamic VNI
assignment model.

Configuration parameters:

* ``ngs_nve_interface`` - NVE interface name (default: ``nve1``)

Configuration Example:

.. code-block:: ini

   [genericswitch:leaf01]
   device_type = netmiko_cisco_nxos
   ip = 192.0.2.10
   username = admin
   password = password
   ngs_physical_networks = datacenter1,datacenter2

   # NVE interface (optional, default: nve1)
   ngs_nve_interface = nve1

Prerequisites
^^^^^^^^^^^^^

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

Generated Configuration
^^^^^^^^^^^^^^^^^^^^^^^

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

The driver handles both configuration and cleanup automatically based on
port binding operations. VNI mappings are only removed when the last port
is unplugged from a VLAN.

**SONiC** - Full L2VNI support
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The SONiC implementation uses BGP EVPN with ingress-replication for BUM
(Broadcast, Unknown unicast, Multicast) traffic handling. This approach
relies on EVPN Type-3 IMET routes for dynamic VTEP discovery and avoids
the scaling issues associated with static flood lists.

SONiC Configuration Parameters
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

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

The Arista EOS implementation uses BGP EVPN with ingress-replication for all
VXLAN deployments. This approach aligns with Arista best practices and avoids
multicast group scaling issues that occur with Neutron's dynamic VNI
assignment model.

Arista EOS Configuration Parameters
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Configuration parameters:

* ``vxlan_interface`` - VXLAN interface name (default: ``Vxlan1``)
* ``ngs_bgp_asn`` - BGP AS number (required)

Configuration Example:

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

Prerequisites
^^^^^^^^^^^^^

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

Generated Configuration
^^^^^^^^^^^^^^^^^^^^^^^

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

The driver handles both configuration and cleanup automatically based on
port binding operations. VNI mappings are only removed when the last port
is unplugged from a VLAN.

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

**Cisco IOS** - Not supported
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Classic Cisco IOS does not support VXLAN. VXLAN is only available in NX-OS
and IOS-XE (Catalyst 9000 series and newer).

**Dell OS10** - Not supported

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
