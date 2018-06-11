#!/usr/bin/python3

import os 
import sys
import logging
import time
import subprocess
import random
import requests
import socket
import json
from datetime import datetime, timedelta
from daemon import runner

logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S',
                    # handlers='console',
                    filename='/var/log/regnum_raspi.log',
                    # filemode='w'
                    )


class Raspi(object):
    def __init__(self):
        self.check_int = 5 
        self.last_check_ts = datetime.now()


class Channel(object):
    ''' Controls channels statuses '''
    def __init__(self, channel_id):
        self.id = channel_id
        self.channel_name = 'channel' + str(channel_id)

        self.pairing_status = None
        self.channel_status = None
        self.route_status = None
        self.workinghours_status = None
        self.wifi_status = None

        # self.channel_block_int = 600  # Seconds
        
        self.total_call_time = 0  # Total duration to call before blocking
        self.workinghours = [5, 19] # GMT
        
        self.last_busy_period = 0
        self.last_free_period = 0

        self.idle_period = random.randint(30, 600) # Interval to wait between calls
        self.min_busy_period = 20 # Minimum call duration to consider channel busy

        # self.last_check_ts = datetime.now() # last periodical check ts
        
        self.download_int = random.randint(10,15)  # period between downloads
        # self.last_downloads = datetime.now()


raspi = Raspi()
channels = []

channels_amount = len(subprocess.getoutput('asterisk -x "mobile show devices"').split('\n')[1:])
logging.info('Total configured channels ' + str(channels_amount))

for channel_id in range(1,channels_amount+1):
    channel = Channel(channel_id)
    print(channel.__dict__)
    channels.append(channel)


s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect(("10.9.0.1", 5555))

# def send_status_message(id):

def main():
    ''' Start process '''
    logging.info('*'*50)
    logging.info('Raspi daemon was started')
    sites = get_sites_list()
    # add_routes(sites)

    while True:
        # Checking actual channel status - paired/not paired, no service
        check_channels()
        # Check current routes , blocked/unblocked
        check_routes()

        raspi.last_check_ts = datetime.now()

        for channel in channels:
            # Check workinghours status
            check_workinghours(channel)

            # Block route if not workinghours
            if not channel.workinghours_status and channel.route_status == 'unblocked':
                logging.info('Non working hours - will block ' + channel.channel_name)
                block_route(channel)
            elif not channel.workinghours_status and channel.route_status == 'blocked':
                pass
            else:
                if channel.channel_status == 'busy' and channel.route_status == 'unblocked' and channel.last_busy_period > channel.min_busy_period:    # Block route during the conversation, not to make next call immediately
                    logging.info('Channel is busy - blocking route ' + channel.channel_name)
                    block_route(channel)
                if channel.channel_status == 'free' and channel.route_status == 'blocked' and channel.last_free_period > channel.idle_period:  # Unblock after randomly assigned idle period
                    logging.info('Channel is free more than idle period - unblocking the route ' + channel.channel_name)
                    unblock_route(channel)
                if channel.last_free_period:
                    channel.unblocked_in =  channel.idle_period - channel.last_free_period

        messages = []
        for channel in channels:
            messages.append(channel.__dict__)
            print(channel.__dict__)
        try:
            s.send(json.dumps(messages).encode())
        except Exception as e:
            logging.error('Could not send status to server, error: '+str(e))
        
        time.sleep(raspi.check_int)



def get_sites_list():
    '''Gets sites list '''
    fileH = open('sites.txt', 'r')
    return fileH.read().split('\n')


def add_routes(sites):
    ''' Bring up wlan interface and add routes '''
    for site in sites:
        ip_addr = socket.gethostbyname(site)
        output = subprocess.getoutput('ip r add %s dev wlan0 via 192.168.43.1' % ip_addr)
        if 'File exists' in output:
            logging.warning('Route to %s already exists' % ip_addr)
        else:
            logging.info('Added route to %s via wlan' % ip_addr)



def check_workinghours(channel):
    ''' Check workinghours '''
    if (channel.workinghours[0] <= int(datetime.now().strftime('%H')) < channel.workinghours[1]):
        channel.workinghours_status = True
    else:
        channel.workinghours_status = False


def check_channels():
    ''' Check mobile status from asterisk console '''
    # logging.info('Checking asterisk status')
    output = subprocess.getoutput('asterisk -x "mobile show devices"')
    if 'No such command' in output:
        os.system('asterisk -x "module load chan_mobile.so"')
        logging.info('Loaded chan_mobile.so')
        return

    output_spl = output.split('\n')[1:]
    # logging.info(output_spl)

    for idx, line in enumerate(output_spl):
        try:
            phone_id, mac_addr, group, adapter, connected, state, sms = line.split()
        except:
            continue
        if connected == 'No':
            channels[idx].pairing_status = 'not paired'
        elif connected == 'Yes':
            channels[idx].pairing_status = 'paired'

        if state == 'Free':
            channels[idx].channel_status = 'free'
            channels[idx].last_free_period += round((datetime.now() - raspi.last_check_ts).total_seconds(), 2)
            channels[idx].last_busy_period = 0
        elif state == 'Busy':
            channels[idx].channel_status = 'busy'
            channels[idx].last_free_period = 0 
            channels[idx].last_busy_period += round((datetime.now() - raspi.last_check_ts).total_seconds(), 2)
        elif state == 'None':
            channels[idx].channel_status = 'offline'



def check_routes():
    ''' Checks dialplan status '''
    dialplan_output = subprocess.getoutput('asterisk -x "dialplan show outgoing"')
    for channel in channels:
        if channel.channel_name not in dialplan_output:
            channel.route_status = 'blocked'
        else:
            channel.route_status = 'unblocked'



def block_route(channel):
    os.system('asterisk -rx  "dialplan remove extension _X.@outgoing %s"' % channel.id )
    os.system('asterisk -rx  "dialplan add extension _X.,%s,NoOp() into outgoing"' % channel.id )
    channel.idle_period = random.randint(30,600)  # we need to change this period every time
    logging.info('Channel %s was blocked' % channel.channel_name )
    # channel.channel_ts_last = datetime.now()


def unblock_route(channel):
    os.system('asterisk -rx "dialplan remove extension _X.@outgoing %s"' % channel.id )
    os.system('asterisk -rx "dialplan add extension _X.,%s,Dial(Mobile/channel%s/\${EXTEN},45) into outgoing"' % (channel.id, channel.id))
    logging.info('Channel %s was unblocked' % channel.channel_name )
    # channel.channel_ts_last = datetime.now()


def check_wlan_status():
    pass
    # wlan_output = subprocess.getoutput('iwconfig')
    # for channel in channels:
    #     if channel.wifi_ssid in wlan_output:
    


def start_downloading_activity(channel, sites):
    ''' Connect to wifi and start downloading activity to simulate ordinary subscriber '''
    url = random.choice(sites)
    if not 'http:' in url:
        url = 'http://'+url
    logging.info('Channel %s is downloading site %s ' % (channel.id, url))
    s.send(json.dumps({'channel_id': channel.id, 'channel_status': 'downloading'}).encode())
    try:
        requests.get(url, 10)
    except:
        pass
    s.send(json.dumps({'channel_id': channel.id, 'channel_status': 'blocked'}).encode())
    channel.last_downloads = datetime.now()



if __name__ == '__main__':

    main()

