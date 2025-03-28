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
* Cumulus Linux (via NVUE)
* Dell Force10 (netmiko_dell_force10)
* Dell OS10 (netmiko_dell_os10)
* Dell PowerConnect
* HPE 5900 Series switches
* Huawei switches
* Juniper Junos OS switches
* OpenVSwitch
* Ruijie switches
* SONiC switches
* Supermicro switches

This Mechanism Driver architecture allows easily to add more devices
of any type.

::

  OpenStack Neutron v2.0 => ML2 plugin => Generic Mechanism Driver => Device plugin

These device plugins use `Netmiko <https://github.com/ktbyers/netmiko>`_
library, which in turn uses `Paramiko` library to access and configure
the switches via the SSH protocol.

Cisco Nexus (netmiko_cisco_nxos)
--------------------------------

Known working firmware versions: 10.3.7

Notes:

 * Default state for switches is well suited for networking-generic-switch
   as long as SSH is utilized *and* the underlying role provided to the
   account permits configuration of switchports.
 * Pre-configuration of upstream network trunk ports to the neutron networking
   nodes is advisable, however the ``ngs_trunk_ports`` setting should be
   suitable for most users as well.
 * Use of an "enable" secret through the ``secret`` configuration option has
   not been tested.

Dell Force10 OS9 (netmiko_dell_force10)
---------------------------------------

Known working firmware versions: 9.13.0.0

Notes:

 * Dell Force10 Simulator for 9.13.0 lacks the ability to set a switchport
   mode to trunk, which prevents automated or even semi-automated testing.
   That being said, creating VLANs and tagging/untagging works as expected.
 * Uplink switchports to the rest of the network fabric must be configured in
   advance if the ``ngs_trunk_ports`` switch device level configuration
   option is *not* utilized.
 * Use of SSH is expected and must be configured on the remote switch.
 * Set each port to "switchport" to enable L2 switchport mode.
 * Use of an "enable" secret through the switch level configuration option
   ``secret`` was the tested path. Depending on precise switch configuration
   and access control modeling, it may be possible to use without an enable
   secret, but that has not been tested.

Known Issues:

 * `bug 2100641 <https://bugs.launchpad.net/ironic/+bug/2100641>`_ is
   alieviated by setting a port to "switchport" *before* attempting to utilize
   networking-generic-switch.

Dell Force10 OS10 (netmiko_dell_os10)
-------------------------------------

Known working firmware version: 10.6.0.2.74

Notes:

 * Uplink switchports may need to be configured as Trunk ports prior to the
   use of networking-generic-switch through a "switchport mode trunk" command.
   Further specific trunk configuration may be necessary, however NGS can
   leverage the ``ngs_trunk_ports`` configuration option and does appropriately
   tag switchports as permitted when creating/deleting attachments.
 * Password authentication for networking-generic-switch needs to be setup in
   advance, specifically "ip ssh server enable" and
   "ip ssh server password-authentication" commands.
 * This driver was tested *without* the use of an enable secret to
   permit a higher level of configuration access within the Switch.

Sonic - Community Distribution (netmiko_sonic)
----------------------------------------------

Known working firmware version: master branch - March 2025

Notes:

 * The driver expects to be able to SSH into the switch running
   SONiC, execute sudo, and then execute configuration commands.
 * Ports *must* be in Layer-2 mode. As such,
   ``sudo config interface ip remove $INTERFACE $IP_ADDRESS/$CIDR``
   and ``sudo config switchport mode access $INTERFACE`` commands
   may be required.
 * Uplink switch ports should be configured in advance with the
   ``sudo config switchport mode trunk $INTERFACE`` command.
   Testing for the configuraiton utilized this advanced state
   configuration of the trunk uplink ports with the ``ngs_trunk_ports``
   configuration option for Networking-Generic-Switch.
