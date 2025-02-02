# Copyright 2024 StackHPC Ltd
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

from neutron.objects.ports import Port
from neutron.services.trunk.drivers import base as trunk_base
from neutron_lib.api.definitions import portbindings
from neutron_lib.callbacks import events
from neutron_lib.callbacks import registry
from neutron_lib.callbacks import resources
from neutron_lib import context as n_context
from neutron_lib.db import api as db_api
from neutron_lib.plugins import directory
from neutron_lib.services.trunk import constants as trunk_consts
from oslo_config import cfg
from oslo_log import log as logging

LOG = logging.getLogger(__name__)

MECH_DRIVER_NAME = 'genericswitch'

SUPPORTED_INTERFACES = (
    portbindings.VIF_TYPE_OTHER,
    portbindings.VIF_TYPE_VHOST_USER,
)

SUPPORTED_SEGMENTATION_TYPES = (
    trunk_consts.SEGMENTATION_TYPE_VLAN,
)


class GenericSwitchTrunkDriver(trunk_base.DriverBase):
    @property
    def is_loaded(self):
        try:
            return (MECH_DRIVER_NAME in
                    cfg.CONF.ml2.mechanism_drivers)
        except cfg.NoSuchOptError:
            return False

    @registry.receives(resources.TRUNK_PLUGIN, [events.AFTER_INIT])
    def register(self, resource, event, trigger, payload=None):
        super(GenericSwitchTrunkDriver, self).register(
            resource, event, trigger, payload=payload)
        self._handler = GenericSwitchTrunkHandler(self.plugin_driver)
        registry.subscribe(
            self._handler.subports_added,
            resources.SUBPORTS,
            events.AFTER_CREATE)
        registry.subscribe(
            self._handler.subports_deleted,
            resources.SUBPORTS,
            events.AFTER_DELETE)

    @classmethod
    def create(cls, plugin_driver):
        cls.plugin_driver = plugin_driver
        return cls(MECH_DRIVER_NAME,
                   SUPPORTED_INTERFACES,
                   SUPPORTED_SEGMENTATION_TYPES,
                   None,
                   can_trunk_bound_port=True)


class GenericSwitchTrunkHandler(object):
    def __init__(self, plugin_driver):
        self.plugin_driver = plugin_driver
        self.core_plugin = directory.get_plugin()

    def subports_added(self, resource, event, trunk_plugin, payload):
        trunk = payload.states[0]
        subports = payload.metadata['subports']
        LOG.debug("GenericSwitch: subports added %s to trunk %s",
                  subports, trunk)
        context = n_context.get_admin_context()
        with db_api.CONTEXT_READER.using(context):
            parent_port = Port.get_object(context, id=trunk.port_id)

            parent_port_obj = self.core_plugin._make_port_dict(parent_port)

            self.plugin_driver.subports_added(
                context,
                parent_port_obj,
                subports)

    def subports_deleted(self, resource, event, trunk_plugin, payload):
        trunk = payload.states[0]
        subports = payload.metadata['subports']
        LOG.debug("GenericSwitch: subports deleted %s from trunk %s",
                  subports, trunk)
        context = n_context.get_admin_context()
        with db_api.CONTEXT_READER.using(context):
            parent_port = Port.get_object(context, id=trunk.port_id)

            parent_port_obj = self.core_plugin._make_port_dict(parent_port)
            self.plugin_driver.subports_deleted(
                context,
                parent_port_obj,
                subports)
