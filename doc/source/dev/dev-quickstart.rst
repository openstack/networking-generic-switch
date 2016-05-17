.. _dev-quickstart:

=====================
Developer Quick-Start
=====================

This is a quick walkthrough to get you started developing code for
Networking-generic-switch. This assumes you are already familiar with
submitting code reviews to an OpenStack project.

=================================================
Deploying Networking-generic-switch with DevStack
=================================================

DevStack may be configured to deploy Networking-generic-switch, setup Neutron to
use the Networking-generic-switch ML2 driver. It is highly recommended
to deploy on an expendable virtual machine and not on your personal work
station.  Deploying Networking-generic-switch with DevStack requires a machine
running Ubuntu 14.04 (or later) or Fedora 20 (or later).

.. seealso::

    http://docs.openstack.org/developer/devstack/

Devstack will no longer create the user 'stack' with the desired
permissions, but does provide a script to perform the task::

    git clone https://github.com/openstack-dev/devstack.git devstack
    sudo ./devstack/tools/create-stack-user.sh

Switch to the stack user and clone DevStack::

    sudo su - stack
    git clone https://github.com/openstack-dev/devstack.git devstack

Create devstack/local.conf with minimal settings required to enable
Networking-generic-switch. Here is and example of local.conf::

    [[local|localrc]]
    # Set credentials
    ADMIN_PASSWORD=secrete
    DATABASE_PASSWORD=secrete
    RABBIT_PASSWORD=secrete
    SERVICE_PASSWORD=secrete
    SERVICE_TOKEN=secrete

    # Enable minimal required services
    ENABLED_SERVICES="dstat,mysql,rabbit,key,q-svc,q-agt,q-dhcp"

    # Enable networking-generic-switch plugin
    enable_plugin networking-generic-switch https://review.openstack.org/openstack/networking-generic-switch

    # Configure Neutron
    Q_PLUGIN_EXTRA_CONF_PATH=/etc/neutron/plugins/ml2
    Q_PLUGIN_EXTRA_CONF_FILES['networking-generic-switch']=ml2_conf_genericswitch.ini
    OVS_PHYSICAL_BRIDGE=brbm
    PHYSICAL_NETWORK=mynetwork
    Q_PLUGIN=ml2
    ENABLE_TENANT_VLANS=True
    Q_ML2_TENANT_NETWORK_TYPE=vlan
    TENANT_VLAN_RANGE=100:150

    # Configure logging
    LOGFILE=$HOME/devstack.log
    LOGDIR=$HOME/logs

Run stack.sh::

    ./stack.sh

Source credentials::

    source ~/devstack/openrc admin admin


Test with OVS
-------------

Launch exercise.sh from networking-generic-switch. This script
creates port in Neutron/update it with local_link_information and
verifies that ovs port has been assigned to correct VLAN::

   bash ~/networking-generic-switch/devstack/exercise.sh


Test with real hardware:
------------------------

Add information about hardware switch to Networking-generic-switch
config ``/etc/neutron/plugins/ml2/ml2_conf_genericswitch.ini`` and
restart Neutron server::

    [genericswitch:cisco_switch_1]
    device_type = netmiko_cisco_ios
    ip = 1.2.3.4
    username = cisco
    password = cisco
    secret = enable_password


Get current configuration of the port on the switch, for example for
Cisco IOS device::

     sh running-config int gig 0/12
     Building configuration...

     Current configuration : 283 bytes
     !
     interface GigabitEthernet0/12
      switchport mode access
     end

Run exercise.py to create/update Neutron port. It will print VLAN id to be
assigned::

    $ neutron net-create test
    $ python ~/networking-generic-switch/devstack/exercise.py --switch_name cisco_switch_1 --port Gig0/12 --switch_id=06:58:1f:e7:b4:44 --network test
    126


Verify that VLAN has been changed on the switch port, for example for
Cisco IOS device::

     sh running-config int gig 0/12
     Building configuration...

     Current configuration : 311 bytes
     !
     interface GigabitEthernet0/12
      switchport access vlan 126
      switchport mode access
     end
