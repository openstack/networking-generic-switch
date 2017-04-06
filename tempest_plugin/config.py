# Copyright 2016 Mirantis, Inc.
# All Rights Reserved.
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


from oslo_config import cfg

service_option = cfg.BoolOpt('ngs',
                             default=False,
                             help='Whether or not Networking Generic Switch'
                                  'is expected to be available')

ngs_group = cfg.OptGroup(name='ngs',
                         title='Networking Generic Switch',
                         help='Options group for Networking Generic Switch')

NGSGroup = [
    cfg.StrOpt('device_type',
               default='ovs_linux',
               help='Type of the switch.'),
    cfg.StrOpt('bridge_name',
               default='genericswitch',
               help='Bridge name to use.'),
    cfg.StrOpt('port_name',
               default='gs_port_01',
               help='Port name to use.'),
    cfg.IntOpt('port_dlm_concurrency',
               default=0,
               min=0,
               help='Concurrency to run the DLM tests with. '
                    'With default values DLM tests are skipped.'),
    cfg.StrOpt('network_name',
               default='private',
               help='Test network name to use.')
]
