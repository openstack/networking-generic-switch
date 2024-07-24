# Copyright 2020 StackHPC
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
import re

from networking_generic_switch.devices import netmiko_devices


class Cumulus(netmiko_devices.NetmikoSwitch):
    """Built for Cumulus 4.x

    Note for this switch you want config like this,
    where secret is the password needed for sudo su:

    [genericswitch:<hostname>]
    device_type = netmiko_cumulus
    ip = <ip>
    username = <username>
    password = <password>
    secret = <password for sudo>
    ngs_physical_networks = physnet1
    ngs_max_connections = 1
    ngs_port_default_vlan = 123
    ngs_disable_inactive_ports = False
    """
    NETMIKO_DEVICE_TYPE = "linux"

    ADD_NETWORK = [
        'net add vlan {segmentation_id}',
    ]

    DELETE_NETWORK = [
        'net del vlan {segmentation_id}',
    ]

    PLUG_PORT_TO_NETWORK = [
        'net add interface {port} bridge access {segmentation_id}',
    ]

    DELETE_PORT = [
        'net del interface {port} bridge access {segmentation_id}',
    ]

    PLUG_BOND_TO_NETWORK = [
        'net add bond {bond} bridge access {segmentation_id}',
    ]

    UNPLUG_BOND_FROM_NETWORK = [
        'net del bond {bond} bridge access {segmentation_id}',
    ]

    ENABLE_PORT = [
        'net del interface {port} link down',
    ]

    DISABLE_PORT = [
        'net add interface {port} link down',
    ]

    ENABLE_BOND = [
        'net del bond {bond} link down',
    ]

    DISABLE_BOND = [
        'net add bond {bond} link down',
    ]

    SAVE_CONFIGURATION = [
        'net commit',
    ]

    ERROR_MSG_PATTERNS = [
        # Its tempting to add this error message, but as only one
        # bridge-access is allowed, we ignore that error for now:
        # re.compile(r'configuration does not have "bridge-access')
        re.compile(r'ERROR: Command not found.'),
        re.compile(r'command not found'),
        re.compile(r'is not a physical interface on this switch'),
    ]


class CumulusNVUE(netmiko_devices.NetmikoSwitch):
    """Built for Cumulus 5.x

    Note for this switch you want config like this,
    where secret is the password needed for sudo su:

    [genericswitch:<hostname>]
    device_type = netmiko_cumulus
    ip = <ip>
    username = <username>
    password = <password>
    secret = <password for sudo>
    ngs_physical_networks = physnet1
    ngs_max_connections = 1
    ngs_port_default_vlan = 123
    ngs_disable_inactive_ports = False
    """
    NETMIKO_DEVICE_TYPE = "linux"

    ADD_NETWORK = [
        'nv set bridge domain br_default vlan {segmentation_id}',
    ]

    DELETE_NETWORK = [
        'nv unset bridge domain br_default vlan {segmentation_id}',
    ]

    PLUG_PORT_TO_NETWORK = [
        'nv set interface {port} bridge domain br_default access '
        '{segmentation_id}',
    ]

    DELETE_PORT = [
        'nv unset interface {port} bridge domain br_default access',
    ]

    ENABLE_PORT = [
        'nv set interface {port} link state up',
    ]

    DISABLE_PORT = [
        'nv set interface {port} link state down',
    ]

    SAVE_CONFIGURATION = [
        'nv config save',
    ]

    ERROR_MSG_PATTERNS = [
        # Its tempting to add this error message, but as only one
        # bridge-access is allowed, we ignore that error for now:
        # re.compile(r'configuration does not have "bridge-access')
        re.compile(r'Invalid config'),
        re.compile(r'Config invalid at'),
        re.compile(r'ERROR: Command not found.'),
        re.compile(r'command not found'),
        re.compile(r'is not a physical interface on this switch'),
        re.compile(r'Error: Invalid parameter'),
        re.compile(r'Unable to restart services'),
        re.compile(r'Failure during apply'),
    ]

    def send_config_set(self, net_connect, cmd_set):
        """Send a set of configuration lines to the device.

        :param net_connect: a netmiko connection object.
        :param cmd_set: a list of configuration lines to send.
        :returns: The output of the configuration commands.
        """
        cmd_set.append('nv config apply --assume-yes')
        net_connect.enable()
        # NOTE: Do not exit config mode because save needs elevated
        # privileges
        return net_connect.send_config_set(config_commands=cmd_set,
                                           cmd_verify=False,
                                           exit_config_mode=False)
