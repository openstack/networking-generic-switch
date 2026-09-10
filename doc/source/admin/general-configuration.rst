======================
General Configuration
======================

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

Port Carrier Bounce
===================

When a port is bound (VLAN and MTU configured), the physical host has no way
to detect that the port configuration changed because the line carrier stays
up. This means the host OS will not re-trigger DHCP, resulting in stale
network configurations on baremetal hosts.

The ``ngs_bounce_ports_on_plug`` option causes the port to be shut down before
VLAN/MTU configuration and brought back up after, creating a carrier
drop/raise that signals the host to re-run DHCP. Ports remain UP when not
bound, preserving LLDP and other discovery mechanisms::

    [genericswitch:device-hostname]
    ngs_bounce_ports_on_plug = True

When combined with ``ngs_disable_inactive_ports``, the port is already
admin-down from a prior unbind so the disable step is skipped, but the port
is still enabled after configuration is applied.

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

MTU Management
==============

By default, no MTU management is performed on switch ports. In environments
where different networks require different MTU settings (e.g. jumbo frames on
some networks, standard 1500-byte MTU on others), this can cause frame size
mismatches and silent packet drops.

Networking Generic Switch can optionally propagate the MTU from Neutron
networks to the physical switch ports. MTU management must be explicitly
enabled on a per-device basis by setting ``ngs_manage_mtu`` to ``True``.
When disabled (the default), no MTU commands are sent to the switch,
preserving backward-compatible behavior::

    [genericswitch:device-hostname]
    ngs_manage_mtu = True

``ngs_port_default_mtu`` sets the default MTU for access (bound) ports. This
value is used as a fallback when the network object does not specify an MTU,
and to reset the port MTU when a port is unbound. When used as a Neutron ML2
mechanism driver, all networks include an MTU value (Neutron's database enforces
a non-nullable default of 1500), but this fallback is useful for standalone
usage or when directly invoking the driver::

    [genericswitch:device-hostname]
    ngs_port_default_mtu = 1500

``ngs_trunk_port_mtu`` sets the MTU on trunk (uplink) ports when VLANs are
created. It also serves as the upper bound for access port MTU validation.
If a Neutron network requests an MTU that exceeds this value, port binding
will fail with a ``GenericSwitchMtuExceedError``. If this option is not set,
no trunk port MTU is configured and no upper-bound validation occurs::

    [genericswitch:device-hostname]
    ngs_trunk_port_mtu = 9216

A typical jumbo-frame configuration might look like::

    [genericswitch:leaf-switch-01]
    device_type = netmiko_arista_eos
    ip = 192.0.2.10
    username = admin
    password = password
    ngs_trunk_ports = Ethernet49/1, Ethernet50/1
    ngs_manage_mtu = True
    ngs_port_default_mtu = 1500
    ngs_trunk_port_mtu = 9216

Not all device drivers include MTU command templates. Devices without
MTU command templates will silently skip MTU configuration even when
``ngs_manage_mtu`` is enabled. Refer to the individual driver
documentation or source for per-device support details.

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

.. _neutron-trunk-ports:

Neutron Trunk Ports
===================

When a baremetal port is the parent of a Neutron trunk, subports can be
added and removed dynamically via the trunk API. The parent port's VLAN is
configured as the native (untagged) VLAN on the switch interface, while each
subport carries a ``segmentation_id`` (VLAN) that is tagged on the same
interface.

Some drivers support a converging approach for trunk subport management.
When the mechanism driver has access to the full trunk state (all subports,
not just the delta), it writes the complete set of trunk VLANs in a single
operation. This ensures the switch converges to the desired state regardless
of any intermediate inconsistencies.

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

The ``ngs_ssh_disabled_algorithms`` configuration parameter allows to
selectively disable algorithms of a given type (key exchange, cipher, MAC,
etc). It is based on `Paramiko's disabled_algorithms setting
<https://docs.paramiko.org/en/stable/api/transport.html>`__.

The format is a list of ``<type>:<algorithm>`` entries to disable. The same
type can be repeated several times with different algorithms. Here is an
example configuration::

    [genericswitch:device-hostname]
    ngs_ssh_disabled_algorithms = kex:diffie-hellman-group-exchange-sha1, ciphers:blowfish-cbc, ciphers:3des-cbc

As of Paramiko 2.9.1, the valid types are ``ciphers``, ``macs``, ``keys``,
``pubkeys``, ``kex``, ``gsskex``.  However, this might change depending on
the version of Paramiko. Check Paramiko source code or documentation to
determine the accepted algorithm types.

Advanced Netmiko configuration
==============================

It is sometimes necessary to perform advanced configuration of Netmiko, for
instance to tune connection timeout or other low-level SSH parameters.

Any device configuration parameter that does not start with the ``ngs_``
prefix will be passed directly to Netmiko.  Well-known Netmiko parameters
are passed through a type conversion step to ensure compatibility with
Netmiko.

Here is an example configuration with a float, a boolean and a string::

    [genericswitch:device-hostname]
    conn_timeout = 1.5
    alt_host_keys = True
    alt_key_file = /path/to/host_keys

A list and description of available parameters can be consulted in the
`Netmiko documentation
<https://ktbyers.github.io/netmiko/docs/netmiko/index.html>`__.
