#!/usr/bin/env bash
# plugin.sh - DevStack plugin.sh dispatch script template

GENERIC_SWITCH_DIR=${GENERIC_SWITCH_DIR:-$DEST/networking-generic-switch}
GENERIC_SWITCH_INI_FILE='/etc/neutron/plugins/ml2/ml2_conf_genericswitch.ini'
GENERIC_SWITCH_SSH_KEY_FILENAME="networking-generic-switch"
GENERIC_SWITCH_SSH_PORT=${GENERIC_SWITCH_SSH_PORT:-}
GENERIC_SWITCH_DATA_DIR=""$DATA_DIR/networking-generic-switch""
GENERIC_SWITCH_KEY_DIR="$GENERIC_SWITCH_DATA_DIR/keys"
GENERIC_SWITCH_KEY_FILE=${GENERIC_SWITCH_KEY_FILE:-"$GENERIC_SWITCH_KEY_DIR/$GENERIC_SWITCH_SSH_KEY_FILENAME"}
GENERIC_SWITCH_KEY_AUTHORIZED_KEYS_FILE="$HOME/.ssh/authorized_keys"
GENERIC_SWITCH_TEST_BRIDGE="genericswitch"
GENERIC_SWITCH_TEST_PORT="gs_port_01"

function install_generic_switch {
    setup_develop $GENERIC_SWITCH_DIR
}

function configure_generic_switch_ssh_keypair {
    if [[ ! -d $HOME/.ssh ]]; then
        mkdir -p $HOME/.ssh
        chmod 700 $HOME/.ssh
    fi
    if [[ ! -e $GENERIC_SWITCH_KEY_FILE ]]; then
        if [[ ! -d $(dirname $GENERIC_SWITCH_KEY_FILE) ]]; then
            mkdir -p $(dirname $GENERIC_SWITCH_KEY_FILE)
        fi
        echo -e 'n\n' | ssh-keygen -q -t rsa -P '' -f $GENERIC_SWITCH_KEY_FILE
    fi
    # NOTE(vsaienko) check for new line character, add if doesn't exist.
    if [[ "$(tail -c1 $GENERIC_SWITCH_KEY_AUTHORIZED_KEYS_FILE | wc -l)" == "0" ]]; then
        echo "" >> $GENERIC_SWITCH_KEY_AUTHORIZED_KEYS_FILE
    fi
    cat $GENERIC_SWITCH_KEY_FILE.pub | tee -a $GENERIC_SWITCH_KEY_AUTHORIZED_KEYS_FILE
    # remove duplicate keys.
    sort -u -o $GENERIC_SWITCH_KEY_AUTHORIZED_KEYS_FILE $GENERIC_SWITCH_KEY_AUTHORIZED_KEYS_FILE
}

function configure_generic_switch {
    if [[ -z "$Q_ML2_PLUGIN_MECHANISM_DRIVERS" ]]; then
        Q_ML2_PLUGIN_MECHANISM_DRIVERS='genericswitch'
    else
        if [[ ! $Q_ML2_PLUGIN_MECHANISM_DRIVERS =~ $(echo '\<genericswitch\>') ]]; then
            Q_ML2_PLUGIN_MECHANISM_DRIVERS+=',genericswitch'
        fi
    fi
    populate_ml2_config /$Q_PLUGIN_CONF_FILE ml2 mechanism_drivers=$Q_ML2_PLUGIN_MECHANISM_DRIVERS

    # Generate SSH keypair
    configure_generic_switch_ssh_keypair

    # Create generic_switch ml2 config
    for switch in $GENERIC_SWITCH_TEST_BRIDGE $IRONIC_VM_NETWORK_BRIDGE; do
        switch="genericswitch:$switch"
        add_generic_switch_to_ml2_config $switch $GENERIC_SWITCH_KEY_FILE $STACK_USER localhost netmiko_ovs_linux "$GENERIC_SWITCH_SSH_PORT"
    done
    echo "HOST_TOPOLOGY: $HOST_TOPOLOGY"
    echo "HOST_TOPOLOGY_SUBNODES: $HOST_TOPOLOGY_SUBNODES"
    if [ -n "$HOST_TOPOLOGY_SUBNODES" ]; then
        # NOTE(vsaienko) with multinode topology we need to add switches from all
        # the subnodes to the config on primary node
        local cnt=0
        local section
        for node in $HOST_TOPOLOGY_SUBNODES; do
            cnt=$((cnt+1))
            section="genericswitch:sub${cnt}${IRONIC_VM_NETWORK_BRIDGE}"
            add_generic_switch_to_ml2_config $section $GENERIC_SWITCH_KEY_FILE $STACK_USER $node netmiko_ovs_linux "$GENERIC_SWITCH_SSH_PORT"
        done
    fi

    neutron_server_config_add $GENERIC_SWITCH_INI_FILE

}

function add_generic_switch_to_ml2_config {
    local switch_name=$1
    local key_file=$2
    local username=$3
    local ip=$4
    local device_type=$5
    local port=$6

    populate_ml2_config $GENERIC_SWITCH_INI_FILE $switch_name key_file=$key_file
    populate_ml2_config $GENERIC_SWITCH_INI_FILE $switch_name username=$username
    populate_ml2_config $GENERIC_SWITCH_INI_FILE $switch_name ip=$ip
    populate_ml2_config $GENERIC_SWITCH_INI_FILE $switch_name device_type=$device_type
    if [[ -n "$port" ]]; then
        populate_ml2_config $GENERIC_SWITCH_INI_FILE $switch_name port=$port
    fi
}

function cleanup_networking_generic_switch {
    rm -f $GENERIC_SWITCH_INI_FILE
    if [[ -f $GENERIC_SWITCH_KEY_FILE ]]; then
        local key
        key=$(cat $GENERIC_SWITCH_KEY_FILE.pub)
        # remove public key from authorized_keys
        grep -v "$key" $GENERIC_SWITCH_KEY_AUTHORIZED_KEYS_FILE > temp && mv temp $GENERIC_SWITCH_KEY_AUTHORIZED_KEYS_FILE
        chmod 0600 $IRONIC_AUTHORIZED_KEYS_FILE
    fi
    sudo ovs-vsctl --if-exists del-br $GENERIC_SWITCH_TEST_BRIDGE

    rm -rf $GENERIC_SWITCH_DATA_DIR
}

function ngs_configure_tempest {
    sudo ovs-vsctl --may-exist add-br $GENERIC_SWITCH_TEST_BRIDGE
    ip link show gs_port_01 || sudo ip link add gs_port_01 type dummy
    sudo ovs-vsctl --may-exist add-port $GENERIC_SWITCH_TEST_BRIDGE $GENERIC_SWITCH_TEST_PORT

    iniset $TEMPEST_CONFIG service_available ngs True
    iniset $TEMPEST_CONFIG ngs bridge_name $GENERIC_SWITCH_TEST_BRIDGE
    iniset $TEMPEST_CONFIG ngs port_name $GENERIC_SWITCH_TEST_PORT
}

# check for service enabled
if is_service_enabled generic_switch; then

    if [[ "$1" == "stack" && "$2" == "install" ]]; then
        # Perform installation of service source
        echo_summary "Installing Generic_swtich ML2"
        install_generic_switch

    elif [[ "$1" == "stack" && "$2" == "post-config" ]]; then
        # Configure after the other layer 1 and 2 services have been configured
        echo_summary "Configuring Generic_swtich Ml2"
        configure_generic_switch
    elif [[ "$1" == "stack" && "$2" == "test-config" ]]; then
        if is_service_enabled tempest; then
            echo_summary "Configuring Tempest NGS"
            ngs_configure_tempest
        fi
    fi

    if [[ "$1" == "unstack" ]]; then
        echo_summary "Cleaning Networking-generic-switch"
        cleanup_networking_generic_switch
    fi
fi
