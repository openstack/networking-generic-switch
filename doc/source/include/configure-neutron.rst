Enable genericswitch mechanism driver in Neutron
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

To enable mechanism drivers in the ML2 plug-in, edit the
``/etc/neutron/plugins/ml2/ml2_conf.ini`` file on the neutron server::

  [ml2]
    mechanism_drivers = ovs,genericswitch
