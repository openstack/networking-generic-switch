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
    key_file = <ssh key file>
    secret = <enable secret>

    # If set ngs_port_default_vlan to default_vlan, switch's
    # interface will restore the default_vlan.
    ngs_port_default_vlan = <port default vlan>

The ``device_type`` entry is mandatory.  Most other configuration entries
are optional, see below.

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
    device_type = netmiko_aruba_os
    username = admin
    password = password
    ip = <switch mgmt ip address>

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

This is currently supported by the following devices:

* Juniper Junos OS
* ArubaOS-CX
* Cisco NX-OS

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
