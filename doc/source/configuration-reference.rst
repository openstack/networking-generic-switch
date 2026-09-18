.. _configuration-reference:

===============================
Configuration Options Reference
===============================

This page lists every per-switch ``ngs_`` option, generated directly from
the option definitions in the source code. Each option is set in a
``[genericswitch:<switch name>]`` section of the switch configuration file.

For usage guidance, examples and vendor-specific notes, see
:doc:`configuration`.

Common options
==============

These options apply to all device drivers.

.. ngs-config-options:: networking_generic_switch.devices.NGS_INTERNAL_OPTS

Juniper (Netmiko) options
=========================

Additional options accepted by the ``netmiko_juniper`` device type.

.. ngs-config-options:: networking_generic_switch.devices.netmiko_devices.juniper.JUNIPER_INTERNAL_OPTS

Open vSwitch options
====================

Additional options accepted by the ``netmiko_ovs_linux`` device type.

.. ngs-config-options:: networking_generic_switch.devices.netmiko_devices.ovs.OVS_INTERNAL_OPTS
