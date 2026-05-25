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
import enum

from networking_generic_switch.netconf_models.openconfig import constants


class LACPPeriod(enum.Enum):
    """Defines the time between sending LACP messages

    reference "IEEE 802.3ad"
    FAST: Send LACP packets every second
    SLOW: Send LACP packets every 30 seconds
    """
    FAST = constants.LACP_PERIOD_FAST
    SLOW = constants.LACP_PERIOD_SLOW


class LACPActivity(enum.Enum):
    """Describes the LACP membership type

    Active or passive, of the interface in the aggregate.
    reference "IEEE 802.1AX-2008"

    ACTIVE:  Interface is an active member, i.e., will detect and
             maintain aggregates
    PASSIVE: Interface is a passive member, i.e., it participates
             with an active partner
    """
    ACTIVE = constants.LACP_ACTIVITY_ACTIVE
    PASSIVE = constants.LACP_ACTIVITY_PASSIVE
