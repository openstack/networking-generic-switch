#!/usr/bin/env python 

from oslo_log import log as logging
import requests
import json

LOG = logging.getLogger(__name__)

#
# ENDPOINTS
#
endpoint = '/api/v1'
ep_datapath = endpoint + '/datapath'    # Datapath
ep_bridges = endpoint + '/bridges'      # Bridge
ep_stats = endpoint + '/stats'          # Stats
ep_users = endpoint + '/users'          # Users
ep_system = endpoint + '/system'        # System
ep_equipment = endpoint + '/equipment'  # Equipment
ep_tunnels = endpoint + '/tunnels'      # Tunnels
ep_qp = endpoint + '/queue-profiles'    # Queue-profiles        
ep_ports = endpoint + '/ports'          # Ports
ep_containers = endpoint + '/containers'# Containers
ep_netns = endpoint + '/netns'



#
# PORT MODIFY
#
#   204 No content
#   400 Bad Request
#   403 Forbidden
#   404 Not Found
#   409 Conflict 


def port_modify_tunnel_mode(headers, url_switch , port_number, tunnel_mode):
    url = url_switch + ep_ports + '/' + str(port_number)
    data = [
              { "op": "replace", "path": "/tunnel-mode", "value": tunnel_mode },
           ]
    try:
        r = requests.patch(url, data=json.dumps(data), headers=headers, verify=False)
    except Exception as e:
        raise e
    return r
 
  
def port_modify_mtu(headers, url_switch , port_number, mtu):
    url = url_switch + ep_ports + '/' + str(port_number)
    data = [
              { "op": "replace", "path": "/mtu", "value": mtu },
           ]
    try:
        r = requests.patch(url, data=json.dumps(data), headers=headers, verify=False)
    except Exception as e:
        raise e
    return r


def port_modify_descr(headers, url_switch , port_number, descr):
    url = url_switch + ep_ports + '/' + str(port_number)
    data = [
              { "op": "replace", "path": "/ifdescr", "value": descr },
           ]
    try:
        r = requests.patch(url, data=json.dumps(data), headers=headers, verify=False)
    except Exception as e:
        raise e
    return r


def port_modify_bandwidth(headers, url_switch , port_number, bandwidth):
    url = url_switch + ep_ports + '/' + str(port_number)
    data = [
              { "op": "replace", "path": "/bandwidth", "value": bandwidth },
           ]
    try:
        r = requests.patch(url, data=json.dumps(data), headers=headers, verify=False)
    except Exception as e:
        raise e
    return r


def port_modify_admin_state(headers, url_switch , port_number, admin_state):
    url = url_switch + ep_ports + '/' + str(port_number)
    data = [
              { "op": "replace", "path": "/admin-state", "value": admin_state },
           ]
    try:
        r = requests.patch(url, data=json.dumps(data), headers=headers, verify=False)
    except Exception as e:
        raise e
    return r


#
# BRIDGE CREATE
#
#   201 Created
#   400 Bad Request
#   403 Forbidden
#   409 Conflict

def bridge_create(headers, 
                  url_switch, 
                  br_id, 
                  br_dpid = None, 
                  br_subtype = None, 
                  br_resources = None, 
                  br_traffic_class = None, 
                  br_netns = None, 
                  br_descr = None): 
    url = url_switch + ep_bridges
    data = {
             'bridge':br_id,
             'subtype':br_subtype,
             'resources': br_resources,
             'dpid': br_dpid,
             'traffic-class': br_traffic_class,
             'netns': br_netns,
             'bridge-descr': br_descr
           }

    try:
        output = requests.post(url ,data=data, headers=headers, verify=False)
        print output.json()

        if output.status_code == 201:
            LOG.info(" Create Bridge: " + "url: " + str(url) + ", " + str(output.status_code) + " Success")
        else:
            if output.status_code == 400:
                raise Exception(" Create Bridge Failed: " + "url: " + str(url) + ", " + str(output.status_code) + " Bad Request")
            elif output.status_code == 403:
                raise Exception(" Create Bridge Failed: " + "url: " + str(url) + ", " + str(output.status_code) + " Forbidden")
            elif output.status_code == 409:
                raise Exception(" Create Bridge Failed: " + "url: " + str(url) + ", " + str(output.status_code) + " Conflict")
            else:
                raise Exception(" Create Bridge Failed: " + "url: " + str(url) + ", " + str(output.status_code) + " Unknown Error")


    except Exception as e:
        raise e
    return output


#
# BRIDGE DELETE
#
#   200 OK   PRUTH: I think its actually 204
#   403 Forbidden
#   404 Not found

def bridge_delete(headers,
                  url_switch,
                  br_id):
    url = url_switch + ep_bridges + '/' +  br_id 

    try:
        output = requests.delete(url, headers=headers, verify=False)

        if output.status_code == 204:
            LOG.info(" Delete Bridge: " + "url: " + str(url) + ", " + str(output.status_code) + " Success")
        else:
            if output.status_code == 403:
                raise Exception(" Delete Bridge Failed: " + "url: " + str(url) + ", " + str(output.status_code) + " Forbidden")
            elif output.status_code == 404:
                raise Exception(" Delete Bridge Failed: " + "url: " + str(url) + ", " + str(output.status_code) + " Not Found")
            else:
                raise Exception(" Delete Bridge Failed: " + "url: " + str(url) + ", " + str(output.status_code) + " Unknown Error")

    except Exception as e:
        raise e
    return output


#
# ADD CONTROLLER
#
#   201 Created
#   400 Bad Request
#   403 Forbidden
#   404 Not Found
#   409 Conflict

def bridge_add_controller(headers,
                         url_switch,
                         br_id, 
                         cont_id,
                         cont_ip,
                         cont_port, 
                         cont_tls = False):
    url = url_switch + ep_bridges + '/' + br_id + '/controllers'
    data = {
             'controller':cont_id,
             'ip':cont_ip,
             'port': cont_port,
             'tls': cont_tls
           }

    try:
        output = requests.post(url ,data=data, headers=headers, verify=False)

        if output.status_code == 201:
            LOG.info(" Add Controller: url: " + str(url)  + ", " + str(output.status_code) + " Success")
        else:
            if output.status_code == 400:
                raise Exception(" Add Controller Failed:  url: " + str(url)  + ", "  + str(output.status_code) + " Bad Request")
            elif output.status_code == 403:
                raise Exception(" Add Controller Failed:  url: " + str(url)  + ", "  + str(output.status_code) + " Forbidden")
            elif output.status_code == 404:
                raise Exception(" Add Controller Failed:  url: " + str(url)  + ", "  + str(output.status_code) + " Not Found")
            else:
                raise Exception(" Add Controller Failed:  url: " + str(url)  + ", "  + str(output.status_code) + " Unknown Error")

    except Exception as e:
        raise e
    return output


#
# DETACH CONTROLLER
#
#   204 No Content
#   403 Forbidden
#   404 Not Found

def bridge_detach_controller(headers,
                             url_switch,
                             br_id,
                             cont_id):
    url = url_switch + ep_bridges + '/' +  br_id + '/controllers' + '/' + cont_id

    try:
        output = requests.delete(url, headers=headers, verify=False)
        if output.status_code == 204:
            LOG.info(" Add Controller: " + "url: " + str(url) + ", " + str(output.status_code) + " Success")
        else:
            if output.status_code == 400:
                raise Exception(" Add Controller Failed: " + "url: " + str(url) + ", " + str(output.status_code) + " Bad Request")
            elif output.status_code == 403:
                raise Exception(" Add Controller Failed: " + "url: " + str(url) + ", " + str(output.status_code) + " Forbidden")
            elif output.status_code == 404:
                raise Exception(" Add Controller Failed: " + "url: " + str(url) + ", " + str(output.status_code) + " Not Found")
            elif output.status_code == 409:
                raise Exception(" Add Controller Failed: " + "url: " + str(url) + ", " + str(output.status_code) + " Conflict")
            else:
                raise Exception(" Add Controller Failed: " + "url: " + str(url) + ", " + str(output.status_code) + " Unknown Error")

    except Exception as e:
        raise e
    return r


#
# ATTACH TUNNEL - VLAN ID
#
#   201 Created
#   400 Bad Request
#   403 Forbidden
#   404 Not Found

def bridge_attach_tunnel_ctag_vlan(headers,
                                   url_switch,
                                   br_id, 
                                   ofport,
                                   port,
                                   vlan_id,
                                   tc = None,
                                   descr = None,
                                   shaped_rate = None):
    url = url_switch + ep_bridges + '/' +  br_id + '/tunnels'
    data = {
             'ofport': ofport,
             'port': port,
             'vlan-id': vlan_id,
             'traffic-class': tc,
             'ifdescr': descr,
             'shaped-rate': shaped_rate,
           }

    try:
        output = requests.post(url ,data=data, headers=headers, verify=False)
        print output.json()

        if output.status_code == 201:
                LOG.info(" Attach ctag vlan port to bridge: " + "url: " + str(url) + ", " + str(output.status_code) + " Success")
        else:
            if output.status_code == 400:
                raise Exception(" Attach ctag vlan port to bridge Failed: " + "url: " + str(url) + ", " + str(output.status_code) + " Bad Request")
            elif output.status_code == 403:
                raise Exception(" Attach ctag vlan port to bridge Failed: " + "url: " + str(url) + ", " + str(output.status_code) + " Forbidden")
            elif output.status_code == 404:
                raise Exception(" Attach ctag vlan port to bridge Failed: " + "url: " + str(url) + ", " + str(output.status_code) + " Not Found")
            else:
                raise Exception(" Attach ctag vlan port to bridge Failed: " + "url: " + str(url) + ", " + str(output.status_code) + " Unknown Error")

    except Exception as e:
        raise e
    return output


#
# ATTACH TUNNEL - PASSTHROUGH
#
#   201 Created
#   400 Bad Request
#   403 Forbidden  
#   404 Not Found 

def bridge_attach_tunnel_passthrough(headers,
                                     url_switch,
                                     br_id,
                                     port,
                                     ofport = None,
                                     tc = None,
                                     descr = None,
                                     shaped_rate = None):
    url = url_switch + ep_bridges +  '/' +  str(br_id) + '/tunnels'
    data = {
             'ofport': ofport,
             'port': port,
             'traffic-class': tc,
             'ifdescr': descr,
             'shaped-rate': shaped_rate,
           }

    LOG.info(" Attach passthrough port to bridge: port: " + str(port) + ", ofport = " + str(ofport))

    try:
        output = requests.post(url ,data=data, headers=headers, verify=False)
        print output.json()

        if output.status_code == 201:
            LOG.info(" Attach passthrough port to bridge: " + "url: " + str(url) + ", " + str(output.status_code) + " Success")
        else:
            if output.status_code == 400:
                raise Exception(" Attach passthrough port to bridge Failed: " + "url: " + str(url) + ", " + str(output.status_code) + " Bad Request")
            elif output.status_code == 403:
                raise Exception(" Attach passthrough port to bridge Failed: " + "url: " + str(url) + ", " + str(output.status_code) + " Forbidden")
            elif output.status_code == 404:
                raise Exception(" Attach passthrough port to bridge Failed: " + "url: " + str(url) + ", " + str(output.status_code) + " Not Found")
            else:
                raise Exception(" Attach passthrough port to bridge Failed: " + "url: " + str(url) + ", " + str(output.status_code) + " Unknown Error")


    except Exception as e:
        raise e
    return output



#
# ATTACH TUNNEL - VLAN RANGE
#
#   201 Created
#   400 Bad Request
#   403 Forbidden
#   404 Not Found

def bridge_attach_tunnel_ctag_vlan_range(headers,
                                         url_switch,
                                         br_id, 
                                         ofport,
                                         port,
                                         vlan_range,
                                         tc = None,
                                         descr = None,
                                         shaped_rate = None):
    url = url_switch + ep_bridges +  '/' +  br_id + '/tunnels'
    data = {
             'ofport': ofport,
             'port': port,
             'vlan-range': vlan_range,
             'traffic-class': tc,
             'ifdescr': descr,
             'shaped-rate': shaped_rate,
           }

    try:
        r = requests.post(url ,data=data, headers=headers, verify=False)
        print r.json()
    except Exception as e:
        raise e
    return r


#
# DETACH TUNNEL
#
#   204 No content
#   403 Forbidden
#   404 Not Found

def bridge_detach_tunnel(headers,
                         url_switch,
                         br_id,
                         port):
    url = url_switch + ep_bridges + '/' +  str(br_id) + '/tunnels' + '/' + str(port)

    try:
        output = requests.delete(url, headers=headers, verify=False)
        if output.status_code == 204:
            LOG.info(" Detach port from bridge: " + "url: " + str(url) + ", " + str(output.status_code) + " Success")
        else:
            if output.status_code == 400:
                raise Exception(" Detach port from bridge Failed: " + "url: " + str(url) + ", " + str(output.status_code) + " Bad Request")
            elif output.status_code == 403:
                raise Exception(" Detach port from bridge Failed: " + "url: " + str(url) + ", " + str(output.status_code) + " Forbidden")
            elif output.status_code == 404:
                raise Exception(" Detach port from bridge Failed: " + "url: " + str(url) + ", " + str(output.status_code) + " Not Found")
            else:
                raise Exception(" Detach port from bridge Failed: " + "url: " + str(url) + ", " + str(output.status_code) + " Unknown Error")


    except Exception as e:
        raise e
    return output


#
# GET BRIDGES
#
#   200
#   403 Forbidden
def get_bridges(headers,
                url_switch):
    url = url_switch + ep_bridges

    try:
        r = requests.get(url, headers=headers, verify=False)
    except Exception as e:
        raise e
    return r


#
# GET BRIDGE
#
#   200     
#   403 Forbidden
def get_bridge(headers,
                url_switch,
                bridge_url):
    
    try:
        r = requests.get(bridge_url, headers=headers, verify=False)
    except Exception as e:
        raise e
    return r



#
# 
#
# get_free_bridge_name
#
#
def get_free_bridge(headers,
                    url_switch):

    bridges = get_bridges(headers,url_switch)

    links=bridges.json()["links"]
    for i in range(33,63):
        bridge = 'br'+str(i)
        if bridge in links.keys():
            continue
        return bridge

    return None

#
# 
#
# get_bridge_by_segmentation_id
#
# By convention we are putting the segmentation_id in the "bridge-description" field
#
def get_bridge_by_segmentation_id(headers,
                                  url_switch,
                                  segementation_id):
    bridges = get_bridges(headers,url_switch)

    links=bridges.json()["links"]
    for bridge,value in links.items():
        url=value['href']
        link = get_bridge(headers,url_switch,url).json()
        if "bridge-descr" in link.keys():
            bridge_descr=str(link["bridge-descr"])
            if bridge_descr == "VLAN-"+str(segementation_id):
                return bridge
    return None




