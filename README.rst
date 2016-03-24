Networking-generic-switch Neutron ML2 driver
============================================

This is a Modular Layer 2 `Neutron Mechanism driver
<https://wiki.openstack.org/wiki/Neutron/ML2>`_. The mechanism driver is
responsible for applying configuration information to hardware equipment.
``GenericSwitch`` uses `Netmiko <https://github.com/ktbyers/netmiko>`_ library
as the backend to configure network equipment. It has pluggable mechanism of
adding new SSH-enabled devices support.

.. contents:: Contents:
   :local:

Supported Devices
-----------------
* Cisco IOS switches
* Openvswitch


Configuration
-------------

In order to use this mechnism the generic configuration file needs to be
updated with the appropriate configuration information. Here is an example
of ``/etc/neutron/plugins/ml2/ml2_conf_genericswitch.ini``::

    [genericswitch:sw-hostname]
    device_type = cisco_ios
    username = admin
    password = password
    secret = secret
    ip = <switch mgmt ip address>

Additionally the ``GenericSwitch`` mechanism driver needs to be enabled from
the ml2 config file ``/etc/neutron/plugins/ml2/ml2_conf.ini``::

   [ml2]
   tenant_network_types = vlan
   type_drivers = local,flat,vlan,gre,vxlan
   mechanism_drivers = openvswitch,genericswitch
   ...
   ...
