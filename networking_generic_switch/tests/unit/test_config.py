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

    @mock.patch('oslo_config.cfg.MultiConfigParser.read')
    def test_get_config(self, m_read):
        config.get_config()
        m_read.assert_called_with('The path')

    @mock.patch('networking_generic_switch.config.get_config')
    def test_get_devices(self, m_get_config):
        # get_config array
        m_get_config.return_value = [  # parsed_file dict
            {  # parsed_item str
                'genericswitch:foo':  # device_tag
                {  # parsed_file[device].items() dict
                    'device_type': ['foo_device'],  # {k: v[0] for k, v
                    'spam': ['eggs']
                },
                'genericswitch:bar':  # device_tag
                {  # parsed_file[device].items() dict
                    'device_type': ['bar_device'],  # {k: v[0] for k, v
                    'ham': ['vikings']
                }
            },
            {
                'other_driver:bar': {}
            }

        ]
        device_list = config.get_devices()
        m_get_config.assert_called_with()
        self.assertEqual(set(device_list), set(['foo', 'bar']))
        self.assertEqual({"device_type": "foo_device", "spam": "eggs"},
                         device_list['foo'])
        self.assertEqual({"device_type": "bar_device", "ham": "vikings"},
                         device_list['bar'])
