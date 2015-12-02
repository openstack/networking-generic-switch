# plugin.sh - DevStack plugin.sh dispatch script template

GENERIC_SWITCH_DIR=${GENERIC_SWITCH_DIR:-$DEST/generic_switch}
GENERIC_SWITCH_INI_FILE='/etc/neutron/plugins/ml2/ml2_conf_genericswitch.ini'

function install_generic_switch {
    setup_develop $GENERIC_SWITCH_DIR
}

function configure_generic_switch {
    if [[ -z "$Q_ML2_PLUGIN_MECHANISM_DRIVERS" ]]; then
        Q_ML2_PLUGIN_MECHANISM_DRIVERS='genericswitch'
    else
        Q_ML2_PLUGIN_MECHANISM_DRIVERS+=',genericswitch'
    fi
    populate_ml2_config /$Q_PLUGIN_CONF_FILE ml2 mechanism_drivers=$Q_ML2_PLUGIN_MECHANISM_DRIVERS

    # Create generic_switch ml2 config
    local cfg_sec="genericswitch:$IRONIC_VM_NETWORK_BRIDGE"
    if ! is_ironic_hardware; then
        populate_ml2_config $GENERIC_SWITCH_INI_FILE $cfg_sec key_file=$IRONIC_KEY_FILE
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
