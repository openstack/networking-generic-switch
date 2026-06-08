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

import fixtures
from oslo_config import fixture as config_fixture
import requests
import tenacity
from tooz import coordination

from networking_generic_switch.devices.restconf_devices import restconf_switch
from networking_generic_switch.devices import utils as device_utils
from networking_generic_switch import exceptions as exc
from networking_generic_switch import locking as ngs_lock


DEVICE_CFG_MINIMAL = {
    'device_type': 'restconf_openconfig',
    'host': 'switch.example.com',
    'username': 'admin',
    'password': 'secret',
    'ngs_manage_vlans': True,
    'ngs_network_name_format': '{network_id}',
    'ngs_max_connections': 1,
}


def _make_switch(extra_cfg=None):
    cfg = dict(DEVICE_CFG_MINIMAL)
    if extra_cfg:
        cfg.update(extra_cfg)
    return restconf_switch.RestconfSwitch(cfg, device_name='test-switch')


class TestRestconfSwitchInit(unittest.TestCase):

    def test_base_url_built(self):
        # Test with hostname (default)
        switch = _make_switch()
        self.assertEqual('https://switch.example.com:443', switch._base_url)

        # Test with IPv4 address
        switch = _make_switch({'host': '192.168.1.1'})
        self.assertEqual('https://192.168.1.1:443', switch._base_url)

        # Test with IPv6 address
        switch = _make_switch({'host': '2001:db8::1'})
        self.assertEqual('https://[2001:db8::1]:443', switch._base_url)

        # Test with IPv6 address and custom port
        switch = _make_switch({'host': '2001:db8::1', 'port': '8443'})
        self.assertEqual('https://[2001:db8::1]:8443', switch._base_url)

    def test_default_scheme(self):
        switch = _make_switch()
        self.assertEqual('https', switch._restconf_scheme)

    def test_custom_scheme(self):
        switch = _make_switch({'ngs_restconf_scheme': 'http'})
        self.assertEqual('http', switch._restconf_scheme)
        self.assertEqual('http://switch.example.com:443', switch._base_url)

    def test_default_content_type(self):
        switch = _make_switch()
        self.assertEqual('application/yang-data+json', switch._content_type)

    def test_custom_content_type_nxos(self):
        switch = _make_switch(
            {'ngs_restconf_content_type': 'application/yang.data+json'})
        self.assertEqual('application/yang.data+json', switch._content_type)

    def test_default_port(self):
        switch = _make_switch()
        self.assertEqual(443, switch._restconf_port)

    def test_custom_port(self):
        switch = _make_switch({'port': '8443'})
        self.assertEqual(8443, switch._restconf_port)
        self.assertEqual('https://switch.example.com:8443', switch._base_url)

    def test_default_base_path(self):
        switch = _make_switch()
        self.assertEqual('/restconf/data', switch._base_path)

    def test_custom_base_path(self):
        switch = _make_switch({'ngs_restconf_base_path': '/rests/data'})
        self.assertEqual('/rests/data', switch._base_path)

    def test_verify_ssl_default(self):
        switch = _make_switch()
        self.assertTrue(switch._verify_ssl)

    def test_verify_ssl_false(self):
        switch = _make_switch({'ngs_verify_tls': 'false'})
        self.assertFalse(switch._verify_ssl)

    def test_trunk_vlans_converge_is_true(self):
        switch = _make_switch()
        self.assertTrue(switch.trunk_vlans_converge)

    def test_host_and_credentials_in_config(self):
        switch = _make_switch()
        self.assertEqual('switch.example.com', switch.config.get('host'))
        self.assertEqual('admin', switch.config.get('username'))
        self.assertEqual('secret', switch.config.get('password'))


class TestResourceUrl(unittest.TestCase):

    def test_resource_url_no_path(self):
        switch = _make_switch()
        self.assertEqual(
            'https://switch.example.com:443/restconf/data',
            switch._resource_url())

    def test_resource_url_with_path(self):
        switch = _make_switch()
        self.assertEqual(
            'https://switch.example.com:443/restconf/data/'
            'openconfig-interfaces:interfaces',
            switch._resource_url('openconfig-interfaces:interfaces'))

    def test_resource_url_strips_leading_slash(self):
        switch = _make_switch()
        self.assertEqual(
            'https://switch.example.com:443/restconf/data/'
            'openconfig-interfaces:interfaces',
            switch._resource_url('/openconfig-interfaces:interfaces'))

    def test_resource_url_custom_base_path(self):
        switch = _make_switch({'ngs_restconf_base_path': '/rests/data'})
        self.assertEqual(
            'https://switch.example.com:443/rests/data/'
            'openconfig-interfaces:interfaces',
            switch._resource_url('openconfig-interfaces:interfaces'))

    def test_resource_url_trailing_slash_on_base_path(self):
        switch = _make_switch({'ngs_restconf_base_path': '/restconf/data/'})
        self.assertEqual(
            'https://switch.example.com:443/restconf/data/'
            'openconfig-interfaces:interfaces',
            switch._resource_url('openconfig-interfaces:interfaces'))


class TestBuildSession(unittest.TestCase):

    def test_session_auth(self):
        switch = _make_switch()
        self.assertEqual(('admin', 'secret'), switch._session.auth)

    def test_session_headers(self):
        switch = _make_switch()
        self.assertEqual(
            'application/yang-data+json',
            switch._session.headers['Content-Type'])
        self.assertEqual(
            'application/yang-data+json',
            switch._session.headers['Accept'])

    def test_session_headers_nxos(self):
        switch = _make_switch(
            {'ngs_restconf_content_type': 'application/yang.data+json'})
        self.assertEqual(
            'application/yang.data+json',
            switch._session.headers['Content-Type'])
        self.assertEqual(
            'application/yang.data+json',
            switch._session.headers['Accept'])

    def test_session_verify_true(self):
        switch = _make_switch()
        self.assertTrue(switch._session.verify)

    def test_session_verify_false(self):
        switch = _make_switch({'ngs_verify_tls': 'false'})
        self.assertFalse(switch._session.verify)

    def test_session_no_auth_when_no_username(self):
        cfg = dict(DEVICE_CFG_MINIMAL)
        del cfg['username']
        del cfg['password']
        switch = restconf_switch.RestconfSwitch(cfg, device_name='test')
        self.assertIsNone(switch._session.auth)

    def test_session_password_defaults_to_empty(self):
        cfg = dict(DEVICE_CFG_MINIMAL)
        del cfg['password']
        switch = restconf_switch.RestconfSwitch(cfg, device_name='test')
        self.assertEqual(('admin', ''), switch._session.auth)


class TestSendRequest(unittest.TestCase):

    def setUp(self):
        super().setUp()
        self._orig_wait = (
            restconf_switch.RestconfSwitch._send_request.retry.wait)
        restconf_switch.RestconfSwitch._send_request.retry.wait = (
            tenacity.wait_none())

    def tearDown(self):
        restconf_switch.RestconfSwitch._send_request.retry.wait = (
            self._orig_wait)
        super().tearDown()

    def _make_response(self, status_code=200, text='', reason='OK',
                       json_data=None):
        resp = mock.Mock(spec=requests.Response)
        resp.status_code = status_code
        resp.text = text
        resp.reason = reason
        if json_data is not None:
            resp.json.return_value = json_data
        return resp

    def test_successful_request(self):
        switch = _make_switch()
        session = mock.Mock(spec=requests.Session)
        session.request.return_value = self._make_response(200)
        result = switch._send_request(session, 'GET', 'https://x/restconf')
        self.assertEqual(200, result.status_code)
        session.request.assert_called_once_with(
            'GET', 'https://x/restconf')

    def test_successful_patch(self):
        switch = _make_switch()
        session = mock.Mock(spec=requests.Session)
        session.request.return_value = self._make_response(
            204, reason='No Content')
        payload = {'openconfig-interfaces:interfaces': {}}
        result = switch._send_request(
            session, 'PATCH', 'https://x/restconf/data', json=payload)
        self.assertEqual(204, result.status_code)
        session.request.assert_called_once_with(
            'PATCH', 'https://x/restconf/data', json=payload)

    def test_409_raises_retryable(self):
        switch = _make_switch()
        session = mock.Mock(spec=requests.Session)
        session.request.return_value = self._make_response(
            409, text='Conflict', reason='Conflict')
        self.assertRaises(
            exc.GenericSwitchRestconfRetryable,
            switch._send_request, session, 'PATCH', 'https://x/restconf')

    def test_503_raises_retryable(self):
        switch = _make_switch()
        session = mock.Mock(spec=requests.Session)
        session.request.return_value = self._make_response(
            503, text='Service Unavailable', reason='Service Unavailable')
        self.assertRaises(
            exc.GenericSwitchRestconfRetryable,
            switch._send_request, session, 'PATCH', 'https://x/restconf')

    def test_connection_error_raises_retryable(self):
        switch = _make_switch()
        session = mock.Mock(spec=requests.Session)
        session.request.side_effect = requests.exceptions.ConnectionError(
            'Connection refused')
        self.assertRaises(
            exc.GenericSwitchRestconfRetryable,
            switch._send_request, session, 'GET', 'https://x/restconf')

    def test_400_raises_restconf_error(self):
        switch = _make_switch()
        session = mock.Mock(spec=requests.Session)
        session.request.return_value = self._make_response(
            400, text='Bad Request', reason='Bad Request')
        self.assertRaises(
            exc.GenericSwitchRestconfError,
            switch._send_request, session, 'PATCH', 'https://x/restconf')

    def test_404_raises_restconf_error(self):
        switch = _make_switch()
        session = mock.Mock(spec=requests.Session)
        session.request.return_value = self._make_response(
            404, text='Not Found', reason='Not Found')
        self.assertRaises(
            exc.GenericSwitchRestconfError,
            switch._send_request, session, 'GET', 'https://x/restconf')

    def test_500_raises_restconf_error(self):
        switch = _make_switch()
        session = mock.Mock(spec=requests.Session)
        session.request.return_value = self._make_response(
            500, text='Internal Server Error',
            reason='Internal Server Error')
        self.assertRaises(
            exc.GenericSwitchRestconfError,
            switch._send_request, session, 'PATCH', 'https://x/restconf')

    def test_retryable_is_retried_then_succeeds(self):
        switch = _make_switch()
        session = mock.Mock(spec=requests.Session)
        fail_resp = self._make_response(
            409, text='Conflict', reason='Conflict')
        ok_resp = self._make_response(204, reason='No Content')
        session.request.side_effect = [fail_resp, ok_resp]
        result = switch._send_request(
            session, 'PATCH', 'https://x/restconf')
        self.assertEqual(204, result.status_code)
        self.assertEqual(2, session.request.call_count)

    def test_connection_error_retried_then_succeeds(self):
        switch = _make_switch()
        session = mock.Mock(spec=requests.Session)
        ok_resp = self._make_response(200)
        session.request.side_effect = [
            requests.exceptions.ConnectionError('fail'),
            ok_resp,
        ]
        result = switch._send_request(
            session, 'GET', 'https://x/restconf')
        self.assertEqual(200, result.status_code)
        self.assertEqual(2, session.request.call_count)

    def test_non_retryable_error_not_retried(self):
        switch = _make_switch()
        session = mock.Mock(spec=requests.Session)
        session.request.return_value = self._make_response(
            400, text='Bad Request', reason='Bad Request')
        self.assertRaises(
            exc.GenericSwitchRestconfError,
            switch._send_request, session, 'PATCH', 'https://x/restconf')
        self.assertEqual(1, session.request.call_count)


class TestSendConfigToDevice(unittest.TestCase):

    @mock.patch.object(restconf_switch.RestconfSwitch,
                       '_send_request', autospec=True)
    def test_patch_called_with_json_payload(self, mock_send):
        switch = _make_switch()
        mock_sess = mock.Mock(spec=requests.Session)
        switch._session = mock_sess
        fake_config = mock.Mock()
        fake_config.to_restconf_dict.return_value = {
            'openconfig-interfaces:interfaces': {'interface': []}}
        switch.send_config_to_device([fake_config])
        mock_send.assert_called_once_with(
            switch, mock_sess, 'PATCH',
            'https://switch.example.com:443/restconf/data/'
            'openconfig-interfaces:interfaces',
            json={'interface': []})

    @mock.patch.object(restconf_switch.RestconfSwitch,
                       '_send_request', autospec=True)
    def test_put_called_when_method_is_put(self, mock_send):
        switch = _make_switch()
        mock_sess = mock.Mock(spec=requests.Session)
        switch._session = mock_sess
        fake_config = mock.Mock()
        fake_config.to_restconf_dict.return_value = {
            'openconfig-interfaces:interfaces': {'interface': []}}
        switch.send_config_to_device([fake_config], method='PUT')
        mock_send.assert_called_once_with(
            switch, mock_sess, 'PUT',
            'https://switch.example.com:443/restconf/data/'
            'openconfig-interfaces:interfaces',
            json={'interface': []})

    @mock.patch.object(restconf_switch.RestconfSwitch,
                       '_send_request', autospec=True)
    def test_single_config_wrapped_in_list(self, mock_send):
        switch = _make_switch()
        mock_sess = mock.Mock(spec=requests.Session)
        switch._session = mock_sess
        fake_config = mock.Mock()
        fake_config.to_restconf_dict.return_value = {'key': 'value'}
        switch.send_config_to_device(fake_config)
        mock_send.assert_called_once_with(
            switch, mock_sess, 'PATCH',
            'https://switch.example.com:443/restconf/data/key',
            json='value')

    @mock.patch.object(restconf_switch.RestconfSwitch,
                       '_send_request', autospec=True)
    def test_empty_payload_skipped(self, mock_send):
        switch = _make_switch()
        fake_config = mock.Mock()
        fake_config.to_restconf_dict.return_value = {}
        switch.send_config_to_device([fake_config])
        mock_send.assert_not_called()

    @mock.patch.object(restconf_switch.RestconfSwitch,
                       '_send_request', autospec=True)
    def test_session_closed_on_error(self, mock_send):
        switch = _make_switch()
        mock_sess = mock.Mock(spec=requests.Session)
        switch._session = mock_sess
        mock_send.side_effect = exc.GenericSwitchRestconfError(
            device='test', error='fail')
        fake_config = mock.Mock()
        fake_config.to_restconf_dict.return_value = {'key': 'value'}
        self.assertRaises(
            exc.GenericSwitchRestconfError,
            switch.send_config_to_device, [fake_config])

    @mock.patch.object(restconf_switch.RestconfSwitch,
                       '_send_request', autospec=True)
    def test_multiple_configs_merged(self, mock_send):
        switch = _make_switch()
        mock_sess = mock.Mock(spec=requests.Session)
        switch._session = mock_sess
        config_a = mock.Mock()
        config_a.to_restconf_dict.return_value = {'key-a': 'value-a'}
        config_b = mock.Mock()
        config_b.to_restconf_dict.return_value = {'key-b': 'value-b'}
        switch.send_config_to_device([config_a, config_b])
        self.assertEqual(2, mock_send.call_count)
        mock_send.assert_any_call(
            switch, mock_sess, 'PATCH',
            'https://switch.example.com:443/restconf/data/key-a',
            json='value-a')
        mock_send.assert_any_call(
            switch, mock_sess, 'PATCH',
            'https://switch.example.com:443/restconf/data/key-b',
            json='value-b')


class TestGetFromDevice(unittest.TestCase):

    @mock.patch.object(restconf_switch.RestconfSwitch,
                       '_send_request', autospec=True)
    def test_get_returns_json(self, mock_send):
        switch = _make_switch()
        mock_sess = mock.Mock(spec=requests.Session)
        switch._session = mock_sess
        mock_resp = mock.Mock()
        mock_resp.json.return_value = {'data': 'value'}
        mock_send.return_value = mock_resp
        result = switch.get_from_device(
            'openconfig-interfaces:interfaces')
        self.assertEqual({'data': 'value'}, result)
        mock_send.assert_called_once_with(
            switch, mock_sess, 'GET',
            'https://switch.example.com:443/restconf/data/'
            'openconfig-interfaces:interfaces')

    @mock.patch.object(restconf_switch.RestconfSwitch,
                       '_send_request', autospec=True)
    def test_get_session_closed_on_error(self, mock_send):
        switch = _make_switch()
        mock_sess = mock.Mock(spec=requests.Session)
        switch._session = mock_sess
        mock_send.side_effect = exc.GenericSwitchRestconfError(
            device='test', error='fail')
        self.assertRaises(
            exc.GenericSwitchRestconfError,
            switch.get_from_device, 'some/path')


class TestDeleteFromDevice(unittest.TestCase):

    @mock.patch.object(restconf_switch.RestconfSwitch,
                       '_send_request', autospec=True)
    def test_delete_called(self, mock_send):
        switch = _make_switch()
        mock_sess = mock.Mock(spec=requests.Session)
        switch._session = mock_sess
        switch.delete_from_device(
            'openconfig-interfaces:interfaces/interface=eth1%2F1')
        mock_send.assert_called_once_with(
            switch, mock_sess, 'DELETE',
            'https://switch.example.com:443/restconf/data/'
            'openconfig-interfaces:interfaces/interface=eth1%2F1')

    @mock.patch.object(restconf_switch.RestconfSwitch,
                       '_send_request', autospec=True)
    def test_delete_session_closed_on_error(self, mock_send):
        switch = _make_switch()
        mock_sess = mock.Mock(spec=requests.Session)
        switch._session = mock_sess
        mock_send.side_effect = exc.GenericSwitchRestconfError(
            device='test', error='fail')
        self.assertRaises(
            exc.GenericSwitchRestconfError,
            switch.delete_from_device, 'some/path')


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
        self.assertEqual(2, mock_send.call_count)
        mock_send.assert_any_call([net_obj])
        mock_send.assert_any_call([trunk_obj], method='PUT')

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
        self.assertEqual(2, mock_send.call_count)
        mock_send.assert_any_call([net_obj])
        mock_send.assert_any_call([trunk_obj], method='PUT')

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
        self.assertEqual(2, mock_send.call_count)
        mock_send.assert_any_call([trunk_obj], method='PUT')
        mock_send.assert_any_call([del_obj])

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
        mock_send.assert_called_with(mock.ANY, method='PUT')

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
        mock_send.assert_called_once_with(
            [enable_obj, plug_obj], method='PUT')

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
        mock_send.assert_called_once_with(
            [clear_obj, plug_obj], method='PUT')

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
        mock_send.assert_called_with(mock.ANY, method='PUT')

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
            [unplug_obj, restore_net_obj, restore_port_obj], method='PUT')

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
        mock_send.assert_called_once_with(
            [unplug_obj, disable_obj], method='PUT')


class TestStubMethods(unittest.TestCase):

    @mock.patch.object(restconf_switch, 'LOG', autospec=True)
    def test_plug_switch_to_network_noop(self, mock_log):
        switch = _make_switch()
        switch.plug_switch_to_network(5000, 100)
        mock_log.debug.assert_called_once()

    @mock.patch.object(restconf_switch, 'LOG', autospec=True)
    def test_unplug_switch_from_network_noop(self, mock_log):
        switch = _make_switch()
        switch.unplug_switch_from_network(5000, 100)
        mock_log.debug.assert_called_once()

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
        mock_send.assert_called_once_with([config_obj], method='PUT')

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
        mock_send.assert_called_once_with([config_obj], method='PUT')

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
        mock_send.assert_called_once_with([config_obj], method='PUT')

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


class TestRestconfSwitchCoordination(fixtures.TestWithFixtures):

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
    @mock.patch.object(restconf_switch.RestconfSwitch,
                       '_send_request', autospec=True)
    @mock.patch.object(coordination, 'get_coordinator', autospec=True)
    def test_pool_lock_called_with_coordinator(
            self, mock_get_coord, mock_send,
            mock_pool_lock, mock_hostname):
        self.cfg.config(acquire_timeout=120, backend_url='etcd3://localhost',
                        group='ngs_coordination')
        coord = mock.Mock()
        mock_get_coord.return_value = coord
        mock_hostname.return_value = 'viking'
        switch = _make_switch({'ngs_max_connections': 2})

        mock_sess = mock.Mock(spec=requests.Session)
        switch._session = mock_sess
        mock_pool_lock.return_value.__enter__ = mock.Mock()
        mock_pool_lock.return_value.__exit__ = mock.Mock(return_value=False)

        fake_config = mock.Mock()
        fake_config.to_restconf_dict.return_value = {'key': 'value'}
        switch.send_config_to_device(fake_config)

        mock_pool_lock.assert_called_once_with(
            coord, locks_pool_size=2,
            locks_prefix='switch.example.com',
            timeout=120)

    def test_locker_none_when_no_backend_url(self):
        switch = _make_switch()
        self.assertIsNone(switch.locker)

    def test_warning_logged_when_no_backend_url(self):
        with mock.patch.object(restconf_switch, 'LOG',
                               autospec=True) as mock_log:
            _make_switch()
        mock_log.warning.assert_called_once_with(
            "Switch %s: [ngs_coordination] backend_url is not "
            "configured. The ngs_max_connections is ignored.",
            'switch.example.com')
