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
from unittest import mock

import fixtures
import netmiko
import netmiko.base_connection
from oslo_config import fixture as config_fixture
import paramiko
import tenacity
from tooz import coordination

from networking_generic_switch.devices import netmiko_devices
from networking_generic_switch.devices import utils
from networking_generic_switch import exceptions as exc


class NetmikoSwitchTestBase(fixtures.TestWithFixtures):
    def setUp(self):
        super(NetmikoSwitchTestBase, self).setUp()
        self.cfg = self.useFixture(config_fixture.Config())
        self.switch = self._make_switch_device()
        self.ctxt = mock.MagicMock()

    def _make_switch_device(self, extra_cfg={}):
        patcher = mock.patch.object(
            netmiko_devices.netmiko, 'platforms', new=['base'])
        patcher.start()
        self.addCleanup(patcher.stop)
        device_cfg = {'device_type': 'netmiko_base',
                      'ip': 'host'}
        device_cfg.update(extra_cfg)
        switch = netmiko_devices.NetmikoSwitch(device_cfg)
        switch.ADD_NETWORK = (
            'add network {segmentation_id} {network_id} {network_name}',
        )
        switch.DELETE_NETWORK = (
            'delete network {segmentation_id} {network_id} {network_name}',
        )
        switch.PLUG_PORT_TO_NETWORK = (
            'plug port {port} to network {segmentation_id}',
        )
        switch.DELETE_PORT = (
            'delete port {port} from network {segmentation_id}',
        )
        switch.PLUG_BOND_TO_NETWORK = (
            'plug bond {bond} to network {segmentation_id}',
        )
        switch.UNPLUG_BOND_FROM_NETWORK = (
            'unplug bond {bond} from network {segmentation_id}',
        )
        switch.ADD_NETWORK_TO_TRUNK = (
            'add network {segmentation_id} to trunk {port}',
        )
        switch.REMOVE_NETWORK_FROM_TRUNK = (
            'remove network {segmentation_id} from trunk {port}',
        )
        switch.ENABLE_PORT = (
            'enable port {port}',
        )
        switch.DISABLE_PORT = (
            'disable port {port}',
        )
        switch.ENABLE_BOND = (
            'enable bond {bond}',
        )
        switch.DISABLE_BOND = (
            'disable bond {bond}',
        )
        switch.SET_NATIVE_VLAN = (
            'set native vlan to {segmentation_id} on port {port}',
        )
        switch.DELETE_NATIVE_VLAN = (
            'delete native vlan {segmentation_id} on port {port}',
        )
        switch.SET_NATIVE_VLAN_BOND = (
            'set native vlan to {segmentation_id} on bond {bond}',
        )
        switch.DELETE_NATIVE_VLAN_BOND = (
            'delete native vlan {segmentation_id} on bond {bond}',
        )
        switch.ADD_NETWORK_TO_BOND_TRUNK = (
            'add network {segmentation_id} to bond trunk {port}',
        )
        switch.DELETE_NETWORK_ON_BOND_TRUNK = (
            'delete network {segmentation_id} on bond trunk {port}',
        )
        switch.ADD_SECURITY_GROUP = (
            "add security group {security_group}",
        )
        switch.ADD_SECURITY_GROUP_COMPLETE = (
            "add security group complete",
        )
        switch.REMOVE_SECURITY_GROUP = (
            "remove security group {security_group}",
        )
        switch.ADD_SECURITY_GROUP_RULE_INGRESS = (
            "add ingress rule {protocol} "
            "source {remote_ip_prefix} "
            "port {port_range_min} to {port_range_max}",
        )
        switch.ADD_SECURITY_GROUP_RULE_EGRESS = (
            "add egress rule {protocol} "
            "source {remote_ip_prefix} "
            "port {port_range_min} to {port_range_max}",
        )
        switch.BIND_SECURITY_GROUP = (
            "bind security group {security_group} to port {port}",
        )
        switch.UNBIND_SECURITY_GROUP = (
            "unbind security group {security_group} from port {port}",
        )
        return switch


class TestNetmikoSwitch(NetmikoSwitchTestBase):

    def test_batch(self):
        self.cfg.config(backend_url='url', group='ngs_coordination')
        self._make_switch_device({'ngs_batch_requests': True})

    def test_batch_missing_backend_url(self):
        self.assertRaisesRegex(
            Exception, "switch configuration operation failed",
            self._make_switch_device, {'ngs_batch_requests': True})

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device',
                return_value='fake output', autospec=True)
    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.check_output', autospec=True)
    def test_add_network(self, m_check, m_sctd):
        self.switch.add_network(22, '0ae071f5-5be9-43e4-80ea-e41fefe85b21')
        m_sctd.assert_called_with(self.switch, [
            'add network 22 0ae071f55be943e480eae41fefe85b21 '
            '0ae071f55be943e480eae41fefe85b21'])
        m_check.assert_called_once_with(self.switch,
                                        'fake output', 'add network')

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device',
                return_value='fake output', autospec=True)
    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.check_output', autospec=True)
    def test_add_network_with_trunk_ports(self, m_check, m_sctd):
        switch = self._make_switch_device({'ngs_trunk_ports': 'port1, port2'})
        switch.add_network(22, '0ae071f5-5be9-43e4-80ea-e41fefe85b21')
        m_sctd.assert_called_with(switch, [
            'add network 22 0ae071f55be943e480eae41fefe85b21 '
            '0ae071f55be943e480eae41fefe85b21',
            'add network 22 to trunk port1',
            'add network 22 to trunk port2'
        ])
        m_check.assert_called_once_with(switch, 'fake output', 'add network')

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device',
                return_value='fake output', autospec=True)
    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.check_output', autospec=True)
    def test_add_network_with_no_manage_vlans(self, m_check, m_sctd):
        switch = self._make_switch_device({'ngs_manage_vlans': False})
        switch.add_network(22, '0ae071f5-5be9-43e4-80ea-e41fefe85b21')
        self.assertFalse(m_sctd.called)
        m_check.assert_called_once_with(switch, '', 'add network')

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device',
                return_value='fake output', autospec=True)
    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.check_output', autospec=True)
    def test_del_network(self, m_check, m_sctd):
        self.switch.del_network(22, '0ae071f5-5be9-43e4-80ea-e41fefe85b21')
        m_sctd.assert_called_with(self.switch, [
            'delete network 22 0ae071f55be943e480eae41fefe85b21 '
            '0ae071f55be943e480eae41fefe85b21'])
        m_check.assert_called_once_with(self.switch,
                                        'fake output', 'delete network')

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device',
                return_value='fake output', autospec=True)
    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.check_output', autospec=True)
    def test_del_network_with_trunk_ports(self, m_check, m_sctd):
        switch = self._make_switch_device({'ngs_trunk_ports': 'port1, port2'})
        switch.del_network(22, '0ae071f5-5be9-43e4-80ea-e41fefe85b21')
        m_sctd.assert_called_with(switch, [
            'remove network 22 from trunk port1',
            'remove network 22 from trunk port2',
            'delete network 22 0ae071f55be943e480eae41fefe85b21 '
            '0ae071f55be943e480eae41fefe85b21'])
        m_check.assert_called_once_with(switch,
                                        'fake output', 'delete network')

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device',
                return_value='fake output', autospec=True)
    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.check_output', autospec=True)
    def test_del_network_with_no_manage_vlans(self, m_check, m_sctd):
        switch = self._make_switch_device({'ngs_manage_vlans': False})
        switch.del_network(22, '0ae071f5-5be9-43e4-80ea-e41fefe85b21')
        self.assertFalse(m_sctd.called)
        m_check.assert_called_once_with(switch, '', 'delete network')

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device',
                return_value='fake output', autospec=True)
    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.check_output', autospec=True)
    def test_plug_port_to_network(self, m_check, m_sctd):
        self.switch.plug_port_to_network(2222, 22)
        m_sctd.assert_called_with(self.switch, [
            'plug port 2222 to network 22'])
        m_check.assert_called_once_with(self.switch,
                                        'fake output', 'plug port')

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device',
                return_value='fake output', autospec=True)
    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.check_output', autospec=True)
    def test_plug_port_has_default_vlan(self, m_check, m_sctd):
        switch = self._make_switch_device({'ngs_port_default_vlan': '20'})
        switch.plug_port_to_network(2222, 22)
        m_sctd.assert_called_with(switch, [
            'delete port 2222 from network 20',
            'plug port 2222 to network 22'
        ])
        m_check.assert_called_once_with(switch, 'fake output', 'plug port')

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device',
                return_value='fake output', autospec=True)
    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.check_output', autospec=True)
    def test_plug_port_to_network_disable_inactive(self, m_check, m_sctd):
        switch = self._make_switch_device(
            {'ngs_disable_inactive_ports': 'true'})
        switch.plug_port_to_network(2222, 22)
        m_sctd.assert_called_with(switch, [
            'enable port 2222',
            'plug port 2222 to network 22'
        ])
        m_check.assert_called_once_with(switch, 'fake output', 'plug port')

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device',
                return_value='fake output', autospec=True)
    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.check_output', autospec=True)
    def test_delete_port(self, m_check, m_sctd):
        self.switch.delete_port(2222, 22, trunk_details={})
        m_sctd.assert_called_with(self.switch, [
            'delete port 2222 from network 22'])
        m_check.assert_called_once_with(self.switch,
                                        'fake output', 'unplug port')

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device',
                return_value='fake output', autospec=True)
    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.check_output', autospec=True)
    def test_delete_port_has_default_vlan(self, m_check, m_sctd):
        switch = self._make_switch_device({'ngs_port_default_vlan': '20'})
        switch.delete_port(2222, 22, trunk_details={})
        m_sctd.assert_called_with(switch, [
            'delete port 2222 from network 22',
            'add network 20 20 20',
            'plug port 2222 to network 20'])
        m_check.assert_called_once_with(switch, 'fake output', 'unplug port')

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device',
                return_value='fake output', autospec=True)
    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.check_output', autospec=True)
    def test_delete_port_disable_inactive(self, m_check, m_sctd):
        switch = self._make_switch_device(
            {'ngs_disable_inactive_ports': 'true'})
        switch.delete_port(2222, 22)
        m_sctd.assert_called_with(switch, [
            'delete port 2222 from network 22',
            'disable port 2222'])
        m_check.assert_called_once_with(switch, 'fake output', 'unplug port')

    def test__validate_rule(self):
        empty_rule = mock.Mock(
            protocol=None,
            port_range_min=None,
            port_range_max=None,
        )
        rule = mock.Mock(
            protocol='tcp',
            port_range_min='8080',
            port_range_max='8088',
        )
        self.assertFalse(self.switch._validate_rule(empty_rule))
        self.assertTrue(self.switch._validate_rule(rule))
        self.switch.SUPPORT_SG_PORT_RANGE = False
        self.assertRaises(
            exc.GenericSwitchSecurityGroupRuleNotSupported,
            self.switch._validate_rule, rule)

    def test__prepare_security_group_rule(self):
        # empty rule
        rule = mock.Mock(
            ethertype=None,
            protocol=None,
            direction=None,
            remote_ip_prefix=None,
            normalized_cidr=None,
            port_range_min=None,
            port_range_max=None,
        )
        self.assertEqual(
            {
                'security_group': 'ngs-1234'
            },
            self.switch._prepare_security_group_rule('1234', rule)
        )
        # full rule
        rule = mock.Mock(
            ethertype='IPv4',
            protocol='tcp',
            direction='ingress',
            remote_ip_prefix='0.0.0.0/0',
            normalized_cidr='0.0.0.0/0',
            port_range_min='22',
            port_range_max='23'
        )
        self.assertEqual(
            {
                'direction': 'ingress',
                'ethertype': 'IPv4',
                'normalized_cidr': '0.0.0.0/0',
                'port_range_max': '23',
                'port_range_min': '22',
                'protocol': 'tcp',
                'remote_ip_prefix': '0.0.0.0/0',
                'security_group': 'ngs-1234'
            },
            self.switch._prepare_security_group_rule('1234', rule))

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device',
                return_value='fake output', autospec=True)
    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.check_output', autospec=True)
    def test_add_security_group(self, m_check, m_sctd):
        rule1 = mock.Mock(
            ethertype='IPv4',
            protocol='tcp',
            direction='ingress',
            remote_ip_prefix='0.0.0.0/0',
            normalized_cidr='0.0.0.0/0',
            port_range_min='22',
            port_range_max='23'
        )
        rule2 = mock.Mock(
            ethertype='IPv4',
            protocol='tcp',
            direction='egress',
            remote_ip_prefix='0.0.0.0/0',
            normalized_cidr='0.0.0.0/0',
            port_range_min='80',
            port_range_max='80'
        )
        sg = mock.Mock()
        sg.id = '1234'
        sg.rules = [rule1, rule2]
        switch = self._make_switch_device(
            {'ngs_disable_inactive_ports': 'true'})
        switch.add_security_group(sg)
        m_sctd.assert_called_with(switch, [
            'add security group ngs-1234',
            'add ingress rule tcp source 0.0.0.0/0 '
            'port 22 to 23',
            'add egress rule tcp source 0.0.0.0/0 '
            'port 80 to 80',
            'add security group complete'])
        m_check.assert_called_once_with(switch, 'fake output',
                                        'add security group')

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device',
                return_value='fake output', autospec=True)
    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.check_output', autospec=True)
    def test_add_security_group_no_range(self, m_check, m_sctd):
        rule1 = mock.Mock(
            ethertype='IPv4',
            protocol='tcp',
            direction='ingress',
            remote_ip_prefix='0.0.0.0/0',
            normalized_cidr='0.0.0.0/0',
            port_range_min='22',
            port_range_max='23'
        )
        rule2 = mock.Mock(
            ethertype='IPv4',
            protocol='tcp',
            direction='egress',
            remote_ip_prefix='0.0.0.0/0',
            normalized_cidr='0.0.0.0/0',
            port_range_min='80',
            port_range_max='80'
        )
        sg = mock.Mock()
        sg.id = '1234'
        sg.rules = [rule1, rule2]
        switch = self._make_switch_device(
            {'ngs_disable_inactive_ports': 'true'})

        switch.SUPPORT_SG_PORT_RANGE = False
        self.assertRaises(
            exc.GenericSwitchSecurityGroupRuleNotSupported,
            switch.add_security_group, sg)
        m_sctd.assert_not_called()
        m_check.assert_not_called()

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device',
                return_value='fake output', autospec=True)
    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.check_output', autospec=True)
    def test_add_security_group_no_egress(self, m_check, m_sctd):
        rule1 = mock.Mock(
            ethertype='IPv4',
            protocol='tcp',
            direction='ingress',
            remote_ip_prefix='0.0.0.0/0',
            normalized_cidr='0.0.0.0/0',
            port_range_min='22',
            port_range_max='23'
        )
        rule2 = mock.Mock(
            ethertype='IPv4',
            protocol='tcp',
            direction='egress',
            remote_ip_prefix='0.0.0.0/0',
            normalized_cidr='0.0.0.0/0',
            port_range_min='80',
            port_range_max='80'
        )
        sg = mock.Mock()
        sg.id = '1234'
        sg.rules = [rule1, rule2]
        switch = self._make_switch_device(
            {'ngs_disable_inactive_ports': 'true'})
        switch.ADD_SECURITY_GROUP_RULE_EGRESS = None

        self.assertRaises(
            NotImplementedError,
            switch.add_security_group, sg)
        m_sctd.assert_not_called()
        m_check.assert_not_called()

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device',
                return_value='fake output', autospec=True)
    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.check_output', autospec=True)
    def test_del_security_group(self, m_check, m_sctd):
        switch = self._make_switch_device(
            {'ngs_disable_inactive_ports': 'true'})
        switch.del_security_group('1234')
        m_sctd.assert_called_with(switch, ['remove security group ngs-1234'])
        m_check.assert_called_once_with(switch, 'fake output',
                                        'delete security group')

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device',
                return_value='fake output', autospec=True)
    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.check_output', autospec=True)
    def test_bind_security_group(self, m_check, m_sctd):
        sg = mock.Mock()
        sg.id = '1234'
        sg.rules = []
        switch = self._make_switch_device(
            {'ngs_disable_inactive_ports': 'true'})
        switch.bind_security_group(sg, 'port1', ['port1', 'port2'])
        m_sctd.assert_called_with(switch, [
            'remove security group ngs-1234',
            'add security group ngs-1234',
            'add security group complete',
            'bind security group ngs-1234 to port port1',
            'bind security group ngs-1234 to port port2'])
        m_check.assert_called_once_with(switch, 'fake output',
                                        'bind security group')

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.send_commands_to_device',
                return_value='fake output', autospec=True)
    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.check_output', autospec=True)
    def test_unbind_security_group(self, m_check, m_sctd):
        switch = self._make_switch_device(
            {'ngs_disable_inactive_ports': 'true'})
        switch.unbind_security_group('1234', 'port1', ['port2'])
        m_sctd.assert_called_with(switch, [
            'unbind security group ngs-1234 from port port1',
            'bind security group ngs-1234 to port port2'])
        m_check.assert_called_once_with(switch, 'fake output',
                                        'unbind security group')

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.plug_port_to_network',
                return_value='fake output', autospec=True)
    def test_plug_bond_to_network_fallback(self, m_plug):
        self.switch.PLUG_BOND_TO_NETWORK = None
        self.switch.plug_bond_to_network(2222, 22)
        m_plug.assert_called_with(self.switch, 2222, 22, trunk_details=None)

    @mock.patch('networking_generic_switch.devices.netmiko_devices.'
                'NetmikoSwitch.delete_port',
                return_value='fake output', autospec=True)
    def test_unplug_bond_from_network_fallback(self, m_delete):
        self.switch.UNPLUG_BOND_FROM_NETWORK = None
        self.switch.unplug_bond_from_network(2222, 22)
        m_delete.assert_called_with(self.switch, 2222, 22, trunk_details=None)

    def test__format_commands(self):
        self.switch.ADD_NETWORK = (
            'add network {segmentation_id} {network_id}',
        )
        cmds = self.switch._format_commands(
            self.switch.ADD_NETWORK,
            segmentation_id=22, network_id=22)
        self.assertEqual(['add network 22 22'], cmds)

    @mock.patch.object(netmiko_devices.tenacity, 'wait_fixed',
                       return_value=tenacity.wait_fixed(0.01), autospec=True)
    @mock.patch.object(netmiko_devices.tenacity, 'stop_after_delay',
                       return_value=tenacity.stop_after_delay(0.1),
                       autospec=True)
    @mock.patch.object(netmiko, 'ConnectHandler', autospec=True)
    def test__get_connection_connect_fail(self, m_conn_handler,
                                          m_stop, m_wait):
        m_conn = mock.MagicMock()
        m_conn_handler.side_effect = [
            paramiko.SSHException, m_conn]
        with self.switch._get_connection() as conn:
            self.assertEqual(conn, m_conn)
        m_stop.assert_called_once_with(60)
        m_wait.assert_called_once_with(10)

    @mock.patch.object(netmiko_devices.tenacity, 'wait_fixed',
                       return_value=tenacity.wait_fixed(0.01), autospec=True)
    @mock.patch.object(netmiko_devices.tenacity, 'stop_after_delay',
                       return_value=tenacity.stop_after_delay(0.1),
                       autospec=True)
    @mock.patch.object(netmiko, 'ConnectHandler', autospec=True)
    def test__get_connection_timeout(self, m_conn_handler, m_stop, m_wait):
        switch = self._make_switch_device({'ngs_ssh_connect_timeout': '1',
                                           'ngs_ssh_connect_interval': '1'})
        m_conn_handler.side_effect = (
            paramiko.SSHException)

        def get_connection():
            with switch._get_connection():
                self.fail()

        self.assertRaises(exc.GenericSwitchNetmikoConnectError, get_connection)
        m_stop.assert_called_once_with(1)
        m_wait.assert_called_once_with(1)

    @mock.patch.object(netmiko_devices.tenacity, 'wait_fixed',
                       return_value=tenacity.wait_fixed(0.01), autospec=True)
    @mock.patch.object(netmiko_devices.tenacity, 'stop_after_delay',
                       return_value=tenacity.stop_after_delay(0.1),
                       autospec=True)
    @mock.patch.object(netmiko, 'ConnectHandler', autospec=True)
    def test__get_connection_caller_failure(self, m_conn_handler,
                                            m_stop, m_wait):
        m_conn = mock.MagicMock()
        m_conn_handler.return_value = m_conn

        class FakeError(Exception):
            pass

        def get_connection():
            with self.switch._get_connection():
                raise FakeError()

        self.assertRaises(FakeError, get_connection)
        m_conn.__exit__.assert_called_once_with(mock.ANY, mock.ANY, mock.ANY)

    @mock.patch.object(netmiko_devices.NetmikoSwitch, '_get_connection',
                       autospec=True)
    def test_send_commands_to_device_empty(self, gc_mock):
        connect_mock = mock.MagicMock()
        gc_mock.return_value.__enter__.return_value = connect_mock
        self.assertIsNone(self.switch.send_commands_to_device([]))
        self.assertFalse(connect_mock.send_config_set.called)
        self.assertFalse(connect_mock.send_command.called)

    @mock.patch.object(netmiko_devices.NetmikoSwitch, '_get_connection',
                       autospec=True)
    @mock.patch.object(netmiko_devices.NetmikoSwitch, 'send_config_set',
                       autospec=True)
    @mock.patch.object(netmiko_devices.NetmikoSwitch, 'save_configuration',
                       autospec=True)
    def test_send_commands_to_device(self, save_mock, send_mock, gc_mock):
        connect_mock = mock.MagicMock(netmiko.base_connection.BaseConnection)
        gc_mock.return_value.__enter__.return_value = connect_mock
        send_mock.return_value = 'fake output'
        result = self.switch.send_commands_to_device(['spam ham aaaa'])
        send_mock.assert_called_once_with(self.switch,
                                          connect_mock, ['spam ham aaaa'])
        self.assertEqual('fake output', result)
        save_mock.assert_called_once_with(self.switch, connect_mock)

    @mock.patch.object(netmiko_devices.NetmikoSwitch, '_get_connection',
                       autospec=True)
    @mock.patch.object(netmiko_devices.NetmikoSwitch, 'send_config_set',
                       autospec=True)
    @mock.patch.object(netmiko_devices.NetmikoSwitch, 'save_configuration',
                       autospec=True)
    def test_send_commands_to_device_without_save_config(self, save_mock,
                                                         send_mock, gc_mock):
        switch = self._make_switch_device(
            extra_cfg={'ngs_save_configuration': False})
        connect_mock = mock.MagicMock(netmiko.base_connection.BaseConnection)
        gc_mock.return_value.__enter__.return_value = connect_mock
        send_mock.return_value = 'fake output'
        result = switch.send_commands_to_device(['spam ham aaaa'])
        send_mock.assert_called_once_with(switch,
                                          connect_mock, ['spam ham aaaa'])
        self.assertEqual('fake output', result)
        save_mock.assert_not_called()

    def test_send_config_set(self):
        connect_mock = mock.MagicMock(netmiko.base_connection.BaseConnection)
        connect_mock.send_config_set.return_value = 'fake output'
        result = self.switch.send_config_set(connect_mock, ['spam ham aaaa'])
        connect_mock.enable.assert_called_once_with()
        connect_mock.send_config_set.assert_called_once_with(
            config_commands=['spam ham aaaa'], cmd_verify=False)
        self.assertEqual('fake output', result)

    @mock.patch.object(netmiko_devices.NetmikoSwitch, '_get_connection',
                       autospec=True)
    def test_send_commands_to_device_send_failure(self, gc_mock):
        connect_mock = mock.MagicMock(netmiko.base_connection.BaseConnection)
        gc_mock.return_value.__enter__.return_value = connect_mock

        class FakeError(Exception):
            pass
        connect_mock.send_config_set.side_effect = FakeError
        self.assertRaises(exc.GenericSwitchNetmikoConnectError,
                          self.switch.send_commands_to_device,
                          ['spam ham aaaa'])
        connect_mock.send_config_set.assert_called_once_with(
            config_commands=['spam ham aaaa'], cmd_verify=False)

    @mock.patch.object(netmiko_devices.NetmikoSwitch, '_get_connection',
                       autospec=True)
    def test_send_commands_to_device_send_ngs_failure(self, gc_mock):
        connect_mock = mock.MagicMock(netmiko.base_connection.BaseConnection)
        gc_mock.return_value.__enter__.return_value = connect_mock

        class NGSFakeError(exc.GenericSwitchException):
            pass
        connect_mock.send_config_set.side_effect = NGSFakeError
        self.assertRaises(NGSFakeError, self.switch.send_commands_to_device,
                          ['spam ham aaaa'])
        connect_mock.send_config_set.assert_called_once_with(
            config_commands=['spam ham aaaa'], cmd_verify=False)

    @mock.patch.object(netmiko_devices.NetmikoSwitch, '_get_connection',
                       autospec=True)
    @mock.patch.object(netmiko_devices.NetmikoSwitch, 'save_configuration',
                       autospec=True)
    def test_send_commands_to_device_save_failure(self, save_mock, gc_mock):
        connect_mock = mock.MagicMock(netmiko.base_connection.BaseConnection)
        gc_mock.return_value.__enter__.return_value = connect_mock

        class FakeError(Exception):
            pass
        save_mock.side_effect = FakeError
        self.assertRaises(exc.GenericSwitchNetmikoConnectError,
                          self.switch.send_commands_to_device,
                          ['spam ham aaaa'])
        connect_mock.send_config_set.assert_called_once_with(
            config_commands=['spam ham aaaa'], cmd_verify=False)
        save_mock.assert_called_once_with(self.switch, connect_mock)

    @mock.patch.object(netmiko_devices.NetmikoSwitch, '_get_connection',
                       autospec=True)
    @mock.patch.object(netmiko_devices.NetmikoSwitch, 'save_configuration',
                       autospec=True)
    def test_send_commands_to_device_save_ngs_failure(self, save_mock,
                                                      gc_mock):
        connect_mock = mock.MagicMock(netmiko.base_connection.BaseConnection)
        gc_mock.return_value.__enter__.return_value = connect_mock

        class NGSFakeError(exc.GenericSwitchException):
            pass
        save_mock.side_effect = NGSFakeError
        self.assertRaises(NGSFakeError, self.switch.send_commands_to_device,
                          ['spam ham aaaa'])
        connect_mock.send_config_set.assert_called_once_with(
            config_commands=['spam ham aaaa'], cmd_verify=False)
        save_mock.assert_called_once_with(self.switch, connect_mock)

    def test_save_configuration(self):
        connect_mock = mock.MagicMock(netmiko.base_connection.BaseConnection,
                                      autospec=True)
        self.switch.save_configuration(connect_mock)
        connect_mock.save_config.assert_called_once_with()

    @mock.patch.object(netmiko_devices.NetmikoSwitch, 'SAVE_CONFIGURATION',
                       ('save', 'y'))
    def test_save_configuration_with_NotImplementedError(self):
        connect_mock = mock.MagicMock(netmiko.base_connection.BaseConnection)

        def fake_save_config():
            raise NotImplementedError
        connect_mock.save_config = fake_save_config
        self.switch.save_configuration(connect_mock)
        connect_mock.send_command.assert_has_calls([mock.call('save'),
                                                    mock.call('y')])

    @mock.patch.object(utils, 'get_hostname', autospec=True)
    @mock.patch.object(netmiko_devices.ngs_lock, 'PoolLock', autospec=True)
    @mock.patch.object(netmiko_devices.netmiko, 'ConnectHandler',
                       autospec=True)
    @mock.patch.object(coordination, 'get_coordinator', autospec=True)
    def test_switch_send_commands_with_coordinator(self, get_coord_mock,
                                                   nm_mock, lock_mock,
                                                   mock_hostname):
        self.cfg.config(acquire_timeout=120, backend_url='mysql://localhost',
                        group='ngs_coordination')
        coord = mock.Mock()
        get_coord_mock.return_value = coord
        mock_hostname.return_value = 'viking'
        switch = self._make_switch_device(
            extra_cfg={'ngs_max_connections': 2})
        self.assertEqual(coord, switch.locker)
        get_coord_mock.assert_called_once_with('mysql://localhost',
                                               'ngs-viking'.encode('ascii'))

        connect_mock = mock.MagicMock(SAVE_CONFIGURATION=None)
        connect_mock.__enter__.return_value = connect_mock
        nm_mock.return_value = connect_mock
        lock_mock.return_value.__enter__.return_value = lock_mock
        switch.send_commands_to_device(['spam ham'])

        lock_mock.assert_called_once_with(coord, locks_pool_size=2,
                                          locks_prefix='host',
                                          timeout=120)
        lock_mock.return_value.__exit__.assert_called_once()
        lock_mock.return_value.__enter__.assert_called_once()
        mock_hostname.assert_called_once()

    def test_check_output(self):
        self.switch.check_output('fake output', 'fake op')

    def test_check_output_error(self):
        self.switch.ERROR_MSG_PATTERNS = (re.compile('fake error message'),)
        output = """
fake switch command
fake error message
"""
        self.assertRaisesRegex(exc.GenericSwitchNetmikoConfigError,
                               "switch configuration operation failed",
                               self.switch.check_output, output, 'fake op')
