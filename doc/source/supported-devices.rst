=================
Supported Devices
=================

The following devices are supported by this plugin:

* Cisco 300-series switches
* Cisco IOS switches
* Huawei switches
* OpenVSwitch
* Arista EOS
* Dell Force10
* Dell PowerConnect
* Brocade ICX (FastIron)
* Ruijie switches
* HPE 5900 Series switches
* Juniper Junos OS switches

This Mechanism Driver architecture allows easily to add more devices
of any type.

::

  OpenStack Neutron v2.0 => ML2 plugin => Generic Mechanism Driver => Device plugin

These device plugins use `Netmiko <https://github.com/ktbyers/netmiko>`_
library, which in turn uses `Paramiko` library to access and configure
the switches via SSH protocol.
