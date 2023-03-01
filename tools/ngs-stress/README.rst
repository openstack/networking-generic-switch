=====================================
Networking-generic-switch Stress Test
=====================================

Stress test for the OpenStack Neutron networking-generic-switch (genericswitch)
ML2 mechanism driver.

This script can stress a switch using the genericswitch driver.  It does not
require an OpenStack or Neutron installation, and can operate in isolation.
There are two modes of operation:

network
    Create and delete a number of networks in parallel.
port
    Create and delete a number of ports in parallel.

It is possible to use an existing genericswitch configuration file containing
switch configuration.

Installation
============

To install dependencies in a virtualenv::

    python3 -m venv venv
    source venv/bin/activate
    pip install -U pip
    pip install -c https://releases.openstack.org/constraints/upper/<release> networking-generic-switch

If you want to use etcd for coordination, install the ``etcd3gw`` package::

    pip install -c https://releases.openstack.org/constraints/upper/<release> etcd3gw

The Bitnami ``Etcd`` container can be used in a standalone mode::

    docker run --detach -it -e ALLOW_NONE_AUTHENTICATION=yes --name Etcd --net=host bitnami/etcd

Configuration
=============

A configuration file is required to provide details of switch devices, as well
as any other NGS config options necessary. For example, to use the Fake device
driver for testing:

.. code-block:: ini

   [genericswitch:fake]
   device_type = netmiko_fake

Other drivers will typically require further configuration.

If you want to use etcd for coordination, add the following:

.. code-block:: ini

   [ngs_coordination]
   backend_url = etcd3+http://localhost:2379?api_version=v3

Usage
=====

To run the stress test in network mode::

    venv/bin/python /path/to/ngs/tools/ngs-stress/ngs_stress.py \
    --config-file /path/to/ngs-stress.conf \
    --mode network \
    --switch <switch name> \
    --vlan-range <min>:<max>

To run the stress test in port mode::

    venv/bin/python /path/to/ngs/tools/ngs-stress/ngs_stress.py \
    --config-file /path/to/ngs-stress.conf \
    --mode port \
    --switch <switch name> \
    --vlan-range <vlan>:<vlan+1> \
    --ports <port1,port2...>

Other arguments are available, see ``--help``.
