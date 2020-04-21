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

import futurist
import futurist.waiters
import netifaces
from tempest.api.network import base as net_base
from tempest import config
from tempest.lib import decorators
from tempest.lib import exceptions
from tempest import test
from tempest_plugin.tests.common import ovs_lib

CONF = config.CONF


class NGSBasicOpsBase(net_base.BaseAdminNetworkTest):

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
        super(NGSBasicOpsBase, cls).skip_checks()
        if not CONF.service_available.ngs:
            raise cls.skipException('Networking Generic Switch is required.')

    def get_local_port_mac(self, bridge_name):
        mac_address = netifaces.ifaddresses(
            bridge_name)[netifaces.AF_LINK][0].get('addr')
        return mac_address

    def cleanup_port(self, port_id):
        """Remove Neutron port and skip NotFound exceptions."""
        try:
            self.admin_ports_client.delete_port(port_id)
        except exceptions.NotFound:
            pass

    def create_neutron_port(self, llc=None, port_name=None):
        port_name = port_name or CONF.ngs.port_name
        net_id = self.admin_networks_client.list_networks(
            name=CONF.ngs.network_name
        )['networks'][0]['id']
        port = self.admin_ports_client.create_port(
            network_id=net_id, name=port_name)['port']
        self.addCleanup(self.cleanup_port, port['id'])

        host = self.admin_agents_client.list_agents(
            agent_type='Open vSwitch agent'
        )['agents'][0]['host']

        if llc is None:
            llc = [{'switch_info': CONF.ngs.bridge_name,
                    'switch_id': self.get_local_port_mac(CONF.ngs.bridge_name),
                    'port_id': port_name}]

        update_args = {
            'device_owner': 'baremetal:none',
            'device_id': 'fake-instance-uuid',
            'admin_state_up': True,
            'binding:vnic_type': 'baremetal',
            'binding:host_id': host,
            'binding:profile': {
                'local_link_information': llc
            }
        }
        self.admin_ports_client.update_port(
            port['id'],
            **update_args
        )

        return port

    def ovs_get_tag(self, port_name=None):
        port_name = port_name or CONF.ngs.port_name
        try:
            tag = int(ovs_lib.get_port_tag_dict(port_name))
        except (ValueError, TypeError):
            tag = None
        return tag

    def _test_ngs_basic_ops(self, llc=None, port_name=None):
        port = self.create_neutron_port(llc=llc, port_name=port_name)
        net_tag = (self.admin_networks_client.list_networks(
            name=CONF.ngs.network_name)
            ['networks'][0]['provider:segmentation_id'])
        ovs_tag = self.ovs_get_tag(port_name=port_name)
        self.assertEqual(net_tag, ovs_tag)

        # Ensure that tag is removed when port is deleted
        self.admin_ports_client.delete_port(port['id'])
        ovs_tag = self.ovs_get_tag(port_name=port_name)
        self.assertIsNone(ovs_tag)


class NGSBasicOps(NGSBasicOpsBase):
    @decorators.idempotent_id('59cb81a5-3fd5-4ad3-8c4a-c0b27435cb9c')
    @test.services('network')
    def test_ngs_basic_ops(self):
        self._test_ngs_basic_ops()

    @decorators.idempotent_id('282a513d-cc01-486c-aa12-1c45f7b6e5a8')
    @test.services('network')
    def test_ngs_basic_ops_switch_id(self):
        llc = [{'switch_id': self.get_local_port_mac(CONF.ngs.bridge_name),
                'port_id': CONF.ngs.port_name}]
        self._test_ngs_basic_ops(llc=llc)


class NGSBasicDLMOps(NGSBasicOpsBase):

    @classmethod
    def skip_checks(cls):
        super(NGSBasicDLMOps, cls).skip_checks()
        if not CONF.ngs.port_dlm_concurrency:
            raise cls.skipException("DLM is not configured for n-g-s")

    def test_ngs_basic_dlm_ops(self):
        pool = futurist.ThreadPoolExecutor()
        self.addCleanup(pool.shutdown)
        fts = []
        for i in range(CONF.ngs.port_dlm_concurrency):
            fts.append(
                pool.submit(
                    self._test_ngs_basic_ops,
                    port_name='{base}_{ind}'.format(
                        base=CONF.ngs.port_name, ind=i)))

        executed = futurist.waiters.wait_for_all(fts)
        self.assertFalse(executed.not_done)
        # TODO(pas-ha) improve test error reporting here
        for ft in executed.done:
            self.assertIsNone(ft.exception())
