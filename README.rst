GenericSwitch ML2 Mechanism driver from ML2 plugin
============================================

* ML2 driver uses Netmiko library

* Issues/Questions/Bugs: vsaienko@mirantis.com

 Supported Devices:
   1. Cisco IOS switches

ML2 plugin requires mechanism driver to support configuring of hardware switches.
GenericSwitch Mechanism for ML2 uses Netmiko library, that uses SSH as the backend
to configure the switch. This ML2 is PoC and any switch that supports SSH can be added.

                                 Neutron
                                  v2.0
                                    |
                                    |
                              +------------+
                              |            |
                              | Openstack  |
                              | Neutron    |
                              | ML2        |
                              | Plugin     |
                              |            |
                              +------------+
                                    |
                                    |
                              +------------+
                              |            |
                              | Generic    |
                              | Mechanism  |
                              | Driver     |
                              |            |
                              +------------+
                                    |
                                    | SSH
                                    |
                              +------------+
                              |   Switch   |
                              +------------+

Configuration

In order to use this mechnism the generic configuration file needs to be edited with the appropriate
configuration information:

        % cat /etc/neutron/plugins/ml2/ml2_conf_genericswitch.ini
        [genericswitch:sw-hostname]
        device_type = cisco_ios
        username = admin
        password = password
        secret = secret
        ip = <switch mgmt ip address>

Additionally the GenericSwitch mechanism driver needs to be enabled from the ml2 config file:

       % cat /etc/neutron/plugins/ml2/ml2_conf.ini

       [ml2]
       tenant_network_types = vlan
       type_drivers = local,flat,vlan,gre,vxlan
       mechanism_drivers = openvswitch,genericswitch
       # OR mechanism_drivers = openvswitch,linuxbridge,hyperv,genericswitch
       ...
       ...
