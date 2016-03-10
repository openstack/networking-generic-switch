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

from networking_generic_switch import devices
from networking_generic_switch.devices import cisco_ios
from networking_generic_switch import exceptions as exc

from oslo_config import cfg

CONF = cfg.CONF


@mock.patch('networking_generic_switch.config.get_config')
class TestDevices(fixtures.TestWithFixtures):
    def setUp(self):
        super(TestDevices, self).setUp()

    def test_get_device(self, m_get_config):
        # get_config array
        m_get_config.return_value = [  # parsed_file dict
            {  # parsed_item str
                'genericswitch:cisco_ios':  # device
                {  # parsed_file[device].items() dict
                    'device_type': ['cisco_ios']  # {k: v[0] for k, v
                }
            }
        ]
        device = devices.get_device('cisco_ios')
        self.assertIs(type(device), cisco_ios.CiscoIos)
        m_get_config.assert_called_with()

    def test_get_device_not_supported(self, m_get_config):
        # get_config array
        m_get_config.return_value = [  # parsed_file dict
            {  # parsed_item str
                'genericswitch:a10':  # device
                {  # parsed_file[device].items() dict
                    'device_type': ['a10']  # {k: v[0] for k, v
                }
            }
        ]
        self.assertRaises(exc.GenericSwitchNotSupported,
                          devices.get_device,
                          'not_supported')
        m_get_config.assert_called_with()

        self.assertRaises(exc.GenericSwitchNotSupported,
                          devices.get_device,
                          None)
        m_get_config.assert_called_with()

        self.assertRaises(exc.GenericSwitchNotSupported,
                          devices.get_device,
                          u'a10')  # no file in devices,
        # but supported by netmiko
        m_get_config.assert_called_with()
