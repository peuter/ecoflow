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
from model.ecoflow.smart_plug import Ecoflow_Smartplug, Simulated_Ecoflow_Smartplug
from model.ecoflow.delta_max import Ecoflow_DeltaMax
from model.utils.message_logger import MessageLogger
from model.utils.settings import Settings

if os.getenv("IN_DOCKER") != "1":
    load_dotenv()

_LOGGER = logging.getLogger(__name__)

parser = argparse.ArgumentParser(description='Ecoflow MQTT<->Homie bridge.')
parser.add_argument('--show', dest='ncurses_show', 
                    help='serial number of device that should be shown in ncurses console screen.')
parser.add_argument('--log', dest='raw_log_mode', choices=["none", "unhandled", "all"], default="none" if os.getenv("EF_LOG") is None else os.getenv("EF_LOG"),
                    help='Mode for logging raw messages')
parser.add_argument('--log-folder', dest='log_folder', default=os.getenv("EF_LOG_FOLDER") if os.getenv("EF_LOG_FOLDER") is not None else "./logs",
                    help='Folder for log files.')
parser.add_argument('--config-folder', dest='config_folder', default=os.getenv("EF_CONFIG_FOLDER") if os.getenv("EF_CONFIG_FOLDER") is not None else "./configs",
                    help='Folder for log files.')

args = parser.parse_args()
Settings.set("args", args) 

handlers=[logging.StreamHandler()]
if args.ncurses_show is not None:
    handlers = [logging.FileHandler(os.path.join(args.log_folder, "ecoflow-bridge.log"))]
                              

logging.basicConfig(level=logging.INFO, handlers=handlers,
                    format='%(asctime)s - %(name)s - %(threadName)s -  %(levelname)s - %(message)s') 

def main(stdscr=None):
    global args
    user = os.getenv("EF_USERNAME")
    passwd = os.getenv("EF_PASSWORD")
   
    if user is not None and passwd is not None:
        config = {"devices": []}
        with open(os.path.join(args.config_folder, 'config.json')) as c:
            config = json.load(c)
        _LOGGER.info("start authorizing")
        auth = EcoflowAuthentication(user, passwd)
        auth.authorize()
        init_client(auth)
        _LOGGER.info('init devices')

        message_logger = None
        clients = []
        if args.raw_log_mode != "none":
            message_logger = MessageLogger(args.raw_log_mode, args.log_folder)

        for device in config["devices"]:
            client = None
            if "disabled" in device and device["disabled"] == True:
                continue
            if device["type"] == "powerstream":
                client = Ecoflow_Powerstream(device["serial"], auth.user_id, stdscr=stdscr if args.ncurses_show is None or args.ncurses_show == device["serial"] else None)
            elif device["type"] == "smart-plug":
                if "simulated" in device and device["simulated"] is True:
                    client = Simulated_Ecoflow_Smartplug(device["serial"], auth.user_id, stdscr=stdscr if args.ncurses_show is None or args.ncurses_show == device["serial"] else None)
                else:
                    client = Ecoflow_Smartplug(device["serial"], auth.user_id, stdscr=stdscr if args.ncurses_show is None or args.ncurses_show == device["serial"] else None)
            elif device["type"] == "delta-max":
                client = Ecoflow_DeltaMax(device["serial"], auth.user_id, stdscr=stdscr if args.ncurses_show is None or args.ncurses_show == device["serial"] else None)
            else:
                _LOGGER.error("unsupported device type: %s" % device["type"])

            if client is not None:
                _LOGGER.info(f"{device['type']} has been created.")
                clients.append(client)
                if message_logger is not None:
                    client.set_message_logger(message_logger)
        # start run loop
        get_client().start()
        for client in clients:
            client.stop()
        _LOGGER.info("DONE")
    else:
        _LOGGER.error("no credentials provided")

if __name__ == '__main__':
    if args.ncurses_show is not None:
        curses.wrapper(main)
    else:
        main()