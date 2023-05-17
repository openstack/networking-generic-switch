#########################################
Contributing to Networking-generic-switch
#########################################

If you would like to contribute to the development of GenericSwitch project, you must follow the
general OpenStack community procedures documented at:

   https://docs.openstack.org/infra/manual/developers.html#development-workflow

Pull requests submitted through GitHub will be ignored.

Contributor License Agreement
=============================

.. index::
   single: license; agreement

In order to contribute to the GenericSwitch project, you need to have
signed OpenStack's contributor's agreement.

.. seealso::

   * https://docs.openstack.org/infra/manual/developers.html
   * https://wiki.openstack.org/CLA

Related Projects
================

   * https://docs.openstack.org/neutron/latest
   * https://docs.openstack.org/ironic/latest


Project Hosting Details
=======================

Bug tracker
    https://bugs.launchpad.net/networking-generic-switch

Code Hosting
    https://opendev.org/openstack/networking-generic-switch

Code Review
    https://review.opendev.org/#/q/status:open+project:openstack/networking-generic-switch,n,z


Creating new device plugins
===========================

#. Subclass the abstract class
   ``networking_generic_switch.devices.GenericSwitch``
   and implement all the abstract methods it defines.

   * Your class must accept as first argument a dictionary that contains
     all fields given in the device config section of the ML2 plugin config.
     This will be available as ``self.config`` in the instantiated object.
     The second argument is the device name as specified in the configuration.
     It is recommended to accept and pass ``*args`` and ``**kwargs`` to the
     __init__ method of the parent class: this helps to stay compatible with
     future changes of the base class.

#. Register your class under ``generic_switch.devices`` entrypoint.
#. Add your device config to the plugin configuration file
   (``/etc/neutron/plugins/ml2/ml2_conf_genericswitch.ini`` by default).
   The only required option is ``device_type`` that must be equal to the
   entrypoint you have registered your plugin under, as it is used for plugin
   lookup (see provided ``Netmiko``-based plugins for example).
