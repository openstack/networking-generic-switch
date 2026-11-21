#
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

import re

from oslo_log import log as logging

from networking_generic_switch import exceptions as ngs_exc

LOG = logging.getLogger(__name__)

# NOTE(TheJulia): Spaces are allowed because some vendors use them in
# interface names, e.g. "FortyGig 4/1". Blocking them would break
# existing local_link_information data.
VALID_PORT_ID_RE = re.compile(r'^[a-zA-Z0-9 /_:.\-]+$')

# The longest standard interface name is ~26 chars
# (TenGigabitEthernet1/0/48); 64 leaves headroom while capping abuse.
MAX_PORT_ID_LEN = 64

# NOTE(TheJulia): Spaces are interpolated into switch commands
# unquoted, so each one is a potential extra CLI token. Real names
# have at most one space; cap at 2 to limit argument injection.
MAX_PORT_ID_SPACES = 2


def validate_port_id(port_id: str | None) -> str | None:
    """Validate and sanitize a port_id from local_link_information.

    :param port_id: Raw port_id value from local_link_information.
    :returns: The sanitized port_id string, or the original value if
              the input is None or empty.
    :raises GenericSwitchInvalidPortId: If the port_id exceeds
            MAX_PORT_ID_LEN, contains more than MAX_PORT_ID_SPACES
            spaces, or contains characters outside the allowed set.
    """
    if not port_id:
        return port_id
    port_id = str(port_id).strip()
    if not port_id:
        return port_id
    if len(port_id) > MAX_PORT_ID_LEN:
        LOG.error(
            "Rejected port_id exceeding %d characters: %r",
            MAX_PORT_ID_LEN, port_id
        )
        raise ngs_exc.GenericSwitchInvalidPortId(
            port_id=port_id
        )
    if port_id.count(' ') > MAX_PORT_ID_SPACES:
        LOG.error(
            "Rejected port_id with more than %d spaces: %r",
            MAX_PORT_ID_SPACES, port_id
        )
        raise ngs_exc.GenericSwitchInvalidPortId(
            port_id=port_id
        )
    if not VALID_PORT_ID_RE.match(port_id):
        LOG.error(
            "Rejected port_id with invalid characters: %r",
            port_id
        )
        raise ngs_exc.GenericSwitchInvalidPortId(
            port_id=port_id
        )
    return port_id
