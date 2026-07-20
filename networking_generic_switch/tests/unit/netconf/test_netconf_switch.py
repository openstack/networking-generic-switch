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

import unittest
from unittest import mock
from xml.etree import ElementTree

import fixtures
from ncclient import manager
from ncclient.operations.rpc import RPCError
from ncclient.transport.errors import AuthenticationError
from ncclient.transport.errors import SSHError
from oslo_config import fixture as config_fixture
from tooz import coordination

from networking_generic_switch.devices.netconf_devices import (
    constants as ncconst)
from networking_generic_switch.devices.netconf_devices import netconf_switch
from networking_generic_switch.devices import utils as device_utils
from networking_generic_switch import exceptions as exc
from networking_generic_switch import locking as ngs_lock
from networking_generic_switch.yang_models.openconfig.interfaces \
    import interfaces


def _make_rpc_error(tag, message=None):
    """Build a minimal RPCError from an XML element."""
    ns = 'urn:ietf:params:xml:ns:netconf:base:1.0'
    root = ElementTree.Element('{%s}rpc-error' % ns)
    tag_el = ElementTree.SubElement(root, '{%s}error-tag' % ns)
    tag_el.text = tag
    if message:
        msg_el = ElementTree.SubElement(root, '{%s}error-message' % ns)
        msg_el.text = message
    return RPCError(root)


DEVICE_CFG_MINIMAL = {
    'device_type': 'netconf_openconfig',
    'host': 'switch.example.com',
    'username': 'admin',
    'port': '830',
    'key_filename': '/test/test_key',
    'password': 'secret',
    'hostkey_verify': 'false',
    'device_params': {'name': 'default'},
    'ngs_manage_vlans': True,
    'ngs_network_name_format': '{network_id}',
    'ngs_max_connections': 1,
}


def _make_switch(extra_cfg=None):
    cfg = dict(DEVICE_CFG_MINIMAL)
    if extra_cfg:
        cfg.update(extra_cfg)
    return netconf_switch.NetconfSwitch(cfg, device_name='test-switch')


class TestNetconfSwitchInit(unittest.TestCase):

    def test_ncclient_args_built(self):
        switch = _make_switch()
        args = switch._ncclient_args
        self.assertEqual(args['host'], 'switch.example.com')
        self.assertEqual(args['port'], 830)
        self.assertEqual(args['username'], 'admin')
        self.assertFalse(args['hostkey_verify'])
        self.assertEqual(args['device_params'], {'name': 'default'})
        self.assertTrue(args['use_libssh'])
        self.assertEqual(args['key_filename'], '/test/test_key')
        self.assertEqual(args['password'], 'secret')

    def test_trunk_vlans_converge_is_true(self):
        switch = _make_switch()
        self.assertTrue(switch.trunk_vlans_converge)

    def test_confirmed_commit_timeout_too_low(self):
        self.assertRaises(
            exc.GenericSwitchConfigException,
            _make_switch,
            {'ngs_netconf_confirmed_commit_timeout': '0'})

    def test_confirmed_commit_timeout_too_high(self):
        self.assertRaises(
            exc.GenericSwitchConfigException,
            _make_switch,
            {'ngs_netconf_confirmed_commit_timeout': '31'})

    def test_ncclient_args_defaults(self):
        cfg = {
            'device_type': 'netconf_openconfig',
            'host': 'switch.example.com',
            'username': 'admin',
            'ngs_manage_vlans': True,
            'ngs_network_name_format': '{network_id}',
            'ngs_max_connections': 1,
        }
        switch = netconf_switch.NetconfSwitch(cfg, device_name='test')
        args = switch._ncclient_args
        self.assertEqual(args['port'], 830)
        self.assertTrue(args['hostkey_verify'])
        self.assertTrue(args['allow_agent'])
        self.assertTrue(args['use_libssh'])
        self.assertNotIn('key_filename', args)
        self.assertNotIn('password', args)


class TestProcessCapabilities(unittest.TestCase):

    def test_iana_capabilities(self):
        fake_caps = set(ncconst.IANA_NETCONF_CAPABILITIES.values())
        result = netconf_switch.NetconfSwitch.process_capabilities(fake_caps)
        for key in ncconst.IANA_NETCONF_CAPABILITIES:
            self.assertIn(key, result)

    def test_openconfig_capabilities(self):
        fake_caps = {
            'http://openconfig.net/yang/interfaces?'
            'module=openconfig-interfaces&revision=2021-04-06',
            'http://openconfig.net/yang/network-instance?'
            'module=openconfig-network-instance&revision=2021-07-22',
        }
        result = netconf_switch.NetconfSwitch.process_capabilities(fake_caps)
        self.assertIn('openconfig-interfaces', result)
        self.assertIn('openconfig-network-instance', result)

    def test_mixed_capabilities(self):
        fake_caps = set(ncconst.IANA_NETCONF_CAPABILITIES.values())
        fake_caps.add(
            'http://openconfig.net/yang/interfaces?'
            'module=openconfig-interfaces&revision=2021-04-06')
        result = netconf_switch.NetconfSwitch.process_capabilities(fake_caps)
        self.assertIn(':candidate', result)
        self.assertIn('openconfig-interfaces', result)


class TestGetCapabilities(unittest.TestCase):

    @mock.patch.object(manager, 'connect', autospec=True)
    def test_get_capabilities(self, mock_manager):
        switch = _make_switch()
        fake_caps = set(ncconst.IANA_NETCONF_CAPABILITIES.values())
        mock_ncclient = mock.Mock()
        mock_ncclient.server_capabilities = fake_caps
        mock_manager.return_value.__enter__.return_value = mock_ncclient
        caps = switch.get_capabilities()
        for key in ncconst.IANA_NETCONF_CAPABILITIES:
            self.assertIn(key, caps)

    @mock.patch.object(manager, 'connect', autospec=True)
    def test_get_capabilities_ssh_error(self, mock_manager):
        switch = _make_switch()
        mock_manager.return_value.__enter__.side_effect = SSHError('fail')
        self.assertRaises(
            exc.GenericSwitchNetconfConnectError, switch.get_capabilities)

    @mock.patch.object(manager, 'connect', autospec=True)
    def test_get_capabilities_auth_error(self, mock_manager):
        switch = _make_switch()
        mock_manager.return_value.__enter__.side_effect = (
            AuthenticationError('fail'))
        self.assertRaises(
            exc.GenericSwitchNetconfConnectError, switch.get_capabilities)


class TestGetFromDevice(unittest.TestCase):

    @mock.patch.object(manager, 'connect', autospec=True)
    def test_get_from_device(self, mock_manager):
        switch = _make_switch()
        fake_query = interfaces.Interfaces()
        fake_query.add('foo1/1')
        mock_ncclient = mock.Mock()
        mock_manager.return_value.__enter__.return_value = mock_ncclient
        switch.get_from_device(fake_query)
        mock_ncclient.get.assert_called_once_with(
            filter=('subtree', mock.ANY))


class TestLockAndConfigure(unittest.TestCase):

    def test_confirmed_commit(self):
        switch = _make_switch()
        switch.capabilities = {':candidate', ':writable-running',
                               ':confirmed-commit'}
        fake_config = mock.Mock()
        fake_config.to_xml_element.return_value = ElementTree.Element('fake')
        mock_client = mock.MagicMock()
        switch._lock_and_configure(
            mock_client, ncconst.CANDIDATE, [fake_config])
        mock_client.locked.assert_called_with(ncconst.CANDIDATE)
        mock_client.discard_changes.assert_called_once()
        mock_client.edit_config.assert_called_with(
            target=ncconst.CANDIDATE,
            config='<config><fake /></config>')
        mock_client.validate.assert_not_called()
        mock_client.commit.assert_has_calls([
            mock.call(confirmed=True, timeout=str(5)), mock.call()])

    def test_confirmed_commit_disabled(self):
        switch = _make_switch({'ngs_netconf_confirmed_commit': 'false'})
        switch.capabilities = {':candidate', ':writable-running',
                               ':confirmed-commit'}
        fake_config = mock.Mock()
        fake_config.to_xml_element.return_value = ElementTree.Element('fake')
        mock_client = mock.MagicMock()
        switch._lock_and_configure(
            mock_client, ncconst.CANDIDATE, [fake_config])
        mock_client.commit.assert_called_once_with()

    def test_confirmed_commit_custom_timeout(self):
        switch = _make_switch(
            {'ngs_netconf_confirmed_commit_timeout': '10'})
        switch.capabilities = {':candidate', ':writable-running',
                               ':confirmed-commit'}
        fake_config = mock.Mock()
        fake_config.to_xml_element.return_value = ElementTree.Element('fake')
        mock_client = mock.MagicMock()
        switch._lock_and_configure(
            mock_client, ncconst.CANDIDATE, [fake_config])
        mock_client.commit.assert_has_calls([
            mock.call(confirmed=True, timeout='10'), mock.call()])

    def test_validate(self):
        switch = _make_switch()
        switch.capabilities = {':candidate', ':writable-running',
                               ':validate'}
        fake_config = mock.Mock()
        fake_config.to_xml_element.return_value = ElementTree.Element('fake')
        mock_client = mock.MagicMock()
        switch._lock_and_configure(
            mock_client, ncconst.CANDIDATE, [fake_config])
        mock_client.locked.assert_called_with(ncconst.CANDIDATE)
        mock_client.discard_changes.assert_called_once()
        mock_client.edit_config.assert_called_with(
            target=ncconst.CANDIDATE,
            config='<config><fake /></config>')
        mock_client.validate.assert_called_once_with(source='candidate')
        mock_client.commit.assert_called_once_with()

    def test_writable_running(self):
        switch = _make_switch()
        switch.capabilities = {':writable-running'}
        fake_config = mock.Mock()
        fake_config.to_xml_element.return_value = ElementTree.Element('fake')
        mock_client = mock.MagicMock()
        with mock.patch.object(switch, '_save_running_config',
                               autospec=True) as mock_save:
            switch._lock_and_configure(
                mock_client, ncconst.RUNNING, [fake_config])
        mock_client.locked.assert_called_with(ncconst.RUNNING)
        mock_client.discard_changes.assert_not_called()
        mock_client.validate.assert_not_called()
        mock_client.commit.assert_not_called()
        mock_client.edit_config.assert_called_with(
            target=ncconst.RUNNING,
            config='<config><fake /></config>')
        mock_save.assert_called_once_with(mock_client)

    def test_writable_running_no_save_when_disabled(self):
        switch = _make_switch({'ngs_save_configuration': 'false'})
        switch.capabilities = {':writable-running'}
        fake_config = mock.Mock()
        fake_config.to_xml_element.return_value = ElementTree.Element('fake')
        mock_client = mock.MagicMock()
        with mock.patch.object(switch, '_save_running_config',
                               autospec=True) as mock_save:
            switch._lock_and_configure(
                mock_client, ncconst.RUNNING, [fake_config])
        mock_client.edit_config.assert_called_once()
        mock_save.assert_not_called()

    @mock.patch('tenacity.nap.time', autospec=True)
    @mock.patch.object(netconf_switch, 'LOG', autospec=True)
    def test_operation_failed_raises_retryable_exception(self, mock_log,
                                                         mock_tenacity_nap):
        switch = _make_switch()
        switch.capabilities = {':candidate'}
        fake_config = mock.Mock()
        fake_config.to_xml_element.return_value = ElementTree.Element('fake')
        mock_client = mock.MagicMock()
        rpc_err = _make_rpc_error(ncconst.OPERATION_FAILED_TAG,
                                  'Operation failed')
        mock_client.commit.side_effect = rpc_err
        self.assertRaises(
            exc.GenericSwitchNetconfOperationFailed,
            switch._lock_and_configure,
            mock_client, ncconst.CANDIDATE, [fake_config])
        mock_log.warning.assert_any_call(
            'Netconf device %(dev)s returned operation-failed, '
            'retrying: %(msg)s',
            {'dev': 'test-switch', 'msg': 'Operation failed'})

    @mock.patch('tenacity.nap.time', autospec=True)
    def test_operation_failed_is_retried(self, mock_tenacity_nap):
        switch = _make_switch()
        switch.capabilities = {':candidate'}
        fake_config = mock.Mock()
        fake_config.to_xml_element.return_value = ElementTree.Element('fake')
        rpc_err = _make_rpc_error(ncconst.OPERATION_FAILED_TAG,
                                  'Operation failed')
        mock_client = mock.MagicMock()
        mock_client.commit.side_effect = [rpc_err, None, None]
        switch._lock_and_configure(
            mock_client, ncconst.CANDIDATE, [fake_config])
        self.assertEqual(2, mock_client.commit.call_count)

    def test_unknown_rpc_error_not_retried(self):
        switch = _make_switch()
        switch.capabilities = {':candidate'}
        fake_config = mock.Mock()
        fake_config.to_xml_element.return_value = ElementTree.Element('fake')
        rpc_err = _make_rpc_error('data-exists')
        mock_client = mock.MagicMock()
        mock_client.commit.side_effect = rpc_err
        self.assertRaises(
            RPCError,
            switch._lock_and_configure,
            mock_client, ncconst.CANDIDATE, [fake_config])


class TestSaveRunningConfig(unittest.TestCase):

    SAVE_CONFIG = ('<config><commands xmlns="http://example.com/yang/cli">'
                   '<command>write memory</command>'
                   '</commands></config>')

    def test_edit_config_save(self):
        switch = _make_switch({'ngs_netconf_save_config': self.SAVE_CONFIG})
        switch.capabilities = {':writable-running'}
        mock_client = mock.MagicMock()
        switch._save_running_config(mock_client)
        mock_client.edit_config.assert_called_once_with(
            target=ncconst.RUNNING, config=self.SAVE_CONFIG)
        mock_client.copy_config.assert_not_called()

    def test_fallback_to_startup_copy(self):
        switch = _make_switch()
        switch.capabilities = {':writable-running', ':startup'}
        mock_client = mock.MagicMock()
        switch._save_running_config(mock_client)
        mock_client.copy_config.assert_called_once_with(
            source=ncconst.RUNNING, target=ncconst.STARTUP)
        mock_client.edit_config.assert_not_called()

    def test_save_config_takes_priority_over_startup(self):
        switch = _make_switch({'ngs_netconf_save_config': self.SAVE_CONFIG})
        switch.capabilities = {':writable-running', ':startup'}
        mock_client = mock.MagicMock()
        switch._save_running_config(mock_client)
        mock_client.edit_config.assert_called_once_with(
            target=ncconst.RUNNING, config=self.SAVE_CONFIG)
        mock_client.copy_config.assert_not_called()

    def test_warning_when_no_save_mechanism(self):
        switch = _make_switch()
        switch.capabilities = {':writable-running'}
        mock_client = mock.MagicMock()
        switch._save_running_config(mock_client)
        mock_client.edit_config.assert_not_called()
        mock_client.copy_config.assert_not_called()


class TestGetDatastoreTarget(unittest.TestCase):

    def test_auto_detect_candidate(self):
        switch = _make_switch()
        switch.capabilities = {':candidate', ':writable-running'}
        self.assertEqual(ncconst.CANDIDATE, switch._get_datastore_target())

    def test_auto_detect_writable_running(self):
        switch = _make_switch()
        switch.capabilities = {':writable-running'}
        self.assertEqual(ncconst.RUNNING, switch._get_datastore_target())

    def test_auto_detect_no_capabilities(self):
        switch = _make_switch()
        switch.capabilities = set()
        self.assertIsNone(switch._get_datastore_target())

    def test_force_running(self):
        switch = _make_switch({'ngs_netconf_target': 'running'})
        switch.capabilities = {':candidate', ':writable-running'}
        self.assertEqual(ncconst.RUNNING, switch._get_datastore_target())

    def test_force_candidate(self):
        switch = _make_switch({'ngs_netconf_target': 'candidate'})
        switch.capabilities = {':candidate', ':writable-running'}
        self.assertEqual(ncconst.CANDIDATE, switch._get_datastore_target())

    def test_invalid_target_raises(self):
        self.assertRaises(
            exc.GenericSwitchConfigException,
            _make_switch, {'ngs_netconf_target': 'bogus'})


class TestSendConfigToDevice(unittest.TestCase):

    @mock.patch.object(manager, 'connect', autospec=True)
    @mock.patch.object(netconf_switch.NetconfSwitch,
                       '_lock_and_configure', autospec=True)
    def test_candidate_dispatch(self, mock_lock_config, mock_manager):
        switch = _make_switch()
        fake_config = mock.Mock()
        fake_config.to_xml_element.return_value = ElementTree.Element('fake')
        mock_ncclient = mock.Mock()
        fake_caps = {ncconst.IANA_NETCONF_CAPABILITIES[':candidate']}
        mock_ncclient.server_capabilities = fake_caps
        mock_manager.return_value.__enter__.return_value = mock_ncclient
        switch.send_config_to_device(fake_config)
        mock_lock_config.assert_called_once_with(
            switch, mock_ncclient, ncconst.CANDIDATE, [fake_config])

    @mock.patch.object(manager, 'connect', autospec=True)
    @mock.patch.object(netconf_switch.NetconfSwitch,
                       '_lock_and_configure', autospec=True)
    def test_writable_running_dispatch(self, mock_lock_config, mock_manager):
        switch = _make_switch()
        fake_config = mock.Mock()
        fake_config.to_xml_element.return_value = ElementTree.Element('fake')
        mock_ncclient = mock.Mock()
        fake_caps = {ncconst.IANA_NETCONF_CAPABILITIES[':writable-running']}
        mock_ncclient.server_capabilities = fake_caps
        mock_manager.return_value.__enter__.return_value = mock_ncclient
        switch.send_config_to_device(fake_config)
        mock_lock_config.assert_called_once_with(
            switch, mock_ncclient, ncconst.RUNNING, [fake_config])

    @mock.patch.object(manager, 'connect', autospec=True)
    @mock.patch.object(netconf_switch.NetconfSwitch,
                       '_lock_and_configure', autospec=True)
    def test_force_running_overrides_candidate(self, mock_lock_config,
                                               mock_manager):
        switch = _make_switch({'ngs_netconf_target': 'running'})
        fake_config = mock.Mock()
        fake_config.to_xml_element.return_value = ElementTree.Element('fake')
        mock_ncclient = mock.Mock()
        fake_caps = {ncconst.IANA_NETCONF_CAPABILITIES[':candidate'],
                     ncconst.IANA_NETCONF_CAPABILITIES[':writable-running']}
        mock_ncclient.server_capabilities = fake_caps
        mock_manager.return_value.__enter__.return_value = mock_ncclient
        switch.send_config_to_device(fake_config)
        mock_lock_config.assert_called_once_with(
            switch, mock_ncclient, ncconst.RUNNING, [fake_config])

    @mock.patch.object(manager, 'connect', autospec=True)
    @mock.patch.object(netconf_switch.NetconfSwitch,
                       '_lock_and_configure', autospec=True)
    def test_list_config_preserved(self, mock_lock_config, mock_manager):
        switch = _make_switch()
        fake_a = mock.Mock()
        fake_a.to_xml_element.return_value = ElementTree.Element('a')
        fake_b = mock.Mock()
        fake_b.to_xml_element.return_value = ElementTree.Element('b')
        mock_ncclient = mock.Mock()
        fake_caps = {ncconst.IANA_NETCONF_CAPABILITIES[':candidate']}
        mock_ncclient.server_capabilities = fake_caps
        mock_manager.return_value.__enter__.return_value = mock_ncclient
        switch.send_config_to_device([fake_a, fake_b])
        mock_lock_config.assert_called_once_with(
            switch, mock_ncclient, ncconst.CANDIDATE,
            [fake_a, fake_b])


class TestGetLockSessionId(unittest.TestCase):

    def test_parse_session_id_zero(self):
        err_info = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<error-info xmlns="urn:ietf:params:xml:ns:netconf:base:1.0">'
            '<session-id>0</session-id>'
            '</error-info>')
        self.assertEqual(
            '0', netconf_switch.NetconfSwitch._get_lock_session_id(err_info))

    def test_parse_session_id_nonzero(self):
        err_info = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<error-info xmlns="urn:ietf:params:xml:ns:netconf:base:1.0">'
            '<session-id>abc-123</session-id>'
            '</error-info>')
        self.assertEqual(
            'abc-123',
            netconf_switch.NetconfSwitch._get_lock_session_id(err_info))


class TestDispatchMethods(unittest.TestCase):

    def test_add_network_calls_send_config(self):
        switch = _make_switch()
        mock_callable = mock.Mock(return_value=[mock.Mock()])
        switch.ADD_NETWORK = mock_callable
        with mock.patch.object(switch, 'send_config_to_device',
                               autospec=True) as mock_send:
            switch.add_network(100, 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee')
        mock_callable.assert_called_once()
        mock_send.assert_called_once()

    def test_add_network_skips_when_no_vlan_management(self):
        switch = _make_switch({'ngs_manage_vlans': 'false'})
        mock_callable = mock.Mock(return_value=[mock.Mock()])
        switch.ADD_NETWORK = mock_callable
        with mock.patch.object(switch, 'send_config_to_device',
                               autospec=True) as mock_send:
            switch.add_network(100, 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee')
        mock_callable.assert_not_called()
        mock_send.assert_not_called()

    def test_add_network_with_trunk_ports(self):
        switch = _make_switch({'ngs_trunk_ports': 'eth1/48,eth1/49'})
        net_obj = mock.Mock()
        trunk_obj = mock.Mock()
        switch.ADD_NETWORK = mock.Mock(return_value=[net_obj])
        switch.ADD_NETWORK_TO_TRUNK = mock.Mock(return_value=[trunk_obj])
        with mock.patch.object(switch, 'send_config_to_device',
                               autospec=True) as mock_send:
            switch.add_network(100, 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee')
        switch.ADD_NETWORK_TO_TRUNK.assert_called_once_with(
            switch, segmentation_id=100,
            trunk_ports=['eth1/48', 'eth1/49'],
            physnet_vlans=None)
        mock_send.assert_called_once_with([net_obj, trunk_obj])

    def test_add_network_with_trunk_ports_and_physnet_vlans(self):
        switch = _make_switch({'ngs_trunk_ports': 'eth1/48,eth1/49'})
        net_obj = mock.Mock()
        trunk_obj = mock.Mock()
        switch.ADD_NETWORK = mock.Mock(return_value=[net_obj])
        switch.ADD_NETWORK_TO_TRUNK = mock.Mock(return_value=[trunk_obj])
        with mock.patch.object(switch, 'send_config_to_device',
                               autospec=True) as mock_send:
            switch.add_network(100, 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee',
                               physnet_vlans={100, 200, 300})
        switch.ADD_NETWORK_TO_TRUNK.assert_called_once_with(
            switch, segmentation_id=100,
            trunk_ports=['eth1/48', 'eth1/49'],
            physnet_vlans={100, 200, 300})
        mock_send.assert_called_once_with([net_obj, trunk_obj])

    def test_add_network_no_trunk_ports(self):
        switch = _make_switch()
        net_obj = mock.Mock()
        switch.ADD_NETWORK = mock.Mock(return_value=[net_obj])
        switch.ADD_NETWORK_TO_TRUNK = mock.Mock(return_value=[mock.Mock()])
        with mock.patch.object(switch, 'send_config_to_device',
                               autospec=True) as mock_send:
            switch.add_network(100, 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee')
        switch.ADD_NETWORK_TO_TRUNK.assert_not_called()
        mock_send.assert_called_once_with([net_obj])

    def test_add_network_trunk_callable_not_set(self):
        switch = _make_switch({'ngs_trunk_ports': 'eth1/48'})
        net_obj = mock.Mock()
        switch.ADD_NETWORK = mock.Mock(return_value=[net_obj])
        with mock.patch.object(switch, 'send_config_to_device',
                               autospec=True) as mock_send:
            switch.add_network(100, 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee')
        mock_send.assert_called_once_with([net_obj])

    def test_del_network_calls_send_config(self):
        switch = _make_switch()
        mock_callable = mock.Mock(return_value=[mock.Mock()])
        switch.DELETE_NETWORK = mock_callable
        with mock.patch.object(switch, 'send_config_to_device',
                               autospec=True) as mock_send:
            switch.del_network(100, 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee')
        mock_callable.assert_called_once()
        mock_send.assert_called_once()

    def test_del_network_with_trunk_ports(self):
        switch = _make_switch({'ngs_trunk_ports': 'eth1/48,eth1/49'})
        trunk_obj = mock.Mock()
        del_obj = mock.Mock()
        switch.REMOVE_NETWORK_FROM_TRUNK = mock.Mock(
            return_value=[trunk_obj])
        switch.DELETE_NETWORK = mock.Mock(return_value=[del_obj])
        with mock.patch.object(switch, 'send_config_to_device',
                               autospec=True) as mock_send:
            switch.del_network(100, 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee')
        switch.REMOVE_NETWORK_FROM_TRUNK.assert_called_once_with(
            switch, segmentation_id=100,
            trunk_ports=['eth1/48', 'eth1/49'],
            physnet_vlans=None)
        mock_send.assert_called_once_with([trunk_obj, del_obj])

    def test_del_network_with_trunk_ports_and_physnet_vlans(self):
        switch = _make_switch({'ngs_trunk_ports': 'eth1/48,eth1/49'})
        trunk_obj = mock.Mock()
        del_obj = mock.Mock()
        switch.REMOVE_NETWORK_FROM_TRUNK = mock.Mock(
            return_value=[trunk_obj])
        switch.DELETE_NETWORK = mock.Mock(return_value=[del_obj])
        with mock.patch.object(switch, 'send_config_to_device',
                               autospec=True) as mock_send:
            switch.del_network(100, 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee',
                               physnet_vlans={200, 300})
        switch.REMOVE_NETWORK_FROM_TRUNK.assert_called_once_with(
            switch, segmentation_id=100,
            trunk_ports=['eth1/48', 'eth1/49'],
            physnet_vlans={200, 300})
        mock_send.assert_called_once_with([trunk_obj, del_obj])

    def test_del_network_no_trunk_ports(self):
        switch = _make_switch()
        del_obj = mock.Mock()
        switch.REMOVE_NETWORK_FROM_TRUNK = mock.Mock(
            return_value=[mock.Mock()])
        switch.DELETE_NETWORK = mock.Mock(return_value=[del_obj])
        with mock.patch.object(switch, 'send_config_to_device',
                               autospec=True) as mock_send:
            switch.del_network(100, 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee')
        switch.REMOVE_NETWORK_FROM_TRUNK.assert_not_called()
        mock_send.assert_called_once_with([del_obj])

    def test_plug_port_to_network(self):
        switch = _make_switch()
        mock_callable = mock.Mock(return_value=[mock.Mock()])
        switch.PLUG_PORT_TO_NETWORK = mock_callable
        switch.DELETE_PORT = mock.Mock()
        with mock.patch.object(switch, 'send_config_to_device',
                               autospec=True) as mock_send:
            switch.plug_port_to_network('eth1/1', 100)
        mock_callable.assert_called_once()
        mock_send.assert_called_once()

    def test_plug_port_with_disable_inactive(self):
        switch = _make_switch({'ngs_disable_inactive_ports': 'true'})
        enable_obj = mock.Mock()
        plug_obj = mock.Mock()
        switch.ENABLE_PORT = mock.Mock(return_value=[enable_obj])
        switch.PLUG_PORT_TO_NETWORK = mock.Mock(return_value=[plug_obj])
        switch.DELETE_PORT = mock.Mock()
        with mock.patch.object(switch, 'send_config_to_device',
                               autospec=True) as mock_send:
            switch.plug_port_to_network('eth1/1', 100)
        switch.ENABLE_PORT.assert_called_once_with(switch, port_id='eth1/1')
        mock_send.assert_called_once_with([enable_obj, plug_obj])

    def test_plug_port_no_enable_when_inactive_ports_disabled(self):
        switch = _make_switch({'ngs_disable_inactive_ports': 'false'})
        plug_obj = mock.Mock()
        switch.ENABLE_PORT = mock.Mock(return_value=[mock.Mock()])
        switch.PLUG_PORT_TO_NETWORK = mock.Mock(return_value=[plug_obj])
        switch.DELETE_PORT = mock.Mock()
        with mock.patch.object(switch, 'send_config_to_device',
                               autospec=True) as mock_send:
            switch.plug_port_to_network('eth1/1', 100)
        switch.ENABLE_PORT.assert_not_called()
        mock_send.assert_called_once_with([plug_obj])

    def test_plug_port_clears_default_vlan(self):
        switch = _make_switch({'ngs_port_default_vlan': '1'})
        clear_obj = mock.Mock()
        plug_obj = mock.Mock()
        switch.DELETE_PORT = mock.Mock(return_value=[clear_obj])
        switch.PLUG_PORT_TO_NETWORK = mock.Mock(return_value=[plug_obj])
        with mock.patch.object(switch, 'send_config_to_device',
                               autospec=True) as mock_send:
            switch.plug_port_to_network('eth1/1', 100)
        switch.DELETE_PORT.assert_called_once_with(
            switch, port_id='eth1/1', segmentation_id='1')
        mock_send.assert_called_once_with([clear_obj, plug_obj])

    def test_plug_port_clears_default_vlan_from_arg(self):
        switch = _make_switch()
        clear_obj = mock.Mock()
        plug_obj = mock.Mock()
        switch.DELETE_PORT = mock.Mock(return_value=[clear_obj])
        switch.PLUG_PORT_TO_NETWORK = mock.Mock(return_value=[plug_obj])
        with mock.patch.object(switch, 'send_config_to_device',
                               autospec=True) as mock_send:
            switch.plug_port_to_network('eth1/1', 100, default_vlan=5)
        switch.DELETE_PORT.assert_called_once_with(
            switch, port_id='eth1/1', segmentation_id=5)
        mock_send.assert_called_once_with([clear_obj, plug_obj])

    def test_delete_port(self):
        switch = _make_switch()
        mock_callable = mock.Mock(return_value=[mock.Mock()])
        switch.DELETE_PORT = mock_callable
        switch.PLUG_PORT_TO_NETWORK = mock.Mock()
        switch.ADD_NETWORK = mock.Mock()
        with mock.patch.object(switch, 'send_config_to_device',
                               autospec=True) as mock_send:
            switch.delete_port('eth1/1', 100)
        mock_callable.assert_called_once()
        mock_send.assert_called_once()

    def test_delete_port_restores_default_vlan(self):
        switch = _make_switch({'ngs_port_default_vlan': '1'})
        unplug_obj = mock.Mock()
        restore_net_obj = mock.Mock()
        restore_port_obj = mock.Mock()
        switch.DELETE_PORT = mock.Mock(return_value=[unplug_obj])
        switch.ADD_NETWORK = mock.Mock(return_value=[restore_net_obj])
        switch.PLUG_PORT_TO_NETWORK = mock.Mock(
            return_value=[restore_port_obj])
        with mock.patch.object(switch, 'send_config_to_device',
                               autospec=True) as mock_send:
            switch.delete_port('eth1/1', 100)
        switch.DELETE_PORT.assert_called_once_with(
            switch, port_id='eth1/1', segmentation_id=100,
            trunk_details=None)
        switch.ADD_NETWORK.assert_called_once_with(
            switch, segmentation_id='1', network_name='1')
        switch.PLUG_PORT_TO_NETWORK.assert_called_once_with(
            switch, port_id='eth1/1', segmentation_id='1')
        mock_send.assert_called_once_with(
            [unplug_obj, restore_net_obj, restore_port_obj])

    def test_delete_port_restores_default_vlan_from_arg(self):
        switch = _make_switch()
        unplug_obj = mock.Mock()
        restore_net_obj = mock.Mock()
        restore_port_obj = mock.Mock()
        switch.DELETE_PORT = mock.Mock(return_value=[unplug_obj])
        switch.ADD_NETWORK = mock.Mock(return_value=[restore_net_obj])
        switch.PLUG_PORT_TO_NETWORK = mock.Mock(
            return_value=[restore_port_obj])
        with mock.patch.object(switch, 'send_config_to_device',
                               autospec=True) as mock_send:
            switch.delete_port('eth1/1', 100, default_vlan=5)
        switch.ADD_NETWORK.assert_called_once_with(
            switch, segmentation_id=5, network_name='5')
        switch.PLUG_PORT_TO_NETWORK.assert_called_once_with(
            switch, port_id='eth1/1', segmentation_id=5)
        mock_send.assert_called_once_with(
            [unplug_obj, restore_net_obj, restore_port_obj])

    def test_delete_port_with_disable_inactive(self):
        switch = _make_switch({'ngs_disable_inactive_ports': 'true'})
        unplug_obj = mock.Mock()
        disable_obj = mock.Mock()
        switch.DELETE_PORT = mock.Mock(return_value=[unplug_obj])
        switch.DISABLE_PORT = mock.Mock(return_value=[disable_obj])
        switch.ADD_NETWORK = mock.Mock()
        switch.PLUG_PORT_TO_NETWORK = mock.Mock()
        with mock.patch.object(switch, 'send_config_to_device',
                               autospec=True) as mock_send:
            switch.delete_port('eth1/1', 100)
        switch.DISABLE_PORT.assert_called_once_with(
            switch, port_id='eth1/1')
        mock_send.assert_called_once_with([unplug_obj, disable_obj])

    def test_delete_port_no_disable_when_inactive_ports_disabled(self):
        switch = _make_switch({'ngs_disable_inactive_ports': 'false'})
        unplug_obj = mock.Mock()
        switch.DELETE_PORT = mock.Mock(return_value=[unplug_obj])
        switch.DISABLE_PORT = mock.Mock(return_value=[mock.Mock()])
        switch.ADD_NETWORK = mock.Mock()
        switch.PLUG_PORT_TO_NETWORK = mock.Mock()
        with mock.patch.object(switch, 'send_config_to_device',
                               autospec=True) as mock_send:
            switch.delete_port('eth1/1', 100)
        switch.DISABLE_PORT.assert_not_called()
        mock_send.assert_called_once_with([unplug_obj])


class TestStubMethods(unittest.TestCase):

    def test_plug_switch_to_network_noop(self):
        switch = _make_switch()
        switch.plug_switch_to_network(5000, 100)

    def test_unplug_switch_from_network_noop(self):
        switch = _make_switch()
        switch.unplug_switch_from_network(5000, 100)

    def test_vlan_has_ports_conservative(self):
        switch = _make_switch()
        self.assertTrue(switch.vlan_has_ports(100))

    def test_vlan_has_vni_false(self):
        switch = _make_switch()
        self.assertFalse(switch.vlan_has_vni(100, 5000))

    def test_add_subports_raises(self):
        switch = _make_switch()
        self.assertRaises(
            exc.GenericSwitchNotSupported,
            switch.add_subports_on_trunk, {}, 'eth1/1', [])

    def test_del_subports_raises(self):
        switch = _make_switch()
        self.assertRaises(
            exc.GenericSwitchNotSupported,
            switch.del_subports_on_trunk, {}, 'eth1/1', [])

    def test_add_subports_dispatches_callable(self):
        switch = _make_switch()
        config_obj = mock.Mock()
        switch.ADD_SUBPORTS_ON_TRUNK = mock.Mock(return_value=[config_obj])
        binding_profile = {'local_link_information': [
            {'port_id': 'eth1/1', 'switch_info': 'test-switch'}]}
        subports = [{'segmentation_id': 200}]
        with mock.patch.object(switch, 'send_config_to_device',
                               autospec=True) as mock_send:
            switch.add_subports_on_trunk(
                binding_profile, 'eth1/1', subports)
        switch.ADD_SUBPORTS_ON_TRUNK.assert_called_once_with(
            switch, binding_profile=binding_profile, port_id='eth1/1',
            subports=subports, trunk_details=None)
        mock_send.assert_called_once_with([config_obj])

    def test_add_subports_dispatches_with_trunk_details(self):
        switch = _make_switch()
        config_obj = mock.Mock()
        switch.ADD_SUBPORTS_ON_TRUNK = mock.Mock(return_value=[config_obj])
        binding_profile = {'local_link_information': [
            {'port_id': 'eth1/1', 'switch_info': 'test-switch'}]}
        subports = [{'segmentation_id': 200}]
        trunk_details = {
            'segmentation_id': 100,
            'sub_ports': [{'segmentation_id': 200}, {'segmentation_id': 300}],
        }
        with mock.patch.object(switch, 'send_config_to_device',
                               autospec=True) as mock_send:
            switch.add_subports_on_trunk(
                binding_profile, 'eth1/1', subports,
                trunk_details=trunk_details)
        switch.ADD_SUBPORTS_ON_TRUNK.assert_called_once_with(
            switch, binding_profile=binding_profile, port_id='eth1/1',
            subports=subports, trunk_details=trunk_details)
        mock_send.assert_called_once_with([config_obj])

    def test_add_subports_no_send_when_callable_returns_none(self):
        switch = _make_switch()
        switch.ADD_SUBPORTS_ON_TRUNK = mock.Mock(return_value=None)
        with mock.patch.object(switch, 'send_config_to_device',
                               autospec=True) as mock_send:
            switch.add_subports_on_trunk({}, 'eth1/1', [])
        mock_send.assert_not_called()

    def test_del_subports_dispatches_callable(self):
        switch = _make_switch()
        config_obj = mock.Mock()
        switch.DEL_SUBPORTS_ON_TRUNK = mock.Mock(return_value=[config_obj])
        binding_profile = {'local_link_information': [
            {'port_id': 'eth1/1', 'switch_info': 'test-switch'}]}
        subports = [{'segmentation_id': 200}]
        with mock.patch.object(switch, 'send_config_to_device',
                               autospec=True) as mock_send:
            switch.del_subports_on_trunk(
                binding_profile, 'eth1/1', subports)
        switch.DEL_SUBPORTS_ON_TRUNK.assert_called_once_with(
            switch, binding_profile=binding_profile, port_id='eth1/1',
            subports=subports, trunk_details=None)
        mock_send.assert_called_once_with([config_obj])

    def test_del_subports_dispatches_with_trunk_details(self):
        switch = _make_switch()
        config_obj = mock.Mock()
        switch.DEL_SUBPORTS_ON_TRUNK = mock.Mock(return_value=[config_obj])
        binding_profile = {'local_link_information': [
            {'port_id': 'eth1/1', 'switch_info': 'test-switch'}]}
        subports = [{'segmentation_id': 200}]
        trunk_details = {
            'segmentation_id': 100,
            'sub_ports': [{'segmentation_id': 300}],
        }
        with mock.patch.object(switch, 'send_config_to_device',
                               autospec=True) as mock_send:
            switch.del_subports_on_trunk(
                binding_profile, 'eth1/1', subports,
                trunk_details=trunk_details)
        switch.DEL_SUBPORTS_ON_TRUNK.assert_called_once_with(
            switch, binding_profile=binding_profile, port_id='eth1/1',
            subports=subports, trunk_details=trunk_details)
        mock_send.assert_called_once_with([config_obj])

    def test_del_subports_no_send_when_callable_returns_none(self):
        switch = _make_switch()
        switch.DEL_SUBPORTS_ON_TRUNK = mock.Mock(return_value=None)
        with mock.patch.object(switch, 'send_config_to_device',
                               autospec=True) as mock_send:
            switch.del_subports_on_trunk({}, 'eth1/1', [])
        mock_send.assert_not_called()

    def test_security_group_methods_are_noop(self):
        switch = _make_switch()
        switch.add_security_group(mock.Mock())
        switch.update_security_group(mock.Mock())
        switch.del_security_group('sg-123')
        switch.bind_security_group(mock.Mock(), 'eth1/1', ['eth1/1'])
        switch.unbind_security_group('sg-123', 'eth1/1', ['eth1/1'])


class TestNetconfSwitchCoordination(fixtures.TestWithFixtures):

    def setUp(self):
        super().setUp()
        self.cfg = self.useFixture(config_fixture.Config())

    @mock.patch.object(device_utils, 'get_hostname', autospec=True)
    @mock.patch.object(coordination, 'get_coordinator', autospec=True)
    def test_coordinator_created_when_backend_url_configured(
            self, mock_get_coord, mock_hostname):
        self.cfg.config(acquire_timeout=120, backend_url='etcd3://localhost',
                        group='ngs_coordination')
        coord = mock.Mock()
        mock_get_coord.return_value = coord
        mock_hostname.return_value = 'viking'
        switch = _make_switch({'ngs_max_connections': 2})
        self.assertEqual(coord, switch.locker)
        mock_get_coord.assert_called_once_with(
            'etcd3://localhost', b'ngs-viking')
        coord.start.assert_called_once()

    @mock.patch.object(device_utils, 'get_hostname', autospec=True)
    @mock.patch.object(ngs_lock, 'PoolLock', autospec=True)
    @mock.patch.object(manager, 'connect', autospec=True)
    @mock.patch.object(coordination, 'get_coordinator', autospec=True)
    def test_pool_lock_called_with_coordinator(
            self, mock_get_coord, mock_manager, mock_pool_lock,
            mock_hostname):
        self.cfg.config(acquire_timeout=120, backend_url='etcd3://localhost',
                        group='ngs_coordination')
        coord = mock.Mock()
        mock_get_coord.return_value = coord
        mock_hostname.return_value = 'viking'
        switch = _make_switch({'ngs_max_connections': 2})

        mock_ncclient = mock.Mock()
        fake_caps = {ncconst.IANA_NETCONF_CAPABILITIES[':candidate']}
        mock_ncclient.server_capabilities = fake_caps
        mock_manager.return_value.__enter__.return_value = mock_ncclient
        mock_pool_lock.return_value.__enter__ = mock.Mock()
        mock_pool_lock.return_value.__exit__ = mock.Mock(return_value=False)

        with mock.patch.object(switch, '_lock_and_configure', autospec=True):
            switch.send_config_to_device(mock.Mock())

        mock_pool_lock.assert_called_once_with(
            coord, locks_pool_size=2,
            locks_prefix='switch.example.com',
            timeout=120)

    def test_locker_none_when_no_backend_url(self):
        switch = _make_switch()
        self.assertIsNone(switch.locker)

    def test_warning_logged_when_no_backend_url(self):
        with mock.patch.object(netconf_switch, 'LOG',
                               autospec=True) as mock_log:
            _make_switch()
        mock_log.warning.assert_called_once_with(
            "Switch %s: [ngs_coordination] backend_url is not "
            "configured. The ngs_max_connections is ignored.",
            'switch.example.com')
