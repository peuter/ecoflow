#!/usr/bin/env python3

import json
import logging

import curses
import argparse
import os
from dotenv import load_dotenv

from model.ecoflow.auth import EcoflowAuthentication
from model.ecoflow.mqtt_client import init_client, get_client
from model.ecoflow.powerstream import Ecoflow_Powerstream


load_dotenv()
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(threadName)s -  %(levelname)s - %(message)s') 

_LOGGER = logging.getLogger(__name__)

parser = argparse.ArgumentParser(description='Ecoflow MQTT<->Homie bridge.')
parser.add_argument('--nc-show', dest='ncurses_show', 
                    help='serial number of device that should be shown in ncurses console screen.')

args = parser.parse_args()

def main(stdscr=None):
    user = os.getenv("EF_USERNAME")
    passwd = os.getenv("EF_PASSWORD")
   
    if user is not None and passwd is not None:
        config = {"devices": []}
        with open('config.json') as c:
            config = json.load(c)
        _LOGGER.info("start authorizing")
        auth = EcoflowAuthentication(user, passwd)
        auth.authorize()
        init_client(auth)
        _LOGGER.info('init devices')
        client = None
        with open('raw_data.txt', 'a') as f:
            for device in config["devices"]:
                if "disabled" in device and device["disabled"] == True:
                    continue
                if device["type"] == "powerstream":
                    client = Ecoflow_Powerstream(device["serial"], auth.user_id, stdscr=stdscr if args.ncurses_show is None or args.ncurses_show == device["serial"] else None, log_file=f)
                else:
                    _LOGGER.error("unsupported device type: %s" % device["type"])
            # start run loop
            get_client().start()
        if client is not None:
            client.stop()
        _LOGGER.info("DONE")
    else:
        _LOGGER.error("no credentials provided")

if __name__ == '__main__':
    if args.ncurses_show is not None:
        curses.wrapper(main)
    else:
        main()