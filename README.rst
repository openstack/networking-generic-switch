============================================
Networking-generic-switch Neutron ML2 driver
============================================

.. image:: https://governance.openstack.org/tc/badges/networking-generic-switch.svg
    :target: https://governance.openstack.org/tc/reference/tags/index.html

This is a Modular Layer 2 `Neutron Mechanism driver
<https://wiki.openstack.org/wiki/Neutron/ML2>`_. The mechanism driver is
responsible for applying configuration information to hardware equipment.
``GenericSwitch`` provides a pluggable framework to implement
functionality required for use-cases like OpenStack Ironic multi-tenancy mode.
It abstracts applying changes to all switches managed by this ML2 plugin
and handling ``local_link_information`` field of Neutron port.

Networking-generic-switch is distributed under the terms of the Apache License,
Version 2.0. The full terms and conditions of this license are detailed in the
LICENSE file.

Project resources
~~~~~~~~~~~~~~~~~

* Documentation: https://docs.openstack.org/networking-generic-switch/latest/
* Source: https://opendev.org/openstack/networking-generic-switch
* Bugs: https://bugs.launchpad.net/networking-generic-switch
* Release notes: https://docs.openstack.org/releasenotes/networking-generic-switch/

For information on how to contribute to Networking-generic-switch, see
https://docs.openstack.org/networking-generic-switch/latest/contributing.html.
