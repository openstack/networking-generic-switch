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
               help='The backend URL to use for distributed coordination.'),
    cfg.IntOpt('acquire_timeout',
               min=0,
               default=60,
               help='Timeout is second after which an attempt to grab a lock '
                    'is failed. Value of 0 is forever.'),
]

CONF.register_opts(coordination_opts, group='ngs_coordination')


# NOTE(pas-ha) as this was a public method before (why, og why..)
# we can not simply drop it without proper deprecation
# TODO(pas-ha) remove n Queens
def get_config():
    LOG.warning("Usage of networking_generic_switch.config.get_config method "
                "is deprecated and this method will be removed after the Pike "
                "release or any time earlier if MultiConfigParser is removed "
                "from oslo_config. Use get_devices method directly.")
    multi_parser = cfg.MultiConfigParser()
    multi_parser.read(CONF.config_file)
    return multi_parser.parsed


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
