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

..note::

    Switch will be selected by local_link_connection/switch_info
    or ngs_mac_address. So, you can use the switch MAC address to identify
    switches if local_link_connection/switch_info is not set.

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
