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
    device_type = netmiko_hpe_comware
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

