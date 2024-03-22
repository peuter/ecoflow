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
from model.ecoflow.constant import *
import random
import datetime
import pprint
from model.utils.interval import InvervalTimer

_LOGGER = logging.getLogger(__name__)

class EcoflowDevice:
    def __init__(self, serial: str, user_id=str, stdscr=None, is_simulated : bool = False, uses_protobuf = False):
        self.screen = stdscr
        self.client = get_client()
        self.device_sn = serial
        self._param_settings_cache = {}
        self._properties: Dict[str, any] = {}
        self.is_simulated = is_simulated
        self._last_heartbeat_time: datetime.datetime = None
        self.uses_protobuf = uses_protobuf
        self.default_cmd_func = CmdFuncs.DEFAULT

        self.pp = pprint.PrettyPrinter(indent=4)

        self.connector = None

        self.message_logger: MessageLogger = None

        self.handlers = {}
        self.pdata_messages = {
            CmdFuncs.SMART_PLUG: {
                CmdIds.PLUG_HEARTBEAT: wn511.plug_heartbeat_pack(),
                CmdIds.TIME_TASK_CONFIG: wn511.time_task_config_post(),
                CmdIds.SET_PLUG_SWITCH: wn511.plug_switch_message(),
                CmdIds.SET_PLUG_BRIGHTNESS: wn511.brightness_pack(),
                CmdIds.SET_UNKNOWN_135: powerstream.SetValue(),
                CmdIds.SET_MAX_WATTS: wn511.max_watts_pack(),
                CmdIds.SET_MESH_ENABLE: wn511.mesh_ctrl_pack(),
                CmdIds.PLUG_POWER_PACK: wn511.PowerPack(),
                CmdIds.INCLUDE_PLUG: wn511.include_plug()
            },
            CmdFuncs.POWERSTREAM: {
                CmdIds.HEARTBEAT: powerstream.InverterHeartbeat(),
                CmdIds.HEARTBEAT2: powerstream.InverterHeartbeat2(),
                CmdIds.SET_PERMANENT_WATTS: wn511.permanent_watts_pack(),
                CmdIds.SET_SUPPLY_PRIORITY: powerstream.SetValue(),
                CmdIds.SET_BAT_LOWER: wn511.bat_lower_pack(),
                CmdIds.SET_BAT_UPPER: wn511.bat_upper_pack(),
                CmdIds.SET_PLUG_BRIGHTNESS: wn511.brightness_pack(),
                CmdIds.SET_UNKNOWN_136: powerstream.SetValue(),
                CmdIds.SET_UNKNOWN_138: powerstream.SetValue(),
            },
            32: {
                11: powerstream.SetValue(),
            },
            CmdFuncs.REPORTS: {
                16: platform.EventRecordReport(),
                CmdIds.ENERGY_TOTAL_REPORT: platform.BatchEnergyTotalReport()
            }
        }   

        self._data_topic = f"/app/device/property/{self.device_sn}"
        self._status_topic = f"/app/device/status/{self.device_sn}"
        self._progress_topic = f"/app/device/progress/{self.device_sn}"
        self._set_topic = f"/app/{user_id}/{self.device_sn}/thing/property/set"
        self._set_reply_topic = f"/app/{user_id}/{self.device_sn}/thing/property/set_reply"
        self._get_topic = f"/app/{user_id}/{self.device_sn}/thing/property/get"
        self._get_reply_topic = f"/app/{user_id}/{self.device_sn}/thing/property/get_reply"
        self._all_topics = f"/app/{user_id}/{self.device_sn}/#"

        self.init_subscriptions()

        self._timer = InvervalTimer(120, self.check_connection)
        self._timer.start()

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
    
    def check_connection(self):
        refresh = False
        _LOGGER.debug('checking last heatbeat time')
        if self._last_heartbeat_time is None:
            refresh = True
        else:
            delta = datetime.datetime.now() - self._last_heartbeat_time
            refresh = delta.total_seconds() > 120
            _LOGGER.debug('last heartbeat is %s minutes old' % (delta.total_seconds() / 60))
        if refresh:
            _LOGGER.info('last heartbeat outdated, requesting new one')
            self.request_data()

    def stop(self):
        self._timer.cancel()
    
    def handle_heartbeat(self, pdata, header):
        for descriptor, val in pdata.ListFields():
            if val is not None:
                mapping_options = descriptor.GetOptions().Extensions[options.mapping_options]
                divisor = mapping_options.divisor if mapping_options.divisor > 1 else 1
                unit = mapping_options.unit
                display_val = None
                if mapping_options.divisor > 1:
                    divisor = mapping_options.divisor
                if mapping_options.converter == "minutes":
                    # time in minutes
                    h = math.floor(val/60)
                    m = val % 60
                    display_val = "%02d:%02d" % (h, m)
                if divisor != 1:
                    val = val / divisor
                if self.connector is not None:
                    self.connector.update(descriptor, val, unit, display_value=display_val)
                self._properties[descriptor.name] = val
                _LOGGER.debug(f"update received {descriptor.name}: {val} {unit}")
        if self.connector is not None:
            self.connector.end_update()
        self._last_heartbeat_time = datetime.datetime.now()

    def handle_status(self, status: int):
        if self.connector is not None:
            self.connector.update_status(status)
        

    def get_value(self, name, default=None):
        if name in self._properties:
            return self._properties[name]
        return default

    def init_subscriptions(self):
        if self.is_simulated:
            self.client.subscribe(self._set_topic, self)
            self.client.subscribe(self._get_topic, self)
        else:
            self.client.subscribe(self._data_topic, self)
            self.client.subscribe(self._status_topic, self)
            #self.client.subscribe(self._progress_topic, self)
            self.client.subscribe(self._set_reply_topic, self)
            self.client.subscribe(self._get_reply_topic, self)

            # self.client.subscribe(self._set_topic, self)
            # self.client.subscribe(self._get_topic, self)
        _LOGGER.info("subscriptions initialized")

    def set_message_logger(self, logger: MessageLogger):
        self.message_logger = logger

    def request_data(self):
        if self.uses_protobuf:
            message = powerstream.SendHeaderMsg()
            header = message.msg.add()
            setattr(header, "from", "Android")
            header.src = DEFAULT_SRC
            header.dest = DEFAULT_DEST
            header.seq = self.generate_seq()
            self.client.publish(self._get_topic, message.SerializeToString())
        else:
            data = {
                "from": "Android",
                "id": "%s" % self.generate_seq(),
                "moduleType": 0,
                "operateType": "latestQuotas",
                "params": {},
                "version": "1.1"
            }
            self.client.publish(self._get_topic, json.dumps(data))

    def on_message(self, client, userdata, mqtt_message):
        try:
            self.decode_message(mqtt_message.payload, log_prefix=self.get_log_prefix(mqtt_message.topic))
        except UnicodeDecodeError as error:
            _LOGGER.error(f"UnicodeDecodeError: {error}. Ignoring message and waiting for the next one.")


    def get_log_prefix(self, topic):
        if topic == self._data_topic:
            return "DATA"
        elif topic == self._status_topic:
            return "STATUS"
        elif topic == self._progress_topic:
            return "PROGRESS"
        elif topic == self._set_topic:
            return "SET"
        elif topic == self._set_reply_topic:
            return "SET_REPLY"
        elif topic == self._get_topic:
            return "GET"
        elif topic == self._get_reply_topic:
            return "GET REPLY"
        return None

    def add_cmd_id_handler(self, handler, cmd_ids, cmd_func=None):
        if cmd_func is None and self.default_cmd_func is not None:
            cmd_func = self.default_cmd_func
        if cmd_func not in self.handlers:
            self.handlers[cmd_func] = {}
        for cmd_id in cmd_ids:
            if cmd_id not in self.handlers[cmd_func]:
                self.handlers[cmd_func][cmd_id] = []
            self.handlers[cmd_func][cmd_id].append(handler)

    def get_pdata_message(self, cmd_func, cmd_id, header=None):
        if cmd_func in self.pdata_messages:
            if cmd_id in self.pdata_messages[cmd_func]:
                return self.pdata_messages[cmd_func][cmd_id]           

    def decode_message(self, payload, log_prefix=None):
        is_json = False
        try:
            msg = payload.decode("utf-8")
            message = json.loads(msg)
            handled = False
            is_json = True
            
            cmd_id = message["cmdId"] if "cmdId" in message else None
            cmd_func = message["cmdFunc"] if "cmdFunc" in message else self.default_cmd_func
            if cmd_id is None and "operateType" in message:
                cmd_id = message["operateType"]
            if cmd_id is None and "params" in message and "status" not in message["params"]:
                cmd_id = "params"
            if cmd_id is not None:
                if cmd_func is None and cmd_id in self.handlers:
                    handled = True
                    for handler in self.handlers[cmd_id]:
                        handler(message)
                elif cmd_func is not None and cmd_func in self.handlers and cmd_id in self.handlers[cmd_func]:
                    handled = True
                    for handler in self.handlers[cmd_func][cmd_id]:
                        handler(message)
                elif "unhandled" in self.handlers:
                    handled = True
                    for handler in self.handlers["unhandled"]:
                        handler(message)
                if "*" in self.handlers:
                    handled = True
                    for handler in self.handlers["*"]:
                        handler(message)
            elif "params" in message and "status" in message["params"]:
                self.handle_status(message["params"]["status"])

            if self.message_logger is not None:
                self.message_logger.log_message(message, prefix=f"{self.device_sn}-{log_prefix}", handled=handled, title=self.device_sn, raw=msg)
            return
        except Exception as e:
            if not is_json:
                self.decode_proto(payload, log_prefix=log_prefix)
            else:
                raise e

    def decode_proto(self, payload, log_prefix=None):
        try:
            packet = powerstream.SendHeaderMsg()
            packet.ParseFromString(payload)
            for message in packet.msg:
                pdata = self.get_pdata_message(message.cmd_func, message.cmd_id)
                if message.device_sn != self.device_sn:
                    continue        

                handled = False
                cmd_id = message.cmd_id if message.HasField("cmd_id") else 0
                cmd_func = message.cmd_func if message.HasField("cmd_func") else 0
                if pdata is not None:
                    _LOGGER.debug(f"{self.device_sn} decoder found for cmd_func {cmd_func} cmd_id {cmd_id}")
                    pdata.ParseFromString(message.pdata)
                if cmd_func in self.handlers:
                    if cmd_id in self.handlers[cmd_func]:
                        handled = True
                        for handler in self.handlers[cmd_func][cmd_id]:
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
                    _LOGGER.debug(f"{self.device_sn} no handler registered for cmd_func {cmd_func} cmd_id {cmd_id}")
                
        except Exception as err:
            _LOGGER.error(f"Unexpected {err=}, {type(err)=}", payload)
            raise err    
        
    def decode_pdata(self, header):
        pass

    def generate_seq(self):
        return random.randint(100000, 999999)
