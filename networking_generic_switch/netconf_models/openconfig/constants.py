# Copyright 2017 Cisco Systems, Inc.
# All Rights Reserved
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

IFACE_TYPE_ETHERNET = 'ethernet'
IFACE_TYPE_AGGREGATE = 'aggregate'
IFACE_TYPE_BASE = 'base'

LAG_TYPE_LACP = 'LACP'
LAG_TYPE_SATIC = 'SATIC'

LACP_PERIOD_FAST = 'FAST'
LACP_PERIOD_SLOW = 'SLOW'
LACP_ACTIVITY_ACTIVE = 'ACTIVE'
LACP_ACTIVITY_PASSIVE = 'PASSIVE'

VLAN_ACTIVE = 'ACTIVE'
VLAN_SUSPENDED = 'SUSPENDED'
VLAN_MODE_TRUNK = 'TRUNK'
VLAN_MODE_ACCESS = 'ACCESS'
VLAN_RANGE = range(1, 4094)
