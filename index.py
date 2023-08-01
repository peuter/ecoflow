#!/usr/bin/env python3

import base64
import json
import requests
import uuid
import ssl
import logging
import time
import re
import math
import paho.mqtt.client as mqtt_client
import model.platform_pb2 as platform
import model.powerstream_pb2 as powerstream
import model.wn511_socket_sys_pb2 as wn511
from model.powerstream import PowerStream
import curses
import argparse
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

_LOGGER = logging.getLogger(__name__)

parser = argparse.ArgumentParser(description='Ecoflow MQTT<->Homie bridge.')
parser.add_argument('--nc-show', dest='ncurses_show', 
                    help='serial number of device that should be shown in ncurses console screen.')

class EcoflowException(Exception):
    def __init__(self, *args, **kwargs):
        super().__init__(args, kwargs)

class EcoflowAuthentication:
    def __init__(self, ecoflow_username, ecoflow_password):
        self.ecoflow_username = ecoflow_username
        self.ecoflow_password = ecoflow_password
        self.user_id = None
        self.token = None
        self.mqtt_url = "mqtt.ecoflow.com"
        self.mqtt_port = 8883
        self.mqtt_username = None
        self.mqtt_password = None
        self.client_id = None

    def authorize(self):
        url = "https://api.ecoflow.com/auth/login"
        headers = {"lang": "en_US", "content-type": "application/json"}
        data = {"email": self.ecoflow_username,
                "password": base64.b64encode(self.ecoflow_password.encode()).decode(),
                "scene": "IOT_APP",
                "userType": "ECOFLOW"}

        print(f"Login to EcoFlow API {url}")
        request = requests.post(url, json=data, headers=headers)
        response = self.get_json_response(request)

        try:
            self.token = response["data"]["token"]
            self.user_id = response["data"]["user"]["userId"]
            user_name = response["data"]["user"]["name"]
        except KeyError as key:
            raise EcoflowException(f"Failed to extract key {key} from response: {response}")

        print(f"Successfully logged in: {user_name}")
        print(response["data"])

        url = "https://api.ecoflow.com/iot-auth/app/certification"
        headers = {"lang": "en_US", "authorization": f"Bearer {self.token}"}
        data = {"userId": self.user_id}

        print(f"Requesting IoT MQTT credentials {url}")
        request = requests.get(url, data=data, headers=headers)
        response = self.get_json_response(request)

        try:
            self.mqtt_url = response["data"]["url"]
            self.mqtt_port = int(response["data"]["port"])
            self.mqtt_username = response["data"]["certificateAccount"]
            self.mqtt_password = response["data"]["certificatePassword"]
        except KeyError as key:
            raise EcoflowException(f"Failed to extract key {key} from {response}")

        print(f"Successfully extracted account: {self.mqtt_username}")
        print(response["data"])
        self.client_id = f"ANDROID_{str(uuid.uuid4()).upper()}_{self.user_id}"
        print(self.client_id)

    def get_json_response(self, request):
        if request.status_code != 200:
            raise EcoflowException(f"Got HTTP status code {request.status_code}: {request.text}")

        try:
            response = json.loads(request.text)
            response_message = response["message"]
        except KeyError as key:
            raise EcoflowException(f"Failed to extract key {key} from {response}")
        except Exception as error:
            raise EcoflowException(f"Failed to parse response: {request.text} Error: {error}")

        if response_message.lower() != "success":
            raise EcoflowException(f"{response_message}")

        return response


class Client:

    def __init__(self, serial: str, auth: EcoflowAuthentication, stdscr, f):
        self.auth = auth
        self.screen = stdscr
        self.raw_file = f

        self.debug_win = curses.newwin(10, curses.COLS-1, curses.LINES - 10, 0)

        self.device_sn = serial
        self.powerstream = PowerStream(self.device_sn, stdscr)

        self._data_topic = f"/app/device/property/{self.device_sn}"
        self._set_topic = f"/app/{auth.user_id}/{self.device_sn}/thing/property/set"
        self._set_reply_topic = f"/app/{auth.user_id}/{self.device_sn}/thing/property/set_reply"
        self._get_topic = f"/app/{auth.user_id}/{self.device_sn}/thing/property/get"
        self._get_reply_topic = f"/app/{auth.user_id}/{self.device_sn}/thing/property/get_reply"

        self.client = mqtt_client.Client(client_id=auth.client_id,
                                         clean_session=True, reconnect_on_failure=True)
        self.client.username_pw_set(self.auth.mqtt_username, self.auth.mqtt_password)
        self.client.tls_set(certfile=None, keyfile=None, cert_reqs=ssl.CERT_REQUIRED)
        self.client.tls_insecure_set(False)
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.on_message = self.on_message

        _LOGGER.info(f"Connecting to MQTT Broker {self.auth.mqtt_url}:{self.auth.mqtt_port}")
        self.client.connect(self.auth.mqtt_url, self.auth.mqtt_port)
        self.client.loop_forever()

    def on_connect(self, client, userdata, flags, rc):
        match rc:
            case 0:
                self.client.subscribe([(self._data_topic, 1),
                                       (self._set_topic, 1), (self._set_reply_topic, 1),
                                       (self._get_topic, 1), (self._get_reply_topic, 1)])
                _LOGGER.info(f"Subscribed to MQTT topic {self._data_topic}")

                self.request_data()
            case -1:
                _LOGGER.error("Failed to connect to MQTT: connection timed out")
            case 1:
                _LOGGER.error("Failed to connect to MQTT: incorrect protocol version")
            case 2:
                _LOGGER.error("Failed to connect to MQTT: invalid client identifier")
            case 3:
                _LOGGER.error("Failed to connect to MQTT: server unavailable")
            case 4:
                _LOGGER.error("Failed to connect to MQTT: bad username or password")
            case 5:
                _LOGGER.error("Failed to connect to MQTT: not authorised")
            case _:
                _LOGGER.error(f"Failed to connect to MQTT: another error occured: {rc}")

        return client
        
    def on_disconnect(self, client, userdata, rc):
        if rc != 0:
            _LOGGER.error(f"Unexpected MQTT disconnection: {rc}. Will auto-reconnect")
            time.sleep(5)
            # self.client.reconnect() ??

    def request_data(self):
        message = powerstream.SendHeaderMsg()
        header = message.msg.add()
        setattr(header, "from", "Android")
        header.seq = 381471004
        self.client.publish(self._get_topic, message.SerializeToString())

    def set_output_power(self, power):
        pdata = powerstream.SetValue()
        pdata.value = min(6000, max(0, power * 10))

        message = powerstream.SendHeaderMsg()
        header = message.msg.add()
        header.src = 32
        header.dest = 53
        header.cmd_func = 20
        header.cmd_id = 129
        header.pdata = pdata.SerializeToString()
        header.data_len = len(header.pdata)
        header.need_ack = 1
        header.seq = 202476
        header.device_sn = self.device_sn
        #self.log_raw("SET AC", message.SerializeToString(), message, pdata)
        self.client.publish(self._set_topic, message.SerializeToString())

    def on_message(self, client, userdata, mqtt_message):
        try:
            # payload = message.payload.decode("utf-8")
            # raw = json.loads(payload)

            if mqtt_message.topic == self._data_topic:
                self.decode_message(mqtt_message.payload)
                #print(packet.msg.pdata)
            elif mqtt_message.topic == self._set_topic:
                #self.data.add_set_command(None, message.payload)
                #self.log_raw("SET", mqtt_message.payload)
                 self.decode_message(mqtt_message.payload, log_prefix="SET")
            elif mqtt_message.topic == self._set_reply_topic:
                #self.data.add_set_command_reply(message.payload)
                self.log_raw("SET REPLY", mqtt_message.payload)
            elif mqtt_message.topic == self._get_topic:
                #self.data.add_get_command(None, message.payload)
                self.log_raw("GET", mqtt_message.payload)
                
                # packet = powerstream.SendHeaderMsg()
                # packet.ParseFromString(mqtt_message.payload)
                # for message in packet.msg:
                #     print(message.cmd_id)
                # self.debug_win.refresh()
            elif mqtt_message.topic == self._get_reply_topic:
                self.decode_message(mqtt_message.payload, log_prefix="GET REPLY")
                #self.data.add_get_command_reply(message.payload)
                #self.log_raw("GET REPLY", mqtt_message.payload)
                # self.debug_win.addnstr("GET topic reply: %s " % mqtt_message.payload.decode("utf-8"), 9*(curses.COLS-1))
                # self.debug_win.refresh()
        except UnicodeDecodeError as error:
            _LOGGER.error(f"UnicodeDecodeError: {error}. Ignoring message and waiting for the next one.")

    def decode_message(self, payload, log_prefix=None):
        try:
            msg = payload.decode("utf-8")
            if log_prefix is not None:
                self.raw_file.write("%s:\n%s\n" % (log_prefix, msg))
            #self.debug_win.addnstr(0, 0, "GET topic: %s " % msg, 10*(curses.COLS-1))
            return
        except:
            self.decode_proto(payload, log_prefix=log_prefix)

    
    def decode_proto(self, payload, log_prefix=None):
        try:
            packet = powerstream.SendHeaderMsg()
            packet.ParseFromString(payload)

            for message in packet.msg:
                pdata = None
                dump = True
                is_heartbeat = False
                handled = False
                if message.cmd_id == 1 or message.cmd_id == 134:
                    pdata = powerstream.InverterHeartbeat()
                    is_heartbeat = True
                    handled = True
                elif message.cmd_id == 32:
                    # 1 grid | 2 plug | 3 to battery (Math.abs) | 4 from battery (Math.abs) | 5 plug single total | 6 plug use time
                    pdata = platform.BatchEnergyTotalReport()
                    dump = False
                    handled = True
                elif message.cmd_id == 136 or message.cmd_id == 11:
                    pdata = powerstream.SetValue()
                    handled = True
                elif message.cmd_id == 138:
                    pdata = wn511.PowerPack()
                    handled = True
                elif message.cmd_id in [4]:
                    dump = False
                    handled = True
                
                if pdata is not None:
                    pdata.ParseFromString(message.pdata)
                    if is_heartbeat:
                        if message.device_sn == self.powerstream.serial:
                            #self.debug_win.clear()
                            for descriptor in pdata.DESCRIPTOR.fields:
                                val = getattr(pdata, descriptor.name)
                                if val != 0:
                                    raw_unit = re.sub(r"([A-Z])", r" \1", descriptor.name).split()[-1].lower()
                                    unit = ""
                                    divisor = 1
                                    if raw_unit == "watts" or raw_unit == "power":
                                        divisor = 10
                                        unit = "W"
                                    elif raw_unit == "cur":
                                        divisor = 10
                                        unit = "A"
                                    elif raw_unit == "temp":
                                        divisor = 10
                                        unit = "°C"
                                    elif raw_unit == "volt":
                                        divisor = 10 # ???
                                        unit = "V"
                                    elif raw_unit == "brightness":
                                        divisor = 10
                                        unit = "%"
                                    elif raw_unit == "time":
                                        # time in minutes
                                        h = math.floor(val/60)
                                        m = val % 60
                                        val = "%02d:%02d" % (h, m)
                                    elif descriptor.name in ["batSoc", "lowerLimit", "upperLimit"]:
                                        unit = "%"
                                    if divisor != 1:
                                        val = val / divisor
                                    self.powerstream.update(descriptor.name, val, unit)
                                    # try:
                                    #     self.debug_win.addstr("%20s: %6s %s" % (descriptor.name, val, unit))                                        
                                    # except:
                                    #     pass
                                    #print("%20s: %6s %s" % (descriptor.name, val, unit))
                            #print()
                            self.powerstream.end_update()
                            #self.debug_win.refresh()
                            self.screen.addstr(15, 0, "Letztes Update: %s" % datetime.now().strftime("%d.%m.%Y %H:%M:%S"))
                    # elif dump:
                    #     self.log_raw("UNHANDLED cmd_id: %s" % message.cmd_id, payload, message, pdata=pdata)
                    if log_prefix is not None:
                        self.log_raw(log_prefix, payload, message, pdata=pdata)
                if not handled and dump:
                    self.log_raw("UNHANDLED cmd_id: %s" % message.cmd_id, payload, message, pdata=pdata)
        except Exception as err:
            self.log_raw(f"Unexpected {err=}, {type(err)=}", payload)
            raise err

    def log_raw(self, prefix, payload, message=None, pdata=None):
        self.raw_file.write("\n\n%s:\n%s" % (prefix, payload.hex()))
        if pdata is not None:
            self.raw_file.write("\nMESSAGE:\n%s" % message)
        if pdata is not None:
            self.raw_file.write("\nPDATA:\n%s" % pdata)
        self.raw_file.flush()

    def stop(self):
        self.client.loop_stop()
        self.client.disconnect()
        self.powerstream.close()


def main(stdscr):
    user = os.getenv("EF_USERNAME")
    passwd = os.getenv("EF_PASSWORD")
   
    if user is not None and passwd is not None:
        config = {"devices": []}
        with open('config.json') as c:
            config = json.load(c)
        print("start authorizing")
        auth = EcoflowAuthentication("tbraeutigam@gmail.com", "C0ckta1l/s")
        auth.authorize()
        with open('raw_data.txt', 'a') as f:
            for device in config["devices"]:
                if device["disabled"]:
                    continue
                if device["type"] in ["powerstream", "smart-plug"]:
                    client = Client(device["serial"], auth, stdscr, f)
                else:
                    print("unsupported device type: %s" % device["type"])
        client.stop()
        print("DONE")
    else:
        print("no credentials provided")

if __name__ == '__main__':
    args = parser.parse_args()
    if args.ncurses_show is not None:
        curses.wrapper(main)