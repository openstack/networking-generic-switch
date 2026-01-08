# Copyright 2016 Mirantis, Inc.
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

# Internal ngs options will not be passed to driver.
OVS_INTERNAL_OPTS = [
    # OVS bridge name to use for VNI mapping storage.
    {'name': 'ngs_ovs_bridge', 'default': 'genericswitch'},
]


class OvsLinux(netmiko_devices.NetmikoSwitch):
    """Device Name: OpenVSwitch

    VXLAN L2VNI Support (CI/Testing Only)
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    **IMPORTANT**: This implementation does NOT configure actual VXLAN tunnels
    on OVS. It is designed exclusively for CI and testing purposes to exercise
    the hierarchical port binding workflow and L2VNI cleanup logic without
    requiring physical hardware switches.

    The implementation uses OVS bridge external_ids to store VNI-to-VLAN
    mappings as metadata, allowing the driver to track and clean up VNI
    associations using the same logic as physical switches.

    Configuration:

    .. code-block:: ini

        [genericswitch:ovs-switch]
        device_type = netmiko_ovs_linux
        ngs_ovs_bridge = genericswitch

    The ``ngs_ovs_bridge`` parameter specifies the OVS bridge name to use
    for VNI mapping storage. Defaults to ``genericswitch``. Common values
    include ``brbm`` (Ironic CI) or ``genericswitch`` (devstack plugin).

    For production VXLAN deployments, use physical switch implementations
    (Cisco NX-OS, Arista EOS, SONiC, Cumulus NVUE, or Juniper Junos).
    """

    PLUG_PORT_TO_NETWORK = (
        'ovs-vsctl set port {port} vlan_mode=access',
        'ovs-vsctl set port {port} tag={segmentation_id}',
    )

    DELETE_PORT = (
        'ovs-vsctl clear port {port} tag',
        'ovs-vsctl clear port {port} trunks',
        'ovs-vsctl clear port {port} vlan_mode'
    )

    SET_NATIVE_VLAN = (
        'ovs-vsctl set port {port} vlan_mode=native-untagged',
        'ovs-vsctl set port {port} tag={segmentation_id}',
        'ovs-vsctl add port {port} trunks {segmentation_id}',
    )

    DELETE_NATIVE_VLAN = (
        'ovs-vsctl clear port {port} vlan_mode',
        'ovs-vsctl clear port {port} tag',
        'ovs-vsctl remove port {port} trunks {segmentation_id}',
    )

    SET_NATIVE_VLAN_BOND = (
        'ovs-vsctl set port {bond} vlan_mode=native-untagged',
        'ovs-vsctl set port {bond} tag={segmentation_id}',
        'ovs-vsctl add port {bond} trunks {segmentation_id}',
    )

    DELETE_NATIVE_VLAN_BOND = (
        'ovs-vsctl clear port {bond} vlan_mode',
        'ovs-vsctl clear port {bond} tag',
        'ovs-vsctl remove port {bond} trunks {segmentation_id}',
    )

    ADD_NETWORK_TO_TRUNK = (
        'ovs-vsctl add port {port} trunks {segmentation_id}',
    )

    REMOVE_NETWORK_FROM_TRUNK = (
        'ovs-vsctl remove port {port} trunks {segmentation_id}',
    )

    ADD_NETWORK_TO_BOND_TRUNK = (
        'ovs-vsctl add port {bond} trunks {segmentation_id}',
    )

    DELETE_NETWORK_ON_BOND_TRUNK = (
        'ovs-vsctl remove port {bond} trunks {segmentation_id}',
    )

    PLUG_SWITCH_TO_NETWORK = (
        'ovs-vsctl set bridge {bridge_name} '
        'external_ids:vni-{vni}={segmentation_id}',
    )

    UNPLUG_SWITCH_FROM_NETWORK = (
        'ovs-vsctl remove bridge {bridge_name} external_ids vni-{vni}',
    )

    SHOW_PORTS = ('ovs-vsctl list port',)

    SHOW_BRIDGE_EXTERNAL_IDS = (
        'ovs-vsctl get bridge {bridge_name} external_ids',
    )

    def __init__(self, device_cfg, *args, **kwargs):
        # Do not expose OVS internal options to device config.
        ovs_cfg = {}
        for opt in OVS_INTERNAL_OPTS:
            opt_name = opt['name']
            if opt_name in device_cfg:
                ovs_cfg[opt_name] = device_cfg.pop(opt_name)
            elif 'default' in opt:
                ovs_cfg[opt_name] = opt['default']
        super(OvsLinux, self).__init__(device_cfg, *args, **kwargs)
        self.ngs_config.update(ovs_cfg)

    def _get_bridge_name(self):
        """Get the OVS bridge name from configuration.

        :returns: Bridge name, defaults to 'genericswitch'
        """
        return self.ngs_config.get('ngs_ovs_bridge', 'genericswitch')

    def _parse_vlan_ports(self, output: str, segmentation_id: int) -> bool:
        """Parse 'ovs-vsctl list port' output for ports with VLAN tag.

        :param output: Command output from OVS
        :param segmentation_id: VLAN identifier being checked
        :returns: True if any port has this VLAN tag, False otherwise
        """
        # OVS output format:
        # _uuid               : 12345678-1234-1234-1234-123456789abc
        # name                : "eth0"
        # tag                 : 100
        # trunks              : []
        lines = output.strip().split('\n')
        for line in lines:
            # Look for tag line with our segmentation_id
            if line.startswith('tag'):
                try:
                    # Format: "tag                 : 100" or "tag : []"
                    parts = line.split(':')
                    if len(parts) >= 2:
                        value = parts[1].strip()
                        # Skip empty tags (shown as [] or empty)
                        if value and value != '[]':
                            tag_id = int(value)
                            if tag_id == segmentation_id:
                                return True
                except (ValueError, IndexError):
                    continue
        return False

    def _parse_vlan_vni(self, output: str, segmentation_id: int,
                        vni: int) -> bool:
        """Parse 'ovs-vsctl get bridge external_ids' output for VNI.

        :param output: Command output from OVS
        :param segmentation_id: VLAN identifier being checked
        :param vni: VNI to check for
        :returns: True if VNI maps to this VLAN, False otherwise
        """
        # OVS external_ids output format:
        # {key1=value1, key2=value2, "vni-5000"="100"}
        # Look for vni-<vni>=<segmentation_id> in the output
        # Handles both quoted and unquoted formats across OVS versions
        pattern = rf'["\']?vni-{vni}["\']?\s*=\s*["\']?(\d+)["\']?'
        match = re.search(pattern, output)
        if match:
            return int(match.group(1)) == segmentation_id
        return False

    @netmiko_devices.check_output('plug vni')
    def plug_switch_to_network(self, vni: int, segmentation_id: int,
                               physnet: str = None):
        """Store VNI-to-VLAN mapping in OVS bridge external_ids.

        NOTE: This does NOT configure actual VXLAN tunnels. It only stores
        the VNI mapping as metadata for CI/testing purposes.

        :param vni: VXLAN Network Identifier
        :param segmentation_id: VLAN identifier
        :param physnet: Physical network name (unused but kept for API
                        consistency)
        :returns: Command output
        """
        bridge_name = self._get_bridge_name()
        cmds = self._format_commands(
            self.PLUG_SWITCH_TO_NETWORK,
            vni=vni,
            segmentation_id=segmentation_id,
            bridge_name=bridge_name)
        return self.send_commands_to_device(cmds)

    @netmiko_devices.check_output('unplug vni')
    def unplug_switch_from_network(self, vni: int, segmentation_id: int,
                                   physnet: str = None):
        """Remove VNI-to-VLAN mapping from OVS bridge external_ids.

        :param vni: VXLAN Network Identifier
        :param segmentation_id: VLAN identifier (unused, kept for API
                                consistency)
        :param physnet: Physical network name (unused but kept for API
                        consistency)
        :returns: Command output
        """
        bridge_name = self._get_bridge_name()
        cmds = self._format_commands(
            self.UNPLUG_SWITCH_FROM_NETWORK,
            vni=vni,
            segmentation_id=segmentation_id,
            bridge_name=bridge_name)
        return self.send_commands_to_device(cmds)

    def vlan_has_ports(self, segmentation_id: int) -> bool:
        """Check if any OVS port has this VLAN tag assigned.

        :param segmentation_id: VLAN identifier
        :returns: True if any port has this tag, False otherwise
        """
        with self._get_connection() as net_connect:
            output = net_connect.send_command(self.SHOW_PORTS[0])
            return self._parse_vlan_ports(output, segmentation_id)

    def vlan_has_vni(self, segmentation_id: int, vni: int) -> bool:
        """Check if VNI mapping exists in bridge external_ids.

        :param segmentation_id: VLAN identifier
        :param vni: VNI to check for
        :returns: True if VNI maps to this VLAN, False otherwise
        """
        bridge_name = self._get_bridge_name()
        cmd = self._format_commands(
            self.SHOW_BRIDGE_EXTERNAL_IDS,
            bridge_name=bridge_name)
        with self._get_connection() as net_connect:
            output = net_connect.send_command(cmd[0])
            return self._parse_vlan_vni(output, segmentation_id, vni)
