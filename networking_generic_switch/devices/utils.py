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
    sanitised_fields = {"password"}
    return {
        key: "******" if key in sanitised_fields else value
        for key, value in config.items()
    }
