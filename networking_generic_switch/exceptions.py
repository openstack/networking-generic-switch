# Copyright 2016 Mirantis, Inc.
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

from neutron.plugins.ml2.common import exceptions as ml2_exc

from networking_generic_switch._i18n import _


class GenericSwitchException(ml2_exc.MechanismDriverError):
    pass


class GenericSwitchEntrypointLoadError(GenericSwitchException):
    message = _("Failed to load entrypoint %(ep)s: %(err)s")


class GenericSwitchConfigError(GenericSwitchException):
    message = _("Can not find configuration for switch %(switch)s")
