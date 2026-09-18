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

"""Sphinx directive to render per-switch NGS config options.

The per-switch options are described as ``oslo_config.cfg.Opt`` instances
(see ``NGS_INTERNAL_OPTS`` and friends). They are not registered with
oslo.config because their config groups (``[genericswitch:<name>]``) are
named dynamically, so oslo's own sphinxext cannot enumerate them. This
directive imports a named list of ``cfg.Opt`` instances and renders each
option's name, type, default and help text, keeping the documentation in
sync with the single source of truth in the code.

Usage::

    .. ngs-config-options:: networking_generic_switch.devices.NGS_INTERNAL_OPTS
"""

import importlib

from docutils import nodes
from docutils.parsers import rst
from docutils.statemachine import ViewList
from oslo_config import cfg
from sphinx.util.nodes import nested_parse_with_titles

# Map the cfg.Opt subclass to a human-readable type name.
_OPT_TYPE_NAMES = {
    cfg.StrOpt: 'string',
    cfg.BoolOpt: 'boolean',
    cfg.IntOpt: 'integer',
    cfg.FloatOpt: 'floating point',
    cfg.ListOpt: 'list',
}


def _opt_type_name(opt):
    """Return a friendly type name for an option."""
    return _OPT_TYPE_NAMES.get(type(opt), type(opt).__name__)


def _format_default(opt):
    """Return a display string for an option's default value."""
    if opt.default is None:
        return 'not set'
    if isinstance(opt.default, bool):
        return str(opt.default)
    if opt.default == '':
        return "'' (empty)"
    return str(opt.default)


def _import_opts(dotted_path):
    """Import a module-level list of cfg.Opt from a dotted path."""
    module_path, _, attr = dotted_path.rpartition('.')
    module = importlib.import_module(module_path)
    return getattr(module, attr)


class NgsConfigOptionsDirective(rst.Directive):
    """Render a list of cfg.Opt instances as an option reference."""

    required_arguments = 1
    has_content = False

    def run(self):
        dotted_path = self.arguments[0]
        opts = _import_opts(dotted_path)

        output = ViewList()
        for opt in opts:
            # Definition-list term: the option name in monospace.
            output.append(f"``{opt.name}``", dotted_path)
            # Indented definition body: help text then type/default.
            help_text = opt.help or 'No description available.'
            for line in help_text.splitlines():
                output.append(f"    {line}", dotted_path)
            output.append("", dotted_path)
            output.append(
                f"    :Type: {_opt_type_name(opt)}", dotted_path)
            output.append(
                f"    :Default: {_format_default(opt)}", dotted_path)
            output.append("", dotted_path)

        node = nodes.section()
        node.document = self.state.document
        nested_parse_with_titles(self.state, output, node)
        return node.children


def setup(app):
    app.add_directive('ngs-config-options', NgsConfigOptionsDirective)
    return {
        'parallel_read_safe': True,
        'parallel_write_safe': True,
    }
