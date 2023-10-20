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

import sys

from neutron.db import provisioning_blocks
from neutron_lib.api.definitions import portbindings
from neutron_lib.callbacks import resources
from neutron_lib import constants as const
from neutron_lib.plugins.ml2 import api
from oslo_log import log as logging

from networking_generic_switch import config as gsw_conf
from networking_generic_switch import devices
from networking_generic_switch.devices import utils as device_utils

LOG = logging.getLogger(__name__)

GENERIC_SWITCH_ENTITY = 'GENERICSWITCH'


class GenericSwitchDriver(api.MechanismDriver):

    def initialize(self):
        """Perform driver initialization.

        Called after all drivers have been loaded and the database has
        been initialized. No abstract methods defined below will be
        called prior to this method being called.
        """

        self.vif_details = {portbindings.VIF_DETAILS_CONNECTIVITY:
                            portbindings.CONNECTIVITY_L2}

        gsw_devices = gsw_conf.get_devices()
        self.switches = {}
        for switch_info, device_cfg in gsw_devices.items():
            switch = devices.device_manager(device_cfg, switch_info)
            self.switches[switch_info] = switch

        LOG.info('Devices %s have been loaded', self.switches.keys())
        if not self.switches:
            LOG.error('No devices have been loaded')

    def create_network_precommit(self, context):
        """Allocate resources for a new network.

        :param context: NetworkContext instance describing the new
            network.

        Create a new network, allocating resources as necessary in the
        database. Called inside transaction context on session. Call
        cannot block.  Raising an exception will result in a rollback
        of the current transaction.
        """
        pass

    def create_network_postcommit(self, context):
        """Create a network.

        :param context: NetworkContext instance describing the new
            network.

        Called after the transaction commits. Call can block, though
        will block the entire process so care should be taken to not
        drastically affect performance. Raising an exception will
        cause the deletion of the resource.
        """

        network = context.current
        network_id = network['id']
        provider_type = network.get('provider:network_type')
        segmentation_id = network.get('provider:segmentation_id')
        physnet = network.get('provider:physical_network')

        if provider_type == 'vlan' and segmentation_id:
            # Create vlan on all switches from this driver
            for switch_name, switch in self._get_devices_by_physnet(physnet):
                try:
                    switch.add_network(segmentation_id, network_id)
                except Exception as e:
                    LOG.error("Failed to create network %(net_id)s "
                              "on device: %(switch)s, reason: %(exc)s",
                              {'net_id': network_id,
                               'switch': switch_name,
                               'exc': e})
                    raise
                else:
                    LOG.info('Network %(net_id)s has been added on device '
                             '%(device)s', {'net_id': network['id'],
                                            'device': switch_name})

    def update_network_precommit(self, context):
        """Update resources of a network.

        :param context: NetworkContext instance describing the new
             state of the network, as well as the original state prior
             to the update_network call.

        Update values of a network, updating the associated resources
        in the database. Called inside transaction context on session.
        Raising an exception will result in rollback of the
        transaction.

        update_network_precommit is called for all changes to the
        network state. It is up to the mechanism driver to ignore
        state or state changes that it does not know or care about.

        """
        pass

    def update_network_postcommit(self, context):
        """Update a network.

        :param context: NetworkContext instance describing the new
            state of the network, as well as the original state prior
            to the update_network call.

        Called after the transaction commits. Call can block, though
        will block the entire process so care should be taken to not
        drastically affect performance. Raising an exception will
        cause the deletion of the resource.

        update_network_postcommit is called for all changes to the
        network state.  It is up to the mechanism driver to ignore
        state or state changes that it does not know or care about.
        """
        pass

    def delete_network_precommit(self, context):
        """Delete resources for a network.

        :param context: NetworkContext instance describing the current
            state of the network, prior to the call to delete it.

        Delete network resources previously allocated by this
        mechanism driver for a network. Called inside transaction
        context on session. Runtime errors are not expected, but
        raising an exception will result in rollback of the
        transaction.
        """
        pass

    def delete_network_postcommit(self, context):
        """Delete a network.

        :param context: NetworkContext instance describing the current
            state of the network, prior to the call to delete it.

        Called after the transaction commits. Call can block, though
        will block the entire process so care should be taken to not
        drastically affect performance. Runtime errors are not
        expected, and will not prevent the resource from being
        deleted.
        """
        network = context.current
        provider_type = network.get('provider:network_type')
        segmentation_id = network.get('provider:segmentation_id')
        physnet = network.get('provider:physical_network')

        if provider_type == 'vlan' and segmentation_id:
            # Delete vlan on all switches from this driver
            exc_info = None
            for switch_name, switch in self._get_devices_by_physnet(physnet):
                try:
                    switch.del_network(segmentation_id, network['id'])
                except Exception as e:
                    LOG.error("Failed to delete network %(net_id)s "
                              "on device: %(switch)s, reason: %(exc)s",
                              {'net_id': network['id'],
                               'switch': switch_name,
                               'exc': e})
                    # Save any exceptions for later reraise.
                    exc_info = sys.exc_info()
                else:
                    LOG.info('Network %(net_id)s has been deleted on device '
                             '%(device)s', {'net_id': network['id'],
                                            'device': switch_name})
            if exc_info:
                raise exc_info[1]

    def create_subnet_precommit(self, context):
        """Allocate resources for a new subnet.

        :param context: SubnetContext instance describing the new
            subnet.

        rt = context.current
        device_id = port['device_id']
        device_owner = port['device_owner']
        Create a new subnet, allocating resources as necessary in the
        database. Called inside transaction context on session. Call
        cannot block.  Raising an exception will result in a rollback
        of the current transaction.
        """
        pass

    def create_subnet_postcommit(self, context):
        """Create a subnet.

        :param context: SubnetContext instance describing the new
            subnet.

        Called after the transaction commits. Call can block, though
        will block the entire process so care should be taken to not
        drastically affect performance. Raising an exception will
        cause the deletion of the resource.
        """
        pass

    def update_subnet_precommit(self, context):
        """Update resources of a subnet.

        :param context: SubnetContext instance describing the new
            state of the subnet, as well as the original state prior
            to the update_subnet call.

        Update values of a subnet, updating the associated resources
        in the database. Called inside transaction context on session.
        Raising an exception will result in rollback of the
        transaction.

        update_subnet_precommit is called for all changes to the
        subnet state. It is up to the mechanism driver to ignore
        state or state changes that it does not know or care about.
        """
        pass

    def update_subnet_postcommit(self, context):
        """Update a subnet.

        :param context: SubnetContext instance describing the new
            state of the subnet, as well as the original state prior
            to the update_subnet call.

        Called after the transaction commits. Call can block, though
        will block the entire process so care should be taken to not
        drastically affect performance. Raising an exception will
        cause the deletion of the resource.

        update_subnet_postcommit is called for all changes to the
        subnet state.  It is up to the mechanism driver to ignore
        state or state changes that it does not know or care about.
        """
        pass

    def delete_subnet_precommit(self, context):
        """Delete resources for a subnet.

        :param context: SubnetContext instance describing the current
            state of the subnet, prior to the call to delete it.

        Delete subnet resources previously allocated by this
        mechanism driver for a subnet. Called inside transaction
        context on session. Runtime errors are not expected, but
        raising an exception will result in rollback of the
        transaction.
        """
        pass

    def delete_subnet_postcommit(self, context):
        """Delete a subnet.

        :param context: SubnetContext instance describing the current
            state of the subnet, prior to the call to delete it.

        Called after the transaction commits. Call can block, though
        will block the entire process so care should be taken to not
        drastically affect performance. Runtime errors are not
        expected, and will not prevent the resource from being
        deleted.
        """
        pass

    def create_port_precommit(self, context):
        """Allocate resources for a new port.

        :param context: PortContext instance describing the port.

        Create a new port, allocating resources as necessary in the
        database. Called inside transaction context on session. Call
        cannot block.  Raising an exception will result in a rollback
        of the current transaction.
        """
        pass

    def create_port_postcommit(self, context):
        """Create a port.

        :param context: PortContext instance describing the port.

        Called after the transaction completes. Call can block, though
        will block the entire process so care should be taken to not
        drastically affect performance.  Raising an exception will
        result in the deletion of the resource.
        """
        pass

    def update_port_precommit(self, context):
        """Update resources of a port.

        :param context: PortContext instance describing the new
            state of the port, as well as the original state prior
            to the update_port call.

        Called inside transaction context on session to complete a
        port update as defined by this mechanism driver. Raising an
        exception will result in rollback of the transaction.

        update_port_precommit is called for all changes to the port
        state. It is up to the mechanism driver to ignore state or
        state changes that it does not know or care about.
        """
        pass

    def update_port_postcommit(self, context):
        """Update a port.

        :param context: PortContext instance describing the new
            state of the port, as well as the original state prior
            to the update_port call.

        Called after the transaction completes. Call can block, though
        will block the entire process so care should be taken to not
        drastically affect performance.  Raising an exception will
        result in the deletion of the resource.

        update_port_postcommit is called for all changes to the port
        state. It is up to the mechanism driver to ignore state or
        state changes that it does not know or care about.
        """
        port = context.current
        network = context.network.current
        if self._is_port_bound(port):
            binding_profile = port['binding:profile']
            local_link_information = binding_profile.get(
                'local_link_information')
            if not local_link_information:
                return
            # Necessary because the "provisioning_complete" event triggers
            # an additional call to update_port_postcommit().  We don't
            # want to configure the port a second time.
            if port['status'] == const.PORT_STATUS_ACTIVE:
                LOG.debug("Port %(port_id)s is already active, "
                          "not doing anything",
                          {'port_id': port['id']})
                return
            # If binding has already succeeded, we should have valid links
            # at this point, but check just in case.
            if not self._is_link_valid(port, network):
                return
            is_802_3ad = self._is_802_3ad(port)
            for link in local_link_information:
                port_id = link.get('port_id')
                switch_info = link.get('switch_info')
                switch_id = link.get('switch_id')
                switch = device_utils.get_switch_device(
                    self.switches, switch_info=switch_info,
                    ngs_mac_address=switch_id)

                # If segmentation ID is None, set vlan 1
                segmentation_id = network.get('provider:segmentation_id') or 1
                LOG.debug("Putting switch port %(switch_port)s on "
                          "%(switch_info)s in vlan %(segmentation_id)s",
                          {'switch_port': port_id, 'switch_info': switch_info,
                           'segmentation_id': segmentation_id})
                # Move port to network
                if is_802_3ad and hasattr(switch, 'plug_bond_to_network'):
                    switch.plug_bond_to_network(port_id, segmentation_id)
                else:
                    switch.plug_port_to_network(port_id, segmentation_id)
                LOG.info("Successfully plugged port %(port_id)s in segment "
                         "%(segment_id)s on device %(device)s",
                         {'port_id': port['id'], 'device': switch_info,
                          'segment_id': segmentation_id})

            provisioning_blocks.provisioning_complete(
                context._plugin_context, port['id'], resources.PORT,
                GENERIC_SWITCH_ENTITY)
        elif self._is_port_bound(context.original):
            # The port has been unbound. This will cause the local link
            # information to be lost, so remove the port from the network on
            # the switch now while we have the required information.
            self._unplug_port_from_network(context.original,
                                           context.network.current)

    def delete_port_precommit(self, context):
        """Delete resources of a port.

        :param context: PortContext instance describing the current
            state of the port, prior to the call to delete it.

        Called inside transaction context on session. Runtime errors
        are not expected, but raising an exception will result in
        rollback of the transaction.
        """
        pass

    def delete_port_postcommit(self, context):
        """Delete a port.

        :param context: PortContext instance describing the current
            state of the port, prior to the call to delete it.

        Called after the transaction completes. Call can block, though
        will block the entire process so care should be taken to not
        drastically affect performance.  Runtime errors are not
        expected, and will not prevent the resource from being
        deleted.
        """

        port = context.current
        if self._is_port_bound(port):
            self._unplug_port_from_network(port, context.network.current)

    def bind_port(self, context):
        """Attempt to bind a port.

        :param context: PortContext instance describing the port

        This method is called outside any transaction to attempt to
        establish a port binding using this mechanism driver. Bindings
        may be created at each of multiple levels of a hierarchical
        network, and are established from the top level downward. At
        each level, the mechanism driver determines whether it can
        bind to any of the network segments in the
        context.segments_to_bind property, based on the value of the
        context.host property, any relevant port or network
        attributes, and its own knowledge of the network topology. At
        the top level, context.segments_to_bind contains the static
        segments of the port's network. At each lower level of
        binding, it contains static or dynamic segments supplied by
        the driver that bound at the level above. If the driver is
        able to complete the binding of the port to any segment in
        context.segments_to_bind, it must call context.set_binding
        with the binding details. If it can partially bind the port,
        it must call context.continue_binding with the network
        segments to be used to bind at the next lower level.

        If the binding results are committed after bind_port returns,
        they will be seen by all mechanism drivers as
        update_port_precommit and update_port_postcommit calls. But if
        some other thread or process concurrently binds or updates the
        port, these binding results will not be committed, and
        update_port_precommit and update_port_postcommit will not be
        called on the mechanism drivers with these results. Because
        binding results can be discarded rather than committed,
        drivers should avoid making persistent state changes in
        bind_port, or else must ensure that such state changes are
        eventually cleaned up.

        Implementing this method explicitly declares the mechanism
        driver as having the intention to bind ports. This is inspected
        by the QoS service to identify the available QoS rules you
        can use with ports.
        """

        port = context.current
        network = context.network.current
        binding_profile = port['binding:profile']
        local_link_information = binding_profile.get('local_link_information')

        if self._is_port_supported(port) and local_link_information:
            # NOTE(jamesdenton): If any link of the port is invalid, none
            # of the links should be processed.
            if not self._is_link_valid(port, network):
                return

            segments = context.segments_to_bind
            context.set_binding(segments[0][api.ID],
                                portbindings.VIF_TYPE_OTHER, {})
            provisioning_blocks.add_provisioning_component(
                context._plugin_context, port['id'], resources.PORT,
                GENERIC_SWITCH_ENTITY)

    def _is_link_valid(self, port, network):
        """Return whether a link references valid switch and physnet.

        If the local link information refers to a switch that is not
        known to NGS or the switch is not associated with the respective
        physnet, the port will not be processed and no exception will
        be raised.

        :param port: The port to check
        :param network: the network mapped to physnet
        :returns: Whether the link refers to a configured switch and/or switch
                  is associated with physnet
        """

        binding_profile = port['binding:profile']
        local_link_information = binding_profile.get('local_link_information')

        for link in local_link_information:
            switch_info = link.get('switch_info')
            switch_id = link.get('switch_id')
            switch = device_utils.get_switch_device(
                self.switches, switch_info=switch_info,
                ngs_mac_address=switch_id)
            if not switch:
                LOG.error("Cannot bind port %(port)s as device %(device)s "
                          "is not configured. Check baremetal port link "
                          "configuration.",
                          {'port': port['id'],
                           'device': switch_info})
                return False

            physnet = network['provider:physical_network']
            switch_physnets = switch._get_physical_networks()

            if switch_physnets and physnet not in switch_physnets:
                LOG.error("Cannot bind port %(port)s as device %(device)s "
                          "is not on physical network %(physnet)s. Check "
                          "baremetal port link configuration.",
                          {'port': port['id'], 'device': switch_info,
                           'physnet': physnet})
                return False
        return True

    @staticmethod
    def _is_port_supported(port):
        """Return whether a port is supported by this driver.

        Ports supported by this driver have a VNIC type of 'baremetal'.

        :param port: The port to check
        :returns: Whether the port is supported by the NGS driver
        """
        vnic_type = port[portbindings.VNIC_TYPE]
        return vnic_type == portbindings.VNIC_BAREMETAL

    @staticmethod
    def _is_port_bound(port):
        """Return whether a port is bound by this driver.

        Ports bound by this driver have their VIF type set to 'other'.

        :param port: The port to check
        :returns: Whether the port is bound by the NGS driver
        """
        if not GenericSwitchDriver._is_port_supported(port):
            return False

        vif_type = port[portbindings.VIF_TYPE]
        return vif_type == portbindings.VIF_TYPE_OTHER

    @staticmethod
    def _is_802_3ad(port):
        """Return whether a port is using 802.3ad link aggregation.

        :param port: The port to check
        :returns: Whether the port is a port group using 802.3ad link
                  aggregation.
        """
        binding_profile = port['binding:profile']
        local_group_information = binding_profile.get(
            'local_group_information')
        if not local_group_information:
            return False
        return local_group_information.get('bond_mode') in ['4', '802.3ad']

    def _unplug_port_from_network(self, port, network):
        """Unplug a port from a network.

        If the configuration required to unplug the port is not present
        (e.g. local link information), the port will not be unplugged and no
        exception will be raised.

        :param port: The port to unplug
        :param network: The network from which to unplug the port
        """
        binding_profile = port['binding:profile']
        local_link_information = binding_profile.get('local_link_information')
        if not local_link_information:
            return

        is_802_3ad = self._is_802_3ad(port)
        for link in local_link_information:
            switch_info = link.get('switch_info')
            switch_id = link.get('switch_id')
            switch = device_utils.get_switch_device(
                self.switches, switch_info=switch_info,
                ngs_mac_address=switch_id)
            if not switch:
                continue
            port_id = link.get('port_id')
            # If segmentation ID is None, set vlan 1
            segmentation_id = network.get('provider:segmentation_id') or 1
            LOG.debug("Unplugging port %(port)s on %(switch_info)s from vlan: "
                      "%(segmentation_id)s",
                      {'port': port_id, 'switch_info': switch_info,
                       'segmentation_id': segmentation_id})
            try:
                if is_802_3ad and hasattr(switch, 'unplug_bond_from_network'):
                    switch.unplug_bond_from_network(port_id, segmentation_id)
                else:
                    switch.delete_port(port_id, segmentation_id)
            except Exception as e:
                LOG.error("Failed to unplug port %(port_id)s "
                          "on device: %(switch)s from network %(net_id)s "
                          "reason: %(exc)s",
                          {'port_id': port['id'], 'net_id': network['id'],
                           'switch': switch_info, 'exc': e})
                raise e
            LOG.info('Port %(port_id)s has been unplugged from network '
                     '%(net_id)s on device %(device)s',
                     {'port_id': port['id'], 'net_id': network['id'],
                      'device': switch_info})

    def _get_devices_by_physnet(self, physnet):
        """Generator yielding switches on a particular physical network.

        :param physnet: Physical network to filter by.
        :returns: Yields 2-tuples containing the name of the switch and the
            switch device object.
        """
        for switch_name, switch in self.switches.items():
            physnets = switch._get_physical_networks()
            # NOTE(mgoddard): If the switch has no physical networks then
            # follow the old behaviour of mapping all networks to it.
            if not physnets or physnet in physnets:
                yield switch_name, switch
