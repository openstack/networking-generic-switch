#!/usr/bin/env bash
# plugin.sh - DevStack plugin.sh dispatch script template

GENERIC_SWITCH_DIR=${GENERIC_SWITCH_DIR:-$DEST/networking-generic-switch}
GENERIC_SWITCH_INI_FILE='/etc/neutron/plugins/ml2/ml2_conf_genericswitch.ini'
GENERIC_SWITCH_SSH_KEY_FILENAME="networking-generic-switch"
GENERIC_SWITCH_SSH_PORT=${GENERIC_SWITCH_SSH_PORT:-}
GENERIC_SWITCH_DATA_DIR=""$DATA_DIR/networking-generic-switch""
# NOTE(pas-ha) NEVER SET THIS TO ANY EXISTING USER!
# you might get locked out of SSH when limitinig SSH sessions is enabled for this user,
# AND THIS USER WILL BE DELETED TOGETHER WITH ITS HOME DIR ON UNSTACK/CLEANUP!!!
# this is why it is left unconfigurable
GENERIC_SWITCH_USER="ngs_ovs_manager"
GENERIC_SWITCH_USER_HOME="$GENERIC_SWITCH_DATA_DIR/$GENERIC_SWITCH_USER"
GENERIC_SWITCH_KEY_AUTHORIZED_KEYS_FILE="$GENERIC_SWITCH_USER_HOME/.ssh/authorized_keys"

GENERIC_SWITCH_KEY_DIR="$GENERIC_SWITCH_DATA_DIR/keys"
GENERIC_SWITCH_KEY_FILE=${GENERIC_SWITCH_KEY_FILE:-"$GENERIC_SWITCH_KEY_DIR/$GENERIC_SWITCH_SSH_KEY_FILENAME"}
GENERIC_SWITCH_TEST_BRIDGE="genericswitch"
GENERIC_SWITCH_TEST_PORT="gs_port_01"
# 0 means unlimited
GENERIC_SWITCH_USER_MAX_SESSIONS=${GENERIC_SWITCH_USER_MAX_SESSIONS:-0}
# 0 would mean wait forever
GENERIC_SWITCH_DLM_ACQUIRE_TIMEOUT=${GENERIC_SWITCH_DLM_ACQUIRE_TIMEOUT:-120}

if ( [[ "$GENERIC_SWITCH_USER_MAX_SESSIONS" -gt 0 ]] ) && (! is_service_enabled etcd3); then
    die $LINENO "etcd3 service must be enabled to use coordination features of networking-generic-switch"
fi

function install_generic_switch {
    setup_develop $GENERIC_SWITCH_DIR
}

# NOTE(pas-ha) almost verbatim copy of devstack/tools/create-stack-user.sh
# adapted to be started w/o sudo from the start
function create_ovs_manager_user {

    # Give the non-root user the ability to run as **root** via ``sudo``
    is_package_installed sudo || install_package sudo

    if ! getent group $GENERIC_SWITCH_USER >/dev/null; then
        echo "Creating a group called $GENERIC_SWITCH_USER"
        sudo groupadd $GENERIC_SWITCH_USER
    fi

    if ! getent passwd $GENERIC_SWITCH_USER >/dev/null; then
        echo "Creating a user called $GENERIC_SWITCH_USER"
        mkdir -p $GENERIC_SWITCH_USER_HOME
        sudo useradd -g $GENERIC_SWITCH_USER -s /bin/bash -d $GENERIC_SWITCH_USER_HOME -m $GENERIC_SWITCH_USER
    fi

    echo "Giving $GENERIC_SWITCH_USER user passwordless sudo privileges"
    # UEC images ``/etc/sudoers`` does not have a ``#includedir``, add one
    sudo grep -q "^#includedir.*/etc/sudoers.d" /etc/sudoers ||
        echo "#includedir /etc/sudoers.d" | sudo tee -a /etc/sudoers
    ( umask 226 && echo "$GENERIC_SWITCH_USER ALL=(ALL) NOPASSWD:ALL" | sudo tee /etc/sudoers.d/99_ngs_ovs_manager )

    # Hush the login banner for ovs user
    touch $GENERIC_SWITCH_USER_HOME/.hushlogin
}

function configure_for_dlm {
    # limit number of ssh connections for generic-switch user
    ( umask 226 && echo "$GENERIC_SWITCH_USER hard maxlogins $GENERIC_SWITCH_USER_MAX_SESSIONS" | sudo tee /etc/security/limits.d/ngs_ovs_manager.conf )
    # set lock acquire timeout
    populate_ml2_config $GENERIC_SWITCH_INI_FILE ngs_coordination acquire_timeout=$GENERIC_SWITCH_DLM_ACQUIRE_TIMEOUT
    # set ectd3 backend
    populate_ml2_config $GENERIC_SWITCH_INI_FILE ngs_coordination backend_url="etcd3+http://${SERVICE_HOST}:${ETCD_PORT:-2379}?api_version=v3"
    }

function configure_generic_switch_ssh_keypair {
    if [[ ! -d $GENERIC_SWITCH_USER_HOME/.ssh ]]; then
        sudo mkdir -p $GENERIC_SWITCH_USER_HOME/.ssh
        sudo chmod 700 $GENERIC_SWITCH_USER_HOME/.ssh
    fi
    # copy over stack user's authorized_keys to GENERIC_SWITCH_USER
    # mostly needed for multinode gate job
    if [[ -e "$HOME/.ssh/authorized_keys" ]]; then
        cat "$HOME/.ssh/authorized_keys" | sudo tee -a $GENERIC_SWITCH_KEY_AUTHORIZED_KEYS_FILE
    fi
    if [[ ! -e $GENERIC_SWITCH_KEY_FILE ]]; then
        if [[ ! -d $(dirname $GENERIC_SWITCH_KEY_FILE) ]]; then
            mkdir -p $(dirname $GENERIC_SWITCH_KEY_FILE)
        fi
        if [[ "$HOST_TOPLOGY" != "multinode" ]]; then
            # NOTE(TheJulia): Self management of ssh keys only works locally
            # and multinode CI jobs cannot leverage it.
            echo -e 'n\n' | ssh-keygen -q -t rsa -P '' -m PEM -f $GENERIC_SWITCH_KEY_FILE
        fi
    fi
    # NOTE(vsaienko) check for new line character, add if doesn't exist.
    if [[ "$(sudo tail -c1 $GENERIC_SWITCH_KEY_AUTHORIZED_KEYS_FILE | wc -l)" == "0" ]]; then
        echo "" | sudo tee -a $GENERIC_SWITCH_KEY_AUTHORIZED_KEYS_FILE
    fi
    cat $GENERIC_SWITCH_KEY_FILE.pub | sudo tee -a $GENERIC_SWITCH_KEY_AUTHORIZED_KEYS_FILE
    # remove duplicate keys.
    sudo sort -u -o $GENERIC_SWITCH_KEY_AUTHORIZED_KEYS_FILE $GENERIC_SWITCH_KEY_AUTHORIZED_KEYS_FILE
    sudo chown $GENERIC_SWITCH_USER:$GENERIC_SWITCH_USER $GENERIC_SWITCH_KEY_AUTHORIZED_KEYS_FILE
    sudo chown -R $GENERIC_SWITCH_USER:$GENERIC_SWITCH_USER $GENERIC_SWITCH_USER_HOME
}

function configure_generic_switch_user {
    create_ovs_manager_user
    configure_generic_switch_ssh_keypair
    if [[ "$GENERIC_SWITCH_USER_MAX_SESSIONS" -gt 0 ]]; then
        configure_for_dlm
    fi

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

    # set netmiko session log
    populate_ml2_config $GENERIC_SWITCH_INI_FILE ngs session_log_file=$GENERIC_SWITCH_DATA_DIR/netmiko_session.log

    # Generate SSH keypair
    configure_generic_switch_user

    if [[ "${IRONIC_NETWORK_SIMULATOR:-ovs}" == "ovs" ]]; then
        sudo ovs-vsctl --may-exist add-br $GENERIC_SWITCH_TEST_BRIDGE
        ip link show gs_port_01 || sudo ip link add gs_port_01 type dummy
        sudo ovs-vsctl --may-exist add-port $GENERIC_SWITCH_TEST_BRIDGE $GENERIC_SWITCH_TEST_PORT
        if [[ "$GENERIC_SWITCH_USER_MAX_SESSIONS" -gt 0 ]]; then
            # NOTE(pas-ha) these are used for concurrent tests in tempest plugin
            N_PORTS=$(($GENERIC_SWITCH_USER_MAX_SESSIONS * 2))
            for ((n=0;n<$N_PORTS;n++)); do
                sudo ovs-vsctl --may-exist add-port $GENERIC_SWITCH_TEST_BRIDGE ${GENERIC_SWITCH_TEST_PORT}_${n}
            done
        fi

        if [ -e "$HOME/.ssh/id_rsa" ] && [[ "$HOST_TOPOLOGY" == "multinode" ]]; then
            # NOTE(TheJulia): Reset the key pair to utilize a pre-existing key,
            # this is instead of generating one, which doesn't work in multinode
            # environments. This is because the keys are managed and placed by zuul.
            GENERIC_SWITCH_KEY_FILE="${HOME}/.ssh/id_rsa"
        fi

        # Create generic_switch ml2 config
        for switch in $GENERIC_SWITCH_TEST_BRIDGE $IRONIC_VM_NETWORK_BRIDGE; do
            local bridge_mac
            bridge_mac=$(ip link show dev $switch | egrep -o "ether [A-Za-z0-9:]+"|sed "s/ether\ //")
            switch="genericswitch:$switch"
            add_generic_switch_to_ml2_config $switch $GENERIC_SWITCH_KEY_FILE $GENERIC_SWITCH_USER ::1 netmiko_ovs_linux "$GENERIC_SWITCH_PORT" "$bridge_mac"
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
                add_generic_switch_to_ml2_config $section $GENERIC_SWITCH_KEY_FILE $GENERIC_SWITCH_USER $node netmiko_ovs_linux "$GENERIC_SWITCH_PORT"
            done
        fi
    fi
    # NOTE(TheJulia): This is not respected presently with uwsgi launched
    # neutron as it auto-identifies it's configuration files.
    neutron_server_config_add $GENERIC_SWITCH_INI_FILE

    # NOTE(JayF): It's possible in some rare cases this config doesn't exist
    #             if so, no big deal, iniset is used in devstack and should
    #             not lose our changes. See `write_uwsgi_config` in lib/apache
    iniset -sudo /etc/neutron/neutron-api-uwsgi.ini uwsgi env OS_NEUTRON_CONFIG_FILES='/etc/neutron/neutron.conf;/etc/neutron/plugins/ml2/ml2_conf.ini;/etc/neutron/plugins/ml2/ml2_conf_genericswitch.ini'
}

function add_generic_switch_to_ml2_config {
    local switch_name=$1
    local key_file=$2
    local username=$3
    local ip=$4
    local device_type=$5
    local port=$6
    local ngs_mac_address=$7
    local password=$8
    local enable_secret=$9
    # Use curly braces above 9 to prevent expression expansion
    local trunk_interface="${10}"

    if [[ -n "$key_file" ]]; then
        populate_ml2_config $GENERIC_SWITCH_INI_FILE $switch_name key_file=$key_file
        populate_ml2_config $GENERIC_SWITCH_INI_FILE $switch_name use_keys=True
    elif [[ -n "$password" ]]; then
        populate_ml2_config $GENERIC_SWITCH_INI_FILE $switch_name password=$password
    fi
    populate_ml2_config $GENERIC_SWITCH_INI_FILE $switch_name username=$username
    populate_ml2_config $GENERIC_SWITCH_INI_FILE $switch_name ip=$ip
    populate_ml2_config $GENERIC_SWITCH_INI_FILE $switch_name device_type=$device_type
    if [[ -n "$enable_secret" ]]; then
        populate_ml2_config $GENERIC_SWITCH_INI_FILE $switch_name secret=$enable_secret
    fi
    if [[ -n "$port" ]]; then
        populate_ml2_config $GENERIC_SWITCH_INI_FILE $switch_name port=$port
    fi
    if [[ -n $ngs_mac_address ]]; then
        populate_ml2_config $GENERIC_SWITCH_INI_FILE $switch_name ngs_mac_address=$ngs_mac_address
    fi

    if [[ "$device_type" =~ "netmiko" && "$GENERIC_SWITCH_USER_MAX_SESSIONS" -gt 0 ]]; then
        populate_ml2_config $GENERIC_SWITCH_INI_FILE $switch_name ngs_max_connections=$GENERIC_SWITCH_USER_MAX_SESSIONS
    fi
    if [[ -n "$trunk_interface" ]]; then
        populate_ml2_config $GENERIC_SWITCH_INI_FILE $switch_name ngs_trunk_ports=$trunk_interface
    fi
}

function cleanup_networking_generic_switch {
    rm -f $GENERIC_SWITCH_INI_FILE
    if [[ -f $GENERIC_SWITCH_KEY_FILE ]]; then
        local key
        key=$(cat $GENERIC_SWITCH_KEY_FILE.pub)
        # remove public key from authorized_keys
        sudo grep -v "$key" $GENERIC_SWITCH_KEY_AUTHORIZED_KEYS_FILE > temp && sudo mv -f temp $GENERIC_SWITCH_KEY_AUTHORIZED_KEYS_FILE
        sudo chown $GENERIC_SWITCH_USER:$GENERIC_SWITCH_USER $GENERIC_SWITCH_KEY_AUTHORIZED_KEYS_FILE
        sudo chmod 0600 $GENERIC_SWITCH_KEY_AUTHORIZED_KEYS_FILE
    fi
    sudo ovs-vsctl --if-exists del-br $GENERIC_SWITCH_TEST_BRIDGE

    # remove generic switch user, its permissions and limits
    sudo rm -f /etc/sudoers.d/99_ngs_ovs_manager
    sudo rm -f /etc/security/limits.d/ngs_ovs_manager.conf
    sudo userdel --remove --force $GENERIC_SWITCH_USER
    sudo groupdel $GENERIC_SWITCH_USER

    sudo rm -rf $GENERIC_SWITCH_DATA_DIR
}

function ngs_configure_tempest {
    iniset $TEMPEST_CONFIG service_available ngs True
    iniset $TEMPEST_CONFIG ngs bridge_name $GENERIC_SWITCH_TEST_BRIDGE
    iniset $TEMPEST_CONFIG ngs port_name $GENERIC_SWITCH_TEST_PORT
    if [ $GENERIC_SWITCH_USER_MAX_SESSIONS -gt 0 ]; then
        iniset $TEMPEST_CONFIG ngs port_dlm_concurrency $(($GENERIC_SWITCH_USER_MAX_SESSIONS * 2))
    fi
    if [[ "${ML2_L3_PLUGIN:-}" =~ "trunk" ]]; then
        iniset $TEMPEST_CONFIG baremetal_feature_enabled trunks_supported True
    fi
}

function ngs_restart_neutron {
    echo_summary "NGS doing required neutron restart. Stopping neutron."
    # NOTE(JayF) In practice restarting OVN causes problems, I'm not sure why.
    # This avoids the restart.
    local existing_skip_stop_ovn
    SKIP_STOP_OVN=True
    # We are changing the base config, and need ot restart the neutron services
    stop_neutron
    # NOTE(JayF): Neutron services are initialized in a particular order, this appears to
    # match that order as currently defined in stack.sh (2025-05-22).
    # TODO(JayF): Introduce a function in upstream devstack that documents this order so
    # ironic won't break anytime initialization steps are rearranged.
    echo_summary "NGS starting neutron service"
    start_neutron_service_and_check
    echo_summary "NGS started neutron service, now launch neutron agents"
    start_neutron
    echo_summary "NGS required neutron restart completed."
    SKIP_STOP_OVN=False
}

# check for service enabled
if is_service_enabled generic_switch; then

    if [[ "$1" == "stack" && "$2" == "install" ]]; then
        # Perform installation of service source
        echo_summary "Installing Generic_switch ML2"
        install_generic_switch

    elif [[ "$1" == "stack" && "$2" == "post-config" ]]; then
        # Configure after the other layer 1 and 2 services have been started
        echo_summary "Configuring Generic_switch ML2"

        # Source ml2 plugin, set default config
        if is_service_enabled neutron; then
            source $RC_DIR/lib/neutron_plugins/ml2
            Q_PLUGIN_CONF_PATH=etc/neutron/plugins/ml2
            Q_PLUGIN_CONF_FILENAME=ml2_conf.ini
            Q_PLUGIN_CONF_FILE="/${Q_PLUGIN_CONF_PATH}/${Q_PLUGIN_CONF_FILENAME}"
            Q_PLUGIN_CLASS="ml2"
        fi

        # TODO(JayF): This currently relies on winning a race, as many of the
        #             files modified by this method are created during this
        #             phase. In practice it works, but moving forward we likely
        #             need a supported-by-devstack/neutron-upstream method to 
        #             ensure this is done at the right moment.
        configure_generic_switch

        if is_service_enabled neutron; then
            # TODO(JayF): Similarly, we'd like to restart neutron to ensure
            #             our config changes have taken effect; we can't do 
            #             that reliably here because it may not be fully
            #             configured, and extra phase is too late.
            echo_summary "Skipping ngs_restart_neutron"
            #ngs_restart_neutron
        fi

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
