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

import fixtures
from oslo_config import fixture as config_fixture

from networking_generic_switch import config


fake_config = """
[genericswitch:foo]
device_type = foo_device
spam = eggs

[genericswitch:bar]
device_type = bar_device
ham = vikings
"""


class TestConfig(fixtures.TestWithFixtures):
    def setUp(self):
        super(TestConfig, self).setUp()
        self.cfg = self.useFixture(config_fixture.Config())
        self._patch_open()
        self.cfg.conf(args=["--config-file=/some/config/path"])

    def _patch_open(self):
        m = mock.mock_open(read_data=fake_config)
        # NOTE(pas-ha) mocks and iterators work differently in Py2 and Py3
        # http://bugs.python.org/issue21258
        m.return_value.__iter__ = lambda self: self
        m.return_value.__next__ = lambda self: next(iter(self.readline, ''))
        patcher = mock.patch('oslo_config.cfg.open', m)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_get_devices(self):
        device_list = config.get_devices()
        self.assertEqual(set(device_list), set(['foo', 'bar']))
        self.assertEqual({"device_type": "foo_device", "spam": "eggs"},
                         device_list['foo'])
        self.assertEqual({"device_type": "bar_device", "ham": "vikings"},
                         device_list['bar'])
