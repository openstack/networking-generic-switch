#  Copyright 2022 Nokia
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

from oslo_log import log as logging

from networking_generic_switch.devices import netmiko_devices
from networking_generic_switch.devices import utils as device_utils
from networking_generic_switch import exceptions as exc
from networking_generic_switch import locking as ngs_lock

LOG = logging.getLogger(__name__)


class NokiaSRL(netmiko_devices.NetmikoSwitch):
    ADD_NETWORK = (
        'set tunnel-interface vxlan0 vxlan-interface {segmentation_id} '
        'type bridged',
        'set tunnel-interface vxlan0 vxlan-interface {segmentation_id} '
        'ingress vni {segmentation_id}',
        'set tunnel-interface vxlan0 vxlan-interface {segmentation_id} '
        'egress source-ip use-system-ipv4-address',
        'set network-instance mac-vrf-{segmentation_id} type mac-vrf',
        'set network-instance mac-vrf-{segmentation_id} description '
        'OS-Network-ID-{network_name}',
        'set network-instance mac-vrf-{segmentation_id} vxlan-interface '
        'vxlan0.{segmentation_id}',
        'set network-instance mac-vrf-{segmentation_id} protocols bgp-evpn '
        'bgp-instance 1 vxlan-interface vxlan0.{segmentation_id}',
        'set network-instance mac-vrf-{segmentation_id} protocols bgp-evpn '
        'bgp-instance 1 evi {segmentation_id}',
        'set network-instance mac-vrf-{segmentation_id} protocols bgp-evpn '
        'bgp-instance 1 ecmp 8',
        'set network-instance mac-vrf-{segmentation_id} protocols bgp-vpn '
        'bgp-instance 1 route-target export-rt target:1:{segmentation_id}',
        'set network-instance mac-vrf-{segmentation_id} protocols bgp-vpn '
        'bgp-instance 1 route-target import-rt target:1:{segmentation_id}',
    )

    DELETE_NETWORK = (
        'delete network-instance mac-vrf-{segmentation_id}',
        'delete tunnel-interface vxlan0 vxlan-interface {segmentation_id}',
    )

    PLUG_PORT_TO_NETWORK = (
        'set interface {port} subinterface {segmentation_id} type bridged',
        'set network-instance mac-vrf-{segmentation_id} interface '
        '{port}.{segmentation_id}',
    )

    DELETE_PORT = (
        'delete network-instance mac-vrf-{segmentation_id} interface '
        '{port}.{segmentation_id}',
        'delete interface {port} subinterface {segmentation_id}',
    )

    def send_commands_to_device(self, cmd_set):
        if not cmd_set:
            LOG.debug('Nothing to execute')
            return

        try:
            with ngs_lock.PoolLock(self.locker, **self.lock_kwargs):
                with self._get_connection() as net_connect:
                    output = self.send_config_set(net_connect, cmd_set)
                    # A commit is required with Nokia SRL before saving
                    output += self.commit(net_connect)
                    self.save_configuration(net_connect)
        except exc.GenericSwitchException:
            # Reraise without modification exceptions originating from this
            # module.
            raise
        except Exception as e:
            raise exc.GenericSwitchNetmikoConnectError(
                config=device_utils.sanitise_config(self.config), error=e
            )

        LOG.debug(output)
        return output

    def commit(self, net_connect) -> str:
        '''Try to commit the Nokia SRL configuration.

        :param net_connect: a netmiko connection object.
        '''
        output = ''
        try:
            output = net_connect.commit()
        except AttributeError:
            LOG.warning(
                ' Committing config should be supported for Nokia SRL'
                ' Please verify Nokia SRL support in netmiko'
            )
        return output
