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


def get_devices():
    """Parse supplied config files and fetch defined supported devices."""

    device_tag = 'genericswitch:'
    devices = {}

    for filename in CONF.config_file:
        sections = {}
        parser = cfg.ConfigParser(filename, sections)
        try:
            parser.parse()
        except IOError:
            continue
        for parsed_item, parsed_value in sections.items():
            if parsed_item.startswith(device_tag):
                dev_id = parsed_item.partition(device_tag)[2]
                device_cfg = {k: v[0] for k, v
                              in parsed_value.items()}
                devices[dev_id] = device_cfg

    return devices
