# Copyright 2015 Mirantis, Inc.
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


import argparse
import os
import sys

from keystoneauth1 import identity
from keystoneauth1 import session
from neutronclient.v2_0 import client


parser = argparse.ArgumentParser(description='GenericSwitch functional test')
parser.add_argument('--switch_name',
                    type=str,
                    required=True,
                    help='Name of the switch')
parser.add_argument('--switch_id',
                    type=str,
                    required=True,
                    help='Switch id to create a local_link_information with')
parser.add_argument('--port',
                    type=str,
                    required=True,
                    help='OVS port to manage')
parser.add_argument('--network',
                    type=str,
                    default='private',
                    help='Neutron network name to create port in')
parser.add_argument('--auth-url',
                    type=str,
                    default='http://127.0.0.1:5000/v2.0',
                    help='Keystone auth URL endpoint')
parser.add_argument('--username',
                    type=str,
                    default='admin',
                    help='Keystone user name, must have admin access')
parser.add_argument('--password',
                    type=str,
                    default='admin',
                    help='Keystone user password, must have admin access')
parser.add_argument('--project-name',
                    type=str,
                    default='admin',
                    help='Keystone user project name, must have admin access')
opts = parser.parse_args()

auth_params = {
    "username": os.environ.get("OS_USERNAME", opts.username),
    "password": os.environ.get("OS_PASSWORD", opts.password),
    "tenant_name": os.environ.get("OS_PROJECT_NAME", opts.project_name),
}

auth = identity.V2Password(os.environ.get("OS_AUTH_URL", opts.auth_url),
                           **auth_params)
try:
    sess = session.Session(auth=auth)
    nc = client.Client(session=sess)

    network_name = opts.network

    network = nc.list_networks(name=network_name)['networks'][0]
    print(network['provider:segmentation_id'])

    create_body = {
        'port':
            {'network_id': network['id'],
             'admin_state_up': True,
             'name': 'generic_switch_test'
             }
    }
    port_id = nc.create_port(create_body)['port']['id']
    host = nc.list_agents(
        agent_type='Open vSwitch agent')['agents'][0]['host']
    update_body = {
        'port': {
            'device_owner': 'baremetal:none',
            'device_id': 'fake-instance-uuid',
            'admin_state_up': True,
            'binding:vnic_type': 'baremetal',
            'binding:host_id': host,
            'binding:profile': {
                'local_link_information': [{
                    'switch_info': opts.switch_name,
                    'switch_id': opts.switch_id,
                    'port_id': opts.port}]
            }
        }
    }

    nc.update_port(port_id, update_body)
except Exception as exc:
    msg = "Failed to create and update port, exception is %s" % exc
    sys.exit(msg)
