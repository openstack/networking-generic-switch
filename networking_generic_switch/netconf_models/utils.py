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
