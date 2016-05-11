############################################
Networking-generic-switch Neutron ML2 driver
############################################

This is a Modular Layer 2 `Neutron Mechanism driver
<https://wiki.openstack.org/wiki/Neutron/ML2>`_. The mechanism driver is
responsible for applying configuration information to hardware equipment.
``GenericSwitch`` provides a pluggable framework to implement
functionality required for use-cases like OpenStack Ironic multi-tenancy mode.
It abstracts applying changes to all switches managed by this ML2 plugin
and handling ``local_link_information`` field of Neutron port.

* Code: http://git.openstack.org/cgit/openstack/networking-generic-switch
* Bugs: https://bugs.launchpad.net/networking-generic-switch
* Docs: TBD


.. contents:: Contents:
   :local:


Supported Devices
=================

* Cisco IOS switches
* Huawei switches
* OpenVSwitch
* Arista EOS

This Mechanism Driver architecture allows easily to add more devices
of any type.

::

  OpenStack Neutron v2.0 => ML2 plugin => Generic Mechanism Driver => Device plugin


As example plugins, Cisco IOS and Linux OpenVSwitch are provided.
These device plugins use `Netmiko <https://github.com/ktbyers/netmiko>`_
library, which in turn uses `Paramiko` library to access and configure
the switches via SSH protocol.


Configuration
=============

In order to use this mechanism the generic configuration file needs to be
created/updated with the appropriate configuration information.

Switch configuration format::

    [genericswitch:<switch name>]
    device_type = <netmiko device type>
    ip = <IP address of switch>
    port = <ssh port>
    username = <credential username>
    password = <credential password>
    key_file = <ssh key file>
    secret = <enable secret>

Here is an example of
``/etc/neutron/plugins/ml2/ml2_conf_genericswitch.ini``
for the Cisco IOS device::

    [genericswitch:sw-hostname]
    device_type = netmiko_cisco_ios
    username = admin
    password = password
    secret = secret
    ip = <switch mgmt ip address>

for the Huawei device::

    [genericswitch:sw-hostname]
    device_type = netmiko_huawei
    username = admin
    password = password
    port = 8222
    secret = secret
    ip = <switch mgmt ip address>

for the Arista EOS device::

    [genericswitch:arista-hostname]
    device_type = netmiko_arista_eos
    ip = <switch mgmt ip address>
    username = admin
    key_file = /opt/data/arista_key

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

