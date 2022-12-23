=================
Supported Devices
=================

The following devices are supported by this plugin:

* Arista EOS
* ArubaOS-CX switches
* Brocade ICX (FastIron)
* Cisco 300-series switches
* Cisco IOS switches
* Cisco NX-OS switches (Nexus)
* Cumulus Linux (via NCLU)
* Dell Force10
* Dell OS10
* Dell PowerConnect
* HPE 5900 Series switches
* Huawei switches
* Juniper Junos OS switches
* OpenVSwitch
* Ruijie switches
* SONiC switches

This Mechanism Driver architecture allows easily to add more devices
of any type.

::

  OpenStack Neutron v2.0 => ML2 plugin => Generic Mechanism Driver => Device plugin

These device plugins use `Netmiko <https://github.com/ktbyers/netmiko>`_
library, which in turn uses `Paramiko` library to access and configure
the switches via SSH protocol.
