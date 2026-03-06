===============
Troubleshooting
===============

This guide covers common issues encountered when operating
networking-generic-switch.


Enabling Debug Logging
======================

To get verbose output from the driver, set the log level for the
``networking_generic_switch`` namespace in your Neutron configuration::

    [DEFAULT]
    debug = True

Debug logs include the exact commands sent to each switch and the responses
received, which is often necessary for diagnosing unexpected switch behavior.

.. _troubleshooting-vlans:

VLAN Configuration Errors
=========================

If port binding succeeds but traffic does not flow, the VLAN configuration on
the switch may be incorrect.

Things to check:

* Enable debug logging for the driver and inspect the exact commands sent to
  the switch. Look for command errors returned by the switch CLI.
* If ``ngs_manage_vlans = False``, confirm all required VLANs are
  pre-provisioned on the switch. The driver will not create them.
* If trunk ports are configured via ``ngs_trunk_ports``, verify those
  interfaces exist on the switch and are named exactly as specified (names are
  case-sensitive on some platforms).
* If a VLAN used for switch management or an unmanaged port is being removed by
  the driver, set ``ngs_manage_vlans = False`` and pre-configure VLANs
  manually.

.. _troubleshooting-device-errors:

Device Configuration Errors
============================

Switches return error output as text, directly in the CLI response. The driver
attempts to detect these on supported platforms and will raise an exception
with the switch's error message.

If you see ``Found invalid configuration in device response`` in the logs, the
message body will contain the raw error text from the switch. Common causes:

* The VLAN ID is outside the range permitted by the switch.
* A port name is incorrect or the interface does not exist.
* The switch is in a state that does not allow the configuration change (e.g.,
  an interface is part of a port-channel and cannot be reconfigured directly).

.. _troubleshooting-performance:

Performance Under Load
======================

In deployments with many concurrent port binding operations, long delays or
timeouts may be observed. By default, NGS limits configuration changes to one
at a time per switch, via ``ngs_max_connections``.

The first sign will be port binding timeouts in the Neutron logs::

    Failed to acquire any of N locks for <switch> for a netmiko action
    in 60 seconds. Try increasing acquire_timeout.

The options are either to wait longer, or find ways to speed up the process.

Mitigate by waiting longer
--------------------------

To wait longer instead of failing, consider the following configuration knobs:

**acquire_timeout**::

  [ngs_coordination]
  acquire_timeout = 120

This just increases how long NGS waits to acquire the lock before giving up. If
your switch can process all outstanding commands before the timeout, this will
allow all operations to succeed eventually, but may cause port binding to take
an extremely long time under heavy load, or lead to other timeouts upstream.

.. caution::
  Neutron port binding is synchronous. Setting this too high can cause Neutron
  API responses to take a very long time, which may cause timeouts in clients or
  load balancers.

The following is an example of how to adjust Ironic's neutron-client to be more
tolerant of NGS delays::

    # ironic.conf
    [neutron]
    request_timeout = 120        # should be >= acquire_timeout
    status_code_retries = 3      # retry with exponential backoff on timeout
    # retriable_status_codes = 503  # default is 503, but can permit others

Refer to the `Ironic configuration reference
<https://docs.openstack.org/ironic/latest/configuration/config.html>`__ for
details. This makes the overall provisioning pipeline more resilient to
transient failures, but can multiply the time it takes to provision a node.

Ways to improve performance
---------------------------

**Increase ngs_max_connections**

If your switch supports concurrent configuration sessions, you can allow more
than one::

    [genericswitch:device-hostname]
    ngs_max_connections = 3

Check your switch documentation for its concurrent session limit. Setting
this higher than the switch supports will cause sessions to fail or hang on
the switch side, or can cause corrupt configuration if the switch does not
properly serialize concurrent changes.

This can increase load on the switch's control plane, and individual commands
may take longer to execute. This may cause Netmiko to time out waiting for a
response: ``NetmikoTimeoutException: Timed out reading from the device``.

You can adjust this timeout by setting ``read_timeout_override`` per switch::

    [genericswitch:device-hostname]
    read_timeout_override = 30.0

**Enable batching** (:ref:`batching`)

Batching coalesces multiple configuration requests into a single operation, and
requires the etcd (``etcd3gw`` driver) configured as the coordination backend.
To Enable per device::

    [genericswitch:device-hostname]
    ngs_batch_requests = True


Ways to disable (optional) work
-------------------------------

**Disable VLAN management** (:ref:`manage-vlans` in the admin guide)

With ``ngs_manage_vlans = True`` (the default), the driver creates and deletes
VLANs on every switch whenever a Neutron network is created or deleted. In
deployments where VLANs are pre-provisioned and stable, this work can be
eliminated entirely::

    [genericswitch:device-hostname]
    ngs_manage_vlans = False

Note that this affects network create/delete operations, not individual port
bindings. If VLAN churn is low in your deployment this may not help.

**Disable inactive port management**

When ``ngs_disable_inactive_ports = True``, the driver sends an extra
shutdown command to the switch interface each time a port is unbound, and
a no-shutdown command on bind. Disabling this removes those extra commands
per operation::

    [genericswitch:device-hostname]
    ngs_disable_inactive_ports = False

Only relevant if you had previously enabled this feature.

**Disable configuration saves (risky)**

By default, the driver saves the switch running configuration to persistent
storage after every change. This is safe but slow on many platforms::

    [genericswitch:device-hostname]
    ngs_save_configuration = False

.. caution::

   A switch reboot between a port binding and the next scheduled save will
   lose the configuration change, leaving ports in an incorrect state. Only
   disable this if you have an external mechanism saving the switch config
   regularly, or if your switches run entirely from running configuration.
