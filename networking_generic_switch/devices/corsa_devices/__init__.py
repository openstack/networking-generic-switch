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

import traceback

import atexit
import contextlib
import uuid

from oslo_config import cfg
from oslo_log import log as logging
import paramiko
import tenacity
from tooz import coordination

from networking_generic_switch import devices
from networking_generic_switch import exceptions as exc
from networking_generic_switch import locking as ngs_lock

import logging
import corsavfc
import requests
import json
import sys

import time

LOG = logging.getLogger(__name__)
CONF = cfg.CONF


class CorsaSwitch(devices.GenericSwitchDevice):

    ADD_NETWORK = None

    DELETE_NETWORK = None

    PLUG_PORT_TO_NETWORK = None

    DELETE_PORT = None

    SAVE_CONFIGURATION = None

    def __init__(self, device_cfg):
        super(CorsaSwitch, self).__init__(device_cfg)
        device_type = self.config.get('device_type', '')
        # use part that is after 'netmiko_'
        device_type = device_type.partition('corsa_')[2]
        #if device_type not in netmiko.platforms:
        #    raise exc.GenericSwitchNetmikoNotSupported(
        #        device_type=device_type)
        self.config['device_type'] = device_type

        LOG.info("PRUTH: CONF: " + str(CONF))
        LOG.info("PRUTH: CONF.ngs_coordination.backend_url: " + str(CONF.ngs_coordination.backend_url))
        LOG.info("PRUTH: CONF.host: " + str(CONF.host))
        LOG.info("PRUTH: CONF.ngs_coordination.acquire_timeout: " + str(CONF.ngs_coordination.acquire_timeout))
        LOG.info("PRUTH: CONF self.ngs_config['ngs_max_connections']:" + str(self.ngs_config['ngs_max_connections']))

        self.locker = None
        if CONF.ngs_coordination.backend_url:
            self.locker = coordination.get_coordinator(
                CONF.ngs_coordination.backend_url,
                ('ngs-' + CONF.host).encode('ascii'))
            self.locker.start()
            atexit.register(self.locker.stop)

        self.lock_kwargs = {
            'locks_pool_size': int(self.ngs_config['ngs_max_connections']),
            'locks_prefix': self.config.get(
                'host', '') or self.config.get('ip', ''),
            'timeout': CONF.ngs_coordination.acquire_timeout}
        
        #self.locker = coordination.get_coordinator(
        #        'file:///var/lib/neutron/lock','ngs-host1')
        #self.locker.start()
        #atexit.register(self.locker.stop)
        #
        #self.lock_kwargs = {
        #    'locks_pool_size': 1,
        #    'locks_prefix': self.config.get(
        #        'host', '') or self.config.get('ip', ''),
        #    'timeout': CONF.ngs_coordination.acquire_timeout}





    def _format_commands(self, commands, **kwargs):
        if not commands:
            return
        if not all(kwargs.values()):
            raise exc.GenericSwitchNetmikoMethodError(cmds=commands,
                                                      args=kwargs)
        try:
            cmd_set = [cmd.format(**kwargs) for cmd in commands]
        except (KeyError, TypeError):
            raise exc.GenericSwitchNetmikoMethodError(cmds=commands,
                                                      args=kwargs)
        return cmd_set

    @contextlib.contextmanager
    def _get_connection(self):
        """Context manager providing a netmiko SSH connection object.

        This function hides the complexities of gracefully handling retrying
        failed connection attempts.
        """
        retry_exc_types = (paramiko.SSHException, EOFError)

        # Use tenacity to handle retrying.
        @tenacity.retry(
            # Log a message after each failed attempt.
            after=tenacity.after_log(LOG, logging.DEBUG),
            # Reraise exceptions if our final attempt fails.
            reraise=True,
            # Retry on SSH connection errors.
            retry=tenacity.retry_if_exception_type(retry_exc_types),
            # Stop after the configured timeout.
            stop=tenacity.stop_after_delay(
                int(self.ngs_config['ngs_ssh_connect_timeout'])),
            # Wait for the configured interval between attempts.
            wait=tenacity.wait_fixed(
                int(self.ngs_config['ngs_ssh_connect_interval'])),
        )
        def _create_connection():
            return netmiko.ConnectHandler(**self.config)

        # First, create a connection.
        try:
            net_connect = _create_connection()
        except tenacity.RetryError as e:
            LOG.error("Reached maximum SSH connection attempts, not retrying")
            raise exc.GenericSwitchNetmikoConnectError(
                config=self.config, error=e)
        except Exception as e:
            LOG.error("Unexpected exception during SSH connection")
            raise exc.GenericSwitchNetmikoConnectError(
                config=self.config, error=e)

        # Now yield the connection to the caller.
        with net_connect:
            yield net_connect

    def send_commands_to_device(self, cmd_set):
        if not cmd_set:
            LOG.debug("Nothing to execute")
            return

        try:
            with ngs_lock.PoolLock(self.locker, **self.lock_kwargs):
                with self._get_connection() as net_connect:
                    net_connect.enable()
                    output = net_connect.send_config_set(
                        config_commands=cmd_set)
                    # NOTE (vsaienko) always save configuration
                    # when configuration is applied successfully.
                    if self.SAVE_CONFIGURATION:
                        net_connect.send_command(self.SAVE_CONFIGURATION)
        except Exception as e:
            raise exc.GenericSwitchNetmikoConnectError(config=self.config,
                                                       error=e)

        LOG.debug(output)
        return output

    def add_network(self, segmentation_id, network_id):
        token = self.config['token']
        headers = {'Authorization': token}
                
        logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.DEBUG)
                
        protocol = 'https://'
        sw_ip_addr = self.config['switchIP']
        url_switch = protocol + sw_ip_addr
                
        #./create-vfc.py br1 5 openflow VFC-1 192.168.201.164 6653 100-105
        c_br_res =  self.config['dafaultVFCRes']
        c_br_type = self.config['VFCType']
        c_br_descr = "VLAN-" + str(segmentation_id)
        cont_ip = self.config['defaultControllerIP']
        cont_port = self.config['defaultControllerPort']
        c_vlan = segmentation_id
        c_uplink_port = int(self.config['uplink_port'])

        c_br = None

        try:
            with ngs_lock.PoolLock(self.locker, **self.lock_kwargs):
                c_br = corsavfc.get_free_bridge(headers, url_switch)
                cont_id = 'CONT' + str(c_br) 
                
                LOG.info(" --- Create Bridge: " + str(c_br))
                output = corsavfc.bridge_create(headers, url_switch, c_br, br_subtype = c_br_type, br_resources = c_br_res, br_descr=c_br_descr)
                if output.status_code == 201:
                    LOG.info(" Create Bridge: " + str(output.status_code) + " Success")
                else:
                    if output.status_code == 400:
                        raise Exception(" Create Bridge Failed: " + str(output.status_code) + " Bad Request")
                    elif output.status_code == 403:
                        raise Exception(" Create Bridge Failed: " + str(output.status_code) + " Forbidden")
                    elif output.status_code == 409:
                        raise Exception(" Create Bridge Failed: " + str(output.status_code) + " Conflict")
                    else:
                        raise Exception(" Create Bridge Failed: " + str(output.status_code) + " Unknown Error")
                  
                LOG.info(" --- Add Controller: " + str(cont_ip) + ":" + str(cont_port))
                output = corsavfc.bridge_add_controller(headers, url_switch, br_id = c_br, cont_id = cont_id, cont_ip = cont_ip, cont_port = cont_port)
                if output.status_code == 201:
                    LOG.info(" Add Controller: " + str(output.status_code) + " Success")
                else:
                    if output.status_code == 400:
                        raise Exception(" Add Controller Failed: " + str(output.status_code) + " Bad Request")
                    elif output.status_code == 403:
                        raise Exception(" Add Controller Failed: " + str(output.status_code) + " Forbidden")
                    elif output.status_code == 404:
                        raise Exception(" Add Controller Failed: " + str(output.status_code) + " Not Found")
                    elif output.status_code == 409:
                        raise Exception(" Add Controller Failed: " + str(output.status_code) + " Conflict")
                    else:
                        raise Exception(" Add Controller Failed: " + str(output.status_code) + " Unknown Error")
                
                LOG.info(" --- Attach Tunnel: uplink_port: " + str(c_uplink_port))
                output = corsavfc.bridge_attach_tunnel_ctag_vlan(headers, url_switch, br_id = c_br, ofport = c_uplink_port, port = c_uplink_port, vlan_id = c_vlan)
                if output.status_code == 201:
                    LOG.info(" Attach Tunnel: " + str(output.status_code) + " Success")
                else:
                    if output.status_code == 400:
                        raise Exception(" Attach Tunnel Failed: " + str(output.status_code) + " Bad Request")
                    elif output.status_code == 403:
                        raise Exception(" Attach Tunnel Failed: " + str(output.status_code) + " Forbidden")
                    elif output.status_code == 404:
                        raise Exception(" Attach Tunnel Failed: " + str(output.status_code) + " Not Found")
                    else:
                        raise Exception(" Attach Tunnel Failed: " + str(output.status_code) + " Unknown Error")

        except Exception as e:
            LOG.error("Corsa add_network EXCEPTION: " + str(e) + ", " + traceback.format_exc())
            LOG.error(" --- Cleaning Bridge after Failed Creation: " + str(segmentation_id) + ", bridge: " + str(c_br))
            output = corsavfc.bridge_delete(headers, url_switch, str(c_br))
            if output.status_code == 204:
                LOG.error(" Cleanup: " + str(output.status_code) + " Success")
            elif output.status_code == 403:
                LOG.error(" Cleanup Failed: " + str(output.status_code) + " Forbidden")
            elif output.status_code == 404:
                LOG.error(" Cleanup Failed: " + str(output.status_code) + " Not Found (Possibly because cleaning was not needed)")
            else:
                LOG.error(" Cleanup Failed: " + str(output.status_code) + " Unknown Error")

            raise e

   
    def del_network(self, segmentation_id):
        LOG.info("PRUTH: del_network(self, segmentation_id): " + str(segmentation_id))
        LOG.info("PRUTH: del_network(): self.config " + str(self.config))
        
        token = self.config['token']
        headers = {'Authorization': token}
            
        logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.DEBUG)

        protocol = 'https://'
        sw_ip_addr = self.config['switchIP']
        url_switch = protocol + sw_ip_addr

        bridge = None
        try:    
          with ngs_lock.PoolLock(self.locker, **self.lock_kwargs):
            bridge = corsavfc.get_bridge_by_segmentation_id(headers, url_switch, str(segmentation_id))
            
            LOG.info(" --- Delete Bridge: " + str(segmentation_id) + ", bridge: " + str(bridge))
            output = corsavfc.bridge_delete(headers, url_switch, str(bridge))
            if output.status_code == 204:
                LOG.info(" Delete Bridge: " + str(output.status_code) + " Success")
            else:
                if output.status_code == 400:
                    raise Exception(" Delete Bridge Failed: " + str(output.status_code) + " Bad Request")
                elif output.status_code == 403:
                    raise Exception(" Delete Bridge Failed: " + str(output.status_code) + " Forbidden")
                elif output.status_code == 404:
                    raise Exception(" Delete Bridge Failed: " + str(output.status_code) + " Not Found")
                else:
                    raise Exception(" Delete Bridge Failed: " + str(output.status_code) + " Unknown Error")            

        except Exception as e:
            LOG.error("Corsa del_network EXCEPTION: " + traceback.format_exc())
            LOG.error(" --- Cleaning Bridge after Failed Deletion: " + str(segmentation_id) + ", bridge: " + str(bridge))
            output = corsavfc.bridge_delete(headers, url_switch, str(bridge))
            
            if output.status_code == 204:
                LOG.error(" Cleanup: " + str(output.status_code) + " Success")
            elif output.status_code == 403:
                LOG.error(" Cleanup Failed: " + str(output.status_code) + " Forbidden")
            elif output.status_code == 404:
                LOG.error(" Cleanup Failed: " + str(output.status_code) + " Not Found (Possibly because cleaning was not needed)")
            else:
                LOG.error(" Cleanup Failed: " + str(output.status_code) + " Unknown Error")

            raise e
    


    def plug_port_to_network(self, port, segmentation_id):
        
        LOG.info("PRUTH: plug_port_to_network(self, port, segmentation_id):  port: " +  str(port) + ", segmentation_id: " + str(segmentation_id))

        #strip the 'p' off of the port number
        port_num=port[2:]
        
        LOG.info("PRUTH: plug_port_to_network(self, port, segmentation_id): port_num: " + str(port_num))

        token = self.config['token']
        headers = {'Authorization': token}

        logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.DEBUG)

        protocol = 'https://'
        sw_ip_addr = self.config['switchIP']
        url_switch = protocol + sw_ip_addr

        try:
          with ngs_lock.PoolLock(self.locker, **self.lock_kwargs):
            #Make sure the tunnel_mode is 'passthrough'    
            LOG.info(" --- Set port tunnel mode to passthrough: port: " + str(port) + ", segmentation_id: " +  str(segmentation_id))
            output = corsavfc.port_modify_tunnel_mode(headers, url_switch, port_num, 'passthrough') 

            #get the bridge from segmentation_id
            br_id = corsavfc.get_bridge_by_segmentation_id(headers, url_switch, segmentation_id)

            #bind the port
            LOG.info(" --- Attach the port to bridge: " + str(port) + ", segmentation_id: " +  str(segmentation_id))
            output = corsavfc.bridge_attach_tunnel_passthrough(headers, url_switch, br_id, port, ofport = None, tc = None, descr = None, shaped_rate = None)

        except Exception as e:
            LOG.error("Corsa plug_port_to_network EXCEPTION: " + str(traceback.format_exc()))
            raise e
 
    def delete_port(self, port, segmentation_id):
        LOG.info("PRUTH: delete_port(self, port, segmentation_id):  port: " +  str(port) + ", segmentation_id: " + str(segmentation_id))

        #strip the 'p' off of the port number
        port_num=port[2:]

        LOG.info("PRUTH: plug_port_to_network(self, port, segmentation_id): port_num: " + str(port_num))

        token = self.config['token']
        headers = {'Authorization': token}

        logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.DEBUG)

        protocol = 'https://'
        sw_ip_addr = self.config['switchIP']
        url_switch = protocol + sw_ip_addr

        try:
          with ngs_lock.PoolLock(self.locker, **self.lock_kwargs):
            #get the bridge from segmentation_id
            br_id = corsavfc.get_bridge_by_segmentation_id(headers, url_switch, segmentation_id)

            #unbind the port 
            LOG.info(" --- Detach port from bridge: " + str(port) + ", segmentation_id: " +  str(segmentation_id))
            output = bridge_detach_tunnel_passthrough(headers, url_switch, br_id, port_num)

        except Exception as e:
            LOG.error("Corsa delete_port EXCEPTION: " + traceback.format_exc())
            raise e






