# Copyright 2017 Mirantis, Inc.
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

import fixtures
from oslo_config import fixture as config_fixture
import tenacity
from tooz import coordination

from networking_generic_switch import locking as ngs_lock


class PoolLockTest(fixtures.TestWithFixtures):

    def setUp(self):
        super(PoolLockTest, self).setUp()
        self.cfg = self.useFixture(config_fixture.Config())

    def test_lock_init(self):
        coord = mock.Mock()
        lock = ngs_lock.PoolLock(coord, locks_pool_size=3, locks_prefix='spam',
                                 timeout=120)

        self.assertEqual(coord, lock.coordinator)
        self.assertEqual(['spam0', 'spam1', 'spam2'], list(lock.lock_names))
        self.assertEqual(120, lock.timeout)

    def test_lock_contextmanager_no_coordinator(self):
        lock = ngs_lock.PoolLock(None)
        with lock as lk:
            self.assertFalse(lk.lock)

    @mock.patch.object(ngs_lock.tenacity, 'stop_after_delay',
                       return_value=tenacity.stop_after_delay(0.1))
    @mock.patch.object(ngs_lock.tenacity, 'wait_random',
                       return_value=tenacity.wait_fixed(0.01))
    def test_lock_contextmanager_with_coordinator(self, wait_mock, stop_mock):
        coord = mock.Mock()
        lock_mock = mock.Mock()
        coord.get_lock.return_value = lock_mock
        lock_mock.acquire.side_effect = [False, False, False, True]

        with ngs_lock.PoolLock(coord, locks_pool_size=2, timeout=1) as lk:
            self.assertEqual(coord, lk.coordinator)
            self.assertEqual(1, lk.timeout)
            self.assertEqual(4, lock_mock.acquire.call_count)
            self.assertEqual(lock_mock, lk.lock)

        lock_mock.release.assert_called_once_with()
        stop_mock.assert_called_once_with(1)

    @mock.patch.object(ngs_lock.tenacity, 'stop_after_delay',
                       return_value=tenacity.stop_after_delay(0.1))
    @mock.patch.object(ngs_lock.tenacity, 'wait_random',
                       return_value=tenacity.wait_fixed(0.01))
    @mock.patch.object(ngs_lock.LOG, 'error', autospec=True)
    def test_lock_contextmanager_fail(self, log_mock, wait_mock, stop_mock):
        coord = mock.Mock()
        lock_mock = mock.Mock()
        coord.get_lock.return_value = lock_mock
        lock_mock.acquire.side_effect = coordination.LockAcquireFailed('SPAM!')

        def test_call():
            with ngs_lock.PoolLock(coord, locks_pool_size=2, timeout=1):
                pass

        self.assertRaises(coordination.LockAcquireFailed, test_call)
        log_mock.assert_called_once_with(mock.ANY, exc_info=True)
        lock_mock.release.assert_not_called()
        stop_mock.assert_called_once_with(1)
