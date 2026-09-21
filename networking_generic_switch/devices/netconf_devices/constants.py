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

LOCK_DENIED_TAG = 'lock-denied'  # [RFC 4741]
OPERATION_FAILED_TAG = 'operation-failed'  # [RFC 4741]
CANDIDATE = 'candidate'
RUNNING = 'running'
STARTUP = 'startup'
DEFERRED = 'deferred'

IANA_NETCONF_CAPABILITIES = {
    # [RFC4741][RFC6241]
    ':base:1.0':
        'urn:ietf:params:netconf:base:1.0',
    # [RFC4741]
    ':confirmed-commit':
        'urn:ietf:params:netconf:capability:confirmed-commit:1.0',
    ':validate':
        'urn:ietf:params:netconf:capability:validate:1.0',
    # [RFC6241]
    ':base:1.1':
        'urn:ietf:params:netconf:base:1.1',
    ':writable-running':
        'urn:ietf:params:netconf:capability:writable-running:1.0',
    ':candidate':
        'urn:ietf:params:netconf:capability:candidate:1.0',
    ':confirmed-commit:1.1':
        'urn:ietf:params:netconf:capability:confirmed-commit:1.1',
    ':rollback-on-error':
        'urn:ietf:params:netconf:capability:rollback-on-error:1.0',
    ':validate:1.1':
        'urn:ietf:params:netconf:capability:validate:1.1',
    ':startup':
        'urn:ietf:params:netconf:capability:startup:1.0',
}
