#!/bin/bash

# Many of neutron's repos suffer from the problem of depending on neutron,
# but it not existing on pypi. This ensures its installed into the test environment.
set -ex

ZUUL_CLONER=/usr/zuul-env/bin/zuul-cloner
BRANCH_NAME=master

CONSTRAINTS_FILE=$1
shift

install_cmd="pip install"
if [ $CONSTRAINTS_FILE != "unconstrained" ]; then
    install_cmd="$install_cmd -c$CONSTRAINTS_FILE"
fi

if $(python -c "import neutron" 2> /dev/null); then
    echo "Neutron already installed."
elif [ -x $ZUUL_CLONER ]; then
    export ZUUL_BRANCH={$ZUUL_BRANCH-$BRANCH_NAME}
    #export ZUUL_BRANCH={$ZUUL_BRANCH:-$BRANCH_NAME}
    # Use zuul-cloner to clone openstack/neutron, this will ensure the Depends-On
    # references are retrieved from zuul and rebased into the repo, then installed.
    $ZUUL_CLONER \
        --cache-dir /opt/git \
        --workspace /tmp \
        --branch $BRANCH_NAME \
        git://git.openstack.org openstack/neutron
    cd /tmp/openstack/neutron
    $install_cmd -e .
else
    if [ -z "$NEUTRON_PIP_LOCATION" ]; then
        NEUTRON_PIP_LOCATION="git+git://git.openstack.org/openstack/neutron@$BRANCH_NAME#egg=neutron"
    fi
    $install_cmd -U -e ${NEUTRON_PIP_LOCATION}
fi

# Install the rest of the requirements as normal
$install_cmd -U $*

exit $?
