import logging
import json
import re
import model.protos.platform_pb2 as platform
import model.protos.powerstream_pb2 as powerstream
import model.protos.wn511_socket_sys_pb2 as wn511
import model.protos.options_pb2 as options
import math
from typing import Dict
from model.ecoflow.mqtt_client import get_client
from model.utils.message_logger import MessageLogger

_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel(logging.DEBUG)

class EcoflowDevice:
    def __init__(self, serial: str, user_id=str, stdscr=None):
        self.screen = stdscr
        self.client = get_client()
        self.device_sn = serial
        self._param_settings_cache = {}
        self._properties: Dict[str, any] = {}

        self.connector = None

        self.message_logger: MessageLogger = None

        self.handlers = {}
        self.pdata_decoders = {
            2: {
                1: wn511.plug_heartbeat_pack(),
                2: wn511.time_task_config(),
                32: platform.EnergyTotalReport()
                #134: wn511.plug_heartbeat_pack(),
            },
            20: {
                1: powerstream.InverterHeartbeat(),
                129: powerstream.SetValue()
            },
            32: {
                11: powerstream.SetValue(),
            },
            254: {
                16: platform.EventRecordReport(),
                32: platform.EnergyTotalReport()
            },            
            # 136: powerstream.SetValue(),
            # 138: wn511.PowerPack()
        }   

        self._data_topic = f"/app/device/property/{self.device_sn}"
        self._set_topic = f"/app/{user_id}/{self.device_sn}/thing/property/set"
        self._set_reply_topic = f"/app/{user_id}/{self.device_sn}/thing/property/set_reply"
        self._get_topic = f"/app/{user_id}/{self.device_sn}/thing/property/get"
        self._get_reply_topic = f"/app/{user_id}/{self.device_sn}/thing/property/get_reply"

        self.init_subscriptions()

    def get_param_settings(self, name):
        if name not in self._param_settings_cache:
            self._param_settings_cache[name] = self.detect_param_settings(name)
        return self._param_settings_cache[name]
                    
    def detect_param_settings(self, name) -> dict:
        raw_unit = re.sub(r"([A-Z])", r" \1", name).split()[-1].lower()
        unit = ""
        converter = None
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
            converter = "minutes"
        elif name in ["batSoc", "lowerLimit", "upperLimit"]:
            unit = "%"
        return {
            "unit": unit,
            "divisor": divisor,
            "converter": converter
        }
    
    def handle_heartbeat(self, pdata, header):
        for descriptor, val in pdata.ListFields():
            if val is not None:
                mapping_options = descriptor.GetOptions().Extensions[options.mapping_options]
                divisor = mapping_options.divisor if mapping_options.divisor > 1 else 1
                unit = mapping_options.unit
                if mapping_options.divisor > 1:
                    divisor = mapping_options.divisor
                if mapping_options.converter == "minutes":
                    # time in minutes
                    h = math.floor(val/60)
                    m = val % 60
                    val = "%02d:%02d" % (h, m)
                if divisor != 1:
                    val = val / divisor
                if self.connector is not None:
                    self.connector.update(descriptor, val, unit)
                self._properties[descriptor.name] = val
                _LOGGER.debug(f"update received {descriptor.name}: {val} {unit}")
        if self.connector is not None:
            self.connector.end_update()    

    def get_value(self, name, default=None):
        if name in self._properties:
            return self._properties[name]
        return default

    def init_subscriptions(self):
        self.client.subscribe(self._data_topic, self)
        self.client.subscribe(self._set_topic, self)
        self.client.subscribe(self._set_reply_topic, self)
        self.client.subscribe(self._get_topic, self)
        self.client.subscribe(self._get_reply_topic, self)
        _LOGGER.info("subscriptions initialized")

    def set_message_logger(self, logger: MessageLogger):
        self.message_logger = logger

    def request_data(self):
        message = powerstream.SendHeaderMsg()
        header = message.msg.add()
        setattr(header, "from", "Android")
        header.src = 32
        header.dest = 53
        header.seq = 1651831507
        self.client.publish(self._get_topic, message.SerializeToString())        

    def on_message(self, client, userdata, mqtt_message):
        try:
            if mqtt_message.topic == self._data_topic:
                self.decode_message(mqtt_message.payload, log_prefix="DATA")
            elif mqtt_message.topic == self._set_topic:
                self.decode_message(mqtt_message.payload, log_prefix="SET")
            elif mqtt_message.topic == self._set_reply_topic:
                self.decode_message(mqtt_message.payload, log_prefix="SET_REPLY")
                # if self.message_logger is not None:
                #     self.message_logger.log_message(mqtt_message.payload, handled=False, prefix=f"{self.device_sn}-SET_REPLY", title=self.device_sn)
            elif mqtt_message.topic == self._get_topic:
                self.decode_message(mqtt_message.payload, log_prefix="GET")
                # if self.message_logger is not None:
                #     self.message_logger.log_message(mqtt_message.payload, handled=False, prefix=f"{self.device_sn}-GET", title=self.device_sn)
            elif mqtt_message.topic == self._get_reply_topic:
                self.decode_message(mqtt_message.payload, log_prefix="GET REPLY")
            else:
                _LOGGER.error(f"message for unhandled topic arrived {mqtt_message.topic}")
        except UnicodeDecodeError as error:
            _LOGGER.error(f"UnicodeDecodeError: {error}. Ignoring message and waiting for the next one.")


    def add_cmd_id_handler(self, handler, cmd_ids):
        for cmd_id in cmd_ids:
            if cmd_id not in self.handlers:
                self.handlers[cmd_id] = []
            self.handlers[cmd_id].append(handler)

    def get_pdata_decoder(self, header):
        if header.cmd_func in self.pdata_decoders:
            if header.cmd_id in self.pdata_decoders[header.cmd_func]:
                return self.pdata_decoders[header.cmd_func][header.cmd_id]

    def decode_message(self, payload, log_prefix=None):
        try:
            msg = payload.decode("utf-8")
            message = json.loads(msg)
            handled = False
            if "cmdId" in message:
                if message["cmdId"] in self.handlers:
                    handled = True
                    for handler in self.handlers[message["cmdId"]]:
                        handler(message)
                elif "unhandled" in self.handlers:
                    handled = True
                    for handler in self.handlers["unhandled"]:
                        handler(message)
                if "*" in self.handlers:
                    handled = True
                    for handler in self.handlers["*"]:
                        handler(message)

            if self.message_logger is not None:
                self.message_logger.log_message(message, prefix=f"{self.device_sn}-{log_prefix}", handled=handled, title=self.device_sn, raw=msg)
            return
        except:
            self.decode_proto(payload, log_prefix=log_prefix)

    def decode_proto(self, payload, log_prefix=None):
        try:
            packet = powerstream.SendHeaderMsg()
            packet.ParseFromString(payload)
            for message in packet.msg:
                pdata = self.get_pdata_decoder(message)                

                handled = False
                if pdata is not None:
                    _LOGGER.debug(f"{self.device_sn} decoder found for cmd_func {message.cmd_func} cmd_id {message.cmd_id}")
                    pdata.ParseFromString(message.pdata)
                    if message.cmd_id in self.handlers:
                        handled = True
                        for handler in self.handlers[message.cmd_id]:
                            handler(pdata, message)
                    elif "unhandled" in self.handlers:
                        handled = True
                        for handler in self.handlers["unhandled"]:
                            handler(pdata, message)
                    if "*" in self.handlers:
                        handled = True
                        for handler in self.handlers["*"]:
                            handler(pdata, message)
                    if self.message_logger is not None:
                        self.message_logger.log_message(message, pdata=pdata, handled=handled, prefix=f"{self.device_sn}-{log_prefix}", title=self.device_sn, raw=payload)
                if not handled:
                    _LOGGER.info(f"{self.device_sn} no handler registered for cmd_func {message.cmd_func} cmd_id {message.cmd_id}")
                
        except Exception as err:
            _LOGGER.error(f"Unexpected {err=}, {type(err)=}", payload)
            raise err    
        
    def decode_pdata(self, header):
        pass