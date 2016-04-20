#!/bin/bash

set -eux
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
GENERIC_SWITCH_TEST_BRIDGE=genericswitch
GENERIC_SWITCH_TEST_PORT_NAME=${GENERIC_SWITCH_PORT_NAME:-p_01}
NEUTRON_GENERIC_SWITCH_TEST_PORT_NAME=generic_switch_test

function clear_resources {
    sudo ovs-vsctl --if-exists del-br $GENERIC_SWITCH_TEST_BRIDGE
    if neutron port-show $NEUTRON_GENERIC_SWITCH_TEST_PORT_NAME; then
        neutron port-delete $NEUTRON_GENERIC_SWITCH_TEST_PORT_NAME
    fi
}

function wait_for_openvswitch_agent {
    local openvswitch_agent
    local retries=10
    local retry_delay=20;
    local status=false
    openvswitch_agent="Open vSwitch agent"

    while [[ $retries -ge 0 ]]; do
        if neutron agent-list --fields agent_type | grep -q "Open vSwitch agent"; then
            status=true
            break
        fi
        retries=$((retries - 1))
        echo "$openvswitch_agent is not yet registered. $retries left."
        sleep $retry_delay
    done
    if ! $status; then
        echo "$openvswitch_agent is not started in $((retries * retry_delay))"
    fi
}

clear_resources

# create bridge with its default port and remember and clear tag on that port
sudo ovs-vsctl add-br $GENERIC_SWITCH_TEST_BRIDGE
sudo ovs-vsctl add-port $GENERIC_SWITCH_TEST_BRIDGE $GENERIC_SWITCH_TEST_PORT_NAME
sudo ovs-vsctl clear port $GENERIC_SWITCH_TEST_PORT_NAME tag

switch_id=$(ip link show dev $GENERIC_SWITCH_TEST_BRIDGE | egrep -o "ether [A-Za-z0-9:]+"|sed "s/ether\ //")

wait_for_openvswitch_agent

# create and update Neutron port
expected_tag=$(python ${DIR}/exercise.py --switch_name $GENERIC_SWITCH_TEST_BRIDGE --port $GENERIC_SWITCH_TEST_PORT_NAME --switch_id=$switch_id)

new_tag=$(sudo ovs-vsctl get port $GENERIC_SWITCH_TEST_PORT_NAME tag)

clear_resources

if [ "${new_tag}" != "${expected_tag}" ]; then
    echo "FAIL: OVS port tag is not set correctly!"
    exit 1
else
    echo "SUCCESS: OVS port tag is set correctly"
fi
