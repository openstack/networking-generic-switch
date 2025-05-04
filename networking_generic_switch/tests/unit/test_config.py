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

import os
import shutil
import tempfile

import fixtures
from oslo_config import fixture as config_fixture

from networking_generic_switch import config


fake_config = """
[genericswitch:foo]
device_type = foo_device
spam = eggs
"""

fake_config_bar = """
[genericswitch:bar]
device_type = bar_device
ham = vikings
"""

fake_config_baz = """
[genericswitch:baz]
device_type = baz_device
truffle = brandy
"""


class TestConfig(fixtures.TestWithFixtures):
    def setUp(self):
        super(TestConfig, self).setUp()

        config_file_foo = tempfile.NamedTemporaryFile(
            suffix=".conf", prefix="ngs-", delete=False).name
        self.addCleanup(os.remove, config_file_foo)

        config_dir = tempfile.mkdtemp('-ngs', 'bar-')
        self.addCleanup(shutil.rmtree, config_dir)

        config_file_bar = os.path.join(config_dir, 'bar.conf')
        config_file_baz = os.path.join(config_dir, 'baz.conf')

        with open(config_file_foo, 'w') as f:
            f.write(fake_config)
        with open(config_file_bar, 'w') as f:
            f.write(fake_config_bar)
        with open(config_file_baz, 'w') as f:
            f.write(fake_config_baz)

        self.cfg = self.useFixture(config_fixture.Config())
        self.cfg.conf(args=[f"--config-file={config_file_foo}",
                            f"--config-dir={config_dir}"])

    def test_get_devices(self):
        device_list = config.get_devices()
        self.assertEqual(set(device_list), set(['foo', 'bar', 'baz']))
        self.assertEqual({"device_type": "foo_device", "spam": "eggs"},
                         device_list['foo'])
        self.assertEqual({"device_type": "bar_device", "ham": "vikings"},
                         device_list['bar'])
        self.assertEqual({"device_type": "baz_device", "truffle": "brandy"},
                         device_list['baz'])
