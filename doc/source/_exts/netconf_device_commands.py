# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import xml.dom.minidom

from docutils import nodes
from docutils.parsers import rst
from docutils.statemachine import ViewList
from sphinx.util.nodes import nested_parse_with_titles
import stevedore

from networking_generic_switch.yang_models import utils as yutils


EXAMPLE_SEGMENTATION_ID = 100
EXAMPLE_NETWORK_NAME = 'aabbccdd11223344aabbccdd11223344'
EXAMPLE_PORT_ID = 'Ethernet1/1'
EXAMPLE_TRUNK_PORTS = ['Ethernet1/48']

EXAMPLE_BINDING_PROFILE = {
    'local_link_information': [
        {'switch_id': '00:11:22:33:44:55', 'port_id': 'Ethernet1/1',
         'switch_info': 'example-switch'}
    ]
}
EXAMPLE_SUBPORTS = [
    {'segmentation_id': 200, 'segmentation_type': 'vlan',
     'port_id': 'subport-uuid-1'},
    {'segmentation_id': 201, 'segmentation_type': 'vlan',
     'port_id': 'subport-uuid-2'},
]
EXAMPLE_TRUNK_DETAILS = {
    'trunk_id': 'trunk-uuid',
    'segmentation_id': EXAMPLE_SEGMENTATION_ID,
    'sub_ports': [
        {'segmentation_id': 200, 'segmentation_type': 'vlan',
         'port_id': 'subport-uuid-1'},
        {'segmentation_id': 201, 'segmentation_type': 'vlan',
         'port_id': 'subport-uuid-2'},
        {'segmentation_id': 202, 'segmentation_type': 'vlan',
         'port_id': 'subport-uuid-3'},
    ],
}
EXAMPLE_TRUNK_DETAILS_AFTER_DELETE = {
    'trunk_id': 'trunk-uuid',
    'segmentation_id': EXAMPLE_SEGMENTATION_ID,
    'sub_ports': [
        {'segmentation_id': 202, 'segmentation_type': 'vlan',
         'port_id': 'subport-uuid-3'},
    ],
}

OPERATIONS = [
    {
        'name': 'ADD_NETWORK',
        'description': 'Create a VLAN on the device',
        'method': '_add_network',
        'kwargs': {
            'segmentation_id': EXAMPLE_SEGMENTATION_ID,
            'network_name': EXAMPLE_NETWORK_NAME,
        },
    },
    {
        'name': 'DELETE_NETWORK',
        'description': 'Remove a VLAN from the device',
        'method': '_delete_network',
        'kwargs': {
            'segmentation_id': EXAMPLE_SEGMENTATION_ID,
            'network_name': EXAMPLE_NETWORK_NAME,
        },
    },
    {
        'name': 'ADD_NETWORK_TO_TRUNK',
        'description': 'Tag trunk ports with a VLAN when a network is created',
        'method': '_add_network_to_trunk',
        'kwargs': {
            'segmentation_id': EXAMPLE_SEGMENTATION_ID,
            'trunk_ports': EXAMPLE_TRUNK_PORTS,
        },
    },
    {
        'name': 'REMOVE_NETWORK_FROM_TRUNK',
        'description': 'Untag trunk ports when a network is deleted',
        'method': '_remove_network_from_trunk',
        'kwargs': {
            'segmentation_id': EXAMPLE_SEGMENTATION_ID,
            'trunk_ports': EXAMPLE_TRUNK_PORTS,
        },
    },
    {
        'name': 'PLUG_PORT_TO_NETWORK',
        'description': 'Assign an access VLAN to a port',
        'method': '_plug_port_to_network',
        'kwargs': {
            'port_id': EXAMPLE_PORT_ID,
            'segmentation_id': EXAMPLE_SEGMENTATION_ID,
        },
    },
    {
        'name': 'DELETE_PORT',
        'description': 'Remove VLAN configuration from a port',
        'method': '_delete_port',
        'kwargs': {
            'port_id': EXAMPLE_PORT_ID,
            'segmentation_id': EXAMPLE_SEGMENTATION_ID,
        },
    },
    {
        'name': 'ENABLE_PORT',
        'description': 'Administratively enable a port',
        'method': '_enable_port',
        'kwargs': {
            'port_id': EXAMPLE_PORT_ID,
        },
    },
    {
        'name': 'DISABLE_PORT',
        'description': 'Administratively disable a port',
        'method': '_disable_port',
        'kwargs': {
            'port_id': EXAMPLE_PORT_ID,
        },
    },
    {
        'name': 'ADD_SUBPORTS_ON_TRUNK',
        'description':
            'Add subport VLANs to a trunk port (converging with '
            'trunk_details)',
        'method': '_add_subports_on_trunk',
        'kwargs': {
            'binding_profile': EXAMPLE_BINDING_PROFILE,
            'port_id': EXAMPLE_PORT_ID,
            'subports': EXAMPLE_SUBPORTS,
            'trunk_details': EXAMPLE_TRUNK_DETAILS,
        },
    },
    {
        'name': 'DEL_SUBPORTS_ON_TRUNK',
        'description':
            'Remove subport VLANs from a trunk port (converging '
            'with trunk_details showing remaining subports)',
        'method': '_del_subports_on_trunk',
        'kwargs': {
            'binding_profile': EXAMPLE_BINDING_PROFILE,
            'port_id': EXAMPLE_PORT_ID,
            'subports': EXAMPLE_SUBPORTS,
            'trunk_details': EXAMPLE_TRUNK_DETAILS_AFTER_DELETE,
        },
    },
    {
        'name': 'PLUG_PORT_TO_NETWORK (trunk)',
        'description':
            'Assign a trunk port with native VLAN and subport VLANs',
        'method': '_plug_port_to_network',
        'kwargs': {
            'port_id': EXAMPLE_PORT_ID,
            'segmentation_id': EXAMPLE_SEGMENTATION_ID,
            'trunk_details': EXAMPLE_TRUNK_DETAILS,
        },
    },
]


def _pretty_xml(xml_string):
    """Pretty-print XML with indentation, stripping the declaration."""
    dom = xml.dom.minidom.parseString(xml_string)
    pretty = dom.toprettyxml(indent='  ')
    lines = pretty.splitlines()
    # Skip the XML declaration line
    return '\n'.join(line for line in lines[1:] if line.strip())


def _build_fake_config(device_type):
    """Build minimal device config to instantiate a NETCONF driver."""
    return {
        'device_type': device_type,
        'host': '192.0.2.10',
        'username': 'admin',
        'password': 'secret',
    }


class NetconfDeviceCommandsDirective(rst.Directive):
    """Sphinx directive to render NETCONF device XML payloads."""

    def run(self):
        manager = stevedore.ExtensionManager(
            namespace='generic_switch.devices',
            invoke_on_load=False,
        )

        output_lines = ViewList()

        for ext in manager.extensions:
            if not ext.name.startswith('netconf_'):
                continue

            switch_class = ext.plugin
            device_type = ext.name

            title = f'{switch_class.__name__} (``{device_type}``)'
            output_lines.append(title, '')
            output_lines.append('=' * len(title), '')
            output_lines.append('', '')

            docstring = switch_class.__doc__
            if docstring:
                for line in docstring.strip().splitlines():
                    output_lines.append(line.strip(), '')
                output_lines.append('', '')

            # Instantiate with fake config
            try:
                cfg = _build_fake_config(device_type)
                instance = switch_class(cfg, 'example-switch')
            except Exception as e:
                output_lines.append(
                    f'*Could not instantiate driver: {e}*', '')
                output_lines.append('', '')
                continue

            for op in OPERATIONS:
                method = getattr(instance, op['method'], None)
                if method is None:
                    continue

                output_lines.append(f"{op['name']}", '')
                output_lines.append('-' * len(op['name']), '')
                output_lines.append(op['description'], '')
                output_lines.append('', '')

                try:
                    result = method(**op['kwargs'])
                    if result:
                        xml_str = yutils.config_to_xml(result)
                        pretty = _pretty_xml(xml_str)
                        output_lines.append('.. code-block:: xml', '')
                        output_lines.append('', '')
                        for line in pretty.splitlines():
                            output_lines.append(f'   {line}', '')
                        output_lines.append('', '')
                except Exception as e:
                    output_lines.append(
                        f'*Error generating XML: {e}*', '')
                    output_lines.append('', '')

        node = nodes.section()
        node.document = self.state.document
        nested_parse_with_titles(self.state, output_lines, node)
        return node.children


def setup(app):
    app.add_directive('netconf-device-commands', NetconfDeviceCommandsDirective)
