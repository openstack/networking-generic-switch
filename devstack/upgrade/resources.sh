#!/bin/bash
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

set -o errexit

source $GRENADE_DIR/grenaderc
source $GRENADE_DIR/functions

GENERIC_SWITCH_DEVSTACK_DIR=$(cd $(dirname "$0")/.. && pwd)
source $GENERIC_SWITCH_DEVSTACK_DIR/plugin.sh

set -o xtrace


function early_create {
    :
}

function create {
    # TODO(vsaienko) Add resources tests.
    :
}

function verify {
    :
}

function verify_noapi {
    :
}

function destroy {
    :
}

# Dispatcher
case $1 in
    "early_create")
        early_create
        ;;
    "create")
        create
        ;;
    "verify_noapi")
        verify_noapi
        ;;
    "verify")
        verify
        ;;
    "destroy")
        destroy
        ;;
    "force_destroy")
        set +o errexit
        destroy
        ;;
esac
