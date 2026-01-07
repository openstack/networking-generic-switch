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
import base64
import gzip
import json
import re

from neutron_lib import constants as const
from oslo_log import log as logging

from networking_generic_switch.devices import netmiko_devices
from networking_generic_switch import exceptions as exc

LOG = logging.getLogger(__name__)


class Sonic(netmiko_devices.NetmikoSwitch):
    """Device Name: SONiC

    Built for SONiC

    Note for this switch you want config like this,
    where secret is the password needed for sudo su:

    .. code-block:: ini

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

    VXLAN L2VNI Support
    ~~~~~~~~~~~~~~~~~~~

    For VXLAN L2VNI support, the ``vtep_name`` and ``ngs_bgp_asn``
    configuration parameters are required. Uses BGP EVPN with
    ingress-replication for BUM traffic handling.

    .. code-block:: ini

        [genericswitch:<hostname>]
        device_type = netmiko_sonic
        vtep_name = vtep
        ngs_bgp_asn = 65000

    Security Group Implementation
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    The ACL model in SONiC differs from Security Groups in that the ACL table
    is created when binding to a port. Whereas with security groups a group is
    created and later bound to ports. To handle this inversion, the ACL JSON
    is maintained in files ``/etc/sonic/acl-{security_group}.json`` and
    applied when required.

    This implementation supports IPv4, IPv6, and both ingress and egress
    rules.
    """

    NETMIKO_DEVICE_TYPE = "linux"

    def __init__(self, device_cfg, *args, **kwargs):
        """Initialize SONiC device with VTEP configuration.

        Extracts VTEP-related configuration before parent __init__ removes
        all ngs_* options.
        """
        # Extract VTEP config before parent removes ngs_* options
        self.vtep_name = device_cfg.get('vtep_name')
        self.bgp_asn = device_cfg.get('ngs_bgp_asn')

        super(Sonic, self).__init__(device_cfg, *args, **kwargs)

    ADD_NETWORK = (
        'config vlan add {segmentation_id}',
    )

    DELETE_NETWORK = (
        'config vlan del {segmentation_id}',
    )

    PLUG_SWITCH_TO_NETWORK = (
        'config vxlan map add {vtep_name} {segmentation_id} {vni}',
    )

    UNPLUG_SWITCH_FROM_NETWORK = (
        'config vxlan map del {vtep_name} {segmentation_id} {vni}',
    )

    SHOW_VLAN_PORTS = ('show vlan {segmentation_id}',)

    SHOW_VLAN_VNI = ('show vxlan vlanvnimap',)

    PLUG_PORT_TO_NETWORK = (
        'config vlan member add -u {segmentation_id} {port}',
    )

    DELETE_PORT = (
        'config vlan member del {segmentation_id} {port}',
    )

    ADD_NETWORK_TO_TRUNK = (
        'config vlan member add {segmentation_id} {port}',
    )

    REMOVE_NETWORK_FROM_TRUNK = (
        'config vlan member del {segmentation_id} {port}',
    )

    SAVE_CONFIGURATION = (
        'config save -y',
    )

    TABLE_ADD_COMMAND = "config acl add table"

    TABLE_REMOVE_COMMAND = "config acl remove table"

    WRITE_ACL = (
        'echo -n "{acl}" | base64 -d | gunzip '
        '> /etc/sonic/acl-{security_group}.json',
    )
    LOAD_ACL = (
        "acl-loader update full --table_name {security_group_egress} "
        "/etc/sonic/acl-{security_group}.json",
        "acl-loader update full --table_name {security_group_ingress} "
        "/etc/sonic/acl-{security_group}.json",
    )
    ADD_ACL_TABLE = (
        "{table_remove_command} {security_group_egress}",
        "{table_remove_command} {security_group_ingress}",
        "{table_add_command} {security_group_egress} L3V4V6 "
        "-p {ports} -s ingress",
        "{table_add_command} {security_group_ingress} L3V4V6 "
        "-p {ports} -s egress",
    )

    ADD_SECURITY_GROUP = WRITE_ACL + LOAD_ACL

    BIND_SECURITY_GROUP = ADD_ACL_TABLE + WRITE_ACL + LOAD_ACL

    UNBIND_SECURITY_GROUP = ADD_ACL_TABLE + LOAD_ACL

    REMOVE_SECURITY_GROUP = (
        "{table_remove_command} {security_group_egress}",
        "{table_remove_command} {security_group_ingress}",
        "acl-loader delete {security_group_egress}",
        "acl-loader delete {security_group_ingress}",
        "rm -f /etc/sonic/acl-{security_group}.json",
    )

    ERROR_MSG_PATTERNS = (
        re.compile(r'VLAN[0-9]+ doesn\'t exist'),
        re.compile(r'Invalid Vlan Id , Valid Range : 1 to 4094'),
        re.compile(r'Interface name is invalid!!'),
        re.compile(r'No such command'),
    )

    SUPPORT_SG_PORT_RANGE = True

    def _get_acl_names(self, sg_id):
        # convert to table name format now for consistency
        sg_id_upper = sg_id.upper().replace("-", "_")
        # Create 'in' (device egress) and 'out' (device ingress) acls for each
        # security group
        return {
            "security_group": f"ngs-{sg_id}",
            "security_group_egress": f"NGS_IN_{sg_id_upper}",
            "security_group_ingress": f"NGS_OUT_{sg_id_upper}",
        }

    def _sg_rule_to_entry(self, sequence_id, rule):
        """Build an openconfig-acl acl-entry from a sg rule

        This function converts a security group rule into an OpenConfig ACL
        entry dictionary. It handles IPv4 and IPv6, ingress and egress
        directions, and protocol configurations TCP, UDP, and ICMP.

        :param sequence_id: The sequence ID for the ACL entry.
        :param rule: The security group rule to convert.

        :returns: An OpenConfig ACL entry dictionary.
        """
        if rule.ethertype == const.IPv4:
            ethertype = "ETHERTYPE_IPV4"
            remote_ip_all = "0.0.0.0/0"
        else:
            ethertype = "ETHERTYPE_IPV6"
            remote_ip_all = "::/0"

        entry = {
            "actions": {"config": {"forwarding-action": "ACCEPT"}},
            "config": {"sequence-id": sequence_id},
            "l2": {"config": {"ethertype": ethertype}},
        }

        if rule.direction == "ingress":
            ip_remote_key = "source-ip-address"
            port_key = "source-port"
        else:
            ip_remote_key = "destination-ip-address"
            port_key = "destination-port"

        # IP config specifies IP protocol and source or destination
        # address
        ip_config = {}
        if rule.remote_ip_prefix:
            remote_ip_prefix = str(rule.remote_ip_prefix)
            if remote_ip_prefix != remote_ip_all:
                ip_config[ip_remote_key] = remote_ip_prefix

        if rule.protocol:
            ip_config["protocol"] = const.IP_PROTOCOL_MAP[rule.protocol]
        if ip_config:
            entry["ip"] = {"config": ip_config}

        # transport config specifies port ranges
        transport_config = {}
        pmin = rule.port_range_min
        pmax = rule.port_range_max
        if rule.protocol in (const.PROTO_NAME_TCP, const.PROTO_NAME_UDP):
            if pmin:
                if pmax and pmax != pmin:
                    port_range = f"{pmin}..{pmax}"
                else:
                    port_range = str(pmin)
                transport_config[port_key] = port_range
        if transport_config:
            entry["transport"] = {"config": transport_config}

        icmp_config = {}
        if rule.protocol == const.PROTO_NAME_ICMP:
            if pmin is not None:
                icmp_config["type"] = pmin
                if pmax is not None:
                    icmp_config["code"] = pmax
        if icmp_config:
            entry["icmp"] = {"config": icmp_config}

        return entry

    def _sg_to_acl(self, sg):
        """Build an acl from a security group

        This function converts a security group object into a structured
        dictionary which will be converted to JSON for the acl-loader command.
        It processes the security group's rules and organizes them into
        separate ingress and egress ACL tables.

        :param sg: The security group object to convert.
        :returns: A dictionary representing the ACL structure.
        """
        names = self._get_acl_names(sg.id)
        egress_sequence_id = 1
        ingress_sequence_id = 1
        egress_entries = {}
        ingress_entries = {}

        for rule in sg.rules:
            if not self._validate_rule(rule):
                continue

            if rule.direction == const.INGRESS_DIRECTION:
                eid = str(ingress_sequence_id)
                ingress_entries[eid] = self._sg_rule_to_entry(
                    ingress_sequence_id, rule)
                ingress_sequence_id += 1
            else:
                eid = str(egress_sequence_id)
                egress_entries[eid] = self._sg_rule_to_entry(
                    egress_sequence_id, rule)
                egress_sequence_id += 1

        acl = {
            "acl": {
                "acl-sets": {
                    "acl-set": {
                        names["security_group_egress"]: {
                            "acl-entries": {"acl-entry": egress_entries},
                            "config": {
                                "name": names["security_group_egress"]},
                        },
                        names["security_group_ingress"]: {
                            "acl-entries": {"acl-entry": ingress_entries},
                            "config": {
                                "name": names["security_group_ingress"]},
                        },
                    }
                }
            }
        }
        return acl

    def _encode_acl_base64(self, acl):
        acl_str = json.dumps(acl, indent=2)
        acl_bytes = acl_str.encode("utf-8")
        acl_compressed = gzip.compress(acl_bytes)
        acl_encoded = base64.b64encode(acl_compressed)
        acl_encoded_str = acl_encoded.decode("utf-8")
        return acl_encoded_str

    def _add_update_security_group(self, sg):
        kwargs = self._get_acl_names(sg.id)
        kwargs["acl"] = self._encode_acl_base64(self._sg_to_acl(sg))
        cmds = self._format_commands(self.ADD_SECURITY_GROUP, **kwargs)
        return self.send_commands_to_device(cmds)

    @netmiko_devices.check_output("add security group")
    def add_security_group(self, sg):
        return self._add_update_security_group(sg)

    @netmiko_devices.check_output("update security group")
    def update_security_group(self, sg):
        return self._add_update_security_group(sg)

    @netmiko_devices.check_output("delete security group")
    def del_security_group(self, sg_id):
        kwargs = self._get_acl_names(sg_id)
        kwargs["table_remove_command"] = self.TABLE_REMOVE_COMMAND
        cmds = self._format_commands(self.REMOVE_SECURITY_GROUP, **kwargs)
        return self.send_commands_to_device(cmds)

    @netmiko_devices.check_output("bind security group")
    def bind_security_group(self, sg, port_id, port_ids):
        kwargs = self._get_acl_names(sg.id)
        kwargs["ports"] = ",".join(port_ids)
        kwargs["table_add_command"] = self.TABLE_ADD_COMMAND
        kwargs["table_remove_command"] = self.TABLE_REMOVE_COMMAND
        kwargs["acl"] = self._encode_acl_base64(self._sg_to_acl(sg))
        cmds = self._format_commands(self.BIND_SECURITY_GROUP, **kwargs)
        return self.send_commands_to_device(cmds)

    @netmiko_devices.check_output("unbind security group")
    def unbind_security_group(self, sg_id, port_id, port_ids):
        kwargs = self._get_acl_names(sg_id)
        kwargs["table_remove_command"] = self.TABLE_REMOVE_COMMAND
        if not port_ids:
            # There are now zero ports bound to this security group.
            # Treat this as a delete.
            cmds = self._format_commands(self.REMOVE_SECURITY_GROUP, **kwargs)
        else:
            kwargs["ports"] = ",".join(port_ids)
            kwargs["table_add_command"] = self.TABLE_ADD_COMMAND
            cmds = self._format_commands(self.UNBIND_SECURITY_GROUP, **kwargs)
        return self.send_commands_to_device(cmds)

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

    def _parse_vlan_ports(self, output: str, segmentation_id: int) -> bool:
        """Parse SONiC 'show vlan {segmentation_id}' output for ports.

        Handles multiple SONiC output formats across different versions
        and vendor implementations:
        - Format 1: Pipe-delimited ASCII tables (| VLAN ID | ... | Ports |)
        - Format 2: Dash-separated with whitespace (Name Id Members Mode)
        - Format 3: Dell format (NUM Status Q Ports ...)

        :param output: Command output from switch
        :param segmentation_id: VLAN identifier being checked
        :returns: True if VLAN has ports, False otherwise
        """
        lines = output.strip().split('\n')

        # Try to find a line containing our VLAN ID with port information
        # We look for patterns like:
        # - Vlan100 or VLAN100 followed by port names
        # - Just the number 100 followed by port names
        # Common port patterns: Ethernet, Eth, PortChannel, etc.
        vlan_pattern = re.compile(
            r'(?:Vlan|VLAN)?' + str(segmentation_id) + r'\b')
        port_pattern = re.compile(
            r'\b(?:Ethernet|Eth|PortChannel|Po|Gi|Te|Fa)\d+')  # noqa

        for line in lines:
            # Skip obvious header/border lines
            if (not line.strip()
                    or line.startswith('+')
                    or line.startswith('=')
                    or line.startswith('-' * 10)
                    or 'VLAN ID' in line
                    or ('Name' in line and 'Members' in line)):
                continue

            # Check if this line contains our VLAN ID
            if vlan_pattern.search(line):
                # Format 1: Pipe-delimited table
                if '|' in line:
                    parts = [p.strip() for p in line.split('|')]
                    # Find which column has our VLAN
                    for i, part in enumerate(parts):
                        if (part == str(segmentation_id)
                                or part == f'Vlan{segmentation_id}'):
                            # Check remaining columns for port names
                            for j in range(i + 1, len(parts)):
                                if parts[j] and port_pattern.search(parts[j]):
                                    return True
                            # No ports found in remaining columns
                            return False

                # Format 2 & 3: Whitespace-delimited
                # Look for port names anywhere in the line after VLAN ID
                if port_pattern.search(line):
                    return True

                # VLAN found but no ports detected
                return False

        # VLAN not found in output
        return False

    def _parse_vlan_vni(self, output: str, segmentation_id: int,
                        vni: int) -> bool:
        """Parse SONiC 'show vxlan vlanvnimap' output.

        Handles multiple SONiC output formats across different versions
        and vendor implementations. Looks for VLAN-to-VNI mappings using
        pattern matching rather than assuming a specific table format.

        :param output: Command output from switch
        :param segmentation_id: VLAN identifier being checked
        :param vni: VNI to check for
        :returns: True if VLAN has this VNI, False otherwise
        """
        lines = output.strip().split('\n')

        # Pattern to match our VLAN (Vlan100, VLAN100, or just 100)
        vlan_pattern = re.compile(
            r'\b(?:Vlan|VLAN)?' + str(segmentation_id) + r'\b')

        for line in lines:
            # Skip obvious header/border/footer lines
            if (not line.strip()
                    or line.startswith('+')
                    or line.startswith('=')
                    or line.startswith('-' * 10)
                    or 'total count' in line.lower()
                    or ('VLAN' in line and 'VNI' in line
                        and not re.search(r'\d', line))):  # Header no digits
                continue

            # Check if this line contains our VLAN ID
            if vlan_pattern.search(line):
                # Format 1: Pipe-delimited table
                if '|' in line:
                    parts = [p.strip() for p in line.split('|')]
                    # Find which column has our VLAN
                    for i, part in enumerate(parts):
                        if (part == str(segmentation_id)
                                or part == f'Vlan{segmentation_id}'
                                or part == f'VLAN{segmentation_id}'):
                            # VNI should be in next column
                            if i + 1 < len(parts):
                                try:
                                    configured_vni = int(parts[i + 1])
                                    return configured_vni == vni
                                except (ValueError, IndexError):
                                    pass
                            break

                # Format 2: Whitespace/tab-delimited
                # Extract all numbers from the line (including those
                # embedded in words like "Vlan100")
                numbers = re.findall(r'(\d+)', line)
                # Should have at least 2 numbers: VLAN ID and VNI
                if len(numbers) >= 2:
                    # First number matching our VLAN, second is VNI
                    for i, num in enumerate(numbers):
                        if (int(num) == segmentation_id
                                and i + 1 < len(numbers)):
                            try:
                                configured_vni = int(numbers[i + 1])
                                return configured_vni == vni
                            except (ValueError, IndexError):
                                pass

        # If we can't find the VNI, it's not configured
        return False

    @netmiko_devices.check_output('plug vni')
    def plug_switch_to_network(self, vni: int, segmentation_id: int,
                               physnet: str = None):
        """Configure L2VNI mapping with BGP EVPN on the SONiC switch.

        Uses ingress-replication for BUM traffic handling with BGP EVPN
        control plane. This is the recommended approach for VXLAN
        deployments and avoids static flood list scaling issues.

        Configures the following in order:
        1. Configure EVPN VNI in FRR (BGP control plane)
        2. Map VLAN to VNI on the VTEP

        :param vni: VXLAN Network Identifier
        :param segmentation_id: VLAN identifier
        :param physnet: Physical network name (unused, kept for compatibility)
        :returns: Command output
        """
        if not self.vtep_name:
            raise exc.GenericSwitchNetmikoConfigError(
                switch=self.device_name,
                error='vtep_name configuration parameter is required '
                      'for L2VNI support on SONiC switches')

        if not self.bgp_asn:
            raise exc.GenericSwitchNetmikoConfigError(
                switch=self.device_name,
                error='ngs_bgp_asn configuration parameter is required '
                      'for L2VNI support on SONiC switches')

        cmds = []

        # Step 1: Configure per-VNI EVPN in FRR (BGP control plane)
        evpn_cmd = (
            f'vtysh -c "configure terminal" '
            f'-c "router bgp {self.bgp_asn}" '
            f'-c "address-family l2vpn evpn" '
            f'-c "vni {vni}" '
            f'-c "rd auto" '
            f'-c "route-target import auto" '
            f'-c "route-target export auto"')
        cmds.append(evpn_cmd)

        # Step 2: Map VLAN to VNI
        vxlan_cmds = self._format_commands(
            self.PLUG_SWITCH_TO_NETWORK,
            vni=vni,
            segmentation_id=segmentation_id,
            vtep_name=self.vtep_name)
        cmds.extend(vxlan_cmds)

        return self.send_commands_to_device(cmds)

    @netmiko_devices.check_output('unplug vni')
    def unplug_switch_from_network(self, vni: int, segmentation_id: int,
                                   physnet: str = None):
        """Remove L2VNI mapping and EVPN VNI from the SONiC switch.

        Removes configuration in reverse order of creation:
        1. Remove VXLAN map
        2. Remove EVPN VNI configuration from FRR

        :param vni: VXLAN Network Identifier
        :param segmentation_id: VLAN identifier
        :param physnet: Physical network name (unused but kept for signature)
        :returns: Command output
        """
        if not self.vtep_name:
            raise exc.GenericSwitchNetmikoConfigError(
                switch=self.device_name,
                error='vtep_name configuration parameter is required '
                      'for L2VNI support on SONiC switches')

        if not self.bgp_asn:
            raise exc.GenericSwitchNetmikoConfigError(
                switch=self.device_name,
                error='ngs_bgp_asn configuration parameter is required '
                      'for L2VNI support on SONiC switches')

        # Step 1: Remove VXLAN map
        cmds = self._format_commands(
            self.UNPLUG_SWITCH_FROM_NETWORK,
            vni=vni,
            segmentation_id=segmentation_id,
            vtep_name=self.vtep_name)

        # Step 2: Remove per-VNI EVPN from FRR
        evpn_cmd = (
            f'vtysh -c "configure terminal" '
            f'-c "router bgp {self.bgp_asn}" '
            f'-c "address-family l2vpn evpn" '
            f'-c "no vni {vni}"')
        cmds.append(evpn_cmd)

        return self.send_commands_to_device(cmds)

    def vlan_has_ports(self, segmentation_id: int) -> bool:
        """Check if a VLAN has any switch ports currently assigned.

        :param segmentation_id: VLAN identifier
        :returns: True if VLAN has ports, False otherwise
        """
        cmd = self._format_commands(
            self.SHOW_VLAN_PORTS,
            segmentation_id=segmentation_id)
        with self._get_connection() as net_connect:
            output = net_connect.send_command(cmd[0])
            return self._parse_vlan_ports(output, segmentation_id)

    def vlan_has_vni(self, segmentation_id: int, vni: int) -> bool:
        """Check if a VLAN already has a specific VNI mapping configured.

        :param segmentation_id: VLAN identifier
        :param vni: VNI to check for
        :returns: True if VLAN has this VNI, False otherwise
        """
        cmd = self._format_commands(
            self.SHOW_VLAN_VNI,
            segmentation_id=segmentation_id,
            vni=vni)
        with self._get_connection() as net_connect:
            output = net_connect.send_command(cmd[0])
            return self._parse_vlan_vni(output, segmentation_id, vni)


class DellEnterpriseSonic(Sonic):
    """Device Name: Dell Enterprise SONiC

    SONiC variant for differences in Dell Enterprise SONiC.

    Security Group Implementation
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Known differences in Dell Enterprise SONiC 4.5:
    - Different command for adding an ACL table
    - No support for ICMP security group rules
    """

    TABLE_ADD_COMMAND = "config acl table add"

    TABLE_REMOVE_COMMAND = "config acl table delete"

    def _validate_rule(self, rule):
        if not super(DellEnterpriseSonic, self)._validate_rule(rule):
            return False

        if rule.protocol == const.PROTO_NAME_ICMP:
            raise exc.GenericSwitchSecurityGroupRuleNotSupported(
                switch=self.device_name,
                error="Only protocols tcp, udp, are supported."
            )
        return True
