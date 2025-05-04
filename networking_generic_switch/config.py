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

import glob
import os

from oslo_config import cfg
from oslo_log import log as logging

CONF = cfg.CONF
LOG = logging.getLogger(__name__)

coordination_opts = [
    cfg.StrOpt('backend_url',
               secret=True,
               help='The backend URL to use for distributed coordination.'),
    cfg.IntOpt('acquire_timeout',
               min=0,
               default=60,
               help='Timeout in seconds after which an attempt to grab a lock '
                    'is failed. Value of 0 is forever.'),
]

ngs_opts = [
    cfg.StrOpt('session_log_file',
               default=None,
               help='Netmiko session log file.')
]

CONF.register_opts(coordination_opts, group='ngs_coordination')
CONF.register_opts(ngs_opts, group='ngs')


def config_files():
    """Generate which yields all config files in the required order"""
    for config_file in CONF.config_file:
        yield config_file
    for config_dir in CONF.config_dir:
        config_dir_glob = os.path.join(config_dir, '*.conf')
        for config_file in sorted(glob.glob(config_dir_glob)):
            yield config_file


def get_devices():
    """Parse supplied config files and fetch defined supported devices."""

    device_tag = 'genericswitch:'
    devices = {}

    for filename in config_files():
        LOG.debug(f'Searching for genericswitch config in: {filename}')
        sections = {}
        parser = cfg.ConfigParser(filename, sections)
        try:
            parser.parse()
        except IOError:
            continue
        for parsed_item, parsed_value in sections.items():
            if parsed_item.startswith(device_tag):
                LOG.debug(f'Found genericswitch config: {parsed_item}')
                dev_id = parsed_item.partition(device_tag)[2]
                device_cfg = {k: v[0] for k, v
                              in parsed_value.items()}
                devices[dev_id] = device_cfg

    return devices
