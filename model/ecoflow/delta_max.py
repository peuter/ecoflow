from model.ecoflow.base_device import EcoflowDevice
from model.connector import Connector
import logging
import re
import math
import os
import json

_LOGGER = logging.getLogger(__name__)

class Ecoflow_DeltaMax(EcoflowDevice):
    def __init__(self, serial: str, user_id: str, stdscr=None):
        super().__init__(serial, user_id, stdscr)
        self.uses_protobuf = False
        self.screen_initialized = False

        self.connector = Connector(self.device_sn, "delta-max", name="Delta Max", screen=stdscr)
        self.connector.col_width = 38
        self.connector.show_filter = lambda name : name[0:3] in ["bms", "ems", "pd."] and name[0:7] != "pd.icon"
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
