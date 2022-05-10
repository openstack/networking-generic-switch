# Copyright 2022 James Denton <james.denton@outlook.com>
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


class Sonic(netmiko_devices.NetmikoSwitch):
    """Built for SONiC 3.x

    Note for this switch you want config like this,
    where secret is the password needed for sudo su:

    [genericswitch:<hostname>]
    device_type = netmiko_sonic
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
        'config vlan add {segmentation_id}',
    ]

    DELETE_NETWORK = [
        'config vlan del {segmentation_id}',
    ]

    PLUG_PORT_TO_NETWORK = [
        'config vlan member add -u {segmentation_id} {port}',
    ]

    DELETE_PORT = [
        'config vlan member del {segmentation_id} {port}',
    ]

    ADD_NETWORK_TO_TRUNK = [
        'config vlan member add {segmentation_id} {port}',
    ]

    REMOVE_NETWORK_FROM_TRUNK = [
        'config vlan member del {segmentation_id} {port}',
    ]

    SAVE_CONFIGURATION = [
        'config save -y',
    ]

    ERROR_MSG_PATTERNS = [
        re.compile(r'VLAN[0-9]+ doesn\'t exist'),
        re.compile(r'Invalid Vlan Id , Valid Range : 1 to 4094'),
        re.compile(r'Interface name is invalid!!'),
        re.compile(r'No such command'),
    ]

    def send_config_set(self, net_connect, cmd_set):
        """Send a set of configuration lines to the device.

        :param net_connect: a netmiko connection object.
        :param cmd_set: a list of configuration lines to send.
        :returns: The output of the configuration commands.
        """
        net_connect.enable()

        # Don't exit configuration mode, as config save requires
        # root permissions.
        return net_connect.send_config_set(config_commands=cmd_set,
                                           cmd_verify=False,
                                           exit_config_mode=False)
