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

import atexit
import json

import etcd3gw
from etcd3gw import exceptions as etcd3gw_exc
from etcd3gw.utils import _decode
from etcd3gw.utils import _encode
from etcd3gw.utils import _increment_last_byte
import eventlet
from oslo_log import log as logging
from oslo_utils import netutils
from oslo_utils import uuidutils
import tenacity

from networking_generic_switch import exceptions as exc

SHUTDOWN_TIMEOUT = 60

LOG = logging.getLogger(__name__)

THREAD_POOL = eventlet.greenpool.GreenPool()


class ShutdownTimeout(Exception):
    """Exception raised when shutdown timeout is exceeded."""


@atexit.register
def _wait_for_threads():
    """Wait for all threads in the pool to complete.

    This function is registered to execute at exit, to ensure that all worker
    threads have completed. These threads may be holding switch execution locks
    and performing switch configuration operations which should not be
    interrupted.
    """
    LOG.info("Waiting %d seconds for %d threads to complete",
             SHUTDOWN_TIMEOUT, THREAD_POOL.running())
    try:
        with eventlet.Timeout(SHUTDOWN_TIMEOUT, ShutdownTimeout):
            THREAD_POOL.waitall()
    except ShutdownTimeout:
        LOG.error("Timed out waiting for threads to complete")
    else:
        LOG.info("Finished waiting for threads to complete")


class SwitchQueueItem(object):
    """An item in the queue."""

    def __init__(self, uuid, create_revision):
        self.uuid = uuid
        self.create_revision = create_revision


class SwitchQueue(object):
    INPUT_PREFIX = "/ngs/batch/%s/input/"
    INPUT_ITEM_KEY = "/ngs/batch/%s/input/%s"
    RESULT_ITEM_KEY = "/ngs/batch/%s/output/%s"
    EXEC_LOCK = "/ngs/batch/%s/execute_lock"

    def __init__(self, switch_name, etcd_client):
        self.switch_name = switch_name
        self.client = etcd_client
        self.lease_ttl = 600

    def add_batch(self, cmds):
        """Clients add batch, given key events.

        Each batch is given an uuid that is used to generate both
        and input and result key in etcd.

        First we watch for any results, second we write the input
        in a location that the caller of get_batches will be looking.

        No locks are required when calling this function to send work
        to the workers, and start waiting for results.

        :param cmds: an iterable of commands
        :return: a SwitchQueueItem object
        """

        uuid = uuidutils.generate_uuid()
        result_key = self.RESULT_ITEM_KEY % (self.switch_name, uuid)
        input_key = self.INPUT_ITEM_KEY % (self.switch_name, uuid)

        batch = {
            "uuid": uuid,
            "input_key": input_key,
            "result_key": result_key,
            "cmds": cmds,
        }
        value = json.dumps(batch, sort_keys=True).encode("utf-8")
        lease = self.client.lease(ttl=self.lease_ttl)
        # Use a transaction rather than create() in order to extract the
        # create revision.
        base64_key = _encode(input_key)
        base64_value = _encode(value)
        txn = {
            'compare': [{
                'key': base64_key,
                'result': 'EQUAL',
                'target': 'CREATE',
                'create_revision': 0
            }],
            'success': [{
                'request_put': {
                    'key': base64_key,
                    'value': base64_value,
                }
            }],
            'failure': []
        }
        txn['success'][0]['request_put']['lease'] = lease.id
        result = self.client.transaction(txn)

        success = result.get('succeeded', False)
        # Be sure to free watcher resources on error
        if not success:
            raise exc.GenericSwitchBatchError(
                device=self.switch_name,
                error="Failed to add batch to input key: %s" % input_key)

        put_response = result['responses'][0]['response_put']
        create_revision = put_response['header']['revision']
        LOG.debug("written input key %s revision %s",
                  input_key, create_revision)

        return SwitchQueueItem(uuid, create_revision)

    def wait_for_result(self, item, timeout):
        """Wait for the result of a command batch.

        :param item: SwitchQueueItem object returned by add_batch
        :param timeout: wait timeout in seconds
        :return: output string generated by this command set
        :raises: Exception if waiting times out or the command batch was
            unsuccessful
        """
        result_key = self.RESULT_ITEM_KEY % (self.switch_name, item.uuid)
        try:
            event = self.client.watch_once(result_key, timeout=timeout,
                                           start_revision=item.create_revision)
        except etcd3gw_exc.WatchTimedOut:
            raise exc.GenericSwitchBatchError(
                device=self.switch_name,
                error="Timed out waiting for result key: %s" % result_key)

        LOG.debug("got event: %s", event)
        if event["kv"]["version"] == 0:
            raise exc.GenericSwitchBatchError(
                device=self.switch_name,
                error="Output key was deleted, perhaps lease expired")
        # TODO(johngarbutt) check we have the create event and result?
        result_dict = self._get_and_delete_result(result_key)
        LOG.debug("got result: %s", result_dict)
        if "result" in result_dict:
            return result_dict["result"]
        else:
            raise exc.GenericSwitchBatchError(
                device=self.switch_name,
                error=result_dict["error"])

    def _get_and_delete_result(self, result_key):
        # called when watch event says the result key should exist
        txn = {
            'compare': [],
            'success': [{
                'request_delete_range': {
                    'key': _encode(result_key),
                    'prev_kv': True,
                }
            }],
            'failure': []
        }
        result = self.client.transaction(txn)
        success = result.get('succeeded', False)
        if not success:
            raise exc.GenericSwitchBatchError(
                device=self.switch_name,
                error="Unable to find result: %s" % result_key)
        delete_response = result['responses'][0]['response_delete_range']
        raw_value = delete_response['prev_kvs'][0]['value']
        result_dict = json.loads(_decode(raw_value))
        LOG.debug("fetched and deleted result for: %s", result_key)
        return result_dict

    def _get_raw_batches(self, max_create_revision=None):
        input_prefix = self.INPUT_PREFIX % self.switch_name
        # Sort order ensures FIFO style queue
        # Use get rather than get_prefix since get accepts max_create_revision.
        range_end = _encode(_increment_last_byte(input_prefix))
        raw_batches = self.client.get(input_prefix,
                                      metadata=True,
                                      range_end=range_end,
                                      sort_order="ascend",
                                      sort_target="create",
                                      max_create_revision=max_create_revision)
        return raw_batches

    def get_batches(self, item=None):
        """Return a list of the event dicts written in wait for result.

        This is called both with or without getting a lock to get the
        latest list of work that has send to the per switch queue in
        etcd.

        :param item: Optional SwitchQueueItem object. If provided, only batches
            added up to and including this item are returned.
        """
        max_create_revision = item.create_revision if item else None
        raw_batches = self._get_raw_batches(max_create_revision)
        LOG.debug("found %s batches", len(raw_batches))

        batches = []
        for raw_value, metadata in raw_batches:
            batch = json.loads(raw_value.decode('utf-8'))
            batches.append(batch)
        return batches

    def record_result(self, batch):
        """Record the result from executing given command set.

        We assume that a lock is held before getting a fresh list
        of batches, executing them, and then calling this record
        results function, before finally dropping the lock.
        """
        # Write results and delete input keys so the next worker to hold the
        # lock knows not to execute these batches
        lease = self.client.lease(ttl=self.lease_ttl)
        result_value = json.dumps(batch, sort_keys=True).encode('utf-8')
        txn = {
            'compare': [],
            'success': [
                {
                    'request_put': {
                        'key': _encode(batch['result_key']),
                        'value': _encode(result_value),
                        'lease': lease.id,
                    }
                },
                {
                    'request_delete_range': {
                        'key': _encode(batch['input_key']),
                    }
                }
            ],
            'failure': []
        }
        result = self.client.transaction(txn)
        success = result.get('succeeded', False)
        if not success:
            LOG.error("failed to report batch result for: %s",
                      batch)
        else:
            LOG.debug("written result key: %s", batch['result_key'])

    def acquire_worker_lock(self, item, acquire_timeout=300, lock_ttl=120,
                            wait=None):
        """Wait for lock needed to call record_result.

        This blocks until the work queue is empty of the switch lock is
        acquired. If we timeout waiting for the lock we raise an exception.
        """
        lock_name = self.EXEC_LOCK % self.switch_name
        lock = self.client.lock(lock_name, lock_ttl)

        if wait is None:
            wait = tenacity.wait_random(min=1, max=3)

        @tenacity.retry(
            # Log a message after each failed attempt.
            after=tenacity.after_log(LOG, logging.DEBUG),
            # Retry if we haven't got the lock yet
            retry=tenacity.retry_if_result(lambda x: x is False),
            # Stop after timeout.
            stop=tenacity.stop_after_delay(acquire_timeout),
            # Wait between lock retries
            wait=wait,
        )
        def _acquire_lock_with_retry():
            lock_acquired = lock.acquire()
            if lock_acquired:
                return lock

            # Stop waiting for the lock if there is nothing to do
            work = self._get_raw_batches(item.create_revision)
            if not work:
                return None

            # Trigger a retry
            return False

        return _acquire_lock_with_retry()


class SwitchBatch(object):
    def __init__(self, switch_name, etcd_url=None, switch_queue=None):
        if switch_queue is None:
            parsed_url = netutils.urlsplit(etcd_url)
            host = parsed_url.hostname
            port = parsed_url.port
            protocol = 'https' if parsed_url.scheme.endswith(
                'https') else 'http'
            # Use the same parameter format as tooz etcd3gw driver.
            params = parsed_url.params()
            ca_cert = params.get('ca_cert')
            cert_key = params.get('cert_key')
            cert_cert = params.get('cert_cert')
            api_version = params.get('api_version', 'v3alpha')
            etcd_client = etcd3gw.client(
                host=host, port=port, protocol=protocol,
                ca_cert=ca_cert, cert_key=cert_key, cert_cert=cert_cert,
                api_path='/' + api_version + '/',
                timeout=30)
            self.queue = SwitchQueue(switch_name, etcd_client)
        else:
            self.queue = switch_queue
        self.switch_name = switch_name

    def do_batch(self, device, cmd_set, timeout=300):
        """Batch up switch configuration commands to reduce overheads.

        We collect together the iterables in the cmd_set, and
        execute them toegether in a single larger batch.

        :param device: a NetmikoSwitch device object
        :param cmd_set: an iterable of commands
        :return: output string generated by this command set
        """

        # request that the cmd_set by executed
        cmd_list = list(cmd_set)
        item = self.queue.add_batch(cmd_list)

        def do_work():
            try:
                self._execute_pending_batches(device, item)
            except Exception as e:
                LOG.error("failed to run execute batch: %s", e,
                          exec_info=True)
                raise

        self._spawn(do_work)

        # Wait for our result key
        # as the result might be done before the above task starts
        output = self.queue.wait_for_result(item, timeout)
        LOG.debug("Got batch result: %s", output)
        return output

    @staticmethod
    def _spawn(work_fn):
        # TODO(johngarbutt) remove hard eventlet dependency
        #  in a similar way to etcd3gw
        # Sleep to let possible other work to batch together
        eventlet.sleep(0)
        # Run all pending tasks, which might be a no op
        # if pending tasks already ran
        THREAD_POOL.spawn_n(work_fn)

    def _execute_pending_batches(self, device, item):
        """Execute all batches currently registered.

        Typically called by every caller of add_batch.
        Could be a noop if all batches are already executed.

        :param device: a NetmikoSwitch device object
        :param item: a SwitchQueueItem object
        """
        batches = self.queue.get_batches(item)
        if not batches:
            LOG.debug("Skipped execution for %s", self.switch_name)
            return
        LOG.debug("Found %d batches - trying to acquire lock for %s",
                  len(batches), self.switch_name)

        # Many workers can end up piling up here trying to acquire the
        # lock. Only consider batches at least as old as the one that triggered
        # this worker, to ensure they don't wait forever.
        lock = self.queue.acquire_worker_lock(item)
        if lock is None:
            # This means we stopped waiting as the work queue was empty
            LOG.debug("Work list empty for %s", self.switch_name)
            return

        # Check we got the lock
        if not lock.is_acquired():
            raise exc.GenericSwitchBatchError(
                device=self.switch_name,
                error="unable to get lock for: %s" % self.switch_name)

        # be sure to drop the lock when we are done
        try:
            LOG.debug("got lock for %s", self.switch_name)

            # Fetch fresh list now we have the lock
            # and order the list so we execute in order added
            batches = self.queue.get_batches()
            if not batches:
                LOG.debug("No batches to execute %s", self.switch_name)
                return

            LOG.debug("Starting to execute %d batches", len(batches))
            self._send_commands(device, batches, lock)
        finally:
            lock.release()

        LOG.debug("end of lock for %s", self.switch_name)

    def _send_commands(self, device, batches, lock):
        with device._get_connection() as net_connect:
            for batch in batches:
                try:
                    output = device.send_config_set(net_connect, batch['cmds'])
                    batch["result"] = output
                except Exception as e:
                    batch["error"] = str(e)

                # The switch configuration can take a long time, and may exceed
                # the lock TTL. Periodically refresh our lease, and verify that
                # we still own the lock before recording the results.
                lock.refresh()
                if not lock.is_acquired():
                    raise exc.GenericSwitchBatchError(
                        device=self.switch_name,
                        error="Worker aborting - lock timed out")

                # Tell request watchers the result and
                # tell workers which batches have now been executed
                self.queue.record_result(batch)

            if device._get_save_configuration():
                try:
                    device.save_configuration(net_connect)
                except Exception:
                    LOG.exception("Failed to save configuration")
                    # Probably not worth failing all batches for this.
