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

import ast
import inspect
import stevedore

from docutils import nodes
from docutils.parsers import rst
from docutils.parsers.rst import directives
from docutils.statemachine import ViewList
from sphinx.util.nodes import nested_parse_with_titles

command_descriptions = {
    'ADD_NETWORK': 'A tuple of command strings used to add a VLAN',
    'DELETE_NETWORK': 'A tuple of command strings used to delete a VLAN',
    'PLUG_PORT_TO_NETWORK': 'A tuple of command strings used to configure a \
         port to connect to a specific VLAN',
    'DELETE_PORT': 'A tuple of command strings used to remove a port from the\
         VLAN',
    'NETMIKO_DEVICE_TYPE': 'Netmiko compatible device type',
    'ADD_NETWORK_TO_TRUNK': 'Adds a network to a trunk port.',
    'REMOVE_NETWORK_FROM_TRUNK': 'Removes a network from a trunk port.',
    'ENABLE_PORT': 'Enables the port',
    'DISABLE_PORT': 'Shuts down the port',
    'ERROR_MSG_PATTERNS': 'A tuple of regular expressions. These patterns are\
         used to match and handle error messages returned by the switch.',
    'SET_NATIVE_VLAN': 'Sets a specified native VLAN',
    'DELETE_NATIVE_VLAN': 'Removes the native VLAN',
    'SAVE_CONFIGURATION': 'Saves the configuration',
    'SET_NATIVE_VLAN_BOND': 'Sets the native VLAN for the bond interface',
    'DELETE_NATIVE_VLAN_BOND': 'Unsets the native VLAN for the bond \
        interface',
    'ADD_NETWORK_TO_BOND_TRUNK': 'Adds a VLAN to the bond interface for \
        trunking',
    'DELETE_NETWORK_ON_BOND_TRUNK': 'Removes a VLAN from the bond interface \
        for trunking',
    'PLUG_PORT_TO_NETWORK_GENERAL': 'Allows the VLAN and lets it carry \
        untagged frames',
    'DELETE_PORT_GENERAL': 'Removes VLAN from allowed list and stops allowing\
          it to carry untagged frames',
    'QUERY_PORT': 'Shows details about the switch for that port',
    'PLUG_BOND_TO_NETWORK': 'Adds bond to the bridge as a port for the VLAN',
    'UNPLUG_BOND_FROM_NETWORK': 'Removes bond\'s access VLAN assignment',
    'ENABLE_BOND': 'Enables bond interface by removing link down state',
    'DISABLE_BOND': 'Disables bond interface by setting its link state to \
        down',
}

class DeviceParser:
    """Parses class definitions from device files"""

    def parse_tuples(value):
        """Parses the value in the tuples and returns a list of its contents"""
        tuple_values = []
        for elt in value.elts:
            # Parsing if the item in the tuple is a function call
            if isinstance(elt, ast.Call):
                func_name = ''
                if isinstance(elt.func, ast.Attribute):
                    func_name = f"{ast.unparse(elt.func.value)}.{elt.func.attr}"
                elif isinstance(elt.func, ast.Name):
                    func_name = elt.func.id
                args = [ast.literal_eval(arg) for arg in elt.args]
                call_command = str(func_name) + '(\'' + str(args[0]) + '\')'
                tuple_values.append(call_command)

            else:
                tuple_values.append(ast.literal_eval(elt))
        return tuple_values

    def parse_file(file_content, filename):
        """Uses ast to split document body into nodes and parse them"""
        tree = ast.parse(file_content, filename=filename)
        classes = {}
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                device_name = node.name
                cli_commands = {}
                docstring = ast.get_docstring(node)

                if docstring:
                    cli_commands['__doc__'] = docstring
                # Iterates through nodes, checks for type of node and extracts the value
                for subnode in node.body:
                    if isinstance(subnode, ast.Assign):
                        for target in subnode.targets:
                            command_name = target.id
                            if isinstance(target, ast.Name):
                                ast_type = subnode.value
                                if isinstance(ast_type, ast.Tuple):
                                    cli_commands[command_name] = DeviceParser.parse_tuples(ast_type)
                                else:
                                    cli_commands[command_name] = ast.literal_eval(ast_type)
                if cli_commands:
                    classes[device_name] = cli_commands
        return classes


class DeviceCommandsDirective(rst.Directive):
    """To output documentation based on the output-type that is requested"""

    option_spec = {
        'output-type': directives.unchanged,
    }

    def format_output(switch_details):
        """Formats output that is to be displayed"""
        formatted_output = ViewList()
        if '__doc__' in switch_details:
            for line in switch_details['__doc__'].splitlines():
                formatted_output.append(f"    {line}", "")
            formatted_output.append("", "")
            del switch_details['__doc__']
        for command_name, cli_commands in switch_details.items():
            desc = command_descriptions.get(command_name, 'No description provided')
            formatted_output.append(f"    - {command_name}: {desc}", "")
            formatted_output.append(f"        - CLI commands:", "")
            if isinstance(cli_commands, list):
                if cli_commands:
                    for command in cli_commands:
                        formatted_output.append(f"            - {command}", "")
                else:
                    formatted_output.append(f"            - No cli commands for this switch command", "")
            else:
                formatted_output.append(f"            - {cli_commands}", "")
        return formatted_output

    def run(self):
        """Loads the files, parses them and formats the output"""

        # default output type is full device documentation. other output types
        # display names of compatible devices or only devices capable of
        # disabling ports
        output_type = self.options.get('output-type', 'documentation')

        manager = stevedore.ExtensionManager(
            namespace='generic_switch.devices',
            invoke_on_load=False,
        )
        devices_info = []

        for file_loader in manager.extensions:
            switch = file_loader.plugin
            module = inspect.getmodule(switch)
            file_content = inspect.getsource(module)
            filename = module.__file__
            parsed_device_file = DeviceParser.parse_file(file_content, filename)
            switch_class_name = switch.__name__
            device_name = switch_class_name
            docstring = parsed_device_file.get(switch_class_name, {}).get('__doc__', '')
            can_disable_port = False

            # parses docstring for device name and whether port can be disabled
            if docstring:
                for line in docstring.splitlines():
                    if line.startswith('Device Name'):
                        _, device_name = line.split(': ', 1)
                    elif line.startswith('Port can be disabled'):
                        _, disable_str = line.split(': ', 1)
                        can_disable_port = disable_str.lower() == 'true'

            devices_info.append({
                'switch_class_name': switch_class_name,
                'device_name': device_name,
                'supports_disable': can_disable_port,
                'parsed_data': parsed_device_file.get(switch_class_name, {})
            })

        # to store output for documentation
        output_lines = ViewList()

        if output_type == 'all-devices':
            for device in devices_info:
                output_lines.append(f"- {device['device_name']}", "")

        elif output_type == 'devices-supporting-port-disable':
            for device in devices_info:
                if device['supports_disable']:
                    output_lines.append(f"- {device['device_name']}", "")

        else:
            output_lines.append("Switches", "")
            output_lines.append("========", "")
            for device in devices_info:
                switch_class_name = device['switch_class_name']
                output_lines.append(f"{switch_class_name}:", "")
                subheading_characters = "^"
                subheading = subheading_characters * (len(switch_class_name) + 1)
                output_lines.append(subheading, "")

                if device['parsed_data']:
                    output_lines.extend(DeviceCommandsDirective.format_output(device['parsed_data']))
                    output_lines.append("", "")

        node = nodes.section()
        node.document = self.state.document
        nested_parse_with_titles(self.state, output_lines, node)
        return node.children

def setup(app):
    app.add_directive('netmiko-device-commands', DeviceCommandsDirective)
