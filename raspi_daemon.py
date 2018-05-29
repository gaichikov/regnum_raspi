#!/usr/bin/python3

import os 
import sys
import logging
import time
import subprocess
from datetime import datetime
from daemon import runner

logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S',
                    # handlers='console',
                    filename='/var/log/regnum_raspi.log',
                    # filemode='w'
                    )


class Raspi():
    def __init__(self):
        self.asterisk_check_int = 5 
        self.asterisk_status_last = datetime.now()
        self.status_dict = {}

raspi = Raspi()


def main():
    ''' Start process '''
    logging.info('*'*50)
    logging.info('Process is started')
    while True:
        if (datetime.now() - raspi.asterisk_status_last).total_seconds() > raspi.asterisk_check_int:
            check_asterisk_mobile()

        time.sleep(1)


def get_configuation():
    ''' Gets current controller configuration '''
    pass

def check_asterisk_mobile():
    ''' Check mobile status from asterisk console '''
    logging.info('Checking asterisk status')
    output = subprocess.getoutput('asterisk -x "mobile show devices"')
    if 'No such command' in output:
        os.system('asterisk -x "module load chan_mobile.so"')
        logging.info('Loaded chan_mobile.so')

    output_spl = output.split('\n')[1:]
    logging.info(output_spl)
    
    for line in output_spl:

        logging.info(line)

    raspi.asterisk_status_last = datetime.now()


def start_downloading_activity():
    ''' Starts downloading activity to simulate normal subscriber activity '''
    pass


if __name__ == '__main__':
    main()

