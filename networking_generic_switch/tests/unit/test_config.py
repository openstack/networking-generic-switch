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


import fixtures
import mock

from networking_generic_switch import config

from oslo_config import cfg
from oslo_config import fixture as config_fixture

CONF = cfg.CONF


class TestConfig(fixtures.TestWithFixtures):
    def setUp(self):
        super(TestConfig, self).setUp()
        CONF.reset()
        CONF.config_file = 'The path'
        self.cfg = self.useFixture(config_fixture.Config(CONF))
        self.cfg.register_opt(cfg.Opt(name='test'), 'baremetal')

    @mock.patch('oslo_config.cfg.MultiConfigParser.read')
    def test_get_config(self, m_read):
        config.get_config()
        m_read.assert_called_with('The path')

    @mock.patch('networking_generic_switch.config.get_config')
    def test_get_config_for_device(self, m_get_config):
        # get_config array
        m_get_config.return_value = [  # parsed_file dict
            {  # parsed_item str
                'genericswitch:base':  # device
                {  # parsed_file[device].items() dict
                    'device_type': ['cisco_ios']  # {k: v[0] for k, v
                }
            }
        ]
        device_cfg = config.get_config_for_device('base')
        self.assertEqual(device_cfg, {'device_type': 'cisco_ios'})
        m_get_config.assert_called_with()

    @mock.patch('networking_generic_switch.config.get_config')
    def test_get_device_list(self, m_get_config):
        # get_config array
        m_get_config.return_value = [  # parsed_file dict
            {  # parsed_item str
                'genericswitch:base':  # device_tag
                {  # parsed_file[device].items() dict
                    'device_type': ['cisco_ios']  # {k: v[0] for k, v
                },
                'genericswitch:cisco_ios':  # device_tag
                {  # parsed_file[device].items() dict
                    'device_type': ['cisco_ios']  # {k: v[0] for k, v
                }
            }
        ]
        device_list = config.get_device_list()
        self.assertEqual(set(device_list), set(['cisco_ios', 'base']))
        m_get_config.assert_called_with()
