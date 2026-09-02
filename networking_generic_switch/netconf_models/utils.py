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

from xml.etree import ElementTree

from networking_generic_switch.netconf_models import constants as ncconst


def txt_subelement(parent, tag, text, *args, **kwargs):
    element = ElementTree.SubElement(parent, tag, *args, **kwargs)
    element.text = text
    return element


def config_to_xml(config):
    element = ElementTree.Element(ncconst.CFG_ELEMENT)
    for conf in config:
        element.append(conf.to_xml_element())
    return ElementTree.tostring(element).decode("utf-8")


def config_to_restconf_json(config):
    """Serialize model objects to RESTCONF JSON (RFC 7951).

    Returns a dict suitable for passing to requests.patch(json=...).
    """
    result = {}
    for conf in config:
        result.update(conf.to_restconf_dict())
    return result


def restconf_resource_path(*segments, base_path='/restconf/data'):
    """Build a RESTCONF URL path from model path segments.

    Composes segments from model ``to_restconf_path()`` calls into a
    full RESTCONF data-resource URL path (RFC 8040 Section 3.5.3).

    :param segments: One or more RESTCONF path segments.
    :param base_path: RESTCONF base path (default ``/restconf/data``).
    :returns: Full RESTCONF URL path string.
    """
    parts = [base_path.rstrip('/')]
    parts.extend(s for s in segments if s)
    return '/'.join(parts)
