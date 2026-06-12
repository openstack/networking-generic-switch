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

from networking_generic_switch.yang_models import constants as yconst
from networking_generic_switch.yang_models.openconfig import (
    constants as oc_constants)
from networking_generic_switch.yang_models.openconfig.interfaces \
    .interfaces import Interfaces
from networking_generic_switch.yang_models.openconfig \
    .network_instance.network_instance import NetworkInstances
from networking_generic_switch.yang_models.openconfig.vlan \
    .vlan import VlanSwitchedVlan


class OpenConfigModelMixin:
    """Build OpenConfig model objects for network and port operations."""

    def _add_network(self, segmentation_id, network_name, **kwargs):
        """Build OpenConfig objects to create a VLAN.

        :param segmentation_id: VLAN ID.
        :param network_name: Name to assign to the VLAN on the device.
        :returns: list of OpenConfig model objects.
        """
        segmentation_id = int(segmentation_id)
        net_instances = NetworkInstances()
        net_inst = net_instances.add(self._network_instance)
        _vlan = net_inst.vlans.add(segmentation_id)
        _vlan.config.name = network_name
        _vlan.config.status = oc_constants.VLAN_ACTIVE
        return [net_instances]

    def _delete_network(self, segmentation_id, network_name, **kwargs):
        """Build OpenConfig objects to remove a VLAN.

        Not all devices support outright VLAN removal, so the VLAN is
        also set to SUSPENDED with a ``neutron-DELETED-`` name prefix
        as a fallback.

        :param segmentation_id: VLAN ID.
        :param network_name: Original network name (unused in the
            delete payload but accepted for signature compatibility).
        :returns: list of OpenConfig model objects.
        """
        segmentation_id = int(segmentation_id)
        net_instances = NetworkInstances()
        net_inst = net_instances.add(self._network_instance)
        _vlan = net_inst.vlans.remove(segmentation_id)
        _vlan.config.name = f'neutron-DELETED-{segmentation_id}'
        _vlan.config.status = oc_constants.VLAN_SUSPENDED
        return [net_instances]

    def _add_network_to_trunk(self, segmentation_id, trunk_ports, **kwargs):
        """Build OpenConfig objects to tag trunk ports with a VLAN.

        When *physnet_vlans* is provided the complete set of trunk VLANs
        is written with ``operation="replace"`` so that the device
        converges to the desired state.  Falls back to a single-VLAN
        merge when *physnet_vlans* is ``None``.

        :param segmentation_id: VLAN ID to add to trunk ports.
        :param trunk_ports: List of switch interface names.
        :param physnet_vlans: (kwarg) Complete set of VLAN IDs on the
            physical network, or ``None``.
        :returns: list of OpenConfig model objects.
        """
        physnet_vlans = kwargs.get('physnet_vlans')
        segmentation_id = int(segmentation_id)
        ifaces = Interfaces()
        for port in trunk_ports:
            port = self._port_id_resub(port)
            iface = ifaces.add(port)
            switched_vlan = VlanSwitchedVlan()
            switched_vlan.config.interface_mode = oc_constants.VLAN_MODE_TRUNK
            if physnet_vlans is not None:
                switched_vlan.config.operation = yconst.EditOperation.REPLACE
                for vlan_id in sorted(physnet_vlans):
                    switched_vlan.config.trunk_vlans = vlan_id
            else:
                switched_vlan.config.trunk_vlans = segmentation_id
            iface.ethernet.switched_vlan = switched_vlan
        return [ifaces]

    def _remove_network_from_trunk(self, segmentation_id, trunk_ports,
                                   **kwargs):
        """Build OpenConfig objects to untag trunk ports from a VLAN.

        When *physnet_vlans* is provided the complete set (which already
        excludes the deleted VLAN) is written with
        ``operation="replace"``.  Falls back to per-element
        ``operation="remove"`` when *physnet_vlans* is ``None``.

        :param segmentation_id: VLAN ID to remove from trunk ports.
        :param trunk_ports: List of switch interface names.
        :param physnet_vlans: (kwarg) Complete set of VLAN IDs on the
            physical network after deletion, or ``None``.
        :returns: list of OpenConfig model objects.
        """
        physnet_vlans = kwargs.get('physnet_vlans')
        segmentation_id = int(segmentation_id)
        ifaces = Interfaces()
        for port in trunk_ports:
            port = self._port_id_resub(port)
            iface = ifaces.add(port)
            switched_vlan = VlanSwitchedVlan()
            switched_vlan.config.interface_mode = oc_constants.VLAN_MODE_TRUNK
            if physnet_vlans is not None:
                switched_vlan.config.operation = yconst.EditOperation.REPLACE
                for vlan_id in sorted(physnet_vlans):
                    switched_vlan.config.trunk_vlans = vlan_id
            else:
                switched_vlan.config.trunk_vlans.remove(segmentation_id)
            iface.ethernet.switched_vlan = switched_vlan
        return [ifaces]

    def _plug_port_to_network(self, port_id, segmentation_id, **kwargs):
        """Build OpenConfig objects to assign a VLAN to a port.

        When *trunk_details* is provided the port is configured as a trunk
        with ``native_vlan`` set to *segmentation_id* and all subport VLANs
        in ``trunk_vlans`` using ``operation="replace"``.  Without
        *trunk_details* the port is set to access mode.

        :param port_id: Switch interface name.
        :param segmentation_id: VLAN ID.
        :param trunk_details: (kwarg) Trunk information dict from the
            parent port, or ``None``.
        :returns: list of OpenConfig model objects.
        """
        trunk_details = kwargs.get('trunk_details')
        segmentation_id = int(segmentation_id)
        port_id = self._port_id_resub(port_id)

        ifaces = Interfaces()
        iface = ifaces.add(port_id)

        switched_vlan = VlanSwitchedVlan()
        switched_vlan.config.operation = yconst.EditOperation.REPLACE

        if trunk_details:
            switched_vlan.config.interface_mode = oc_constants.VLAN_MODE_TRUNK
            switched_vlan.config.native_vlan = segmentation_id
            for sub_port in sorted(trunk_details.get('sub_ports', []),
                                   key=lambda s: s['segmentation_id']):
                switched_vlan.config.trunk_vlans = int(
                    sub_port['segmentation_id'])
        else:
            switched_vlan.config.interface_mode = oc_constants.VLAN_MODE_ACCESS
            switched_vlan.config.access_vlan = segmentation_id

        iface.ethernet.switched_vlan = switched_vlan

        return [ifaces]

    def _delete_port(self, port_id, segmentation_id, **kwargs):
        """Build OpenConfig objects to remove VLAN config from a port.

        :param port_id: Switch interface name.
        :param segmentation_id: VLAN ID.
        :returns: list of OpenConfig model objects.
        """
        port_id = self._port_id_resub(port_id)

        ifaces = Interfaces()
        iface = ifaces.add(port_id)
        iface.config.operation = yconst.EditOperation.REMOVE
        iface.config.description = ''
        iface.ethernet.switched_vlan.config.operation = (
            yconst.EditOperation.REMOVE)

        return [ifaces]

    def _enable_port(self, port_id, **kwargs):
        """Build OpenConfig objects to enable an interface.

        :param port_id: Switch interface name.
        :returns: list of OpenConfig model objects.
        """
        port_id = self._port_id_resub(port_id)

        ifaces = Interfaces()
        iface = ifaces.add(port_id)
        iface.config.enabled = True

        return [ifaces]

    def _disable_port(self, port_id, **kwargs):
        """Build OpenConfig objects to disable an interface.

        :param port_id: Switch interface name.
        :returns: list of OpenConfig model objects.
        """
        port_id = self._port_id_resub(port_id)

        ifaces = Interfaces()
        iface = ifaces.add(port_id)
        iface.config.enabled = False

        return [ifaces]

    def _add_subports_on_trunk(self, binding_profile, port_id, subports,
                               trunk_details=None, **kwargs):
        """Build OpenConfig objects to add subport VLANs on a trunk port.

        When *trunk_details* is provided the complete set of subport
        VLANs is written with ``operation="replace"`` so that the device
        converges to the desired state.  Falls back to a per-VLAN merge
        when *trunk_details* is ``None``.

        :param binding_profile: Binding profile of the parent port.
        :param port_id: Switch interface name.
        :param subports: List of subport dicts (delta being added).
        :param trunk_details: Full trunk details dict from the parent
            port, or ``None``.
        :returns: list of OpenConfig model objects.
        """
        port_id = self._port_id_resub(port_id)

        ifaces = Interfaces()
        iface = ifaces.add(port_id)
        switched_vlan = VlanSwitchedVlan()
        switched_vlan.config.interface_mode = oc_constants.VLAN_MODE_TRUNK

        if trunk_details is not None:
            switched_vlan.config.operation = yconst.EditOperation.REPLACE
            native_vlan = trunk_details.get('segmentation_id')
            if native_vlan:
                switched_vlan.config.native_vlan = int(native_vlan)
            for sub_port in sorted(trunk_details.get('sub_ports', []),
                                   key=lambda s: s['segmentation_id']):
                switched_vlan.config.trunk_vlans = int(
                    sub_port['segmentation_id'])
        else:
            for sub_port in subports:
                switched_vlan.config.trunk_vlans = int(
                    sub_port['segmentation_id'])

        iface.ethernet.switched_vlan = switched_vlan
        return [ifaces]

    def _del_subports_on_trunk(self, binding_profile, port_id, subports,
                               trunk_details=None, **kwargs):
        """Build OpenConfig objects to remove subport VLANs from a trunk.

        When *trunk_details* is provided the remaining set of subport
        VLANs (already excluding the deleted ones) is written with
        ``operation="replace"``.  Falls back to per-element
        ``operation="remove"`` when *trunk_details* is ``None``.

        :param binding_profile: Binding profile of the parent port.
        :param port_id: Switch interface name.
        :param subports: List of subport dicts (delta being removed).
        :param trunk_details: Full trunk details dict from the parent
            port, or ``None``.
        :returns: list of OpenConfig model objects.
        """
        port_id = self._port_id_resub(port_id)

        ifaces = Interfaces()
        iface = ifaces.add(port_id)
        switched_vlan = VlanSwitchedVlan()
        switched_vlan.config.interface_mode = oc_constants.VLAN_MODE_TRUNK

        if trunk_details is not None:
            switched_vlan.config.operation = yconst.EditOperation.REPLACE
            remaining = trunk_details.get('sub_ports', [])
            native_vlan = trunk_details.get('segmentation_id')
            if remaining:
                if native_vlan:
                    switched_vlan.config.native_vlan = int(native_vlan)
                for sub_port in sorted(remaining,
                                       key=lambda s: s['segmentation_id']):
                    switched_vlan.config.trunk_vlans = int(
                        sub_port['segmentation_id'])
            else:
                switched_vlan.config.interface_mode = (
                    oc_constants.VLAN_MODE_ACCESS)
                if native_vlan:
                    switched_vlan.config.access_vlan = int(native_vlan)
        else:
            for sub_port in subports:
                switched_vlan.config.trunk_vlans.remove(
                    int(sub_port['segmentation_id']))

        iface.ethernet.switched_vlan = switched_vlan
        return [ifaces]
