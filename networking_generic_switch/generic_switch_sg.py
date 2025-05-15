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

import collections

from neutron.objects import ports as ports_obj
from neutron.objects import securitygroup as sg_obj
from neutron_lib.api.definitions import portbindings
from neutron_lib.callbacks import events
from neutron_lib.callbacks import registry
from neutron_lib.callbacks import resources
from neutron_lib.services import base as service_base
from oslo_config import cfg
from oslo_log import log as logging

from networking_generic_switch import devices
from networking_generic_switch.devices import utils as device_utils
from networking_generic_switch import exceptions as exc
from networking_generic_switch import utils as ngs_utils


LOG = logging.getLogger(__name__)
CONF = cfg.CONF


class GenericSwitchSecurityGroupHandler(service_base.ServicePluginBase):
    """Security Group Handler for generic networking hardware.

    Registers for the notification of security group updates.
    Once a notification is recieved, it takes appropriate actions by updating
    hardware appropriately.
    """

    def __init__(self):
        super(GenericSwitchSecurityGroupHandler, self).__init__()
        self.switches = {}
        self.subscribe()
        # filter the list of switches to only those that haven't explicitly
        # disabled port security
        for switch_info, switch in devices.get_devices().items():
            if switch.ngs_config.get('ngs_security_groups_enabled', True):
                self.switches[switch_info] = switch

        LOG.info('Devices %s have been loaded', self.switches.keys())
        if not self.switches:
            LOG.error('No devices have been loaded')

        # TODO(stevebaker) A periodic worker can be implemented to ensure
        # switch state is in sync with security group state. It would be
        # created here with:
        # self.add_worker(GenericSwitchSecurityGroupSyncWorker())

    def get_plugin_description(self):
        return "Generic switch baremetal security group service plugin"

    @classmethod
    def get_plugin_type(cls):
        return "generic_switch_security_group"

    def create_security_group(self, resource, event, trigger, payload):
        sg_id = payload.resource_id
        sg = sg_obj.SecurityGroup.get_object(payload.context, id=sg_id)
        for switch_name, switch in self.switches.items():
            try:
                switch.add_security_group(sg)
            except Exception as e:
                LOG.error("Failed to create security group %(sg_id)s "
                          "on device: %(switch)s, reason: %(exc)s",
                          {'sg_id': sg_id, 'switch': switch_name, 'exc': e})
                raise
            else:
                LOG.info('Security group %(sg_id)s has been added on device '
                         '%(device)s',
                         {'sg_id': sg_id, 'device': switch_name})

    def update_security_group_rules(self, resource, event, trigger, payload):
        sgr = payload.latest_state
        sg_id = sgr['security_group_id']
        sg = sg_obj.SecurityGroup.get_object(payload.context, id=sg_id)
        for switch_name, switch in self.switches.items():
            try:
                switch.update_security_group(sg)
            except Exception as e:
                LOG.error("Failed to add rule to security group %(sg_id)s "
                          "on device: %(switch)s, reason: %(exc)s",
                          {'sg_id': sg_id, 'switch': switch_name, 'exc': e})
                raise
            else:
                LOG.info('Rule has been added to security group %(sg_id)s '
                         'on device %(device)s',
                         {'sg_id': sg_id, 'device': switch_name})

    def delete_security_group(self, resource, event, trigger, payload):
        sg_id = payload.resource_id
        for switch_name, switch in self.switches.items():
            try:
                switch.del_security_group(sg_id)
            except Exception as e:
                LOG.error("Failed to delete security group %(sg_id)s "
                          "on device: %(switch)s, reason: %(exc)s",
                          {'sg_id': sg_id, 'switch': switch_name, 'exc': e})
                raise
            else:
                LOG.info('Security group %(sg_id)s has been deleted from '
                         '%(device)s',
                         {'sg_id': sg_id, 'device': switch_name})

    @staticmethod
    def _valid_baremetal_port(port):
        """Check if port is a baremetal port with exactly one security group"""
        if not ngs_utils.is_port_bound(port):
            return False
        if len(port.get('security_groups', [])) > 1:
            LOG.warning('SG provisioning failed for %(port)s. Only one '
                        'SG may be applied per port.',
                        {'port': port['id']})
            raise exc.GenericSwitchNotSupported(
                message='Only one security group can be bound to a port')
        return True

    def _get_switch_and_port_id(self, port):
        """Get the port id from the binding profile.

        The port id is stored in the binding profile as
        'local_link_information' and is used to bind the security group to the
        port on the switch.

        :param port: The port to check
        :returns: The switch object, port id, switch info, and switch id
        """
        binding_profile = port['binding:profile']
        local_link_information = binding_profile.get('local_link_information')
        if not local_link_information:
            return None, None, None, None
        for link in local_link_information:
            switch_info = link.get('switch_info')
            switch_id = link.get('switch_id')
            switch = device_utils.get_switch_device(
                self.switches, switch_info=switch_info,
                ngs_mac_address=switch_id)
            if not switch:
                continue
            port_id = link.get('port_id')
            LOG.info('Found port %(port_id)s on switch %(switch)s',
                     {'port_id': port_id, 'switch': switch_info})
            return switch, port_id, switch_info, switch_id
        return None, None, None, None

    def _all_security_group_ports(self, context, switch_info, switch_id):
        """Find all security groups and ports related to this switch

        :param context: Database context
        :param switch_info: Local link information switch_info
        :param switch_id: Local link information switch_id
        :returns: A dict with key security group ID and value set of
                  port names bound to that group
        """
        # iterate all baremetal ports and collect port names and security
        # group IDs related to this switch
        sg_ports = collections.defaultdict(set)
        ports = ports_obj.Port.get_ports_by_vnic_type_and_host(
            context, portbindings.VNIC_BAREMETAL)
        for port in ports:
            if not port.bindings:
                continue
            if not port.security_group_ids:
                continue

            port_ids = set()
            for binding in port.bindings:
                local_link_information = binding.profile.get(
                    'local_link_information', [])
                for link in local_link_information:
                    if not link.get('port_id'):
                        continue
                    if switch_info and link.get('switch_info') == switch_info:
                        port_ids.add(link.get('port_id'))
                    if switch_id and link.get('switch_id') == switch_id:
                        port_ids.add(link.get('port_id'))

            for sg_id in port.security_group_ids:
                sg_ports[sg_id].update(port_ids)

        return dict(sg_ports)

    def update_port_security_group(self, resource, event, trigger, payload):
        port = payload.latest_state
        prev_port = payload.states[0]
        if not self._valid_baremetal_port(port):
            return
        switch, port_id, switch_info, switch_id = \
            self._get_switch_and_port_id(port)
        if not switch or not port_id:
            return

        sgs = port.get('security_groups', [])
        if (ngs_utils.is_port_bound(port)
                and not ngs_utils.is_port_bound(prev_port)):
            # The port is being bound to a switch interface,
            # treat any security groups as being bound to the interface too
            prev_sgs = []
        else:
            prev_sgs = prev_port.get('security_groups', [])

        if set(sgs) == set(prev_sgs):
            # security groups have not changed, no bind changes required
            return

        sg_ports_all = self._all_security_group_ports(
            payload.context, switch_info, switch_id)

        # _valid_baremetal_port currently enforces there will be zero or
        # one security groups but we implement support for more than one
        # here regardless.
        for sg_id in prev_sgs:
            if sg_id not in sgs:
                # Security group missing from current state, removed in this
                # port update
                sg_ports = sg_ports_all.get(sg_id, [])
                switch.unbind_security_group(sg_id, port_id, sg_ports)
                LOG.info('Security group %(sg_id)s has been removed from '
                         'port %(port_id)s. All bound ports: %(sg_ports)s',
                         {'sg_id': sg_id, 'port_id': port_id,
                          'sg_ports': ', '.join(sg_ports)})
        for sg_id in sgs:
            if sg_id not in prev_sgs:
                # Security group added in this port update
                sg = sg_obj.SecurityGroup.get_object(payload.context, id=sg_id)
                sg_ports = sg_ports_all.get(sg_id, [])
                switch.bind_security_group(sg, port_id, sg_ports)
                LOG.info('Security group %(sg_id)s has been applied to port '
                         '%(port_id)s. All bound ports: %(sg_ports)s',
                         {'sg_id': sg_id, 'port_id': port_id,
                          'sg_ports': ', '.join(sg_ports)})

    def remove_port_security_group(self, resource, event, trigger, payload):
        port = payload.latest_state
        try:
            if not self._valid_baremetal_port(port):
                return
        except exc.GenericSwitchNotSupported:
            # this is a bound port with (somehow) multiple security groups
            # do best effort to unbind all
            pass

        switch, port_id, switch_info, switch_id = \
            self._get_switch_and_port_id(port)
        if not switch or not port_id:
            return

        sg_ports_all = self._all_security_group_ports(
            payload.context, switch_info, switch_id)

        sgs = port.get('security_groups', [])
        for sg_id in sgs:
            sg_ports = sg_ports_all.get(sg_id, [])
            switch.unbind_security_group(sg_id, port_id, sg_ports)
            LOG.info('Security group %(sg_id)s has been removed from '
                     'deleted port %(port_id)s. All bound ports: %(sg_ports)s',
                     {'sg_id': sg_id, 'port_id': port_id,
                      'sg_ports': ', '.join(sg_ports)})

    def subscribe(self):
        # Subscribe to the events related to security groups and rules.

        # Creates a new security group, and the payload may include existing
        # rules.
        registry.subscribe(
            self.create_security_group, resources.SECURITY_GROUP,
            events.AFTER_CREATE)
        # Deletes an existing security group.
        registry.subscribe(
            self.delete_security_group, resources.SECURITY_GROUP,
            events.AFTER_DELETE)

        # Adds one rule to an existing security group.
        registry.subscribe(
            self.update_security_group_rules, resources.SECURITY_GROUP_RULE,
            events.AFTER_CREATE)
        # Deletes one rule from an existing security group
        registry.subscribe(
            self.update_security_group_rules, resources.SECURITY_GROUP_RULE,
            events.AFTER_DELETE)

        # Apply/remove SG rules on AFTER_UPDATE.
        # Binds or unbinds a security group to a port.
        registry.subscribe(
            self.update_port_security_group, resources.PORT,
            events.AFTER_UPDATE)
        # Unbinds a security group from a port as part of port delete.
        registry.subscribe(
            self.remove_port_security_group, resources.PORT,
            events.AFTER_DELETE)
