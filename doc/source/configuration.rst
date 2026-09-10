=============
Configuration
=============

In order to use this mechanism driver the Neutron configuration file needs to
be created/updated with the appropriate configuration information.

Each managed switch is configured as a section in the form
``[genericswitch:<switch name>]``. The ``device_type`` entry is mandatory and
determines which driver is used. Most other configuration entries are optional.

.. note::

    Switch will be selected by local_link_connection/switch_info
    or ngs_mac_address. So, you can use the switch MAC address to identify
    switches if local_link_connection/switch_info is not set.

General configuration
=====================

The ``GenericSwitch`` mechanism driver needs to be enabled from
the ml2 config file ``/etc/neutron/plugins/ml2/ml2_conf.ini``::

   [ml2]
   tenant_network_types = vlan
   type_drivers = local,flat,vlan,gre,vxlan
   mechanism_drivers = openvswitch,genericswitch
   ...

Physical networks need to be declared in the ML2 config as well, with a range
of VLANs that can be allocated to tenant networks.  Several physical networks
can coexist, possibly with overlapping VLAN ranges: in that case, each switch
configuration needs to include its physical network, see :ref:`physicalnetworks`.
Example of ``/etc/neutron/plugins/ml2/ml2_conf.ini`` with two physical networks::

   [ml2_type_vlan]
   network_vlan_ranges = physnet1:700:799,physnet2:600:850

For a given physical network, it is possible to specify several disjoint
ranges of VLANs by simply repeating the physical network name multiple times::

   [ml2_type_vlan]
   network_vlan_ranges = physnet1:700:720,physnet1:750:760

If drivers support security groups then ``genericswitch_security_group`` can be appended
to the list of ``service_plugins`` (this also needs to be enabled per switch configuration)::

    [DEFAULT]
    service_plugins = qos,ovn-router,trunk,segments,port_forwarding,log,genericswitch_security_group

(Re)start ``neutron-server`` specifying the additional configuration file
containing switch configuration::

    neutron-server \
        --config-file /etc/neutron/neutron.conf \
        --config-file /etc/neutron/plugins/ml2/ml2_conf.ini \
        --config-file /etc/neutron/plugins/ml2/ml2_conf_genericswitch.ini

For operational topics such as performance tuning, VXLAN L2VNI support,
and advanced features, see the :doc:`admin/index` guide.

Switch configuration
====================

These example device configuration snippets are assumed to be part of a
specific file ``/etc/neutron/plugins/ml2/ml2_conf_genericswitch.ini``, but
they could also be added directly to ``/etc/neutron/plugins/ml2/ml2_conf.ini``.

Shared NGS options
------------------

These options apply to all device drivers:

* ``ngs_mac_address`` — MAC address of the switch for identification via
  ``local_link_connection/switch_info``.
* ``ngs_physical_networks`` — comma-separated list of physical networks
  this switch belongs to.
* ``ngs_manage_vlans`` — if ``False``, the driver will not create or delete
  VLANs on the switch (default: ``True``).
* ``ngs_allowed_vlans`` — comma-separated list of allowed VLAN IDs. If set,
  only listed VLANs will be configured.
* ``ngs_allowed_ports`` — comma-separated list of allowed port names. If set,
  only listed ports will be configured.
* ``ngs_max_connections`` — maximum number of concurrent sessions to the
  device (default: ``1``). Used with the coordination lock pool.
* ``ngs_network_name_format`` — Python format string for VLAN names on the
  switch (default: ``{network_id}``). Accepts ``{network_id}`` and
  ``{segmentation_id}`` placeholders.
* ``ngs_trunk_ports`` — comma-separated list of interfaces to be tagged with
  each VLAN when created (e.g. ``Ethernet1/48, Port-channel1``).
* ``ngs_port_default_vlan`` — VLAN to restore on a port when it is released.
* ``ngs_switchport_mode`` — switchport mode to use (default: ``access``).
  Some devices support ``general``.
* ``ngs_disable_inactive_ports`` — if ``True``, administratively shut down
  ports that are not in use (default: ``False``).
* ``ngs_security_groups_enabled`` — if ``True``, enable security group
  support on this device (default: ``False``).
* ``ngs_save_configuration`` — if ``False``, skip saving configuration to
  persistent storage after each change (default: ``True``). For NETCONF
  devices targeting the running datastore, this controls whether the driver
  attempts to persist the configuration (see :ref:`netconf-persistence`).
* ``ngs_manage_mtu`` — if ``True``, allow the driver to set port MTU
  (default: ``False``). Must be enabled before any MTU commands are sent to
  the switch. See :doc:`admin/general-configuration` for details.
* ``ngs_port_default_mtu`` — default MTU applied to access/bound ports when
  the Neutron network has no MTU set, and the value restored on unbind.
* ``ngs_trunk_port_mtu`` — MTU applied to trunk (uplink) ports; also the
  upper bound used to validate access port MTU.

Netmiko (SSH/CLI) Devices
-------------------------

Switch configuration format::

    [genericswitch:<switch name>]
    device_type = <netmiko device type>
    ngs_mac_address = <switch mac address>
    ip = <IP address of switch>
    port = <ssh port>
    username = <credential username>
    password = <credential password>
    use_keys = <set to True when key_file is set>
    key_file = <ssh key file>
    secret = <enable secret>
    ngs_allowed_vlans = <comma-separated list of allowed vlans for switch>
    ngs_allowed_ports = <comma-separated list of allowed ports for switch>

Netmiko-specific NGS options:

* ``ngs_batch_requests`` — if ``True``, batch concurrent switch requests
  into a single SSH session (default: ``False``). Requires etcd coordination.
* ``ngs_ssh_disabled_algorithms`` — comma-separated list of
  ``<type>:<algorithm>`` entries to disable during SSH negotiation.
* ``ngs_ssh_connect_timeout`` — SSH connection timeout in seconds
  (default: ``60``).
* ``ngs_ssh_connect_interval`` — interval between SSH connection retries in
  seconds (default: ``10``).
* ``ngs_ssh_reuse_connection`` — if ``True``, reuse SSH connections across
  requests (default: ``False``).

Examples
^^^^^^^^

Here is an example for the Cisco 300 series device::

    [genericswitch:sw-hostname]
    device_type = netmiko_cisco_s300
    ngs_mac_address = <switch mac address>
    username = admin
    password = password
    ip = <switch mgmt ip address>

for the Cisco IOS device::

    [genericswitch:sw-hostname]
    device_type = netmiko_cisco_ios
    ngs_mac_address = <switch mac address>
    username = admin
    password = password
    secret = secret
    ip = <switch mgmt ip address>

for the Cisco NX-OS device::

    [genericswitch:sw-hostname]
    device_type = netmiko_cisco_nxos
    ngs_mac_address = <switch mac address>
    # if security group support is required
    ngs_security_groups_enabled = True
    ip = <switch mgmt ip address>
    username = admin
    password = password
    secret = secret

for the Huawei VRPV3 or VRPV5 device::

    [genericswitch:sw-hostname]
    device_type = netmiko_huawei
    ngs_mac_address = <switch mac address>
    username = admin
    password = password
    port = 8222
    secret = secret
    ip = <switch mgmt ip address>

for the Huawei VRPV8 device::

    [genericswitch:sw-hostname]
    device_type = netmiko_huawei_vrpv8
    ngs_mac_address = <switch mac address>
    username = admin
    password = password
    port = 8222
    secret = secret
    ip = <switch mgmt ip address>

for the Arista EOS device::

    [genericswitch:arista-hostname]
    device_type = netmiko_arista_eos
    ngs_mac_address = <switch mac address>
    ip = <switch mgmt ip address>
    username = admin
    key_file = /opt/data/arista_key

for the Dell Force10 device::

    [genericswitch:dell-hostname]
    device_type = netmiko_dell_force10
    ngs_mac_address = <switch mac address>
    ip = <switch mgmt ip address>
    username = admin
    password = password
    secret = secret

for the Dell OS10 device::

    [genericswitch:dell-hostname]
    device_type = netmiko_dell_os10
    ngs_mac_address = <switch mac address>
    ip = <switch mgmt ip address>
    username = admin
    password = password
    secret = secret

for the Dell PowerConnect device::

    [genericswitch:dell-hostname]
    device_type = netmiko_dell_powerconnect
    ip = <switch mgmt ip address>
    username = admin
    password = password
    secret = secret

    # You can set ngs_switchport_mode according to switchmode you have set on
    # the switch. The following options are supported: general, access. It
    # will default to access mode if left unset. In general mode, the port
    # be set to transmit untagged packets.
    ngs_switchport_mode = access

Dell PowerConnect devices have been seen to have issues with multiple
concurrent configuration sessions. See :ref:`synchronization` and
:ref:`batching` for details on how to limit the number of concurrent active
connections to each device.

for the Brocade FastIron (ICX) device::

    [genericswitch:hostname-for-fast-iron]
    device_type = netmiko_brocade_fastiron
    ngs_mac_address = <switch mac address>
    ip = <switch mgmt ip address>
    username = admin
    password = password

for the Ruijie device::

    [genericswitch:sw-hostname]
    device_type = netmiko_ruijie
    ngs_mac_address = <switch mac address>
    username = admin
    password = password
    secret = secret
    ip = <switch mgmt ip address>

for the HPE 5900 Series device::

    [genericswitch:sw-hostname]
    device_type = netmiko_hp_comware
    username = admin
    password = password
    ip = <switch mgmt ip address>

for the Juniper Junos OS device::

    [genericswitch:hostname-for-juniper]
    device_type = netmiko_juniper
    ip = <switch mgmt ip address>
    username = admin
    password = password
    ngs_commit_timeout = <optional commit timeout (seconds)>
    ngs_commit_interval = <optional commit interval (seconds)>

for a Cumulus Linux device::

    [genericswitch:hostname-for-cumulus]
    device_type = netmiko_cumulus
    ip = <switch mgmt_ip address>
    username = admin
    password = password
    secret = secret
    ngs_mac_address = <switch mac address>

for a Cumulus NVUE Linux device::

    [genericswitch:hostname-for-cumulus]
    device_type = netmiko_cumulus_nvue
    ip = <switch mgmt_ip address>
    username = admin
    password = password
    secret = secret
    ngs_mac_address = <switch mac address>

for the Nokia SRL series device::

    [genericswitch:sw-hostname]
    device_type = netmiko_nokia_srl
    username = admin
    password = password
    ip = <switch mgmt ip address>

for a Pluribus switch::

    [genericswitch:sw-hostname]
    device_type = netmiko_pluribus
    username = admin
    password = password
    ip = <switch mgmt ip address>

for an ArubaOS-CX switch::

    [genericswitch:aruba-hostname]
    device_type = netmiko_aruba_aoscx
    username = admin
    password = password
    ip = <switch mgmt ip address>

for the Supermicro device::

    [genericswitch:sw-hostname]
    device_type = netmiko_supermicro_smis
    ngs_mac_address = <switch mac address>
    ip = <switch mgmt ip address>
    username = admin
    password = password
    secret = secret

NETCONF Devices
---------------

NETCONF devices use ``host`` (not ``ip``) and connect via the NETCONF
protocol (port 830 by default). Connection parameters are passed directly
to ncclient.

Switch configuration format::

    [genericswitch:<switch name>]
    device_type = <netconf device type>
    ngs_mac_address = <switch mac address>
    ngs_physical_networks = <comma-separated list of physical networks>
    host = <IP address or hostname of switch>
    port = <NETCONF port, default 830>
    username = <credential username>
    password = <credential password>
    key_filename = <ssh key file>
    hostkey_verify = <true or false>
    device_params = <ncclient device handler, e.g. name:nexus>

.. _netconf-specific-options:

NETCONF-specific NGS options
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

* ``ngs_openconfig_network_instance`` — OpenConfig network-instance
  for VLAN management (default: ``default``).
* ``ngs_port_id_re_sub`` — JSON object with ``pattern``
  and ``repl`` keys for regex substitution on port IDs from LLDP.
  Example: ``{"pattern": "^Eth", "repl": "Ethernet"}``
* ``ngs_openconfig_disabled_properties`` — comma-separated list of
  properties to omit from configuration payloads
  (e.g. ``port_mtu``).
* ``ngs_netconf_target`` — force the NETCONF datastore target to
  ``candidate`` or ``running``. When unset (the default) the driver
  auto-detects from the server's capabilities. Override this when the
  device's candidate datastore is known to be unreliable.
* ``ngs_netconf_confirmed_commit`` — whether to use confirmed commit when the
  switch advertises the ``:confirmed-commit`` capability (default: ``true``).
  Set to ``false`` to skip the tentative commit entirely. This is useful for
  switches that hold their config backend busy for the full timeout window
  (e.g. Cisco NX-OS), blocking concurrent sessions.
* ``ngs_netconf_confirmed_commit_timeout`` — rollback timeout in seconds for
  the tentative confirmed commit, integer between 1 and 30 (default: ``5``).
  Only used when confirmed commit is enabled and the switch advertises the
  capability. The confirming commit is sent immediately after the tentative
  commit, so a small value is usually sufficient.
* ``ngs_netconf_save_config`` — XML config payload sent via ``edit-config``
  to the running datastore to persist the configuration. Only used when
  ``ngs_save_configuration`` is enabled and the target datastore is
  ``running``. Takes priority over the standard ``copy-config`` to startup.
  See :ref:`netconf-persistence` for vendor-specific examples.

.. _netconf-datastore-selection:

Datastore Selection
^^^^^^^^^^^^^^^^^^^

The driver automatically detects which NETCONF datastore to use based on
the capabilities advertised in the server's hello message:

1. If the switch advertises the ``:candidate`` capability, the driver uses
   the candidate datastore with lock, discard, edit-config, validate,
   confirmed-commit, and commit.
2. If only ``:writable-running`` is available, the driver edits the running
   datastore directly with lock and edit-config.

Set ``ngs_netconf_target`` to override auto-detection when the device's
candidate datastore is known to be unreliable.

.. _netconf-persistence:

Configuration Persistence
^^^^^^^^^^^^^^^^^^^^^^^^^

When the target datastore is ``candidate``, the commit operation implicitly
persists the configuration. When targeting the ``running`` datastore
directly, an additional step is needed to save the configuration to
non-volatile storage so it survives a reboot.

The driver attempts to persist the running configuration when
``ngs_save_configuration`` is enabled, using the following priority:

1. **Custom save config** — if ``ngs_netconf_save_config`` is configured,
   the driver sends it as an ``edit-config`` to the running datastore.
2. **copy-config to startup** — if the device advertises the ``:startup``
   capability, the driver performs ``copy-config`` from ``running`` to
   ``startup``.
3. **Warning** — if neither mechanism is available, the driver logs a
   warning that the configuration cannot be persisted.

Vendor examples for ``ngs_netconf_save_config``:

Arista EOS (via the ``arista-cli`` YANG module)::

    ngs_netconf_save_config = <config><commands xmlns="http://arista.com/yang/cli"><command>write memory</command></commands></config>

Cisco IOS (via CLI config data)::

    ngs_netconf_save_config = <config><cli-config-data><cmd>write memory</cmd></cli-config-data></config>

Examples
^^^^^^^^

For a NETCONF OpenConfig device::

    [genericswitch:sw-hostname]
    device_type = netconf_openconfig
    ngs_mac_address = <switch mac address>
    ngs_physical_networks = physnet1
    ngs_trunk_ports = Ethernet1/48
    ngs_disable_inactive_ports = True
    ngs_port_default_vlan = 1
    ngs_port_id_re_sub = {"pattern": "^Eth", "repl": "Ethernet"}
    host = <switch mgmt ip address>
    port = 830
    username = admin
    password = password
    device_params = name:nexus

For an Arista EOS device via NETCONF (requires targeting the running
datastore due to known candidate datastore issues)::

    [genericswitch:arista-hostname]
    device_type = netconf_openconfig
    ngs_mac_address = <switch mac address>
    ngs_physical_networks = physnet1
    ngs_trunk_ports = Ethernet1
    ngs_netconf_target = running
    ngs_save_configuration = true
    ngs_netconf_save_config = <config><commands xmlns="http://arista.com/yang/cli"><command>write memory</command></commands></config>
    host = <switch mgmt ip address>
    username = admin
    password = password
