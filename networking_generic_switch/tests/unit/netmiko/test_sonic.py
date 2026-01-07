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
from unittest import mock

import netaddr
from neutron_lib import constants as const

from networking_generic_switch.devices.netmiko_devices import sonic
from networking_generic_switch import exceptions as exc
from networking_generic_switch.tests.unit.netmiko import test_netmiko_base


class TestNetmikoSonic(test_netmiko_base.NetmikoSwitchTestBase):

    def _make_switch_device(self, extra_cfg={}):
        device_cfg = {
            'device_type': 'netmiko_sonic',
            'ngs_port_default_vlan': '123',
            'ngs_disable_inactive_ports': 'True',
        }
        device_cfg.update(extra_cfg)
        return sonic.Sonic(device_cfg)

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device',
                return_value="", autospec=True)
    def test_add_network(self, mock_exec):
        self.switch.add_network(3333, '0ae071f5-5be9-43e4-80ea-e41fefe85b21')
        mock_exec.assert_called_with(
            self.switch,
            ['config vlan add 3333'])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device',
                return_value="", autospec=True)
    def test_delete_network(self, mock_exec):
        self.switch.del_network(3333, '0ae071f5-5be9-43e4-80ea-e41fefe85b21')
        mock_exec.assert_called_with(
            self.switch,
            ['config vlan del 3333'])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device',
                return_value="", autospec=True)
    def test_plug_port_to_network(self, mock_exec):
        self.switch.plug_port_to_network(3333, 33)
        mock_exec.assert_called_with(
            self.switch,
            ['config vlan member del 123 3333',
             'config vlan member add -u 33 3333'])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device', autospec=True)
    def test_plug_port_to_network_fails(self, mock_exec):
        mock_exec.return_value = (
            'Error: No such command "test".\n\nasdf'
        )
        self.assertRaises(exc.GenericSwitchNetmikoConfigError,
                          self.switch.plug_port_to_network, 3333, 33)

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device', autospec=True)
    def test_plug_port_to_network_fails_bad_port(self, mock_exec):
        mock_exec.return_value = (
            'Error: Interface name is invalid!!'
            '\n\nasdf'
        )
        self.assertRaises(exc.GenericSwitchNetmikoConfigError,
                          self.switch.plug_port_to_network, 3333, 33)

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device',
                return_value="", autospec=True)
    def test_plug_port_simple(self, mock_exec):
        switch = self._make_switch_device({
            'ngs_disable_inactive_ports': 'false',
            'ngs_port_default_vlan': '',
        })
        switch.plug_port_to_network(3333, 33)
        mock_exec.assert_called_with(switch,
                                     ['config vlan member add -u 33 3333'])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device',
                return_value="", autospec=True)
    def test_delete_port(self, mock_exec):
        self.switch.delete_port(3333, 33)
        mock_exec.assert_called_with(
            self.switch,
            ['config vlan member del 33 3333',
             'config vlan add 123',
             'config vlan member add -u 123 3333'])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device',
                return_value="", autospec=True)
    def test_delete_port_simple(self, mock_exec):
        switch = self._make_switch_device({
            'ngs_disable_inactive_ports': 'false',
            'ngs_port_default_vlan': '',
        })
        switch.delete_port(3333, 33)
        mock_exec.assert_called_with(switch,
                                     ['config vlan member del 33 3333'])

    def test_save(self):
        mock_connect = mock.MagicMock()
        mock_connect.save_config.side_effect = NotImplementedError
        self.switch.save_configuration(mock_connect)
        mock_connect.send_command.assert_called_with('config save -y')

    def test__get_acl_names(self):
        self.assertEqual(
            {
                "security_group": "ngs-abcd1234",
                "security_group_egress": "NGS_IN_ABCD1234",
                "security_group_ingress": "NGS_OUT_ABCD1234",
            },
            self.switch._get_acl_names("abcd1234"),
        )

    def test__sg_rule_to_entry(self):
        # allow tcp ports 8080 - 8089 ingress all remote addresses
        self.assertEqual(
            {
                "actions": {"config": {"forwarding-action": "ACCEPT"}},
                "config": {"sequence-id": 1},
                "ip": {
                    "config": {
                        "protocol": const.PROTO_NUM_TCP,
                    }
                },
                "l2": {"config": {"ethertype": "ETHERTYPE_IPV4"}},
                "transport": {"config": {"source-port": "8080..8099"}},
            },
            self.switch._sg_rule_to_entry(
                1,
                mock.Mock(
                    ethertype=const.IPv4,
                    protocol=const.PROTO_NAME_TCP,
                    direction="ingress",
                    port_range_min=8080,
                    port_range_max=8099,
                    remote_ip_prefix=None,
                ),
            ),
        )

        # allow tcp port 22 egress to test-net-1
        self.assertEqual(
            {
                "actions": {"config": {"forwarding-action": "ACCEPT"}},
                "config": {"sequence-id": 1},
                "ip": {
                    "config": {
                        "protocol": const.PROTO_NUM_TCP,
                        "destination-ip-address": "192.0.2.0/24",
                    }
                },
                "l2": {"config": {"ethertype": "ETHERTYPE_IPV4"}},
                "transport": {"config": {"destination-port": "22"}},
            },
            self.switch._sg_rule_to_entry(
                1,
                mock.Mock(
                    ethertype=const.IPv4,
                    protocol=const.PROTO_NAME_TCP,
                    direction="egress",
                    port_range_min=22,
                    port_range_max=None,
                    remote_ip_prefix=netaddr.IPNetwork("192.0.2.0/24"),
                ),
            ),
        )

        # allow UDP 1000 ingress from IPv6 2001:db8::/32
        self.assertEqual(
            {
                "actions": {"config": {"forwarding-action": "ACCEPT"}},
                "config": {"sequence-id": 1},
                "ip": {
                    "config": {
                        "protocol": const.PROTO_NUM_UDP,
                        "source-ip-address": "2001:db8::/32",
                    }
                },
                "l2": {"config": {"ethertype": "ETHERTYPE_IPV6"}},
                "transport": {"config": {"source-port": "1000"}},
            },
            self.switch._sg_rule_to_entry(
                1,
                mock.Mock(
                    ethertype=const.IPv6,
                    protocol=const.PROTO_NAME_UDP,
                    direction="ingress",
                    port_range_min=1000,
                    port_range_max=1000,
                    remote_ip_prefix=netaddr.IPNetwork("2001:db8::/32"),
                ),
            ),
        )

        # allow ping
        self.assertEqual(
            {
                "actions": {"config": {"forwarding-action": "ACCEPT"}},
                "config": {"sequence-id": 1},
                "ip": {
                    "config": {
                        "protocol": const.PROTO_NUM_ICMP,
                    }
                },
                "l2": {"config": {"ethertype": "ETHERTYPE_IPV4"}},
                "icmp": {"config": {"code": 0, "type": 8}},
            },
            self.switch._sg_rule_to_entry(
                1,
                mock.Mock(
                    ethertype=const.IPv4,
                    protocol=const.PROTO_NAME_ICMP,
                    direction="ingress",
                    port_range_min=8,
                    port_range_max=0,
                    remote_ip_prefix=None,
                ),
            ),
        )

    def test__sg_to_acl(self):
        self.maxDiff = None
        # allow ping, incoming tcp port 8080-8099, outgoing 22 to test-net-q
        sg_id = "abcd1234"
        rules = [
            mock.Mock(
                ethertype=const.IPv4,
                protocol=const.PROTO_NAME_ICMP,
                direction="ingress",
                port_range_min=8,
                port_range_max=0,
                remote_ip_prefix=None,
            ),
            mock.Mock(
                ethertype=const.IPv4,
                protocol=const.PROTO_NAME_TCP,
                direction="egress",
                port_range_min=22,
                port_range_max=None,
                remote_ip_prefix=netaddr.IPNetwork("192.0.2.0/24"),
            ),
            mock.Mock(
                ethertype=const.IPv4,
                protocol=const.PROTO_NAME_TCP,
                direction="ingress",
                port_range_min=8080,
                port_range_max=8099,
                remote_ip_prefix=None,
            ),
        ]
        sg = mock.Mock(id=sg_id, rules=rules)

        self.assertEqual(
            {
                "acl": {
                    "acl-sets": {
                        "acl-set": {
                            "NGS_IN_ABCD1234": {
                                "acl-entries": {
                                    "acl-entry": {
                                        "1": {
                                            "actions": {
                                                "config": {
                                                    "forwarding-action":
                                                    "ACCEPT"
                                                }
                                            },
                                            "config": {"sequence-id": 1},
                                            "ip": {
                                                "config": {
                                                    "destination-ip-address":
                                                    "192.0.2.0/24",
                                                    "protocol": 6,
                                                }
                                            },
                                            "l2": {
                                                "config": {
                                                    "ethertype":
                                                    "ETHERTYPE_IPV4"
                                                }
                                            },
                                            "transport": {
                                                "config": {
                                                    "destination-port": "22"
                                                }
                                            },
                                        }
                                    }
                                },
                                "config": {"name": "NGS_IN_ABCD1234"},
                            },
                            "NGS_OUT_ABCD1234": {
                                "acl-entries": {
                                    "acl-entry": {
                                        "1": {
                                            "actions": {
                                                "config": {
                                                    "forwarding-action":
                                                    "ACCEPT"
                                                }
                                            },
                                            "config": {"sequence-id": 1},
                                            "icmp": {
                                                "config": {
                                                    "code": 0,
                                                    "type": 8,
                                                }
                                            },
                                            "ip": {"config": {"protocol": 1}},
                                            "l2": {
                                                "config": {
                                                    "ethertype":
                                                    "ETHERTYPE_IPV4"
                                                }
                                            },
                                        },
                                        "2": {
                                            "actions": {
                                                "config": {
                                                    "forwarding-action":
                                                    "ACCEPT"
                                                }
                                            },
                                            "config": {"sequence-id": 2},
                                            "ip": {"config": {"protocol": 6}},
                                            "l2": {
                                                "config": {
                                                    "ethertype":
                                                    "ETHERTYPE_IPV4"
                                                }
                                            },
                                            "transport": {
                                                "config": {
                                                    "source-port": "8080..8099"
                                                }
                                            },
                                        },
                                    }
                                },
                                "config": {"name": "NGS_OUT_ABCD1234"},
                            },
                        }
                    }
                }
            },
            self.switch._sg_to_acl(sg),
        )

    def test__sg_to_acl_empty(self):
        self.maxDiff = None
        sg_id = "abcd1234"
        rules = []
        sg = mock.Mock(id=sg_id, rules=rules)

        self.assertEqual(
            {
                "acl": {
                    "acl-sets": {
                        "acl-set": {
                            "NGS_IN_ABCD1234": {
                                "acl-entries": {"acl-entry": {}},
                                "config": {"name": "NGS_IN_ABCD1234"},
                            },
                            "NGS_OUT_ABCD1234": {
                                "acl-entries": {"acl-entry": {}},
                                "config": {"name": "NGS_OUT_ABCD1234"},
                            },
                        }
                    }
                }
            },
            self.switch._sg_to_acl(sg),
        )

    def test__encode_acl_base64(self):
        acl = {"foo": "bar"}
        encoded = self.switch._encode_acl_base64(acl)
        decoded = base64.b64decode(encoded)
        decompressed = gzip.decompress(decoded)
        self.assertEqual({"foo": "bar"}, json.loads(decompressed))

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'sonic.Sonic._sg_to_acl',
                autospec=True)
    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device',
                return_value="", autospec=True)
    def test__add_update_security_group(self, mock_exec, mock_sg_to_acl):
        sg = mock.Mock(id='1234abcd')

        acl = {"foo": "bar"}
        encoded = self.switch._encode_acl_base64(acl)
        mock_sg_to_acl.return_value = acl

        # test add security group
        self.switch.add_security_group(sg)
        mock_exec.assert_called_with(
            self.switch,
            [f'echo -n "{encoded}" | '
             'base64 -d | gunzip > /etc/sonic/acl-ngs-1234abcd.json',
             'acl-loader update full --table_name NGS_IN_1234ABCD '
             '/etc/sonic/acl-ngs-1234abcd.json',
             'acl-loader update full --table_name NGS_OUT_1234ABCD '
             '/etc/sonic/acl-ngs-1234abcd.json'])

        # test update security group
        mock_exec.reset_mock()
        acl = {"foo": "bar"}
        encoded = self.switch._encode_acl_base64(acl)
        mock_sg_to_acl.return_value = acl
        self.switch.update_security_group(sg)
        mock_exec.assert_called_with(
            self.switch,
            [f'echo -n "{encoded}" | '
             'base64 -d | gunzip > /etc/sonic/acl-ngs-1234abcd.json',
             'acl-loader update full --table_name NGS_IN_1234ABCD '
             '/etc/sonic/acl-ngs-1234abcd.json',
             'acl-loader update full --table_name NGS_OUT_1234ABCD '
             '/etc/sonic/acl-ngs-1234abcd.json'])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device',
                return_value="", autospec=True)
    def test_del_security_group(self, mock_exec):
        self.switch.del_security_group('1234abcd')
        mock_exec.assert_called_with(
            self.switch,
            ['config acl remove table NGS_IN_1234ABCD',
             'config acl remove table NGS_OUT_1234ABCD',
             'acl-loader delete NGS_IN_1234ABCD',
             'acl-loader delete NGS_OUT_1234ABCD',
             'rm -f /etc/sonic/acl-ngs-1234abcd.json'])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'sonic.Sonic._sg_to_acl',
                autospec=True)
    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device',
                return_value="", autospec=True)
    def test_bind_security_group(self, mock_exec, mock_sg_to_acl):
        sg = mock.Mock(id='1234abcd')

        acl = {"foo": "bar"}
        encoded = self.switch._encode_acl_base64(acl)
        mock_sg_to_acl.return_value = acl

        self.switch.bind_security_group(
            sg, 'Ethernet12', ['Ethernet10', 'Ethernet11', 'Ethernet12'])
        mock_exec.assert_called_with(
            self.switch,
            ['config acl remove table NGS_IN_1234ABCD',
             'config acl remove table NGS_OUT_1234ABCD',
             'config acl add table NGS_IN_1234ABCD L3V4V6 '
             '-p Ethernet10,Ethernet11,Ethernet12 -s ingress',
             'config acl add table NGS_OUT_1234ABCD L3V4V6 '
             '-p Ethernet10,Ethernet11,Ethernet12 -s egress',
             f'echo -n "{encoded}" | '
             'base64 -d | gunzip > /etc/sonic/acl-ngs-1234abcd.json',
             'acl-loader update full --table_name NGS_IN_1234ABCD '
             '/etc/sonic/acl-ngs-1234abcd.json',
             'acl-loader update full --table_name NGS_OUT_1234ABCD '
             '/etc/sonic/acl-ngs-1234abcd.json'])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device',
                return_value="", autospec=True)
    def test_unbind_security_group(self, mock_exec):
        self.switch.unbind_security_group(
            '1234abcd', 'Ethernet12', ['Ethernet10', 'Ethernet11'])
        mock_exec.assert_called_with(
            self.switch,
            ['config acl remove table NGS_IN_1234ABCD',
             'config acl remove table NGS_OUT_1234ABCD',
             'config acl add table NGS_IN_1234ABCD L3V4V6 '
             '-p Ethernet10,Ethernet11 -s ingress',
             'config acl add table NGS_OUT_1234ABCD L3V4V6 '
             '-p Ethernet10,Ethernet11 -s egress',
             'acl-loader update full --table_name NGS_IN_1234ABCD '
             '/etc/sonic/acl-ngs-1234abcd.json',
             'acl-loader update full --table_name NGS_OUT_1234ABCD '
             '/etc/sonic/acl-ngs-1234abcd.json'])

    def test_plug_switch_to_network_no_vtep_name(self):
        self.assertRaises(
            exc.GenericSwitchNetmikoConfigError,
            self.switch.plug_switch_to_network,
            5000,
            100
        )

    def test_unplug_switch_from_network_no_vtep_name(self):
        self.assertRaises(
            exc.GenericSwitchNetmikoConfigError,
            self.switch.unplug_switch_from_network,
            5000,
            100
        )

    def test__parse_vlan_ports_with_ports(self):
        output = '''+-----------+--------------+-----------+--------+
| VLAN ID   | IP Address   | Ports     | Port Tagging   |
+===========+==============+===========+================+
| 100       |              | Ethernet0 | untagged       |
+-----------+--------------+-----------+----------------+'''
        result = self.switch._parse_vlan_ports(output, 100)
        self.assertTrue(result)

    def test__parse_vlan_ports_without_ports(self):
        output = '''+-----------+--------------+-----------+--------+
| VLAN ID   | IP Address   | Ports     | Port Tagging   |
+===========+==============+===========+================+
| 100       |              |           | untagged       |
+-----------+--------------+-----------+----------------+'''
        result = self.switch._parse_vlan_ports(output, 100)
        self.assertFalse(result)

    def test__parse_vlan_ports_vlan_not_found(self):
        output = '''+-----------+--------------+-----------+--------+
| VLAN ID   | IP Address   | Ports     | Port Tagging   |
+===========+==============+===========+================+
| 200       |              | Ethernet0 | untagged       |
+-----------+--------------+-----------+----------------+'''
        result = self.switch._parse_vlan_ports(output, 100)
        self.assertFalse(result)

    def test__parse_vlan_ports_dash_format_with_ports(self):
        """Test parsing dash-separated format with ports."""
        output = '''---------------------------------------------------------
Name Id Members Mode
---------------------------------------------------------
Vlan100 100 Ethernet0 tagged
---------------------------------------------------------'''
        result = self.switch._parse_vlan_ports(output, 100)
        self.assertTrue(result)

    def test__parse_vlan_ports_dash_format_without_ports(self):
        """Test parsing dash-separated format without ports."""
        output = '''---------------------------------------------------------
Name Id Members Mode
---------------------------------------------------------
Vlan100 100
---------------------------------------------------------'''
        result = self.switch._parse_vlan_ports(output, 100)
        self.assertFalse(result)

    def test__parse_vlan_vni_match(self):
        output = '''+---------+-------+
| VLAN    | VNI   |
+=========+=======+
| Vlan100 | 5000  |
+---------+-------+
| Vlan200 | 6000  |
+---------+-------+
Total count : 2'''
        result = self.switch._parse_vlan_vni(output, 100, 5000)
        self.assertTrue(result)

    def test__parse_vlan_vni_no_match(self):
        output = '''+---------+-------+
| VLAN    | VNI   |
+=========+=======+
| Vlan100 | 5000  |
+---------+-------+
| Vlan200 | 6000  |
+---------+-------+
Total count : 2'''
        result = self.switch._parse_vlan_vni(output, 100, 9999)
        self.assertFalse(result)

    def test__parse_vlan_vni_vlan_not_found(self):
        output = '''+---------+-------+
| VLAN    | VNI   |
+=========+=======+
| Vlan100 | 5000  |
+---------+-------+
| Vlan200 | 6000  |
+---------+-------+
Total count : 2'''
        result = self.switch._parse_vlan_vni(output, 300, 5000)
        self.assertFalse(result)

    # VTEP Configuration Tests

    def test_init_default_config(self):
        """Test __init__ with default configuration."""
        device_cfg = {'device_type': 'netmiko_sonic'}
        switch = sonic.Sonic(device_cfg)
        self.assertIsNone(switch.vtep_name)
        self.assertIsNone(switch.bgp_asn)

    def test_init_with_vtep_name(self):
        """Test __init__ with vtep_name."""
        device_cfg = {
            'device_type': 'netmiko_sonic',
            'vtep_name': 'vtep1'
        }
        switch = sonic.Sonic(device_cfg)
        self.assertEqual(switch.vtep_name, 'vtep1')

    def test_init_with_bgp_asn(self):
        """Test __init__ with BGP ASN configuration."""
        device_cfg = {
            'device_type': 'netmiko_sonic',
            'ngs_bgp_asn': '65000'
        }
        switch = sonic.Sonic(device_cfg)
        self.assertEqual(switch.bgp_asn, '65000')

    # EVPN Plug/Unplug Tests

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device',
                return_value='', autospec=True)
    def test_plug_switch_to_network(self, mock_exec):
        """Test plug_switch_to_network with BGP EVPN."""
        device_cfg = {
            'device_type': 'netmiko_sonic',
            'vtep_name': 'vtep',
            'ngs_bgp_asn': '65000'
        }
        switch = sonic.Sonic(device_cfg)
        switch.plug_switch_to_network(10100, 100)
        expected_evpn_cmd = (
            'vtysh -c "configure terminal" '
            '-c "router bgp 65000" '
            '-c "address-family l2vpn evpn" '
            '-c "vni 10100" '
            '-c "rd auto" '
            '-c "route-target import auto" '
            '-c "route-target export auto"')
        mock_exec.assert_called_with(
            switch,
            [expected_evpn_cmd,
             'config vxlan map add vtep 100 10100'])

    def test_plug_switch_to_network_without_vtep_name(self):
        """Test plug_switch_to_network fails without vtep_name."""
        device_cfg = {
            'device_type': 'netmiko_sonic',
            'ngs_bgp_asn': '65000'
        }
        switch = sonic.Sonic(device_cfg)
        self.assertRaises(exc.GenericSwitchNetmikoConfigError,
                          switch.plug_switch_to_network, 10100, 100)

    def test_plug_switch_to_network_without_bgp_asn(self):
        """Test plug_switch_to_network fails without BGP ASN."""
        device_cfg = {
            'device_type': 'netmiko_sonic',
            'vtep_name': 'vtep'
        }
        switch = sonic.Sonic(device_cfg)
        self.assertRaises(exc.GenericSwitchNetmikoConfigError,
                          switch.plug_switch_to_network, 10100, 100)

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device',
                return_value='', autospec=True)
    def test_unplug_switch_from_network(self, mock_exec):
        """Test unplug_switch_from_network with BGP EVPN."""
        device_cfg = {
            'device_type': 'netmiko_sonic',
            'vtep_name': 'vtep',
            'ngs_bgp_asn': '65000'
        }
        switch = sonic.Sonic(device_cfg)
        switch.unplug_switch_from_network(10100, 100)
        expected_evpn_cmd = (
            'vtysh -c "configure terminal" '
            '-c "router bgp 65000" '
            '-c "address-family l2vpn evpn" '
            '-c "no vni 10100"')
        mock_exec.assert_called_with(
            switch,
            ['config vxlan map del vtep 100 10100',
             expected_evpn_cmd])

    def test_unplug_switch_from_network_without_vtep_name(self):
        """Test unplug_switch_from_network fails without vtep_name."""
        device_cfg = {
            'device_type': 'netmiko_sonic',
            'ngs_bgp_asn': '65000'
        }
        switch = sonic.Sonic(device_cfg)
        self.assertRaises(exc.GenericSwitchNetmikoConfigError,
                          switch.unplug_switch_from_network, 10100, 100)

    def test_unplug_switch_from_network_without_bgp_asn(self):
        """Test unplug_switch_from_network fails without BGP ASN."""
        device_cfg = {
            'device_type': 'netmiko_sonic',
            'vtep_name': 'vtep'
        }
        switch = sonic.Sonic(device_cfg)
        self.assertRaises(exc.GenericSwitchNetmikoConfigError,
                          switch.unplug_switch_from_network, 10100, 100)

    # vlan_has_ports() tests

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch._get_connection', autospec=True)
    def test_vlan_has_ports_true(self, mock_get_conn):
        """Test vlan_has_ports returns True when VLAN has ports."""
        device_cfg = {'device_type': 'netmiko_sonic'}
        switch = sonic.Sonic(device_cfg)

        mock_net_connect = mock.MagicMock()
        mock_get_conn.return_value.__enter__.return_value = mock_net_connect

        # Simulate output with ports
        output = '''+-----------+--------------+-----------+--------+
| VLAN ID   | IP Address   | Ports     | Port Tagging   |
+===========+==============+===========+================+
| 100       |              | Ethernet0 | untagged       |
+-----------+--------------+-----------+----------------+'''
        mock_net_connect.send_command.return_value = output

        result = switch.vlan_has_ports(100)
        self.assertTrue(result)
        mock_net_connect.send_command.assert_called_once_with(
            'show vlan 100')

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch._get_connection', autospec=True)
    def test_vlan_has_ports_false(self, mock_get_conn):
        """Test vlan_has_ports returns False when VLAN has no ports."""
        device_cfg = {'device_type': 'netmiko_sonic'}
        switch = sonic.Sonic(device_cfg)

        mock_net_connect = mock.MagicMock()
        mock_get_conn.return_value.__enter__.return_value = mock_net_connect

        # Simulate output without ports
        output = '''+-----------+--------------+-----------+--------+
| VLAN ID   | IP Address   | Ports     | Port Tagging   |
+===========+==============+===========+================+
| 100       |              |           | untagged       |
+-----------+--------------+-----------+----------------+'''
        mock_net_connect.send_command.return_value = output

        result = switch.vlan_has_ports(100)
        self.assertFalse(result)

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch._get_connection', autospec=True)
    def test_vlan_has_ports_multiple_ports(self, mock_get_conn):
        """Test vlan_has_ports with multiple ports assigned."""
        device_cfg = {'device_type': 'netmiko_sonic'}
        switch = sonic.Sonic(device_cfg)

        mock_net_connect = mock.MagicMock()
        mock_get_conn.return_value.__enter__.return_value = mock_net_connect

        # Simulate output with multiple ports
        output = '''+-----------+--------------+--------------------+--------+
| VLAN ID   | IP Address   | Ports              | Port Tagging   |
+===========+==============+====================+================+
| 100       |              | Ethernet0,Eth1     | untagged       |
+-----------+--------------+--------------------+----------------+'''
        mock_net_connect.send_command.return_value = output

        result = switch.vlan_has_ports(100)
        self.assertTrue(result)

    # vlan_has_vni() tests

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch._get_connection', autospec=True)
    def test_vlan_has_vni_true(self, mock_get_conn):
        """Test vlan_has_vni returns True when VNI is configured."""
        device_cfg = {'device_type': 'netmiko_sonic'}
        switch = sonic.Sonic(device_cfg)

        mock_net_connect = mock.MagicMock()
        mock_get_conn.return_value.__enter__.return_value = mock_net_connect

        # Simulate output with matching VNI
        output = '''+---------+-------+
| VLAN    | VNI   |
+=========+=======+
| Vlan100 | 5000  |
+---------+-------+
| Vlan200 | 6000  |
+---------+-------+
Total count : 2'''
        mock_net_connect.send_command.return_value = output

        result = switch.vlan_has_vni(100, 5000)
        self.assertTrue(result)
        mock_net_connect.send_command.assert_called_once_with(
            'show vxlan vlanvnimap')

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch._get_connection', autospec=True)
    def test_vlan_has_vni_false_wrong_vni(self, mock_get_conn):
        """Test vlan_has_vni returns False when VNI doesn't match."""
        device_cfg = {'device_type': 'netmiko_sonic'}
        switch = sonic.Sonic(device_cfg)

        mock_net_connect = mock.MagicMock()
        mock_get_conn.return_value.__enter__.return_value = mock_net_connect

        # Simulate output with wrong VNI for this VLAN
        output = '''+---------+-------+
| VLAN    | VNI   |
+=========+=======+
| Vlan100 | 5000  |
+---------+-------+
| Vlan200 | 6000  |
+---------+-------+
Total count : 2'''
        mock_net_connect.send_command.return_value = output

        result = switch.vlan_has_vni(100, 9999)
        self.assertFalse(result)

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch._get_connection', autospec=True)
    def test_vlan_has_vni_false_vlan_not_found(self, mock_get_conn):
        """Test vlan_has_vni returns False when VLAN not in output."""
        device_cfg = {'device_type': 'netmiko_sonic'}
        switch = sonic.Sonic(device_cfg)

        mock_net_connect = mock.MagicMock()
        mock_get_conn.return_value.__enter__.return_value = mock_net_connect

        # Simulate output without the queried VLAN
        output = '''+---------+-------+
| VLAN    | VNI   |
+=========+=======+
| Vlan200 | 6000  |
+---------+-------+
| Vlan300 | 7000  |
+---------+-------+
Total count : 2'''
        mock_net_connect.send_command.return_value = output

        result = switch.vlan_has_vni(100, 5000)
        self.assertFalse(result)

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch._get_connection', autospec=True)
    def test_vlan_has_vni_empty_output(self, mock_get_conn):
        """Test vlan_has_vni returns False with empty switch output."""
        device_cfg = {'device_type': 'netmiko_sonic'}
        switch = sonic.Sonic(device_cfg)

        mock_net_connect = mock.MagicMock()
        mock_get_conn.return_value.__enter__.return_value = mock_net_connect

        # Simulate empty output (no VNIs configured)
        output = '''+---------+-------+
| VLAN    | VNI   |
+=========+=======+
Total count : 0'''
        mock_net_connect.send_command.return_value = output

        result = switch.vlan_has_vni(100, 5000)
        self.assertFalse(result)

    def test__parse_vlan_vni_format_with_vtep_column(self):
        """Test parsing format with VTEP Name column (Format 3)."""
        output = '''VTEP Name    VLAN ID    VNI
-----------  ---------  -------
vtep1        100        10000
vtep1        200        20000
vtep1        300        30000'''
        result = self.switch._parse_vlan_vni(output, 100, 10000)
        self.assertTrue(result)

    def test__parse_vlan_vni_format_with_vtep_column_no_match(self):
        """Test parsing format with VTEP Name column, wrong VNI."""
        output = '''VTEP Name    VLAN ID    VNI
-----------  ---------  -------
vtep1        100        10000
vtep1        200        20000'''
        result = self.switch._parse_vlan_vni(output, 100, 9999)
        self.assertFalse(result)

    def test__parse_vlan_vni_format_with_equals_separator(self):
        """Test parsing format with equals sign separator (Format 4)."""
        output = '''VLAN VNI
= = = = = =
Vlan99 99
Total count: 1'''
        result = self.switch._parse_vlan_vni(output, 99, 99)
        self.assertTrue(result)

    def test__parse_vlan_vni_format_right_aligned(self):
        """Test parsing with right-aligned VNI column."""
        output = '''+---------+-------+
| VLAN    |   VNI |
+=========+=======+
| Vlan100 |   100 |
+---------+-------+
| Vlan101 |   101 |
+---------+-------+'''
        result = self.switch._parse_vlan_vni(output, 101, 101)
        self.assertTrue(result)


class TestNetmikoDellEnterpriseSonic(test_netmiko_base.NetmikoSwitchTestBase):

    def _make_switch_device(self, extra_cfg={}):
        device_cfg = {
            "device_type": "netmiko_dell_enterprise_sonic",
            "ngs_port_default_vlan": "123",
            "ngs_disable_inactive_ports": "True",
        }
        device_cfg.update(extra_cfg)
        return sonic.DellEnterpriseSonic(device_cfg)

    def test__validate_rule(self):
        # acceptable rule
        self.assertTrue(self.switch._validate_rule(mock.Mock(
            protocol='tcp',
            ethertype='IPv4',
            direction='egress'
        )))
        # no icmp
        self.assertRaises(
            exc.GenericSwitchSecurityGroupRuleNotSupported,
            self.switch._validate_rule,
            mock.Mock(
                protocol='icmp',
                ethertype='IPv4',
                direction='egress'
            )
        )

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'sonic.Sonic._sg_to_acl',
                autospec=True)
    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device',
                return_value="", autospec=True)
    def test_bind_security_group(self, mock_exec, mock_sg_to_acl):
        sg = mock.Mock(id='1234abcd')

        acl = {"foo": "bar"}
        encoded = self.switch._encode_acl_base64(acl)
        mock_sg_to_acl.return_value = acl

        self.switch.bind_security_group(
            sg, 'Ethernet12', ['Ethernet10', 'Ethernet11', 'Ethernet12'])

        # this differs from the Sonic class as the command is
        # 'config acl table add' instead of 'config acl add table'
        mock_exec.assert_called_with(
            self.switch,
            ['config acl table delete NGS_IN_1234ABCD',
             'config acl table delete NGS_OUT_1234ABCD',
             'config acl table add NGS_IN_1234ABCD L3V4V6 '
             '-p Ethernet10,Ethernet11,Ethernet12 -s ingress',
             'config acl table add NGS_OUT_1234ABCD L3V4V6 '
             '-p Ethernet10,Ethernet11,Ethernet12 -s egress',
             f'echo -n "{encoded}" | '
             'base64 -d | gunzip > /etc/sonic/acl-ngs-1234abcd.json',
             'acl-loader update full --table_name NGS_IN_1234ABCD '
             '/etc/sonic/acl-ngs-1234abcd.json',
             'acl-loader update full --table_name NGS_OUT_1234ABCD '
             '/etc/sonic/acl-ngs-1234abcd.json'])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device',
                return_value="", autospec=True)
    def test_del_security_group(self, mock_exec):
        self.switch.del_security_group('1234abcd')
        mock_exec.assert_called_with(
            self.switch,
            ['config acl table delete NGS_IN_1234ABCD',
             'config acl table delete NGS_OUT_1234ABCD',
             'acl-loader delete NGS_IN_1234ABCD',
             'acl-loader delete NGS_OUT_1234ABCD',
             'rm -f /etc/sonic/acl-ngs-1234abcd.json'])
