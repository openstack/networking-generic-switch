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

import fixtures
from neutron.objects import ports as ports_obj
from neutron.objects import securitygroup as sg_obj
from neutron_lib.callbacks import events
from neutron_lib.callbacks import registry
from neutron_lib.callbacks import resources
from oslo_config import fixture as config_fixture

from networking_generic_switch import devices
from networking_generic_switch import exceptions as exc
from networking_generic_switch import generic_switch_sg as sg
from networking_generic_switch import utils as ngs_utils


class TestGenericSwitchSecurityGroupHandler(fixtures.TestWithFixtures):

    def setUp(self):
        super(TestGenericSwitchSecurityGroupHandler, self).setUp()
        self.cfg = self.useFixture(config_fixture.Config())

        with mock.patch.object(devices, 'get_devices',
                               autospec=True) as mock_gd:
            self.switch1 = mock.Mock(ngs_config={
                'ngs_security_groups_enabled': True,
            })
            self.switch2 = mock.Mock(ngs_config={
                'ngs_security_groups_enabled': True,
            })
            self.switch3 = mock.Mock(ngs_config={
                'ngs_security_groups_enabled': False,
            })
            mock_gd.return_value = {
                'switch1': self.switch1,
                'switch2': self.switch2,
                'switch3': self.switch3
            }
            with mock.patch.object(registry, 'subscribe',
                                   autospec=True) as mock_subscribe:
                self.handler = sg.GenericSwitchSecurityGroupHandler()
                mock_subscribe.assert_has_calls([
                    mock.call(self.handler.create_security_group,
                              resources.SECURITY_GROUP,
                              events.AFTER_CREATE),
                    mock.call(self.handler.delete_security_group,
                              resources.SECURITY_GROUP,
                              events.AFTER_DELETE),
                    mock.call(self.handler.update_security_group_rules,
                              resources.SECURITY_GROUP_RULE,
                              events.AFTER_CREATE),
                    mock.call(self.handler.update_security_group_rules,
                              resources.SECURITY_GROUP_RULE,
                              events.AFTER_DELETE),
                    mock.call(self.handler.update_port_security_group,
                              resources.PORT,
                              events.AFTER_UPDATE),
                    mock.call(self.handler.remove_port_security_group,
                              resources.PORT,
                              events.AFTER_DELETE)
                ])

    @mock.patch.object(sg_obj.SecurityGroup, 'get_object', autospec=True)
    def test_create_security_group(self, m_get_object):
        sg = mock.Mock()
        sg.id = 'sg_id'
        sg.rules([])
        sg_data = {'id': sg.id, 'rules': []}
        m_get_object.return_value = sg

        payload = mock.Mock()
        payload.latest_state = sg_data
        payload.resource_id = sg.id

        self.handler.create_security_group(
            None, events.AFTER_CREATE, None, payload)
        m_get_object.assert_called_once_with(payload.context, id='sg_id')
        self.switch1.add_security_group.assert_called_once_with(
            sg)
        self.switch2.add_security_group.assert_called_once_with(
            sg)
        self.switch3.add_security_group.assert_not_called()

    def test_delete_security_group(self):
        payload = mock.Mock()
        payload.resource_id = 'sg_id'

        self.handler.delete_security_group(
            None, events.AFTER_DELETE, None, payload)
        self.switch1.del_security_group.assert_called_once_with('sg_id')
        self.switch2.del_security_group.assert_called_once_with('sg_id')
        self.switch3.del_security_group.assert_not_called()

    @mock.patch.object(sg_obj.SecurityGroup, 'get_object', autospec=True)
    def test_change_security_group_rule(self, m_get_object):
        rule = mock.Mock()
        rule.id = 'rule1'
        sg = mock.Mock()
        sg.id = 'sg_id'
        sg.rules([rule])
        m_get_object.return_value = sg

        rule_data = {'security_group_id': sg.id, 'id': rule.id}
        payload = mock.Mock()
        payload.latest_state = rule_data

        self.handler.update_security_group_rules(
            None, events.AFTER_CREATE, None, payload)
        m_get_object.assert_called_once_with(payload.context, id='sg_id')
        self.switch1.update_security_group.assert_called_once_with(sg)
        self.switch2.update_security_group.assert_called_once_with(sg)
        self.switch3.update_security_group.assert_not_called()

    def test__valid_baremetal_port(self):
        with mock.patch.object(ngs_utils, 'is_port_bound',
                               autospec=True) as mock_ipb:
            mock_ipb.return_value = True

            port = {'id': 'p1'}
            self.assertTrue(self.handler._valid_baremetal_port(port))
            port = {'id': 'p1', 'security_groups': []}
            self.assertTrue(self.handler._valid_baremetal_port(port))
            port = {'id': 'p1', 'security_groups': ['sg1', 'sg2']}
            self.assertRaises(exc.GenericSwitchNotSupported,
                              self.handler._valid_baremetal_port, port)
            port = {'id': 'p1', 'security_groups': ['sg1']}
            self.assertTrue(self.handler._valid_baremetal_port(port))

            mock_ipb.return_value = False
            port = {'id': 'p1', 'security_groups': ['sg1']}
            self.assertFalse(self.handler._valid_baremetal_port(port))

    def test_get_switch_and_port_id(self):
        port = {'binding:profile': {
            'local_link_information': [{'switch_info': 'switch1',
                                        'port_id': 'port1'}]}}
        switch, port_id, switch_info, switch_id = \
            self.handler._get_switch_and_port_id(port)
        self.assertEqual(switch, self.switch1)
        self.assertEqual(port_id, 'port1')
        self.assertEqual('switch1', switch_info)
        self.assertIsNone(switch_id)

        port = {'binding:profile': {}}
        switch, port_id, switch_info, switch_id = \
            self.handler._get_switch_and_port_id(port)
        self.assertIsNone(switch)
        self.assertIsNone(port_id)
        self.assertIsNone(switch_info)
        self.assertIsNone(switch_id)

        port = {'binding:profile': {
            'local_link_information': [{'switch_info': 'unknown_switch',
                                        'port_id': 'port1'}]}}
        switch, port_id, switch_info, switch_id = \
            self.handler._get_switch_and_port_id(port)
        self.assertIsNone(switch)
        self.assertIsNone(port_id)
        self.assertIsNone(switch_info)
        self.assertIsNone(switch_id)

    @mock.patch.object(ports_obj.Port, 'get_ports_by_vnic_type_and_host',
                       autospec=True)
    def test__all_security_group_ports(self, m_get_ports):
        m_get_ports.return_value = [
            # port with switch_info, 2 bindings
            mock.Mock(
                security_group_ids=['sg1', 'sg2', 'sg3'],
                bindings=[
                    mock.Mock(
                        profile={
                            'local_link_information': [{
                                'port_id': 'p1a',
                                'switch_info': '192.168.2.100'
                            }]
                        }
                    ),
                    mock.Mock(
                        profile={
                            'local_link_information': [{
                                'port_id': 'p1b',
                                'switch_info': '192.168.2.100'
                            }]
                        }
                    )
                ]
            ),
            # port with switch_id
            mock.Mock(
                security_group_ids=['sg1'],
                bindings=[
                    mock.Mock(
                        profile={
                            'local_link_information': [{
                                'port_id': 'p2',
                                'switch_id': '3c:e1:a1:4e:c6:a3'
                            }]
                        }
                    )
                ]
            ),
            # port with missing bindings
            mock.Mock(
                security_group_ids=['sg1'],
                bindings=None
            ),
            # port with missing security_group_ids
            mock.Mock(
                security_group_ids=None,
                bindings=[
                    mock.Mock(
                        profile={
                            'local_link_information': [{
                                'port_id': 'p4',
                                'switch_info': '192.168.2.100'
                            }]
                        }
                    )
                ]
            ),
            # port with not matching switch_info
            mock.Mock(
                security_group_ids=['sg1', 'sg2', 'sg3'],
                bindings=[
                    mock.Mock(
                        profile={
                            'local_link_information': [{
                                'port_id': 'p5',
                                'switch_info': '192.168.2.101'
                            }]
                        }
                    )
                ]
            ),
        ]
        context = mock.Mock()
        self.assertEqual(
            {
                'sg1': {'p1b', 'p1a', 'p2'},
                'sg2': {'p1b', 'p1a'},
                'sg3': {'p1b', 'p1a'}
            }, self.handler._all_security_group_ports(
                context, '192.168.2.100', '3c:e1:a1:4e:c6:a3'))

    @mock.patch.object(sg_obj.SecurityGroup, 'get_object', autospec=True)
    @mock.patch.object(sg.GenericSwitchSecurityGroupHandler,
                       '_all_security_group_ports', autospec=True)
    def test_update_port_security_group(self, m_asgp, m_get_object):
        sg = mock.Mock()
        sg.id = 'sg_id'
        sg.rules([])
        m_get_object.return_value = sg
        m_asgp.return_value = {}

        port_prev = {
            'id': '1234',
            'binding:profile': {
                'local_link_information': [{'switch_info': 'switch1',
                                            'port_id': 'port1'}]},
            'security_groups': [],
            'binding:vif_type': 'unbound',
            'binding:vnic_type': 'baremetal'}

        port = {
            'id': '1234',
            'binding:profile': {
                'local_link_information': [{'switch_info': 'switch1',
                                            'port_id': 'port1'}]},
            'security_groups': [],
            'binding:vif_type': 'other',
            'binding:vnic_type': 'baremetal'}

        payload = mock.Mock()
        payload.latest_state = port
        payload.states = [port_prev, port]

        # update from zero to one security groups
        port_prev['security_groups'] = []
        port['security_groups'] = ['sg1']
        m_asgp.return_value = {
            'sg1': ['port1', 'port2']
        }
        self.handler.update_port_security_group(
            None, events.AFTER_UPDATE, None, payload)
        self.switch1.bind_security_group.assert_called_once_with(
            sg, 'port1', ['port1', 'port2'])
        self.switch1.unbind_security_group.assert_not_called()

        # update with no security group changes but the port has just
        # become bound
        self.switch1.reset_mock()
        port_prev['security_groups'] = ['sg1']
        port['security_groups'] = ['sg1']
        self.handler.update_port_security_group(
            None, events.AFTER_UPDATE, None, payload)
        self.switch1.bind_security_group.assert_called_once_with(
            sg, 'port1', ['port1', 'port2'])
        self.switch1.unbind_security_group.assert_not_called()

        # update with no security group changes
        self.switch1.reset_mock()
        port_prev['security_groups'] = ['sg1']
        port_prev['binding:vif_type'] = 'other'
        port['security_groups'] = ['sg1']
        self.handler.update_port_security_group(
            None, events.AFTER_UPDATE, None, payload)
        self.switch1.unbind_security_group.assert_not_called()
        self.switch1.bind_security_group.assert_not_called()

        # update from one to zero security groups
        self.switch1.reset_mock()
        port_prev['security_groups'] = ['sg1']
        port['security_groups'] = []
        m_asgp.return_value = {
            'sg1': ['port2']
        }
        self.handler.update_port_security_group(
            None, events.AFTER_UPDATE, None, payload)
        self.switch1.unbind_security_group.assert_called_once_with(
            'sg1', 'port1', ['port2'])
        self.switch1.bind_security_group.assert_not_called()

        # update replacing one security group with another
        self.switch1.reset_mock()
        port_prev['security_groups'] = ['sg1']
        port['security_groups'] = ['sg2']
        m_asgp.return_value = {
            'sg2': ['port1']
        }
        self.handler.update_port_security_group(
            None, events.AFTER_UPDATE, None, payload)
        self.switch1.unbind_security_group.assert_called_once_with(
            'sg1', 'port1', [])
        self.switch1.bind_security_group.assert_called_once_with(
            sg, 'port1', ['port1'])

        # update from one to two security groups
        self.switch1.reset_mock()
        port_prev['security_groups'] = ['sg1']
        port['security_groups'] = ['sg1', 'sg2']
        self.assertRaises(exc.GenericSwitchNotSupported,
                          self.handler.update_port_security_group,
                          None, events.AFTER_UPDATE, None, payload)
        self.switch1.unbind_security_group.assert_not_called()
        self.switch1.bind_security_group.assert_not_called()

        # invalid port
        port['binding:vif_type'] = 'unbound'
        port_prev['security_groups'] = []
        port['security_groups'] = ['sg1']
        self.switch1.reset_mock()
        self.handler.update_port_security_group(
            None, events.AFTER_UPDATE, None, payload)
        self.switch1.bind_security_group.assert_not_called()

        port['binding:vif_type'] = 'other'
        # invalid profile
        del port['binding:profile']['local_link_information']
        self.switch1.reset_mock()
        self.handler.update_port_security_group(
            None, events.AFTER_UPDATE, None, payload)
        self.switch1.bind_security_group.assert_not_called()

    @mock.patch.object(sg.GenericSwitchSecurityGroupHandler,
                       '_all_security_group_ports', autospec=True)
    def test_remove_port_security_group(self, m_asgp):
        port = {
            'id': '1234',
            'binding:profile': {
                'local_link_information': [{'switch_info': 'switch1',
                                            'port_id': 'port1'}]},
            'security_groups': ['sg1'],
            'binding:vif_type': 'other',
            'binding:vnic_type': 'baremetal'}
        payload = mock.Mock()
        payload.latest_state = port
        m_asgp.return_value = {}

        # no security groups to unbind
        port['security_groups'] = []
        self.handler.remove_port_security_group(
            None, events.AFTER_DELETE, None, payload)
        self.switch1.unbind_security_group.assert_not_called()

        # unbind one security group
        self.switch1.reset_mock()
        port['security_groups'] = ['sg1']
        m_asgp.return_value = {
            'sg1': ['port2']
        }
        self.handler.remove_port_security_group(
            None, events.AFTER_DELETE, None, payload)
        self.switch1.unbind_security_group.assert_called_once_with(
            'sg1', 'port1', ['port2'])

        # unbind two security groups
        self.switch1.reset_mock()
        port['security_groups'] = ['sg1', 'sg2']
        m_asgp.return_value = {
            'sg1': ['port3']
        }
        self.handler.remove_port_security_group(
            None, events.AFTER_DELETE, None, payload)
        self.switch1.unbind_security_group.assert_has_calls([
            mock.call('sg1', 'port1', ['port3']),
            mock.call('sg2', 'port1', []),
        ])

        # invalid port
        port['binding:vnic_type'] = 'normal'
        self.switch1.reset_mock()
        self.handler.remove_port_security_group(
            None, events.AFTER_DELETE, None, payload)
        self.switch1.unbind_security_group.assert_not_called()

        port['binding:vnic_type'] = 'baremetal'
        # invalid profile
        del port['binding:profile']['local_link_information']
        self.switch1.reset_mock()
        self.handler.remove_port_security_group(
            None, events.AFTER_DELETE, None, payload)
        self.switch1.unbind_security_group.assert_not_called()
