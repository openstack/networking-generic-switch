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

import netifaces

from tempest.api.network import base as net_base
from tempest import config
from tempest.lib import decorators
from tempest.lib import exceptions
from tempest import test
from tempest_plugin.tests.common import ovs_lib

CONF = config.CONF


class NGSBasicOps(net_base.BaseAdminNetworkTest):

    """This smoke test tests the ovs_linux driver.

    It follows this basic set of operations:
        * Clear Resources
          ** Delete Bridge
          ** Delete Port
        * Add new Bridge in OVS
        * Add new Port in OVS
        * Remember and clear the port Tag
        * Create and Update Neutron port
        * Get new Tag from OVS
        * Assert that Tag created via Neutron is equal Tag in OVS
    """
    @classmethod
    def skip_checks(cls):
        super(NGSBasicOps, cls).skip_checks()
        if not CONF.service_available.ngs:
            raise cls.skipException('Networking Generic Switch is required.')

    def get_local_port_mac(self, bridge_name):
        mac_address = netifaces.ifaddresses(bridge_name).get('addr')
        return mac_address

    def cleanup_port(self, port_id):
        """Remove Neutron port and skip NotFound exceptions."""
        try:
            self.admin_ports_client.delete_port(port_id)
        except exceptions.NotFound:
            pass

    def create_neutron_port(self):
        net_id = self.admin_networks_client.list_networks(
            name=CONF.ngs.network_name
        )['networks'][0]['id']
        port = self.admin_ports_client.create_port(network_id=net_id)['port']
        self.addCleanup(self.cleanup_port, port['id'])

        host = self.admin_agents_client.list_agents(
            agent_type='Open vSwitch agent'
        )['agents'][0]['host']

        update_args = {
            'device_owner': 'baremetal:none',
            'device_id': 'fake-instance-uuid',
            'admin_state_up': True,
            'binding:vnic_type': 'baremetal',
            'binding:host_id': host,
            'binding:profile': {
                'local_link_information': [{
                    'switch_info': CONF.ngs.bridge_name,
                    'switch_id': self.get_local_port_mac(
                                 CONF.ngs.bridge_name
                        ),
                    'port_id': CONF.ngs.port_name}
                    ]
            }
        }
        self.admin_ports_client.update_port(
            port['id'],
            **update_args
        )

        return port

    def ovs_get_tag(self):
        try:
            tag = int(ovs_lib.get_port_tag_dict(CONF.ngs.port_name))
        except (ValueError, TypeError):
            tag = None
        return tag

    @decorators.idempotent_id('59cb81a5-3fd5-4ad3-8c4a-c0b27435cb9c')
    @test.services('network')
    def test_ngs_basic_ops(self):
        port = self.create_neutron_port()
        net_tag = self.admin_networks_client.list_networks(
            name=CONF.ngs.network_name
            )['networks'][0]['provider:segmentation_id']
        ovs_tag = self.ovs_get_tag()
        self.assertEqual(net_tag, ovs_tag)

        # Ensure that tag is removed when port is deleted
        self.admin_ports_client.delete_port(port['id'])
        ovs_tag = self.ovs_get_tag()
        self.assertIsNone(ovs_tag)
