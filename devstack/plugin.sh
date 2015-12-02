# plugin.sh - DevStack plugin.sh dispatch script template

GENERIC_SWITCH_DIR=${GENERIC_SWITCH_DIR:-$DEST/generic_switch}
GENERIC_SWITCH_INI_FILE='/etc/neutron/plugins/ml2/ml2_conf_genericswitch.ini'
GENERIC_SWITCH_SSH_KEY_FILENAME="generic_switch"
GENERIC_SWITCH_KEY_DIR="$DATA_DIR/neutron"
GENERIC_SWITCH_KEY_FILE="$GENERIC_SWITCH_KEY_DIR/$GENERIC_SWITCH_SSH_KEY_FILENAME"
GENERIC_SWITCH_KEY_AUTHORIZED_KEYS_FILE="$HOME/.ssh/authorized_keys"

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
    cat $GENERIC_SWITCH_KEY_FILE.pub | tee -a $GENERIC_SWITCH_KEY_AUTHORIZED_KEYS_FILE
}

function configure_generic_switch {
    if [[ -z "$Q_ML2_PLUGIN_MECHANISM_DRIVERS" ]]; then
        Q_ML2_PLUGIN_MECHANISM_DRIVERS='genericswitch'
    else
        Q_ML2_PLUGIN_MECHANISM_DRIVERS+=',genericswitch'
    fi
    populate_ml2_config /$Q_PLUGIN_CONF_FILE ml2 mechanism_drivers=$Q_ML2_PLUGIN_MECHANISM_DRIVERS

    # Generate SSH keypair
    configure_generic_switch_ssh_keypair

    # Create generic_switch ml2 config
    local cfg_sec="genericswitch:$IRONIC_VM_NETWORK_BRIDGE"
    if ! is_ironic_hardware; then
        populate_ml2_config $GENERIC_SWITCH_INI_FILE $cfg_sec key_file=$GENERIC_SWITCH_KEY_FILE
        populate_ml2_config $GENERIC_SWITCH_INI_FILE $cfg_sec username=$STACK_USER
        populate_ml2_config $GENERIC_SWITCH_INI_FILE $cfg_sec ip=localhost
        populate_ml2_config $GENERIC_SWITCH_INI_FILE $cfg_sec device_type=ovs_linux
    fi
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
    fi
fi
