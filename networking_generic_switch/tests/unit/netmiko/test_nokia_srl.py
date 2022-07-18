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

from unittest import mock

from networking_generic_switch.devices.netmiko_devices import nokia
from networking_generic_switch.tests.unit.netmiko import test_netmiko_base


class TestNetmikoNokiaSRL(test_netmiko_base.NetmikoSwitchTestBase):

    def _make_switch_device(self):
        device_cfg = {'device_type': 'netmiko_nokia_srl'}
        return nokia.NokiaSRL(device_cfg)

    def test_constants(self):
        self.assertIsNone(self.switch.SAVE_CONFIGURATION)

    @mock.patch('networking_generic_switch.devices.netmiko_devices.nokia.'
                'NokiaSRL.send_commands_to_device')
    def test_add_network(self, m_exec):
        self.switch.add_network(33, '0ae071f5-5be9-43e4-80ea-e41fefe85b21')
        m_exec.assert_called_with(
            ['set tunnel-interface vxlan0 vxlan-interface 33 type bridged',
             'set tunnel-interface vxlan0 vxlan-interface 33 ingress vni 33',
             'set tunnel-interface vxlan0 vxlan-interface 33 egress '
             'source-ip use-system-ipv4-address',
             'set network-instance mac-vrf-33 type mac-vrf',
             'set network-instance mac-vrf-33 description '
             'OS-Network-ID-0ae071f55be943e480eae41fefe85b21',
             'set network-instance mac-vrf-33 vxlan-interface vxlan0.33',
             'set network-instance mac-vrf-33 protocols bgp-evpn '
             'bgp-instance 1 vxlan-interface vxlan0.33',
             'set network-instance mac-vrf-33 protocols bgp-evpn '
             'bgp-instance 1 evi 33',
             'set network-instance mac-vrf-33 protocols bgp-evpn '
             'bgp-instance 1 ecmp 8',
             'set network-instance mac-vrf-33 protocols bgp-vpn '
             'bgp-instance 1 route-target export-rt target:1:33',
             'set network-instance mac-vrf-33 protocols bgp-vpn '
             'bgp-instance 1 route-target import-rt target:1:33'])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.nokia.'
                'NokiaSRL.send_commands_to_device')
    def test_del_network(self, mock_exec):
        self.switch.del_network(33, '0ae071f5-5be9-43e4-80ea-e41fefe85b21')
        mock_exec.assert_called_with(
            ['delete network-instance mac-vrf-33',
             'delete tunnel-interface vxlan0 vxlan-interface 33'])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.nokia.'
                'NokiaSRL.send_commands_to_device')
    def test_plug_port_to_network(self, mock_exec):
        self.switch.plug_port_to_network(3333, 33)
        mock_exec.assert_called_with(
            ['set interface 3333 subinterface 33 type bridged',
             'set network-instance mac-vrf-33 interface 3333.33'])

    @mock.patch('networking_generic_switch.devices.netmiko_devices.nokia.'
                'NokiaSRL.send_commands_to_device')
    def test_delete_port(self, mock_exec):
        self.switch.delete_port(3333, 33)
        mock_exec.assert_called_with(
            ['delete network-instance mac-vrf-33 interface 3333.33',
             'delete interface 3333 subinterface 33'])

    def test__format_commands(self):
        cmd_set = self.switch._format_commands(
            nokia.NokiaSRL.ADD_NETWORK,
            segmentation_id=22,
            network_id=22,
            network_name='vlan-22')
        add_exp = [
            'set tunnel-interface vxlan0 vxlan-interface 22 type bridged',
            'set tunnel-interface vxlan0 vxlan-interface 22 ingress vni 22',
            'set tunnel-interface vxlan0 vxlan-interface 22 egress source-ip '
            'use-system-ipv4-address',
            'set network-instance mac-vrf-22 type mac-vrf',
            'set network-instance mac-vrf-22 description '
            'OS-Network-ID-vlan-22',
            'set network-instance mac-vrf-22 vxlan-interface vxlan0.22',
            'set network-instance mac-vrf-22 protocols bgp-evpn '
            'bgp-instance 1 vxlan-interface vxlan0.22',
            'set network-instance mac-vrf-22 protocols bgp-evpn '
            'bgp-instance 1 evi 22',
            'set network-instance mac-vrf-22 protocols bgp-evpn '
            'bgp-instance 1 ecmp 8',
            'set network-instance mac-vrf-22 protocols bgp-vpn '
            'bgp-instance 1 route-target export-rt target:1:22',
            'set network-instance mac-vrf-22 protocols bgp-vpn '
            'bgp-instance 1 route-target import-rt target:1:22']
        self.assertEqual(cmd_set, add_exp)

        cmd_set = self.switch._format_commands(
            nokia.NokiaSRL.DELETE_NETWORK,
            segmentation_id=22)
        del_net_exp = ['delete network-instance mac-vrf-22',
                       'delete tunnel-interface vxlan0 vxlan-interface 22']
        self.assertEqual(cmd_set, del_net_exp)

        cmd_set = self.switch._format_commands(
            nokia.NokiaSRL.PLUG_PORT_TO_NETWORK,
            port=3333,
            segmentation_id=33)
        plug_exp = ['set interface 3333 subinterface 33 type bridged',
                    'set network-instance mac-vrf-33 interface 3333.33']
        self.assertEqual(plug_exp, cmd_set)

        cmd_set = self.switch._format_commands(
            nokia.NokiaSRL.DELETE_PORT,
            port=3333,
            segmentation_id=33)
        del_port_exp = ['delete network-instance mac-vrf-33 interface 3333.33',
                        'delete interface 3333 subinterface 33']
        self.assertEqual(del_port_exp, cmd_set)
