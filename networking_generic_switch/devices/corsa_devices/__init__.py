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
        c_vlan = segmentation_id
        c_uplink_ports = self.config['uplink_ports']


        c_br_type = self.config['VFCType']
        cont_ip = self.config['defaultControllerIP']
        cont_port = self.config['defaultControllerPort']
        LOG.info("segmentation_id    " + str(segmentation_id)) 
        LOG.info("provisioning vlan  " + str(self.config['provisioningVLAN']))
        try:
            if self.config.has_key('provisioningVLAN'):
                if str(segmentation_id) == self.config['provisioningVLAN']:
                    LOG.info("Creating provisioning network on VLAN " + self.config['provisioningVLAN'] + " with controller " + self.config['provisioningControllerPort'] + ":" + self.config['provisioningControllerPort'])
                    c_br_type = self.config['provisioningVFCType']
                    cont_ip = self.config['provisioningControllerIP']
                    cont_port = self.config['provisioningControllerPort']
        except Exception as e:
            LOG.error("Failed to find provisioning network controller.  Using default controller")

        
        c_br = None
        try:
            with ngs_lock.PoolLock(self.locker, **self.lock_kwargs):
                c_br = corsavfc.get_free_bridge(headers, url_switch)
                cont_id = 'CONT' + str(c_br) 
                
                #Create the bridge
                corsavfc.bridge_create(headers, url_switch, c_br, br_subtype = c_br_type, br_resources = c_br_res, br_descr=c_br_descr)
                #Add the controller
                corsavfc.bridge_add_controller(headers, url_switch, br_id = c_br, cont_id = cont_id, cont_ip = cont_ip, cont_port = cont_port)
                
                LOG.info("About to get_ofport: c_br: " + str(c_br) + ", c_uplink_ports: " + str(c_uplink_ports))
                for uplink in c_uplink_ports.split(','):
                     #Attach the uplink tunnel
                     LOG.info("About to get_ofport: c_br: " + str(c_br) + ", uplink: " + str(uplink)) 
                     ofport=self.get_ofport(c_br,'P '+str(uplink))
                     LOG.info("ofport: " + str(ofport))
                     corsavfc.bridge_attach_tunnel_ctag_vlan(headers, url_switch, br_id = c_br, ofport = ofport, port = int(uplink), vlan_id = c_vlan)

        except Exception as e:
            LOG.error("Failed add network. attempting to cleanup bridge: " + str(e) + ", " + traceback.format_exc())
            try:
                output = corsavfc.bridge_delete(headers, url_switch, str(c_br))
            except Exception as e2:
                LOG.error(" Failed to cleanup bridge after failed add_network: " + str(segmentation_id) + ", bridge: " + str(bridge) + ", Error: " + str(e2))
            raise e

   
    def del_network(self, segmentation_id):
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
            
            output = corsavfc.bridge_delete(headers, url_switch, str(bridge))
        except Exception as e:
            LOG.error("failed delete bridge: " + traceback.format_exc())
            raise e
    
    # gets the unique ofport based on the bridge number and port number
    # Example: bridge=br3,port=P 32 -> ofport 332
    #          bridge=br33,port=P 2 -> ofport 3302 
    def get_ofport(self, bridge, port):
        ofport = bridge[2:]
        if int(port[2:]) < 10:
            ofport += '0'
        ofport += port[2:]
            
        return ofport


    def plug_port_to_network(self, port, segmentation_id):
        #OpenStack requires port ids to not be numbers
        #Corsa uses numbers
        #We are lying to OpenStack by adding a 'p ' to the beging of each port number.
        #We need to strip the 'p ' off of the port number.
        port_num=port[2:]
        
        token = self.config['token']
        headers = {'Authorization': token}

        logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.DEBUG)

        protocol = 'https://'
        sw_ip_addr = self.config['switchIP']
        url_switch = protocol + sw_ip_addr

        try:
          with ngs_lock.PoolLock(self.locker, **self.lock_kwargs):
            # Make sure the tunnel_mode is 'passthrough'    
            corsavfc.port_modify_tunnel_mode(headers, url_switch, port_num, 'passthrough') 

            # get the bridge from segmentation_id
            br_id = corsavfc.get_bridge_by_segmentation_id(headers, url_switch, segmentation_id)

            try:
                # unbind the port (probably not necessary)
                # openflow port was mapped to the physical port with the same port number in plug_port_to_network
                ofport = self.get_ofport(br_id,port)
                corsavfc. bridge_detach_tunnel(headers, url_switch, br_id, ofport)
                LOG.info("needed to delete_port: probably a leaked port from a node that did not completely boot the previous time. ")
            except Exception as e:
                LOG.info("Tried to delete_port but it was not there: this is expected." + traceback.format_exc())
                pass

            # bind the port
            # physical port is mapped to the openflow port with the same port number
            ofport = self.get_ofport(br_id,port)
            corsavfc.bridge_attach_tunnel_passthrough(headers, url_switch, br_id, port_num, ofport, tc = None, descr = None, shaped_rate = None)

        except Exception as e:
            LOG.error("Failed to plug to network: " + str(traceback.format_exc()))
            raise e
 
    def delete_port(self, port, segmentation_id):
        #OpenStack requires port ids to not be numbers       
        #Corsa uses numbers 
        #We are lying to OpenStack by adding a 'p ' to the beging of each port number.
        #We need to strip the 'p ' off of the port number.      
        port_num=port[2:]

        token = self.config['token']
        headers = {'Authorization': token}

        logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.DEBUG)

        protocol = 'https://'
        sw_ip_addr = self.config['switchIP']
        url_switch = protocol + sw_ip_addr

        try:
          with ngs_lock.PoolLock(self.locker, **self.lock_kwargs):
            # get the bridge from segmentation_id
            br_id = corsavfc.get_bridge_by_segmentation_id(headers, url_switch, segmentation_id)

            # unbind the port 
            # openflow port was mapped to the physical port with the same port number in plug_port_to_network
            ofport = self.get_ofport(br_id,port)
            corsavfc. bridge_detach_tunnel(headers, url_switch, br_id, ofport)
 
        except Exception as e:
            LOG.error("Failed delete_port: " + traceback.format_exc())
            raise e






