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
        self.asterisk_check_int = 5 
        self.asterisk_status_last = datetime.now()


class Channel(object):
    ''' Controls channels statuses '''
    def __init__(self, channel_id):
        self.id = channel_id
        self.pairing_status = False
        self.status = True
        
        self.channel_status = True
        self.channel_active_int = 20 # Seconds
        self.channel_block_int = 30  # Seconds
        self.channel_ts_last = datetime.now() + timedelta(seconds=random.randint(20, 50))  # Start count from different timestamps

        self.download_int = 50  # period between downloads
        self.last_downloads = datetime.now()


raspi = Raspi()
channels = []
for channel_id in range(1,5):
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
    add_routes(sites)

    while True:
        if (datetime.now() - raspi.asterisk_status_last).total_seconds() > raspi.asterisk_check_int:
            check_asterisk_mobile()

        for channel in channels:
            if (datetime.now() - channel.channel_ts_last).total_seconds() > channel.channel_active_int and channel.channel_status:
                remove_extension(channel)
            elif (datetime.now() - channel.channel_ts_last).total_seconds() > channel.channel_block_int and not channel.channel_status:
                add_extension(channel)
            # if (datetime.now() - channel.last_downloads).total_seconds() > channel.download_int and not channel.channel_status:
            #     start_downloading_activity(channel, sites)

        time.sleep(1)


def get_configuation():
    ''' Gets current controller and cellphones configuration '''
    pass



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



def check_asterisk_mobile():
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
        phone_id, mac_addr, group, adapter, connected, state, sms = line.split()
        if connected == 'No' and channels[idx].pairing_status:
            channels[idx].pairing_status = False
            s.send(json.dumps({'channel_id': idx+1, 'pairing_status': 'unpaired'}).encode())
            logging.error('Device %s was unpaired!!' % phone_id)
        elif connected == 'Yes' and not channels[idx].pairing_status:
            channels[idx].pairing_status = True
            s.send(json.dumps({'channel_id': idx+1, 'pairing_status': 'paired'}).encode())
            logging.info('Device %s was connected again and ready to receive calls' % phone_id)

    raspi.asterisk_status_last = datetime.now()


def remove_extension(channel):
    os.system('asterisk -rx  "dialplan remove extension _X.@outgoing %s"' % channel.id )
    channel.channel_status = False
    logging.info('Channel %s was blocked' % channel.id )
    s.send(json.dumps({'channel_id': channel.id, 'channel_status': 'blocked'}).encode())
    channel.channel_ts_last = datetime.now()


def add_extension(channel):
    os.system('asterisk -rx "dialplan add extension _X.,%s,Dial(Mobile/samsung%s/${EXTEN},45) into outgoing"' % (channel.id, channel.id))
    channel.channel_status = True
    logging.info('Channel %s was unblocked' % channel.id )
    s.send(json.dumps({'channel_id': channel.id, 'channel_status': 'online'}).encode())
    channel.channel_ts_last = datetime.now()


def start_downloading_activity(channel, sites):
    ''' Connect to wifi and start downloading activity to simulate ordinary subscriber '''
    url = random.choice(sites)
    if not 'http:' in url:
        url = 'http://'+url
    logging.info('Channel %s is downloading site %s ' % (channel.id, url))
    requests.get(url)
    channel.last_downloads = datetime.now()



if __name__ == '__main__':

    main()

