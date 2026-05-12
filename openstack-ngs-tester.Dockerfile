FROM registry.ci.openshift.org/ocp/4.22:base-rhel9

RUN dnf install -y python3.12-devel python3.12-pip \
 && dnf clean all \
 && rm -rf /var/cache/yum \
 && python3.12 -m pip install tox

