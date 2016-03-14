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


def get_config():
    CONF = cfg.CONF
    multi_parser = cfg.MultiConfigParser()
    multi_parser.read(CONF.config_file)

    return multi_parser.parsed


def get_devices():

    device_tag = 'genericswitch:'
    devices = {}

    for parsed_file in get_config():
        for parsed_item, parsed_value in parsed_file.items():
            if parsed_item.startswith(device_tag):
                dev_id = parsed_item.partition(device_tag)[2]
                device_cfg = {k: v[0] for k, v
                              in parsed_value.items()}
                devices[dev_id] = device_cfg
    return devices
