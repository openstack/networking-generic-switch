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

.. note::

    Switch will be selected by local_link_connection/switch_info
    or ngs_mac_address. So, you can use the switch MAC address to identify
    switches if local_link_connection/switch_info is not set.

Examples
--------

Here is an example of
``/etc/neutron/plugins/ml2/ml2_conf_genericswitch.ini``
for the Cisco 300 series device::

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
concurrent configuration sessions. See :ref:`synchronization` for details on
how to limit the number of concurrent active connections to each device.

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

Additionally the ``GenericSwitch`` mechanism driver needs to be enabled from
the ml2 config file ``/etc/neutron/plugins/ml2/ml2_conf.ini``::

   [ml2]
   tenant_network_types = vlan
   type_drivers = local,flat,vlan,gre,vxlan
   mechanism_drivers = openvswitch,genericswitch
   ...
   ...

(Re)start ``neutron-server`` specifying this additional configuration file::

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

The default is to limit the number of concurrent active connections to each
device to one, but the number may be configured per-device as follows::

    [genericswitch:device-hostname]
    ngs_max_connections = <max connections>

When synchronization is used, each Neutron thread executing the
networking-generic-switch plugin will attempt to acquire a lock, with a default
timeout of 60 seconds before failing. This timeout can be configured as follows
(setting it to 0 means no timeout)::

    [ngs_coordination]
    ...
    acquire_timeout = <timeout in seconds>

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

To stop networking generic switch trying to add or remove VLANs on the switch
administrator are expected to pre-add all enabled VLANs. Once those VLANs are
preconfigured on the switch, you can use the following configuration to stop
networking generic switch adding or removing any VLANs::

    [genericswitch:device-hostname]
    ngs_manage_vlans = False
