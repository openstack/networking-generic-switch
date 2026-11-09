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

import requests

from networking_generic_switch.devices.ndfc_devices import cisco
from networking_generic_switch import exceptions as exc


# Common device configuration shared by the tests. Individual tests override
# or extend it via make_switch(**overrides) instead of repeating the full dict.
BASE_DEVICE_CFG = {
    'device_type': 'cisco_ndfc',
    'host': 'ndfc.example.com',
    'port': 443,
    'username': 'admin',
    'password': 'password',
    'ip': '192.168.1.100',
    'ndfc_fabric_name': 'test-fabric',
    'ngs_verify_tls': False,
    'ndfc_timeout': 30,
    'ngs_network_name_format': '{segmentation_id}',
}


def make_switch(device_name='test-switch', remove=None, **overrides):
    """Build a CiscoNDFC from BASE_DEVICE_CFG with optional overrides.

    :param device_name: config section name passed to the driver.
    :param remove: iterable of keys to drop from the base config.
    :param overrides: config keys to add or replace.
    """
    device_cfg = dict(BASE_DEVICE_CFG)
    for key in remove or ():
        device_cfg.pop(key, None)
    device_cfg.update(overrides)
    return cisco.CiscoNDFC(device_cfg, device_name)


class TestCiscoNDFC(unittest.TestCase):

    def setUp(self):
        super(TestCiscoNDFC, self).setUp()
        self.switch = make_switch()

    def test_init_requires_host(self):
        """Test that the NDFC host is required in configuration."""
        self.assertRaises(
            exc.GenericSwitchNDFCConfigError,
            make_switch, remove=['host'])

    def test_init_switch_identified_by_hostname(self):
        """Hostname defaults to the section name."""
        switch = make_switch(device_name='leaf01', remove=['ip'])
        self.assertEqual(switch.ndfc_switch_hostname, 'leaf01')

    def test_init_switch_identified_by_serial(self):
        """A switch may be identified by an explicit NDFC serial number."""
        switch = make_switch(remove=['ip'], ndfc_switch_serial='ABC1234567')
        self.assertEqual(switch.ndfc_switch_serial, 'ABC1234567')

    def test_init_rejects_network_id_format(self):
        """Test ngs_network_name_format with {network_id} is rejected."""
        self.assertRaises(
            exc.GenericSwitchNDFCConfigError,
            make_switch, ngs_network_name_format='{network_id}')

    def test_init_rejects_missing_segmentation_id_format(self):
        """Test ngs_network_name_format missing segmentation_id is rejected."""
        self.assertRaises(
            exc.GenericSwitchNDFCConfigError,
            make_switch, ngs_network_name_format='static-name')

    def test_init_configuration(self):
        """Test driver initialization with proper configuration."""
        self.assertEqual(self.switch.ndfc_host, 'ndfc.example.com')
        self.assertEqual(self.switch.ndfc_port, 443)
        self.assertEqual(self.switch.ndfc_username, 'admin')
        self.assertEqual(self.switch.ndfc_password, 'password')
        self.assertEqual(self.switch.ndfc_fabric, 'test-fabric')
        self.assertEqual(self.switch.verify_tls, False)
        # ngs_verify_tls is a generic NGS option defaulting to True.
        self.assertTrue(make_switch(remove=['ngs_verify_tls']).verify_tls)
        self.assertEqual(self.switch.ndfc_timeout, 30)
        # Default trunk interface policy
        self.assertEqual(self.switch.ndfc_interface_policy, 'int_trunk_host')
        # ngs_max_connections comes from the base class (default 1).
        self.assertEqual(self.switch.ndfc_max_connections, 1)
        self.assertEqual(
            make_switch(ngs_max_connections=8).ndfc_max_connections, 8)

    def test_support_trunk_on_ports(self):
        """Test that trunk port binding is advertised as supported."""
        self.assertTrue(self.switch.support_trunk_on_ports)

    def test_support_trunk_on_bond_ports(self):
        """Test that trunk on bond ports is explicitly not supported."""
        self.assertFalse(self.switch.support_trunk_on_bond_ports)

    def test_api_base_url(self):
        """Test modern API base URL is correctly constructed."""
        expected = 'api/v1/manage/fabrics/test-fabric/'
        self.assertEqual(self.switch._api_base, expected)

    @mock.patch.object(cisco.CiscoNDFC, '_ndfc_request', autospec=True)
    def test_get_switch_serial(self, mock_request):
        """Test switch serial lookup using modern NDFC API."""
        # Modern API wraps switches in a "switches" key
        # and uses "fabricManagementIp" instead of "ipAddress"
        mock_request.return_value = {
            'switches': [
                {'fabricManagementIp': '192.168.1.99',
                 'serialNumber': 'ABC1111111',
                 'hostname': 'switch-1'},
                {'fabricManagementIp': '192.168.1.100',
                 'serialNumber': 'ABC1234567',
                 'hostname': 'test-switch'},
                {'fabricManagementIp': '192.168.1.101',
                 'serialNumber': 'ABC2222222',
                 'hostname': 'switch-3'}
            ]
        }

        serial = self.switch._get_switch_serial()

        self.assertEqual(serial, 'ABC1234567')
        # Lookup by hostname in NDFC inventory
        mock_request.assert_called_once_with(
            self.switch,
            'GET',
            'api/v1/manage/fabrics/test-fabric/switches'
        )

        # Test caching
        mock_request.reset_mock()
        serial_cached = self.switch._get_switch_serial()
        self.assertEqual(serial_cached, 'ABC1234567')
        mock_request.assert_not_called()

    @mock.patch.object(cisco.CiscoNDFC, '_ndfc_request', autospec=True)
    def test_get_switch_serial_by_hostname(self, mock_request):
        """Switch serial resolves by hostname when no ip is configured."""
        switch = make_switch(device_name='switch-3', remove=['ip'])
        mock_request.return_value = {
            'switches': [
                {'fabricManagementIp': '192.168.1.99',
                 'serialNumber': 'ABC1111111', 'hostname': 'switch-1'},
                {'fabricManagementIp': '192.168.1.101',
                 'serialNumber': 'ABC2222222', 'hostname': 'switch-3'},
            ]
        }

        self.assertEqual(switch._get_switch_serial(), 'ABC2222222')
        # No ip, so the full inventory is fetched (no query filter).
        mock_request.assert_called_once_with(
            switch, 'GET', 'api/v1/manage/fabrics/test-fabric/switches')

    @mock.patch.object(cisco.CiscoNDFC, '_ndfc_request', autospec=True)
    def test_get_switch_serial_explicit_no_lookup(self, mock_request):
        """An explicit serial number skips the inventory lookup entirely."""
        switch = make_switch(remove=['ip'], ndfc_switch_serial='SERIAL123')
        self.assertEqual(switch._get_switch_serial(), 'SERIAL123')
        mock_request.assert_not_called()

    @mock.patch.object(cisco.CiscoNDFC, '_ndfc_request', autospec=True)
    def test_get_switch_serial_not_found(self, mock_request):
        """Test switch serial lookup when IP not found."""
        mock_request.return_value = {
            'switches': [
                {'fabricManagementIp': '192.168.1.99',
                 'serialNumber': 'ABC1111111'}
            ]
        }

        self.assertRaises(
            exc.GenericSwitchNDFCConfigError,
            self.switch._get_switch_serial
        )

    @mock.patch.object(cisco.CiscoNDFC, '_ndfc_request', autospec=True)
    @mock.patch.object(cisco.CiscoNDFC, '_get_switch_serial', autospec=True)
    def test_add_network(self, mock_serial, mock_request):
        """Test VLAN network creation using modern NDFC API.

        add_network only creates the NDFC network object (fabric-level VLAN
        definition). Switch attachment and deployment are deferred to
        plug_port_to_network / plug_switch_to_network at port-binding time.
        """
        mock_serial.return_value = 'ABC1234567'

        self.switch.add_network(100, 'net-uuid-1234')

        # Should make exactly 1 API call: network creation only.
        # No networkAttachments and no deploy - those belong to
        # plug_port_to_network / plug_switch_to_network.
        self.assertEqual(mock_request.call_count, 1)

        # Check the single call - network creation
        call_args = mock_request.call_args_list[0]
        self.assertEqual(call_args[0][1], 'POST')
        self.assertEqual(
            call_args[0][2],
            'api/v1/manage/fabrics/test-fabric/networks'
        )

        # Validate network payload
        payload = call_args[1]['json']
        self.assertIn('networks', payload)
        network_config = payload['networks'][0]
        self.assertEqual(network_config['fabricName'], 'test-fabric')
        self.assertEqual(network_config['vlanId'], 100)
        # networkId same as vlanId for pure VLAN
        self.assertEqual(network_config['networkId'], 100)
        self.assertEqual(network_config['networkType'], 'vxlan')

    @mock.patch.object(cisco.CiscoNDFC, '_ndfc_request', autospec=True)
    @mock.patch.object(cisco.CiscoNDFC, '_get_switch_serial', autospec=True)
    def test_del_network(self, mock_serial, mock_request):
        """Test VLAN network deletion using modern NDFC API."""
        mock_serial.return_value = 'ABC1234567'

        self.switch.del_network(100, 'net-uuid-1234')

        # Should make 2 API calls: detach, then delete network object
        self.assertEqual(mock_request.call_count, 2)

        # First call - detach
        detach_call = mock_request.call_args_list[0]
        self.assertEqual(detach_call[0][1], 'POST')
        self.assertEqual(
            detach_call[0][2],
            'api/v1/manage/fabrics/test-fabric/networkAttachments'
        )
        detach_payload = detach_call[1]['json']
        self.assertIn('attachments', detach_payload)
        self.assertEqual(len(detach_payload['attachments']), 1)
        detachment = detach_payload['attachments'][0]
        self.assertFalse(detachment['attach'])
        self.assertEqual(detachment['switchId'], 'ABC1234567')
        self.assertEqual(detachment['vlanId'], 100)

        # Second call - delete network object
        delete_call = mock_request.call_args_list[1]
        self.assertEqual(delete_call[0][1], 'DELETE')
        self.assertEqual(
            delete_call[0][2],
            'api/v1/manage/fabrics/test-fabric/networks/100'
        )

    @mock.patch.object(cisco.CiscoNDFC, '_deploy_config', autospec=True)
    @mock.patch.object(cisco.CiscoNDFC, '_ndfc_request', autospec=True)
    @mock.patch.object(cisco.CiscoNDFC, '_get_switch_serial', autospec=True)
    def test_add_network_with_trunk_ports(
            self, mock_serial, mock_request, mock_deploy):
        """Test add_network appends VLAN to existing trunk port VLANs."""
        mock_serial.return_value = 'ABC1234567'

        # Mock GET interface to return existing VLANs: 10,20
        def side_effect(obj, method, url, **kwargs):
            if method == 'GET' and 'interface' in url:
                return [{
                    'policy': 'int_trunk_host',
                    'interfaces': [{
                        'nvPairs': {'ALLOWED_VLANS': '10,20'}
                    }]
                }]
            return {}

        mock_request.side_effect = side_effect

        switch = make_switch(ngs_trunk_ports='Eth1/49,Eth1/50')
        switch.add_network(100, 'net-uuid-1234')

        # Should make 7 API calls: POST networks, then per trunk port:
        # GET interface (Eth1/49), PUT interface (Eth1/49),
        # POST interface/deploy (Eth1/49),
        # GET interface (Eth1/50), PUT interface (Eth1/50),
        # POST interface/deploy (Eth1/50)
        self.assertEqual(mock_request.call_count, 7)

        # First call - network creation
        networks_call = mock_request.call_args_list[0]
        self.assertEqual(networks_call[0][1], 'POST')
        self.assertIn('networks', networks_call[0][2])

        # Calls 2-4: Eth1/49 GET + PUT + deploy
        get_49 = mock_request.call_args_list[1]
        self.assertEqual(get_49[0][1], 'GET')
        self.assertIn('Eth1/49', get_49[0][2])

        put_49 = mock_request.call_args_list[2]
        self.assertEqual(put_49[0][1], 'PUT')
        payload_49 = put_49[1]['json']
        self.assertEqual(payload_49['policy'], 'int_trunk_host')
        # Verify VLAN 100 is appended to existing VLANs 10,20
        self.assertEqual(
            payload_49['interfaces'][0]['nvPairs']['ALLOWED_VLANS'],
            '10,20,100')
        self.assertEqual(payload_49['interfaces'][0]['ifName'], 'Eth1/49')

        # Calls 5-7: Eth1/50 GET + PUT + deploy
        put_50 = mock_request.call_args_list[5]
        self.assertEqual(put_50[0][1], 'PUT')
        payload_50 = put_50[1]['json']
        # Verify same appending behavior for second trunk port
        self.assertEqual(
            payload_50['interfaces'][0]['nvPairs']['ALLOWED_VLANS'],
            '10,20,100')
        self.assertEqual(payload_50['interfaces'][0]['ifName'], 'Eth1/50')

        # _deploy_config called once after all trunk ports configured
        self.assertEqual(mock_deploy.call_count, 1)

    @mock.patch.object(cisco.CiscoNDFC, '_deploy_config', autospec=True)
    @mock.patch.object(cisco.CiscoNDFC, '_ndfc_request', autospec=True)
    @mock.patch.object(cisco.CiscoNDFC, '_get_switch_serial', autospec=True)
    def test_del_network_with_trunk_ports(
            self, mock_serial, mock_request, mock_deploy):
        """Test del_network removes VLAN from existing trunk port VLANs."""
        mock_serial.return_value = 'ABC1234567'

        # Mock GET interface to return existing VLANs: 10,100,200
        # Removing VLAN 100 should leave 10,200
        def side_effect(obj, method, url, **kwargs):
            if method == 'GET' and 'interface' in url:
                return [{
                    'policy': 'int_trunk_host',
                    'interfaces': [{
                        'nvPairs': {'ALLOWED_VLANS': '10,100,200'}
                    }]
                }]
            return {}

        mock_request.side_effect = side_effect

        switch = make_switch(ngs_trunk_ports='Eth1/49,Eth1/50')
        switch.del_network(100, 'net-uuid-1234')

        # Per trunk port: GET + PUT + POST interface/deploy
        # Plus: POST networkAttachments (detach) + DELETE network
        # = 2 trunk ports * 3 calls + 2 = 8 calls
        self.assertEqual(mock_request.call_count, 8)

        # First trunk port GET, then PUT
        get_call = mock_request.call_args_list[0]
        self.assertEqual(get_call[0][1], 'GET')
        self.assertIn('Eth1/49', get_call[0][2])

        put_call = mock_request.call_args_list[1]
        self.assertEqual(put_call[0][1], 'PUT')
        payload = put_call[1]['json']
        self.assertEqual(payload['policy'], 'int_trunk_host')
        # Verify VLAN 100 is removed, leaving 10,200
        self.assertEqual(
            payload['interfaces'][0]['nvPairs']['ALLOWED_VLANS'], '10,200')
        self.assertEqual(payload['interfaces'][0]['ifName'], 'Eth1/49')

        # Second trunk port should have same behavior
        put_call_2 = mock_request.call_args_list[4]
        self.assertEqual(put_call_2[0][1], 'PUT')
        payload_2 = put_call_2[1]['json']
        self.assertEqual(
            payload_2['interfaces'][0]['nvPairs']['ALLOWED_VLANS'], '10,200')
        self.assertEqual(payload_2['interfaces'][0]['ifName'], 'Eth1/50')

        # Should deploy after trunk port removal
        self.assertEqual(mock_deploy.call_count, 1)

    @mock.patch.object(cisco.CiscoNDFC, '_ndfc_request', autospec=True)
    @mock.patch.object(cisco.CiscoNDFC, '_get_switch_serial', autospec=True)
    def test_get_interface_allowed_vlans(self, mock_serial, mock_request):
        """Test parsing ALLOWED_VLANS from interface GET response."""
        mock_serial.return_value = 'FLM30040EZF'
        mock_request.return_value = [
            {
                'policy': 'int_trunk_host',
                'interfaces': [{
                    'serialNumber': 'FLM30040EZF',
                    'ifName': 'Ethernet1/1',
                    'nvPairs': {
                        'ALLOWED_VLANS': '746',
                        'BPDUGUARD_ENABLED': 'true',
                        'MTU': 'jumbo'
                    }
                }]
            }
        ]

        result = self.switch._get_interface_allowed_vlans(
            'FLM30040EZF', 'Ethernet1/1')

        self.assertEqual(result, {746})

    @mock.patch.object(cisco.CiscoNDFC, '_ndfc_request', autospec=True)
    @mock.patch.object(cisco.CiscoNDFC, '_get_switch_serial', autospec=True)
    def test_get_interface_allowed_vlans_not_found(
            self, mock_serial, mock_request):
        """Test ALLOWED_VLANS returns empty set when not in response."""
        mock_serial.return_value = 'FLM30040EZF'
        mock_request.return_value = [
            {
                'policy': 'int_access_host',
                'interfaces': [{
                    'serialNumber': 'FLM30040EZF',
                    'ifName': 'Ethernet1/1',
                    'nvPairs': {'ACCESS_VLAN': '100'}
                }]
            }
        ]

        result = self.switch._get_interface_allowed_vlans(
            'FLM30040EZF', 'Ethernet1/1')

        self.assertEqual(result, set())

    @mock.patch.object(cisco.CiscoNDFC, '_ndfc_request', autospec=True)
    @mock.patch.object(cisco.CiscoNDFC, '_get_switch_serial', autospec=True)
    def test_set_interface_policy_trunk(self, mock_serial, mock_request):
        """Test trunk interface policy with ALLOWED_VLANS."""
        mock_serial.return_value = 'ABC1234567'

        self.switch._set_interface_policy(
            'ABC1234567', 'Ethernet1/1',
            policy='int_trunk_host',
            vlan_key='ALLOWED_VLANS',
            vlan_value='100'
        )

        # Should make 2 calls: PUT to set policy, POST to deploy
        self.assertEqual(mock_request.call_count, 2)

        put_call = mock_request.call_args_list[0]
        self.assertEqual(put_call[0][1], 'PUT')
        self.assertIn('lan-fabric/rest/interface', put_call[0][2])
        payload = put_call[1]['json']
        self.assertEqual(payload['policy'], 'int_trunk_host')
        iface = payload['interfaces'][0]
        self.assertEqual(iface['serialNumber'], 'ABC1234567')
        self.assertEqual(iface['ifName'], 'Ethernet1/1')
        self.assertEqual(iface['nvPairs']['ALLOWED_VLANS'], '100')
        self.assertNotIn('ACCESS_VLAN', iface['nvPairs'])

        deploy_call = mock_request.call_args_list[1]
        self.assertEqual(deploy_call[0][1], 'POST')
        self.assertIn('lan-fabric/rest/interface/deploy', deploy_call[0][2])
        self.assertEqual(deploy_call[1]['json'][0]['serialNumber'],
                         'ABC1234567')
        self.assertEqual(deploy_call[1]['json'][0]['ifName'], 'Ethernet1/1')

    @mock.patch.object(cisco.CiscoNDFC, '_ndfc_request', autospec=True)
    @mock.patch.object(cisco.CiscoNDFC, '_get_switch_serial', autospec=True)
    def test_set_interface_policy_access(self, mock_serial, mock_request):
        """Test access interface policy with ACCESS_VLAN."""
        mock_serial.return_value = 'ABC1234567'

        self.switch._set_interface_policy(
            'ABC1234567', 'Ethernet1/1',
            policy='int_access_host',
            vlan_key='ACCESS_VLAN',
            vlan_value='100'
        )

        put_call = mock_request.call_args_list[0]
        payload = put_call[1]['json']
        self.assertEqual(payload['policy'], 'int_access_host')
        iface = payload['interfaces'][0]
        self.assertEqual(iface['nvPairs']['ACCESS_VLAN'], '100')
        self.assertNotIn('ALLOWED_VLANS', iface['nvPairs'])

    @mock.patch.object(cisco.CiscoNDFC, '_deploy_config', autospec=True)
    @mock.patch.object(cisco.CiscoNDFC, '_ndfc_request', autospec=True)
    @mock.patch.object(cisco.CiscoNDFC, '_get_switch_serial', autospec=True)
    def test_plug_port_to_network(
            self, mock_serial, mock_request, mock_deploy):
        """Test plugging port to network via interface policy API."""
        mock_serial.return_value = 'ABC1234567'

        self.switch.plug_port_to_network('Ethernet1/1', 100)

        # Should make 2 API calls: policy PUT, interface deploy
        self.assertEqual(mock_request.call_count, 2)

        # First call - interface policy PUT with ACCESS_VLAN
        policy_call = mock_request.call_args_list[0]
        self.assertEqual(policy_call[0][1], 'PUT')
        self.assertIn('lan-fabric/rest/interface', policy_call[0][2])
        payload = policy_call[1]['json']
        self.assertEqual(payload['policy'], 'int_access_host')
        iface = payload['interfaces'][0]
        self.assertEqual(iface['serialNumber'], 'ABC1234567')
        self.assertEqual(iface['ifName'], 'Ethernet1/1')
        self.assertEqual(iface['nvPairs']['ACCESS_VLAN'], '100')
        self.assertNotIn('ALLOWED_VLANS', iface['nvPairs'])

        # Second call - interface deploy
        deploy_call = mock_request.call_args_list[1]
        self.assertEqual(deploy_call[0][1], 'POST')
        self.assertIn('lan-fabric/rest/interface/deploy', deploy_call[0][2])

        # Should call _deploy_config for switch config sync
        mock_deploy.assert_called_once()

    @mock.patch.object(cisco.CiscoNDFC, '_deploy_config', autospec=True)
    @mock.patch.object(cisco.CiscoNDFC, '_ndfc_request', autospec=True)
    @mock.patch.object(cisco.CiscoNDFC, '_get_switch_serial', autospec=True)
    def test_delete_port(self, mock_serial, mock_request, mock_deploy):
        """Test removing port from network via interface policy API."""
        mock_serial.return_value = 'ABC1234567'

        self.switch.delete_port('Ethernet1/1', 100)

        # Should make 2 API calls: policy PUT with none, interface deploy
        self.assertEqual(mock_request.call_count, 2)

        # First call - interface policy PUT with ACCESS_VLAN set to default (1)
        policy_call = mock_request.call_args_list[0]
        self.assertEqual(policy_call[0][1], 'PUT')
        self.assertIn('lan-fabric/rest/interface', policy_call[0][2])
        payload = policy_call[1]['json']
        self.assertEqual(payload['policy'], 'int_access_host')
        iface = payload['interfaces'][0]
        self.assertEqual(iface['nvPairs']['ACCESS_VLAN'], '1')
        self.assertNotIn('ALLOWED_VLANS', iface['nvPairs'])

        # Should deploy
        mock_deploy.assert_called_once()

    @mock.patch.object(cisco.CiscoNDFC, '_deploy_config', autospec=True)
    @mock.patch.object(cisco.CiscoNDFC, '_ndfc_request', autospec=True)
    @mock.patch.object(cisco.CiscoNDFC, '_get_switch_serial', autospec=True)
    def test_plug_port_to_network_trunk(
            self, mock_serial, mock_request, mock_deploy):
        """Test trunk port binding sets int_trunk_host with NATIVE_VLAN."""
        mock_serial.return_value = 'ABC1234567'
        # Port has no existing VLANs
        mock_request.return_value = [
            {'policy': 'int_trunk_host',
             'interfaces': [{'nvPairs': {'ALLOWED_VLANS': 'none'}}]}
        ]

        trunk_details = {'sub_ports': [
            {'segmentation_id': 200},
            {'segmentation_id': 300},
        ]}
        self.switch.plug_port_to_network(
            'Ethernet1/1', 100, trunk_details=trunk_details)

        # Calls: GET (allowed_vlans), PUT, POST deploy
        self.assertEqual(mock_request.call_count, 3)

        put_call = mock_request.call_args_list[1]
        self.assertEqual(put_call[0][1], 'PUT')
        payload = put_call[1]['json']
        self.assertEqual(payload['policy'], 'int_trunk_host')
        nv_pairs = payload['interfaces'][0]['nvPairs']
        self.assertEqual(nv_pairs['NATIVE_VLAN'], '100')
        # All three VLANs should be in ALLOWED_VLANS
        allowed = set(nv_pairs['ALLOWED_VLANS'].split(','))
        self.assertIn('100', allowed)
        self.assertIn('200', allowed)
        self.assertIn('300', allowed)
        self.assertNotIn('ACCESS_VLAN', nv_pairs)

        mock_deploy.assert_called_once()

    @mock.patch.object(cisco.CiscoNDFC, '_deploy_config', autospec=True)
    @mock.patch.object(cisco.CiscoNDFC, '_ndfc_request', autospec=True)
    @mock.patch.object(cisco.CiscoNDFC, '_get_switch_serial', autospec=True)
    def test_plug_port_to_network_trunk_appends_existing_vlans(
            self, mock_serial, mock_request, mock_deploy):
        """Test trunk plug appends to existing ALLOWED_VLANS."""
        mock_serial.return_value = 'ABC1234567'
        # Port already has VLAN 50 on it
        mock_request.return_value = [
            {'policy': 'int_trunk_host',
             'interfaces': [{'nvPairs': {'ALLOWED_VLANS': '50'}}]}
        ]

        trunk_details = {'sub_ports': [{'segmentation_id': 200}]}
        self.switch.plug_port_to_network(
            'Ethernet1/1', 100, trunk_details=trunk_details)

        put_call = mock_request.call_args_list[1]
        nv_pairs = put_call[1]['json']['interfaces'][0]['nvPairs']
        allowed = set(nv_pairs['ALLOWED_VLANS'].split(','))
        self.assertIn('50', allowed)
        self.assertIn('100', allowed)
        self.assertIn('200', allowed)

    @mock.patch.object(cisco.CiscoNDFC, '_deploy_config', autospec=True)
    @mock.patch.object(cisco.CiscoNDFC, '_ndfc_request', autospec=True)
    @mock.patch.object(cisco.CiscoNDFC, '_get_switch_serial', autospec=True)
    def test_delete_port_trunk(self, mock_serial, mock_request, mock_deploy):
        """Test trunk delete_port strips native and sub-port VLANs."""
        mock_serial.return_value = 'ABC1234567'
        # Port has VLANs 100, 200, 300, 400
        mock_request.return_value = [
            {'policy': 'int_trunk_host',
             'interfaces': [{'nvPairs': {'ALLOWED_VLANS': '100,200,300,400'}}]}
        ]

        trunk_details = {'sub_ports': [
            {'segmentation_id': 200},
            {'segmentation_id': 300},
        ]}
        self.switch.delete_port(
            'Ethernet1/1', 100, trunk_details=trunk_details)

        # Calls: GET (allowed_vlans), PUT, POST deploy
        self.assertEqual(mock_request.call_count, 3)

        put_call = mock_request.call_args_list[1]
        self.assertEqual(put_call[0][1], 'PUT')
        payload = put_call[1]['json']
        self.assertEqual(payload['policy'], 'int_trunk_host')
        nv_pairs = payload['interfaces'][0]['nvPairs']
        # Only VLAN 400 should remain
        self.assertEqual(nv_pairs['ALLOWED_VLANS'], '400')
        # NATIVE_VLAN cleared
        self.assertEqual(nv_pairs['NATIVE_VLAN'], '')
        self.assertNotIn('ACCESS_VLAN', nv_pairs)

        mock_deploy.assert_called_once()

    @mock.patch.object(cisco.CiscoNDFC, '_deploy_config', autospec=True)
    @mock.patch.object(cisco.CiscoNDFC, '_ndfc_request', autospec=True)
    @mock.patch.object(cisco.CiscoNDFC, '_get_switch_serial', autospec=True)
    def test_delete_port_trunk_last_vlan_reverts_to_access(
            self, mock_serial, mock_request, mock_deploy):
        """Test trunk delete_port reverts to access mode with no VLANs left."""
        mock_serial.return_value = 'ABC1234567'
        # Port has only the VLANs being removed
        mock_request.return_value = [
            {'policy': 'int_trunk_host',
             'interfaces': [{'nvPairs': {'ALLOWED_VLANS': '100,200'}}]}
        ]

        trunk_details = {'sub_ports': [{'segmentation_id': 200}]}
        self.switch.delete_port(
            'Ethernet1/1', 100, trunk_details=trunk_details)

        put_call = mock_request.call_args_list[1]
        payload = put_call[1]['json']
        # Should revert to access mode
        self.assertEqual(payload['policy'], 'int_access_host')
        nv_pairs = payload['interfaces'][0]['nvPairs']
        self.assertEqual(nv_pairs['ACCESS_VLAN'], '1')
        self.assertNotIn('ALLOWED_VLANS', nv_pairs)
        self.assertNotIn('NATIVE_VLAN', nv_pairs)

        mock_deploy.assert_called_once()

    @mock.patch.object(cisco.CiscoNDFC, '_deploy_config', autospec=True)
    @mock.patch.object(cisco.CiscoNDFC, '_ndfc_request', autospec=True)
    @mock.patch.object(cisco.CiscoNDFC, '_get_switch_serial', autospec=True)
    def test_add_subports_on_trunk(
            self, mock_serial, mock_request, mock_deploy):
        """Test add_subports_on_trunk appends VLANs in a single PUT."""
        mock_serial.return_value = 'ABC1234567'
        # Port already has VLAN 100 on it
        mock_request.return_value = [
            {'policy': 'int_trunk_host',
             'interfaces': [{'nvPairs': {'ALLOWED_VLANS': '100'}}]}
        ]

        subports = [
            {'segmentation_id': 200},
            {'segmentation_id': 300},
        ]
        self.switch.add_subports_on_trunk({}, 'Ethernet1/1', subports)

        # Calls: GET (allowed_vlans), PUT, POST deploy
        self.assertEqual(mock_request.call_count, 3)

        put_call = mock_request.call_args_list[1]
        self.assertEqual(put_call[0][1], 'PUT')
        payload = put_call[1]['json']
        self.assertEqual(payload['policy'], 'int_trunk_host')
        allowed = set(
            payload['interfaces'][0]['nvPairs']['ALLOWED_VLANS'].split(','))
        self.assertIn('100', allowed)
        self.assertIn('200', allowed)
        self.assertIn('300', allowed)

        mock_deploy.assert_called_once()

    @mock.patch.object(cisco.CiscoNDFC, '_deploy_config', autospec=True)
    @mock.patch.object(cisco.CiscoNDFC, '_ndfc_request', autospec=True)
    @mock.patch.object(cisco.CiscoNDFC, '_get_switch_serial', autospec=True)
    def test_add_subports_on_trunk_appends_existing(
            self, mock_serial, mock_request, mock_deploy):
        """Test add_subports_on_trunk preserves VLANs not being added."""
        mock_serial.return_value = 'ABC1234567'
        mock_request.return_value = [
            {'policy': 'int_trunk_host',
             'interfaces': [{'nvPairs': {'ALLOWED_VLANS': '50,100'}}]}
        ]

        self.switch.add_subports_on_trunk(
            {}, 'Ethernet1/1', [{'segmentation_id': 200}])

        put_call = mock_request.call_args_list[1]
        allowed = set(
            put_call[1]['json']['interfaces'][0]['nvPairs'][
                'ALLOWED_VLANS'].split(','))
        self.assertIn('50', allowed)
        self.assertIn('100', allowed)
        self.assertIn('200', allowed)

    @mock.patch.object(cisco.CiscoNDFC, '_deploy_config', autospec=True)
    @mock.patch.object(cisco.CiscoNDFC, '_ndfc_request', autospec=True)
    @mock.patch.object(cisco.CiscoNDFC, '_get_switch_serial', autospec=True)
    def test_del_subports_on_trunk(
            self, mock_serial, mock_request, mock_deploy):
        """Test del_subports_on_trunk removes VLANs leaving others intact."""
        mock_serial.return_value = 'ABC1234567'
        mock_request.return_value = [
            {'policy': 'int_trunk_host',
             'interfaces': [{'nvPairs': {'ALLOWED_VLANS': '100,200,300,400'}}]}
        ]

        subports = [
            {'segmentation_id': 200},
            {'segmentation_id': 300},
        ]
        self.switch.del_subports_on_trunk({}, 'Ethernet1/1', subports)

        # Calls: GET (allowed_vlans), PUT, POST deploy
        self.assertEqual(mock_request.call_count, 3)

        put_call = mock_request.call_args_list[1]
        payload = put_call[1]['json']
        self.assertEqual(payload['policy'], 'int_trunk_host')
        allowed = set(
            payload['interfaces'][0]['nvPairs']['ALLOWED_VLANS'].split(','))
        self.assertNotIn('200', allowed)
        self.assertNotIn('300', allowed)
        self.assertIn('100', allowed)
        self.assertIn('400', allowed)

        mock_deploy.assert_called_once()

    @mock.patch.object(cisco.CiscoNDFC, '_deploy_config', autospec=True)
    @mock.patch.object(cisco.CiscoNDFC, '_ndfc_request', autospec=True)
    @mock.patch.object(cisco.CiscoNDFC, '_get_switch_serial', autospec=True)
    def test_del_subports_on_trunk_last_reverts_to_access(
            self, mock_serial, mock_request, mock_deploy):
        """Test del_subports_on_trunk reverts to access with no VLANs left."""
        mock_serial.return_value = 'ABC1234567'
        mock_request.return_value = [
            {'policy': 'int_trunk_host',
             'interfaces': [{'nvPairs': {'ALLOWED_VLANS': '200,300'}}]}
        ]

        subports = [
            {'segmentation_id': 200},
            {'segmentation_id': 300},
        ]
        self.switch.del_subports_on_trunk({}, 'Ethernet1/1', subports)

        put_call = mock_request.call_args_list[1]
        payload = put_call[1]['json']
        self.assertEqual(payload['policy'], 'int_access_host')
        nv_pairs = payload['interfaces'][0]['nvPairs']
        self.assertEqual(nv_pairs['ACCESS_VLAN'], '1')
        self.assertNotIn('ALLOWED_VLANS', nv_pairs)

        mock_deploy.assert_called_once()

    @mock.patch.object(cisco.CiscoNDFC, '_ndfc_request', autospec=True)
    @mock.patch.object(cisco.CiscoNDFC, '_get_switch_serial', autospec=True)
    def test_set_port_admin_state(self, mock_serial, mock_request):
        """Test _set_port_admin_state checks state then calls adminstatus."""
        mock_serial.return_value = 'ABC1234567'
        # Port is currently up (ADMIN_STATE=true), we want to shut it
        mock_request.return_value = [
            {'policy': 'int_access_host', 'interfaces': [
                {'nvPairs': {'ADMIN_STATE': 'true'}}
            ]}
        ]

        self.switch._set_port_admin_state('ABC1234567', 'Ethernet1/1', 'shut')

        # Should make 2 calls: GET to check state, POST adminstatus
        self.assertEqual(mock_request.call_count, 2)
        get_call = mock_request.call_args_list[0]
        self.assertEqual(get_call[0][1], 'GET')
        post_call = mock_request.call_args_list[1]
        self.assertEqual(post_call[0][1], 'POST')
        self.assertIn('adminstatus', post_call[0][2])
        self.assertEqual(post_call[1]['json']['operation'], 'shut')
        self.assertEqual(
            post_call[1]['json']['interfaces'][0]['serialNumber'],
            'ABC1234567')
        self.assertEqual(
            post_call[1]['json']['interfaces'][0]['ifName'], 'Ethernet1/1')

    @mock.patch.object(cisco.CiscoNDFC, '_ndfc_request', autospec=True)
    @mock.patch.object(cisco.CiscoNDFC, '_get_switch_serial', autospec=True)
    def test_set_port_admin_state_already_in_desired_state(
            self, mock_serial, mock_request):
        """Test _set_port_admin_state skips POST when in desired state."""
        mock_serial.return_value = 'ABC1234567'
        # Port is already shut (ADMIN_STATE=false)
        mock_request.return_value = [
            {'policy': 'int_access_host', 'interfaces': [
                {'nvPairs': {'ADMIN_STATE': 'false'}}
            ]}
        ]

        self.switch._set_port_admin_state('ABC1234567', 'Ethernet1/1', 'shut')

        # Should make only 1 call: GET to check state, no POST
        mock_request.assert_called_once()
        call_args = mock_request.call_args
        self.assertEqual(call_args[0][1], 'GET')

    @mock.patch.object(cisco.CiscoNDFC, '_deploy_config', autospec=True)
    @mock.patch.object(cisco.CiscoNDFC, '_ndfc_request', autospec=True)
    @mock.patch.object(cisco.CiscoNDFC, '_get_switch_serial', autospec=True)
    def test_plug_port_to_network_disable_inactive(
            self, mock_serial, mock_request, mock_deploy):
        """Test noshut is sent when ngs_disable_inactive_ports is enabled."""
        mock_serial.return_value = 'ABC1234567'
        switch = make_switch(ngs_disable_inactive_ports=True)
        # Port is currently shut, so noshut will be sent
        mock_request.return_value = [
            {'policy': 'int_access_host', 'interfaces': [
                {'nvPairs': {'ADMIN_STATE': 'false'}}
            ]}
        ]
        switch.plug_port_to_network('Ethernet1/1', 100)

        # Should make 4 calls: policy PUT, interface deploy, GET state, noshut
        self.assertEqual(mock_request.call_count, 4)

        noshut_call = mock_request.call_args_list[3]
        self.assertEqual(noshut_call[0][1], 'POST')
        self.assertIn('adminstatus', noshut_call[0][2])
        self.assertEqual(noshut_call[1]['json']['operation'], 'noshut')

    @mock.patch.object(cisco.CiscoNDFC, '_deploy_config', autospec=True)
    @mock.patch.object(cisco.CiscoNDFC, '_ndfc_request', autospec=True)
    @mock.patch.object(cisco.CiscoNDFC, '_get_switch_serial', autospec=True)
    def test_delete_port_disable_inactive(
            self, mock_serial, mock_request, mock_deploy):
        """Test shut is sent when ngs_disable_inactive_ports is enabled."""
        mock_serial.return_value = 'ABC1234567'
        switch = make_switch(ngs_disable_inactive_ports=True)
        # Port is currently up, so shut will be sent
        mock_request.return_value = [
            {'policy': 'int_access_host', 'interfaces': [
                {'nvPairs': {'ADMIN_STATE': 'true'}}
            ]}
        ]
        switch.delete_port('Ethernet1/1', 100)

        # Should make 4 calls: policy PUT, interface deploy, GET state, shut
        self.assertEqual(mock_request.call_count, 4)

        shut_call = mock_request.call_args_list[3]
        self.assertEqual(shut_call[0][1], 'POST')
        self.assertIn('adminstatus', shut_call[0][2])
        self.assertEqual(shut_call[1]['json']['operation'], 'shut')

    @mock.patch.object(cisco.CiscoNDFC, '_ndfc_request', autospec=True)
    @mock.patch.object(cisco.CiscoNDFC, '_get_switch_serial', autospec=True)
    def test_deploy_config(self, mock_serial, mock_request):
        """Test configuration deployment using LAN Fabric REST API."""
        mock_serial.return_value = 'ABC1234567'

        self.switch._deploy_config('ABC1234567')

        # Should make 1 call: POST config-deploy
        mock_request.assert_called_once()
        call_args = mock_request.call_args
        self.assertEqual(call_args[0][1], 'POST')
        self.assertEqual(
            call_args[0][2],
            'appcenter/cisco/ndfc/api/v1/lan-fabric/rest/control'
            '/fabrics/test-fabric/config-deploy/ABC1234567'
        )
        self.assertNotIn('json', call_args[1])

    def test_security_group_not_implemented(self):
        """Test that security groups raise NotImplementedError."""
        self.assertRaises(
            NotImplementedError,
            self.switch.add_security_group,
            'sg-123',
            []
        )


class TestCiscoNDFCVXLAN(unittest.TestCase):
    """Test VXLAN L2VNI support in Cisco NDFC driver."""

    def setUp(self):
        super(TestCiscoNDFCVXLAN, self).setUp()
        self.switch = make_switch()

    def test_l2vni_support_enabled(self):
        """Test that L2VNI support is enabled in driver."""
        self.assertTrue(self.switch.PLUG_SWITCH_TO_NETWORK)
        self.assertTrue(self.switch.UNPLUG_SWITCH_FROM_NETWORK)

    @mock.patch.object(cisco.CiscoNDFC, '_ndfc_request', autospec=True)
    @mock.patch.object(cisco.CiscoNDFC, '_get_switch_serial', autospec=True)
    def test_plug_switch_to_network(self, mock_serial, mock_request):
        """Test L2VNI configures VLAN SVI via interface policy API."""
        mock_serial.return_value = 'ABC1234567'

        self.switch.plug_switch_to_network(
            vni=5000,
            segmentation_id=100,
            physnet='physnet1'
        )

        # 3 API calls: POST networks, POST policies (switch_freeform),
        # POST config-deploy
        self.assertEqual(mock_request.call_count, 3)

        # Call 1 - network object creation
        networks_call = mock_request.call_args_list[0]
        self.assertEqual(networks_call[0][1], 'POST')
        self.assertIn('networks', networks_call[0][2])
        network_config = networks_call[1]['json']['networks'][0]
        self.assertEqual(network_config['networkId'], 5000)
        self.assertEqual(network_config['vlanId'], 100)
        self.assertEqual(network_config['networkType'], 'vxlan')

        # Call 2 - switch_freeform policy with vlan/vn-segment config
        policy_call = mock_request.call_args_list[1]
        self.assertEqual(policy_call[0][1], 'POST')
        self.assertIn('control/policies', policy_call[0][2])
        payload = policy_call[1]['json']
        self.assertEqual(payload['serialNumber'], 'ABC1234567')
        self.assertEqual(payload['entityType'], 'SWITCH')
        self.assertEqual(payload['templateName'], 'switch_freeform')
        self.assertIn('vlan 100', payload['nvPairs']['CONF'])
        self.assertIn('vn-segment 5000', payload['nvPairs']['CONF'])

        # Call 3 - config-deploy
        config_deploy_call = mock_request.call_args_list[2]
        self.assertEqual(config_deploy_call[0][1], 'POST')
        self.assertIn('config-deploy', config_deploy_call[0][2])

    @mock.patch.object(cisco.CiscoNDFC, '_ndfc_request', autospec=True)
    @mock.patch.object(cisco.CiscoNDFC, '_get_switch_serial', autospec=True)
    def test_unplug_switch_from_network(self, mock_serial, mock_request):
        """Test L2VNI removal clears vn-segment on VLAN SVI."""
        mock_serial.return_value = 'ABC1234567'

        self.switch.unplug_switch_from_network(
            vni=5000,
            segmentation_id=100,
            physnet='physnet1'
        )

        # 2 API calls: POST policies (switch_freeform no vn-segment),
        # POST config-deploy
        self.assertEqual(mock_request.call_count, 2)

        # Call 1 - switch_freeform policy to clear vn-segment
        policy_call = mock_request.call_args_list[0]
        self.assertEqual(policy_call[0][1], 'POST')
        self.assertIn('control/policies', policy_call[0][2])
        payload = policy_call[1]['json']
        self.assertEqual(payload['templateName'], 'switch_freeform')
        self.assertIn('vlan 100', payload['nvPairs']['CONF'])
        self.assertIn('no vn-segment', payload['nvPairs']['CONF'])

        # Call 2 - config-deploy
        config_deploy_call = mock_request.call_args_list[1]
        self.assertEqual(config_deploy_call[0][1], 'POST')
        self.assertIn('config-deploy', config_deploy_call[0][2])

    @mock.patch.object(cisco.CiscoNDFC, '_ndfc_request', autospec=True)
    @mock.patch.object(cisco.CiscoNDFC, '_get_switch_serial', autospec=True)
    def test_vlan_has_vni_true(self, mock_serial, mock_request):
        """Test vlan_has_vni returns True when network exists with VNI."""
        mock_serial.return_value = 'ABC1234567'
        # Network GET returns matching networkId and vlanId as integers
        # (as observed in real NDFC responses)
        mock_request.return_value = {
            'networkId': 5000,
            'vlanId': 100
        }

        self.assertTrue(self.switch.vlan_has_vni(100, 5000))

    @mock.patch.object(cisco.CiscoNDFC, '_ndfc_request', autospec=True)
    @mock.patch.object(cisco.CiscoNDFC, '_get_switch_serial', autospec=True)
    def test_vlan_has_vni_true_string_ids(self, mock_serial, mock_request):
        """Test vlan_has_vni handles string networkId/vlanId in response."""
        mock_serial.return_value = 'ABC1234567'
        mock_request.return_value = {
            'networkId': '5000',
            'vlanId': '100'
        }

        self.assertTrue(self.switch.vlan_has_vni(100, 5000))

    @mock.patch.object(cisco.CiscoNDFC, '_ndfc_request', autospec=True)
    @mock.patch.object(cisco.CiscoNDFC, '_get_switch_serial', autospec=True)
    def test_vlan_has_vni_false_vlan_mismatch(self, mock_serial, mock_request):
        """Test vlan_has_vni returns False when VLAN ID does not match."""
        mock_serial.return_value = 'ABC1234567'
        mock_request.return_value = {
            'networkId': 5000,
            'vlanId': 999  # different VLAN
        }

        self.assertFalse(self.switch.vlan_has_vni(100, 5000))

    @mock.patch.object(cisco.CiscoNDFC, '_ndfc_request', autospec=True)
    @mock.patch.object(cisco.CiscoNDFC, '_get_switch_serial', autospec=True)
    def test_vlan_has_vni_false_network_not_found(
            self, mock_serial, mock_request):
        """Test vlan_has_vni returns False when network does not exist."""
        mock_serial.return_value = 'ABC1234567'
        mock_request.side_effect = exc.GenericSwitchNDFCConfigError()

        self.assertFalse(self.switch.vlan_has_vni(100, 5000))

    @mock.patch.object(cisco.CiscoNDFC, '_ndfc_request', autospec=True)
    @mock.patch.object(cisco.CiscoNDFC, '_get_switch_serial', autospec=True)
    def test_vlan_has_ports_access_vlan(self, mock_serial, mock_request):
        """Test vlan_has_ports returns True when ACCESS_VLAN matches."""
        mock_serial.return_value = 'FLM30040EZF'
        mock_request.return_value = [
            {'policy': 'int_access_host', 'interfaces': [
                {'ifName': 'Ethernet1/1',
                 'nvPairs': {'ACCESS_VLAN': '100', 'ALLOWED_VLANS': ''}}
            ]},
            {'policy': 'int_trunk_host', 'interfaces': [
                {'ifName': 'Ethernet1/49',
                 'nvPairs': {'ALLOWED_VLANS': '200,300'}}
            ]},
        ]

        self.assertTrue(self.switch.vlan_has_ports(100))

        call_args = mock_request.call_args
        self.assertEqual(call_args[0][1], 'GET')
        self.assertIn('serialNumber=FLM30040EZF', call_args[0][2])

    @mock.patch.object(cisco.CiscoNDFC, '_ndfc_request', autospec=True)
    @mock.patch.object(cisco.CiscoNDFC, '_get_switch_serial', autospec=True)
    def test_vlan_has_ports_allowed_vlans(self, mock_serial, mock_request):
        """Test vlan_has_ports returns True when VLAN is in ALLOWED_VLANS."""
        mock_serial.return_value = 'FLM30040EZF'
        mock_request.return_value = [
            {'policy': 'int_trunk_host', 'interfaces': [
                {'ifName': 'Ethernet1/49',
                 'nvPairs': {'ALLOWED_VLANS': '100,200,300'}}
            ]},
        ]

        self.assertTrue(self.switch.vlan_has_ports(200))

    @mock.patch.object(cisco.CiscoNDFC, '_ndfc_request', autospec=True)
    @mock.patch.object(cisco.CiscoNDFC, '_get_switch_serial', autospec=True)
    def test_vlan_has_ports_not_found(self, mock_serial, mock_request):
        """Test vlan_has_ports returns False when VLAN not on any port."""
        mock_serial.return_value = 'FLM30040EZF'
        mock_request.return_value = [
            {'policy': 'int_access_host', 'interfaces': [
                {'ifName': 'Ethernet1/1',
                 'nvPairs': {'ACCESS_VLAN': '999'}}
            ]},
        ]

        self.assertFalse(self.switch.vlan_has_ports(100))

    @mock.patch.object(cisco.CiscoNDFC, '_ndfc_request', autospec=True)
    @mock.patch.object(cisco.CiscoNDFC, '_get_switch_serial', autospec=True)
    def test_vlan_has_ports_conservative_on_error(
            self, mock_serial, mock_request):
        """Test vlan_has_ports returns True conservatively on API error."""
        mock_serial.return_value = 'FLM30040EZF'
        mock_request.side_effect = exc.GenericSwitchNDFCConfigError()

        self.assertTrue(self.switch.vlan_has_ports(100))

    def test_parse_vlan_list_simple(self):
        """Test parsing simple VLAN list returns a set."""
        vlans = self.switch._parse_vlan_list('10,20,30')
        self.assertEqual(vlans, {10, 20, 30})

    def test_parse_vlan_list_with_range(self):
        """Test parsing VLAN list with range returns a set."""
        vlans = self.switch._parse_vlan_list('10,20-25,30')
        self.assertEqual(vlans, {10, 20, 21, 22, 23, 24, 25, 30})

    def test_parse_vlan_list_empty(self):
        """Test parsing empty VLAN list returns empty set."""
        vlans = self.switch._parse_vlan_list('')
        self.assertEqual(vlans, set())

    def test_parse_vlan_list_none_string(self):
        """Test parsing 'none' returns empty set."""
        vlans = self.switch._parse_vlan_list('none')
        self.assertEqual(vlans, set())

    def test_vlan_list_to_str_non_sequential(self):
        """Test serialising non-sequential VLANs gives comma-separated list."""
        self.assertEqual(self.switch._vlan_list_to_str({300, 100, 200}),
                         '100,200,300')

    def test_vlan_list_to_str_sequential_range(self):
        """Test sequential VLANs are collapsed into range notation."""
        self.assertEqual(
            self.switch._vlan_list_to_str({100, 200, 201, 202, 300}),
            '100,200-202,300')

    def test_vlan_list_to_str_single_range(self):
        """Test a fully sequential set produces a single range."""
        self.assertEqual(
            self.switch._vlan_list_to_str({10, 11, 12, 13}),
            '10-13')

    def test_vlan_list_to_str_single_vlan(self):
        """Test a single VLAN produces no range notation."""
        self.assertEqual(self.switch._vlan_list_to_str({100}), '100')

    def test_vlan_list_to_str_empty(self):
        """Test serialising an empty set returns 'none'."""
        self.assertEqual(self.switch._vlan_list_to_str(set()), 'none')

    def test_vlan_list_roundtrip(self):
        """Test that parse → serialise → parse is lossless."""
        original = {100, 200, 201, 202, 300, 301, 400}
        serialised = self.switch._vlan_list_to_str(original)
        self.assertEqual(self.switch._parse_vlan_list(serialised), original)


def _make_response(status_code=200, json_body=None, content=b'{}'):
    """Build a mock requests.Response with the given behaviour."""
    resp = mock.Mock()
    resp.status_code = status_code
    resp.content = content
    resp.json.return_value = json_body if json_body is not None else {}
    resp.raise_for_status.return_value = None
    return resp


def _http_error(status_code, json_body=None):
    """Build an HTTPError carrying a response, as raise_for_status would."""
    err_resp = mock.Mock()
    err_resp.status_code = status_code
    err_resp.json.return_value = json_body if json_body is not None else {}
    return requests.exceptions.HTTPError(response=err_resp)


class TestCiscoNDFCRequest(unittest.TestCase):
    """Tests for the _ndfc_request HTTP wrapper and its error handling."""

    def setUp(self):
        super(TestCiscoNDFCRequest, self).setUp()
        self.switch = make_switch()
        self.session = mock.Mock()
        self.pool_entry = {'session': self.session, 'token': 'tok',
                           'lock': mock.MagicMock()}
        patches = [
            mock.patch.object(cisco.CiscoNDFC, '_ensure_authenticated',
                              autospec=True, return_value='tok'),
            mock.patch.object(cisco.CiscoNDFC, '_reauthenticate',
                              autospec=True, return_value='tok2'),
            mock.patch.object(cisco.CiscoNDFC, '_get_session_pool_entry',
                              autospec=True, return_value=self.pool_entry),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def test_request_success_returns_parsed_body(self):
        """A successful response body is parsed and returned."""
        self.session.request.return_value = _make_response(
            json_body={'switches': []}, content=b'{"switches": []}')

        result = self.switch._ndfc_request('GET', 'some/endpoint')

        self.assertEqual(result, {'switches': []})
        self.assertEqual(self.session.request.call_count, 1)

    def test_request_empty_body_returns_empty_dict(self):
        """A response with no body yields an empty dict."""
        self.session.request.return_value = _make_response(content=b'')
        self.assertEqual(self.switch._ndfc_request('POST', 'x'), {})

    def test_request_embedded_failure_raises(self):
        """A 200 response whose body signals failure raises ConfigError."""
        self.session.request.return_value = _make_response(
            json_body={'message': 'operation failed'},
            content=b'{"message": "operation failed"}')

        self.assertRaises(
            exc.GenericSwitchNDFCConfigError,
            self.switch._ndfc_request, 'POST', 'x')

    def test_request_non_auth_http_error_raises(self):
        """A non-auth HTTP error is not retried and raises ConfigError."""
        resp = _make_response()
        resp.raise_for_status.side_effect = _http_error(500)
        self.session.request.return_value = resp

        self.assertRaises(
            exc.GenericSwitchNDFCConfigError,
            self.switch._ndfc_request, 'GET', 'x')
        self.assertEqual(self.session.request.call_count, 1)

    def test_request_auth_error_reauthenticates_and_retries(self):
        """A 401 triggers one re-auth and retry, then succeeds."""
        first = _make_response()
        first.raise_for_status.side_effect = _http_error(401)
        second = _make_response(
            json_body={'ok': True}, content=b'{"ok": true}')
        self.session.request.side_effect = [first, second]

        result = self.switch._ndfc_request('GET', 'x')

        self.assertEqual(result, {'ok': True})
        self.assertEqual(self.session.request.call_count, 2)
        self.switch._reauthenticate.assert_called_once()

    def test_request_connection_error_raises(self):
        """A transport-level error raises ConfigError."""
        self.session.request.side_effect = \
            requests.exceptions.ConnectionError('boom')

        self.assertRaises(
            exc.GenericSwitchNDFCConfigError,
            self.switch._ndfc_request, 'GET', 'x')

    def test_request_auth_error_retry_also_fails_raises(self):
        """A 401 that persists after re-auth raises after a single retry."""
        first = _make_response()
        first.raise_for_status.side_effect = _http_error(401)
        second = _make_response()
        second.raise_for_status.side_effect = _http_error(403)
        self.session.request.side_effect = [first, second]

        self.assertRaises(
            exc.GenericSwitchNDFCConfigError,
            self.switch._ndfc_request, 'GET', 'x')
        self.assertEqual(self.session.request.call_count, 2)
        self.switch._reauthenticate.assert_called_once()

    def test_request_sends_bearer_authorization_header(self):
        """The auth token is applied as a per-request Authorization header."""
        self.session.request.return_value = _make_response()

        self.switch._ndfc_request('GET', 'x')

        headers = self.session.request.call_args.kwargs['headers']
        self.assertEqual(headers['Authorization'], 'Bearer tok')

    def test_request_error_detail_propagates_to_exception(self):
        """A response body detail is surfaced in the raised exception."""
        resp = _make_response()
        resp.raise_for_status.side_effect = _http_error(
            500, json_body={'error': 'thing broke'})
        self.session.request.return_value = resp

        with self.assertRaises(exc.GenericSwitchNDFCConfigError) as cm:
            self.switch._ndfc_request('GET', 'x')
        self.assertIn('thing broke', str(cm.exception))
