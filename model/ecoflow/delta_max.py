from model.ecoflow.base_device import EcoflowDevice
from model.connector import Connector
import logging
import re
import math
import os
import json

from model.ecoflow.constant import CmdIds

_LOGGER = logging.getLogger(__name__)

class Ecoflow_DeltaMax(EcoflowDevice):
    def __init__(self, serial: str, user_id: str, stdscr=None):
        super().__init__(serial, user_id, stdscr)
        self.uses_protobuf = False
        self.screen_initialized = False

        self.connector = Connector(self.device_sn, "delta-max", name="Delta Max", screen=stdscr)
        self.connector.col_width = 38
        self.connector.show_filter = lambda name : name[0:3] in ["bms", "ems", "pd."] and name[0:7] != "pd.icon"
        self.connector.on("set_request", self.on_set_request)
        self.config_file = os.path.join(os.path.dirname(os.path.realpath(__file__)), '..', 'protos', 'delta-max.json')
        self.config = None
        with open(self.config_file) as f:
            try:
                self.config = json.load(f)
            except Exception as err:
                _LOGGER.error('error reading device config file: %s' % self.config_file)
                _LOGGER.error(err)
        if self.config is not None:
            self.connector.set_device_config(self.config)

        self.connector.start()

        self.add_cmd_id_handler(self.handle_heartbeat, [0, "latestQuotas", "params"])
        self.merged_data = {}

    def init_subscriptions(self):        
        super().init_subscriptions()
        self.request_data()       
        self.client.subscribe(self._set_topic, self)
        self.client.subscribe(self._get_topic, self) 

    def handle_heartbeat(self, message: dict):
        data_map = None

        if "params" in message:
            data_map = message["params"]
        elif "data" in message and "quotaMap" in message["data"]:
            data_map = message["data"]["quotaMap"]
            if not self.screen_initialized and self.connector is not None:
                self.connector.init_screen(list(data_map.keys()), prefixes={
                    "bmsMaster.": 1,
                    "bmsSlave1.": 2,
                    "ems.": 3,
                    "pd.": 4
                })
                self.screen_initialized = True

                # dump config
                # config = {"properties": {}}
                # names = list(data_map.keys())
                # names.sort()
                # for name in names:
                #     [unit, divisor, special_handler] = self.get_param_settings(name).values()
                #     [node, property_name] = name.split(".")
                #     config["properties"][name] = {
                #         "divisor": divisor, 
                #         "unit": unit, 
                #         "node": node,
                #         "name": property_name
                #     }
                #     if special_handler is not None:
                #         config[name]["converter"] = special_handler
                # with open('delta-max.json', 'w') as f:
                #     f.write(json.dumps(config, indent=2))

        
        if data_map is not None:
            if self.message_logger is not None:
                self.merged_data = self.merged_data | data_map
                self.message_logger.log_message(dict(sorted(self.merged_data.items())), prefix=f"{self.device_sn}-data", title=self.device_sn)
            for name, val in data_map.items():
                if val is not None:
                    [unit, divisor, special_handler] = self.get_param_settings(name).values()
                   
                    display_val = None               
                    descriptor = name
                    if self.config is not None and name in self.config["properties"]:
                        descriptor = self.config["properties"][name]
                        if "divisor" in descriptor:
                            divisor = descriptor["divisor"]
                        if "unit" in descriptor:
                            unit = descriptor["unit"]
                    if divisor != 1:
                        val = val / divisor

                    if special_handler == "minutes":
                        # time in minutes
                        h = math.floor(val/60)
                        m = val % 60
                        display_val = "%02d:%02d" % (h, m)    

                    if self.connector is not None:
                        self.connector.update(descriptor, val, unit, display_value=display_val)
                    _LOGGER.debug(f"update received {name}: {val} {unit}")
            if self.connector is not None:
                self.connector.end_update()

    def detect_param_settings(self, name) -> dict:
        sub_device, param_name = name.split(".") if "." in name else [None, name]
        name_parts = [x.lower() for x in re.sub(r"([A-Z])", r" \1", param_name).split()]
        unit = ""
        divisor = 1
        special_handler = None

        if "time" in name_parts:
            special_handler = "minutes"
        return {
            "unit": unit,
            "divisor": divisor,
            "special_handler": special_handler
        }
    
    def on_set_request(self, id, value):
        _LOGGER.debug(f"received set-request for {id} with value: {value}")
        if id == "dc-out-state":            
            self.set_out(value, CmdIds.USB_OUT_CFG)
        elif id == "car-state":            
            self.set_out(value, CmdIds.CAR_OUT_CFG)
        elif id == "cfg-ac-enabled":
            self.set_out(value, CmdIds.AC_OUT_CFG)
        elif id == "cfg-ac-xboost":
            self.set_out(value, CmdIds.AC_OUT_CFG, name="xboost")
        else:
            _LOGGER.error(f"unhandled set_request for {id}")

    def set_out(self, power, cmdId, name="enabled"):
        params = {
            "id": cmdId
        }
        params[name] = 1 if power is True else 0
        data = {
            "from": "Android",
            "isMatter": 0,
            "id": "%s" % self.generate_seq(),
            "moduleType": 0,
            "operateType": "TCP",
            "params": params,
            "version": "1.1"
        }        
        self.client.publish(self._set_topic, json.dumps(data))
