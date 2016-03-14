#########################################
Contributing to Networking-generic-switch
#########################################

If you're interested in contributing to the GenericSwitch project,
the following will help get you started.


Contributor License Agreement
=============================

.. index::
   single: license; agreement

In order to contribute to the GenericSwitch project, you need to have
signed OpenStack's contributor's agreement.

.. seealso::

   * http://docs.openstack.org/infra/manual/developers.html
   * http://wiki.openstack.org/CLA


LaunchPad Project
=================

Most of the tools used for OpenStack depend on a launchpad.net ID for
authentication.

.. seealso::

   * https://launchpad.net
   * https://launchpad.net/networking-generic-switch


Related Projects
================

   * https://launchpad.net/neutron
   * https://launchpad.net/ironic


Project Hosting Details
=======================

Bug tracker
    http://launchpad.net/networking-generic-switch

Code Hosting
    https://git.openstack.org/cgit/openstack/networking-generic-switch

Code Review
    https://review.openstack.org/#/q/status:open+project:openstack/networking-generic-switch,n,z


Creating new device plugins
===========================

#. Subclass the abstract class
   ``networking_generic_switch.devices.GenericSwitch``
   and implement all the abstract methods it defines.

   * Your class must accept a single argument for instantiation -
      a dictionary with all fields given in the device config section
      of the ML2 plugin config.
      This will be available as ``self.config`` in the instantiated object.

#. Register your class under ``generic_switch.devices`` entrypoint.
#. Add your device config to the plugin configuration file
   (``/etc/neutron/plugins/ml2/ml2_conf_genericswitch.ini`` by default).
   The only required option is ``device_type`` that must be equal to the
   entrypoint you have registered your plugin under, as it is used for plugin
   lookup (see provided ``Netmiko``-based plugins for example).
