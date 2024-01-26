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


# I'd be happy to reuse ovs_lib from neutron.agent.common
# but Tempest all_plugin run tries to import the module
# and has an issue with importing CLI options
# Current approach is to re-implement a small subset of ovsctl commands

import json

from tempest.lib.cli import base


def get_port_tag_dict(port_name):
    ovsdb_json = json.loads(
        base.execute("sudo", "ovsdb-client dump Port name tag -f json"))

    for data in ovsdb_json['data']:
        name, tag = data
        if name == port_name:
            return tag
