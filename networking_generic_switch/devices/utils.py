# Copyright 2017 Mirantis, Inc.
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

from dataclasses import dataclass
import ipaddress
from typing import Optional

from oslo_config import cfg
from oslo_log import log as logging

from networking_generic_switch import exceptions as exc

LOG = logging.getLogger(__name__)
CONF = cfg.CONF


@dataclass(frozen=True)
class VxlanMulticastConfig:
    """VXLAN multicast BUM replication configuration.

    :param bum_replication_mode: BUM replication mode ('ingress-replication'
        or 'multicast')
    :param mcast_group_base: Base multicast group IP address for automatic
        derivation (optional)
    :param mcast_group_increment: Derivation method for calculating multicast
        groups from base (defaults to 'vni_last_octet')
    :param mcast_group_map: Explicit mapping of VNI to multicast IP addresses
    """
    bum_replication_mode: str
    mcast_group_base: Optional[str]
    mcast_group_increment: str
    mcast_group_map: dict


def get_switch_device(switches, switch_info=None,
                      ngs_mac_address=None):
    """Return switch device by specified identifier.

    Returns switch device from switches array that matched with any of
    passed identifiers. ngs_mac_address takes precedence over switch_info,
    if didn't match any address based on mac fallback to switch_info.

    :param switch_info: hostname of the switch or any other switch identifier.
    :param ngs_mac_address: Normalized mac address of the switch.
    :returns: switch device matches by specified identifier or None.
    """

    if ngs_mac_address:
        for sw_info, switch in switches.items():
            mac_address = switch.ngs_config.get('ngs_mac_address')
            if mac_address and mac_address.lower() == ngs_mac_address.lower():
                return switch
    if switch_info:
        return switches.get(switch_info)


def sanitise_config(config):
    """Return a sanitised configuration of a switch device.

    :param config: a configuration dict to sanitise.
    :returns: a copy of the configuration, with sensitive fields removed.
    """
    sanitised_fields = {"password", "ip", "device_type", "username",
                        "session_log"}
    return {
        key: "******" if key in sanitised_fields else value
        for key, value in config.items()
    }


def get_hostname():
    """Helper to allow isolation of CONF.host and plugin loading."""
    return CONF.host


def parse_vxlan_multicast_config(device_cfg):
    """Parse VXLAN multicast BUM replication configuration from device config.

    Extracts and validates multicast-related configuration parameters before
    the parent class removes all ngs_* options. This provides a consistent
    way for all vendor implementations to handle multicast configuration.

    :param device_cfg: Device configuration dictionary
    :returns: VxlanMulticastConfig instance with parsed configuration
    """
    bum_replication_mode = device_cfg.get('ngs_bum_replication_mode',
                                          'ingress-replication')
    mcast_group_base = device_cfg.get('ngs_mcast_group_base', None)
    mcast_group_increment = device_cfg.get('ngs_mcast_group_increment',
                                           'vni_last_octet')
    mcast_group_map = {}

    # Parse and validate explicit VNI-to-multicast-group mappings
    mcast_map_str = device_cfg.get('ngs_mcast_group_map', '')
    if mcast_map_str:
        for mapping in mcast_map_str.split(','):
            mapping = mapping.strip()
            if not mapping:
                continue
            if ':' not in mapping:
                LOG.warning('Invalid mapping format in ngs_mcast_group_map '
                            '(expected VNI:group): %s', mapping)
                continue

            vni_str, group_str = mapping.split(':', 1)
            vni_str = vni_str.strip()
            group_str = group_str.strip()

            # Validate VNI
            try:
                vni = int(vni_str)
                if vni < 1 or vni > 16777215:
                    LOG.warning('VNI %s out of valid range (1-16777215) '
                                'in ngs_mcast_group_map', vni)
                    continue
            except ValueError:
                LOG.warning('Invalid VNI "%s" in ngs_mcast_group_map: '
                            'must be an integer', vni_str)
                continue

            # Validate multicast group IP address
            try:
                mcast_ip = ipaddress.IPv4Address(group_str)
                # Validate it's in multicast range (224.0.0.0/4)
                if not mcast_ip.is_multicast:
                    LOG.warning('IP address %s is not a valid multicast '
                                'address in ngs_mcast_group_map', group_str)
                    continue
            except (ipaddress.AddressValueError, ValueError):
                LOG.warning('Invalid IP address "%s" in '
                            'ngs_mcast_group_map', group_str)
                continue

            # Warn on duplicate VNI
            if vni in mcast_group_map:
                LOG.warning('Duplicate VNI %s in ngs_mcast_group_map, '
                            'using last entry: %s', vni, group_str)

            mcast_group_map[vni] = group_str

    return VxlanMulticastConfig(
        bum_replication_mode=bum_replication_mode,
        mcast_group_base=mcast_group_base,
        mcast_group_increment=mcast_group_increment,
        mcast_group_map=mcast_group_map
    )


def get_vxlan_multicast_group(vni, mcast_group_map, mcast_group_base,
                              device_name=None):
    """Calculate multicast group address for a given VNI.

    Supports two methods for multicast group assignment:
    1. Explicit mapping via mcast_group_map (checked first)
    2. Automatic derivation from mcast_group_base (fallback)

    For automatic derivation, the group is calculated as:
        mcast_group_base + (VNI % 256)

    Example: With base 239.1.1.0 and VNI 10100:
        239.1.1.0 + (10100 % 256) = 239.1.1.0 + 116 = 239.1.1.116

    :param vni: VXLAN Network Identifier
    :param mcast_group_map: Dict mapping VNI to explicit multicast groups
    :param mcast_group_base: Base multicast group IP address for derivation
    :param device_name: Device name for error messages (optional)
    :returns: Multicast group IP address (e.g., '239.1.1.100')
    :raises: GenericSwitchNetmikoConfigError if no mapping or base configured
    """
    # Check explicit mapping first
    if vni in mcast_group_map:
        return mcast_group_map[vni]

    # Fall back to automatic derivation from base
    if not mcast_group_base:
        error_msg = (f'VNI {vni} not found in ngs_mcast_group_map and '
                     f'ngs_mcast_group_base not configured')
        if device_name:
            error_msg += f' for switch {device_name}'
        LOG.error(error_msg)
        raise exc.GenericSwitchNetmikoConfigError()

    base_ip = ipaddress.IPv4Address(mcast_group_base)

    # Use last octet of VNI as offset from base
    # Example: VNI 10100 with base 239.1.1.0 -> 239.1.1.100
    offset = vni % 256
    mcast_ip = ipaddress.IPv4Address(int(base_ip) + offset)

    return str(mcast_ip)
