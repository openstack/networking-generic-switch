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


from neutron.plugins.ml2 import driver_api
from oslo_log import log as logging
from netmiko import ConnectHandler
from oslo_config import cfg
from neutron.i18n import _LE, _LI
from neutron.plugins.ml2 import driver_api as api
from neutron.common import constants as const
from neutron.extensions import portbindings

LOG = logging.getLogger(__name__)


def _get_config():
    CONF = cfg.CONF
    multi_parser = cfg.MultiConfigParser()
    multi_parser.read(CONF.config_file)

    return multi_parser.parsed


class GenericSwitch (object):

    def __init__(self, device_id):

        self.cmd_set = {}
        self.conn_info = {}

        self.conn_info = self._get_config_for_device(device_id)

        if self.conn_info['device_type'] == 'cisco_ios':
            self.cmd_set = {
                'add_network': ['vlan {segmentation_id}', 'name {network_id}'],
                'plug_port_to_network':
                ['interface {port}',
                 'switchport access vlan {segmentation_id}'],
                'del_network': ['no vlan {segmentation_id}'],
            }
        elif self.conn_info['device_type'] == 'ovs_linux':
            self.cmd_set = {
                'add_network': [''],
                'plug_port_to_network':
                ['ovs-vsctl set port {port} tag={segmentation_id}'],
                'del_network': [''],
            }
        else:
            LOG.error(_LE("Unsupported device type %s"),
                      self.conn_info['device_type'])

    def _get_config_for_device(self, device_id):

        device = 'genericswitch:%s' % device_id
        device_cfg = {}

        for parsed_file in _get_config():
            for parsed_item in parsed_file.keys():
                if parsed_item == device:
                    device_cfg = {k: v[0] for k,
                                  v in parsed_file[device].items()}

        return device_cfg

    def _get_connection(self):
        """Establish ssh connection to switch
        :return  netmiko connection
        """
        net_connect = ConnectHandler(**self.conn_info)
        return net_connect

    def _exec_cmd_set(self, cmd_set):
        net_connect = self._get_connection()
        net_connect.enable()
        output = net_connect.send_config_set(cmd_set)

        return output

    def _add_network(self, segmentation_id, network_id):
        """Add network (vlan) on the switch
        :param net_connect : netmiko connection,
        :param segmentation_id : vlan id
        :parram network_id : neutron network id (vlan name)
        """
        cmd_set = self.cmd_set['add_network']
        tmp_cmd_set = []

        for cmd in cmd_set:
            cmd = cmd.format(segmentation_id=segmentation_id,
                             network_id=network_id)
            tmp_cmd_set.append(cmd)

        cmd_set = tmp_cmd_set

        return cmd_set

    def _del_network(self, segmentation_id):
        """Remove network (vlan) on the switch
        :param segmentation_id : vlan id
        """

        cmd_set = self.cmd_set['del_network']
        tmp_cmd_set = []
        for cmd in cmd_set:
            cmd = cmd.format(segmentation_id=segmentation_id)
            tmp_cmd_set.append(cmd)

        cmd_set = tmp_cmd_set

        return cmd_set

    def _plug_port_to_network(self, port, segmentation_id):
        """Add port to network
        :param net_connect : netmiko connection,
        :param port : name of interface on the switch
        :parram segmentation_id : vlan id
        """

        cmd_set = self.cmd_set['plug_port_to_network']
        tmp_cmd_set = []

        for cmd in cmd_set:
            cmd = cmd.format(segmentation_id=segmentation_id, port=port)
            tmp_cmd_set.append(cmd)

        cmd_set = tmp_cmd_set

        return cmd_set

    def add_network(self, segmentation_id, network_id):
        cmd_set = self._add_network(segmentation_id=segmentation_id,
                                    network_id=network_id)

        self._exec_cmd_set(cmd_set)
        LOG.info('Network  %s has been added', network_id)

    def del_network(self, segmentation_id):
        cmd_set = self._del_network(segmentation_id=segmentation_id)

        self._exec_cmd_set(cmd_set)
        LOG.info('Network %s has been deleted', segmentation_id)

    def plug_port_to_network(self, port, segmentation_id):
        cmd_set = self._plug_port_to_network(
            port=port, segmentation_id=segmentation_id)

        self._exec_cmd_set(cmd_set)
        LOG.info(_LI("Port %(port)s has been added to vlan "
                 "%(segmentation_id)d"),
                 {'port': port, 'segmentation_id': segmentation_id})


class GenericSwitchDriver(driver_api.MechanismDriver):

    def _get_device_list(self):

        device_tag = 'genericswitch'
        device_list = []

        for parsed_file in _get_config():
            for parsed_item in parsed_file.keys():
                if device_tag in parsed_item:
                    dev_tag, sep, dev_id = parsed_item.partition(':')
                    device_list.append(dev_id)

        return device_list

    def _check_for_device(self, device_id):
        """
        Check if device exists in config
        """
        if device_id in self._get_device_list():
            return True

        return False

    def initialize(self):
        """Perform driver initialization.

        Called after all drivers have been loaded and the database has
        been initialized. No abstract methods defined below will be
        called prior to this method being called.
        """
        pass

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
        provider_type = network['provider:network_type']
        segmentation_id = network['provider:segmentation_id']

        if provider_type == 'vlan' and segmentation_id:

            # Create vlan on all switches from this driver
            for device in self._get_device_list():
                switch = GenericSwitch(device_id=device)
                switch.add_network(segmentation_id=segmentation_id,
                                   network_id=network_id)

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
        provider_type = network['provider:network_type']
        segmentation_id = network['provider:segmentation_id']

        if provider_type == 'vlan' and segmentation_id:
            for device in self._get_device_list():
                switch = GenericSwitch(device_id=device)
                switch.del_network(segmentation_id=segmentation_id)

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
        pass

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
        pass

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
        binding_profile = port['binding:profile']
        local_link_information = binding_profile.get('local_link_information',
                                                     False)
        vnic_type = port['binding:vnic_type']
        if vnic_type == 'baremetal' and local_link_information:
            switch_info = local_link_information[0].get('switch_info')
            port_id = local_link_information[0].get('port_id')
            segments = context.segments_to_bind
            segmentation_id = segments[0]['segmentation_id']
            # If segmentation ID is None, set vlan 1
            if not segmentation_id:
                segmentation_id = '1'
            LOG.debug("Putting port {port} on {switch_info} to vlan: "
                      "{segmentation_id}".format(
                          port=port_id,
                          switch_info=switch_info,
                          segmentation_id=segmentation_id))
            if self._check_for_device(device_id=switch_info):
                switch = GenericSwitch(device_id=switch_info)

                # Move port to network
                switch.plug_port_to_network(port=port_id,
                                            segmentation_id=segmentation_id)
                context.set_binding(segments[0][api.ID],
                                    portbindings.VIF_TYPE_OTHER, {},
                                    status=const.PORT_STATUS_ACTIVE)
            else:
                LOG.error(_LE("Can't find configuration for switch %s"),
                          switch_info)
