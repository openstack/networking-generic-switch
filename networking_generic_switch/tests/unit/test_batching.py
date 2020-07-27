# Copyright 2023 StackHPC
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

from unittest import mock

from etcd3gw.exceptions import Etcd3Exception
from etcd3gw.utils import _encode
from etcd3gw.utils import _increment_last_byte
import fixtures
from oslo_config import fixture as config_fixture
from oslo_utils import uuidutils
import tenacity

from networking_generic_switch import batching
from networking_generic_switch import exceptions as exc


class SwitchQueueTest(fixtures.TestWithFixtures):
    def setUp(self):
        super(SwitchQueueTest, self).setUp()
        self.cfg = self.useFixture(config_fixture.Config())

        self.client = mock.Mock()
        self.switch_name = "switch1"
        self.queue = batching.SwitchQueue(self.switch_name, self.client)

    @mock.patch.object(uuidutils, "generate_uuid")
    def test_add_batch(self, mock_uuid):
        mock_uuid.return_value = "uuid"
        self.client.transaction.return_value = {
            "succeeded": True,
            "responses": [{
                "response_put": {
                    "header": {
                        "revision": 42
                    }
                }
            }]
        }

        item = self.queue.add_batch(["cmd1", "cmd2"])

        self.assertEqual("uuid", item.uuid)
        self.assertEqual(42, item.create_revision)
        input_key = '/ngs/batch/switch1/input/uuid'
        expected_value = (
            b'{"cmds": ["cmd1", "cmd2"], '
            b'"input_key": "/ngs/batch/switch1/input/uuid", '
            b'"result_key": "/ngs/batch/switch1/output/uuid", '
            b'"uuid": "uuid"}')
        expected_txn = {
            'compare': [{
                'key': _encode(input_key),
                'result': 'EQUAL',
                'target': 'CREATE',
                'create_revision': 0
            }],
            'success': [{
                'request_put': {
                    'key': _encode(input_key),
                    'value': _encode(expected_value),
                    'lease': mock.ANY,
                }
            }],
            'failure': []
        }
        self.client.transaction.assert_called_once_with(expected_txn)

    @mock.patch.object(uuidutils, "generate_uuid")
    def test_add_batch_failure(self, mock_uuid):
        mock_uuid.return_value = "uuid"
        self.client.transaction.side_effect = Etcd3Exception

        self.assertRaises(Etcd3Exception,
                          self.queue.add_batch, ["cmd1", "cmd2"])

    @mock.patch.object(uuidutils, "generate_uuid")
    def test_add_batch_failure2(self, mock_uuid):
        mock_uuid.return_value = "uuid"
        self.client.transaction.return_value = {"succeeded": False}

        self.assertRaises(exc.GenericSwitchBatchError,
                          self.queue.add_batch, ["cmd1", "cmd2"])

    @mock.patch.object(batching.SwitchQueue, "_get_and_delete_result")
    def test_wait_for_result(self, mock_get):
        event = {
            "kv": {
                "version": 1
            }
        }
        self.client.watch_once.return_value = event
        mock_get.return_value = {"result": "result1"}
        item = batching.SwitchQueueItem("uuid", 42)

        result = self.queue.wait_for_result(item, 43)

        self.assertEqual("result1", result)
        result_key = '/ngs/batch/switch1/output/uuid'
        self.client.watch_once.assert_called_once_with(
            result_key, timeout=43, start_revision=42)
        mock_get.assert_called_once_with(result_key)

    def test_get_and_delete_result(self):
        self.client.transaction.return_value = {
            "succeeded": True,
            "responses": [{
                "response_delete_range": {
                    "prev_kvs": [{
                        "value": _encode(b'{"foo": "bar"}')
                    }]
                }
            }]
        }

        result = self.queue._get_and_delete_result(b"result_key")

        self.assertEqual({"foo": "bar"}, result)

        expected_txn = {
            'compare': [],
            'success': [{
                'request_delete_range': {
                    'key': _encode(b"result_key"),
                    'prev_kv': True,
                }
            }],
            'failure': []
        }
        self.client.transaction.assert_called_once_with(expected_txn)

    def test_get_and_delete_result_failure(self):
        self.client.transaction.return_value = {"succeeded": False}

        self.assertRaises(exc.GenericSwitchBatchError,
                          self.queue._get_and_delete_result, b"result_key")

    def test_get_batches(self):
        self.client.get.return_value = [
            (b'{"foo": "bar"}', {}),
            (b'{"foo1": "bar1"}', {})
        ]

        batches = self.queue.get_batches()

        self.assertEqual([
            {"foo": "bar"},
            {"foo1": "bar1"}
        ], batches)
        input_prefix = '/ngs/batch/switch1/input/'
        self.client.get.assert_called_once_with(
            input_prefix,
            metadata=True,
            range_end=_encode(_increment_last_byte(input_prefix)),
            sort_order='ascend', sort_target='create',
            max_create_revision=None)

    def test_get_batches_with_item(self):
        self.client.get.return_value = [
            (b'{"foo": "bar"}', {}),
            (b'{"foo1": "bar1"}', {})
        ]
        item = batching.SwitchQueueItem("uuid", 42)

        batches = self.queue.get_batches(item)

        self.assertEqual([
            {"foo": "bar"},
            {"foo1": "bar1"}
        ], batches)
        input_prefix = '/ngs/batch/switch1/input/'
        self.client.get.assert_called_once_with(
            input_prefix,
            metadata=True,
            range_end=_encode(_increment_last_byte(input_prefix)),
            sort_order='ascend', sort_target='create',
            max_create_revision=42)

    def test_record_result(self):
        self.client.transaction.return_value = {"succeeded": True}
        batch = {"result_key": "result1", "input_key": "input1",
                 "result": "asdf"}

        self.queue.record_result(batch)

        self.client.lease.assert_called_once_with(ttl=600)
        expected_value = (
            b'{"input_key": "input1", '
            b'"result": "asdf", "result_key": "result1"}')
        expected_txn = {
            'compare': [],
            'success': [
                {
                    'request_put': {
                        'key': _encode("result1"),
                        'value': _encode(expected_value),
                        'lease': mock.ANY,
                    }
                },
                {
                    'request_delete_range': {
                        'key': _encode("input1"),
                    }
                }
            ],
            'failure': []
        }
        self.client.transaction.assert_called_once_with(expected_txn)

    def test_record_result_failure(self):
        self.client.transaction.return_value = {"succeeded": False}
        batch = {"result_key": "result1", "input_key": "input1",
                 "result": "asdf"}

        # Should not raise an exception.
        self.queue.record_result(batch)

    @mock.patch.object(batching.SwitchQueue, "_get_raw_batches")
    def test_acquire_worker_lock_timeout(self, mock_get):
        mock_get.return_value = ["work"]
        lock = mock.MagicMock()
        lock.acquire.return_value = False
        self.client.lock.return_value = lock
        item = batching.SwitchQueueItem("uuid", 42)

        wait = tenacity.wait_none()
        self.assertRaises(
            tenacity.RetryError,
            self.queue.acquire_worker_lock,
            item, wait=wait, acquire_timeout=0.05)

    @mock.patch.object(batching.SwitchQueue, "_get_raw_batches")
    def test_acquire_worker_lock_no_work(self, mock_get):
        mock_get.side_effect = [["work"], None]
        lock = mock.MagicMock()
        lock.acquire.return_value = False
        self.client.lock.return_value = lock
        item = batching.SwitchQueueItem("uuid", 42)

        wait = tenacity.wait_none()
        result = self.queue.acquire_worker_lock(
            item, wait=wait, acquire_timeout=0.05)

        self.assertIsNone(result)
        self.assertEqual(2, mock_get.call_count)
        self.assertEqual(2, lock.acquire.call_count)

    @mock.patch.object(batching.SwitchQueue, "_get_raw_batches")
    def test_acquire_worker_lock_success(self, mock_get):
        mock_get.return_value = ["work"]
        lock = mock.MagicMock()
        lock.acquire.side_effect = [False, False, True]
        self.client.lock.return_value = lock
        item = batching.SwitchQueueItem("uuid", 42)

        wait = tenacity.wait_none()
        result = self.queue.acquire_worker_lock(
            item, wait=wait, acquire_timeout=0.05)

        self.assertEqual(lock, result)
        self.assertEqual(2, mock_get.call_count)
        self.assertEqual(3, lock.acquire.call_count)


class SwitchBatchTest(fixtures.TestWithFixtures):
    def setUp(self):
        super(SwitchBatchTest, self).setUp()
        self.cfg = self.useFixture(config_fixture.Config())

        self.queue = mock.Mock()
        self.switch_name = "switch1"
        self.batch = batching.SwitchBatch(
            self.switch_name, switch_queue=self.queue)

    @mock.patch.object(batching.SwitchBatch, "_spawn")
    def test_do_batch(self, mock_spawn):
        self.queue.add_batch.return_value = "item"
        self.queue.wait_for_result.return_value = "output"

        result = self.batch.do_batch("device", ["cmd1"])

        self.assertEqual("output", result)
        self.assertEqual(1, mock_spawn.call_count)
        self.queue.add_batch.assert_called_once_with(["cmd1"])
        self.queue.wait_for_result.assert_called_once_with("item", 300)

    def test_execute_pending_batches_skip(self):
        self.queue.get_batches.return_value = []

        result = self.batch._execute_pending_batches("device", "item")

        self.assertIsNone(result)

    def test_execute_pending_batches_skip2(self):
        self.queue.get_batches.return_value = ["work"]
        # Work was consumed by another worker before we could get the lock.
        self.queue.acquire_worker_lock.return_value = None

        result = self.batch._execute_pending_batches("device", "item")

        self.assertIsNone(result)

    @mock.patch.object(batching.SwitchBatch, "_send_commands")
    def test_execute_pending_batches_skip3(self, mock_send):
        self.queue.get_batches.side_effect = [["work"], None]
        # Work was consumed by another worker before we got the lock.
        lock = mock.MagicMock()
        self.queue.acquire_worker_lock.return_value = lock

        result = self.batch._execute_pending_batches("device", "item")

        self.assertIsNone(result)
        self.assertEqual(0, mock_send.call_count)

    @mock.patch.object(batching.SwitchBatch, "_send_commands")
    def test_execute_pending_batches_success(self, mock_send):
        batches = [
            {"cmds": ["cmd1", "cmd2"]},
            {"cmds": ["cmd3", "cmd4"]},
        ]
        self.queue.get_batches.return_value = batches
        device = mock.MagicMock()
        lock = mock.MagicMock()
        self.queue.acquire_worker_lock.return_value = lock

        self.batch._execute_pending_batches(device, "item")

        mock_send.assert_called_once_with(device, batches, lock)
        self.queue.acquire_worker_lock.assert_called_once_with("item")
        lock.release.assert_called_once_with()

    @mock.patch.object(batching.SwitchBatch, "_send_commands")
    def test_execute_pending_batches_failure(self, mock_send):
        batches = [
            {"cmds": ["cmd1", "cmd2"]},
            {"cmds": ["cmd3", "cmd4"]},
        ]
        self.queue.get_batches.return_value = batches
        device = mock.MagicMock()
        lock = mock.MagicMock()
        self.queue.acquire_worker_lock.return_value = lock
        mock_send.side_effect = exc.GenericSwitchBatchError

        self.assertRaises(exc.GenericSwitchBatchError,
                          self.batch._execute_pending_batches,
                          device, "item")

        lock.release.assert_called_once_with()

    def test_send_commands_one_batch(self):
        device = mock.MagicMock()
        device.send_config_set.return_value = "output"
        batches = [
            {"cmds": ["cmd1", "cmd2"]},
        ]
        lock = mock.MagicMock()

        self.batch._send_commands(device, batches, lock)

        connection = device._get_connection.return_value.__enter__.return_value
        device.send_config_set.assert_called_once_with(
            connection, ["cmd1", "cmd2"])
        lock.refresh.assert_called_once_with()
        lock.is_acquired.assert_called_once_with()
        self.queue.record_result.assert_called_once_with(
            {"cmds": ["cmd1", "cmd2"], "result": "output"})
        device.save_configuration.assert_called_once_with(connection)

    def test_send_commands_two_batches(self):
        device = mock.MagicMock()
        device.send_config_set.side_effect = ["output1", "output2"]
        batches = [
            {"cmds": ["cmd1", "cmd2"]},
            {"cmds": ["cmd3", "cmd4"]},
        ]
        lock = mock.MagicMock()

        self.batch._send_commands(device, batches, lock)

        connection = device._get_connection.return_value.__enter__.return_value
        self.assertEqual(2, device.send_config_set.call_count)
        device.send_config_set.assert_has_calls([
            mock.call(connection, ["cmd1", "cmd2"]),
            mock.call(connection, ["cmd3", "cmd4"])
        ])
        self.assertEqual(2, lock.refresh.call_count)
        self.assertEqual(2, lock.is_acquired.call_count)
        self.assertEqual(2, self.queue.record_result.call_count)
        self.queue.record_result.assert_has_calls([
            mock.call({"cmds": ["cmd1", "cmd2"], "result": "output1"}),
            mock.call({"cmds": ["cmd3", "cmd4"], "result": "output2"})
        ])
        device.save_configuration.assert_called_once_with(connection)
        self.assertEqual(1, device.save_configuration.call_count)

    def test_send_commands_failure(self):
        device = mock.MagicMock()
        device.send_config_set.side_effect = Exception("Bang")
        batches = [
            {"cmds": ["cmd1", "cmd2"]},
        ]
        lock = mock.MagicMock()

        self.batch._send_commands(device, batches, lock)

        connection = device._get_connection.return_value.__enter__.return_value
        device.send_config_set.assert_called_once_with(
            connection, ["cmd1", "cmd2"])
        lock.refresh.assert_called_once_with()
        lock.is_acquired.assert_called_once_with()
        self.queue.record_result.assert_called_once_with(
            {"cmds": ["cmd1", "cmd2"], "error": "Bang"})
        device.save_configuration.assert_called_once_with(connection)

    def test_send_commands_lock_timeout(self):
        device = mock.MagicMock()
        device.send_config_set.side_effect = Exception("Bang")
        batches = [
            {"cmds": ["cmd1", "cmd2"]},
        ]
        lock = mock.MagicMock()
        lock.is_acquired.return_value = False

        self.assertRaises(exc.GenericSwitchBatchError,
                          self.batch._send_commands, device, batches, lock)

        connection = device._get_connection.return_value.__enter__.return_value
        device.send_config_set.assert_called_once_with(
            connection, ["cmd1", "cmd2"])
        self.assertEqual(0, self.queue.record_result.call_count)
        self.assertEqual(0, device.save_configuration.call_count)
