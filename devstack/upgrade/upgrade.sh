#!/usr/bin/env bash

# ``upgrade networking-generic-switch``

echo "*********************************************************************"
echo "Begin $0"
echo "*********************************************************************"

# Clean up any resources that may be in use
cleanup() {
    set +o errexit

    echo "*********************************************************************"
    echo "ERROR: Abort $0"
    echo "*********************************************************************"

    # Kill ourselves to signal any calling process
    trap 2; kill -2 $$
}

trap cleanup SIGHUP SIGINT SIGTERM

# Keep track of the grenade directory
RUN_DIR=$(cd $(dirname "$0") && pwd)

# Source params
source $GRENADE_DIR/grenaderc

# Import common functions
source $GRENADE_DIR/functions

# This script exits on an error so that errors don't compound and you see
# only the first error that occurred.
set -o errexit

# Upgrade networking-generic-switch
# =================================

# Duplicate some setup bits from target DevStack
source $TARGET_DEVSTACK_DIR/stackrc
source $TARGET_DEVSTACK_DIR/lib/tls
source $TARGET_DEVSTACK_DIR/lib/nova
source $TARGET_DEVSTACK_DIR/lib/apache
source $TARGET_DEVSTACK_DIR/lib/keystone
source $TARGET_DEVSTACK_DIR/lib/neutron


GENERIC_SWITCH_DEVSTACK_DIR=$(dirname "$0")/..
source $GENERIC_SWITCH_DEVSTACK_DIR/plugin.sh

neutron_plugin_configure_common
Q_PLUGIN_CONF_FILE=$Q_PLUGIN_CONF_PATH/$Q_PLUGIN_CONF_FILENAME
if [ "$Q_AGENT" == "linuxbridge" ]; then
    AGENT_BINARY=${AGENT_BINARY:-"$NEUTRON_BIN_DIR/neutron-linuxbridge-agent"}
else
    # fall back to openvswitch as the default
    AGENT_BINARY=${AGENT_BINARY:-"$NEUTRON_BIN_DIR/neutron-openvswitch-agent"}
fi

# Print the commands being run so that we can see the command that triggers
# an error.  It is also useful for following allowing as the install occurs.
set -o xtrace


stack_install_service generic_switch

# calls upgrade-networking-generic-switch for specific release
upgrade_project networking-generic-switch $RUN_DIR $BASE_DEVSTACK_BRANCH $TARGET_DEVSTACK_BRANCH

# Also set in grenade but isn't picked up
AGENT_METERING_BINARY=${AGENT_METERING_BINARY:-"$NEUTRON_BIN_DIR/neutron-metering-agent"}
METERING_AGENT_CONF_FILENAME=${METERING_AGENT_CONF_FILENAME:-"/etc/neutron/services/metering/metering_agent.ini"}

# NOTE(vsaienko) restart neutron to use new networking-generic-switch
neutron_server_config_add ${GENERIC_SWITCH_INI_FILE}
stop_neutron
# Start neutron and agents
start_neutron_service_and_check
start_neutron_agents

echo "*********************************************************************"
echo "SUCCESS: End $0"
echo "*********************************************************************"
