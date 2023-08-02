from model.ecoflow.base_device import EcoflowDevice
from model.connectors.deltamax_connector import DeltaMaxConnector
import model.protos.platform_pb2 as platform
import model.protos.wn511_socket_sys_pb2 as wn511
import logging
import re
import math
from datetime import datetime

_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel(logging.DEBUG)


class Ecoflow_DeltaMax(EcoflowDevice):
    def __init__(self, serial: str, user_id: str, stdscr=None):
        super().__init__(serial, user_id, stdscr)

        self.connector = DeltaMaxConnector(self.device_sn, stdscr)

        self.add_cmd_id_handler(self.handle_heartbeat, [0, 0])
        #self.add_cmd_id_handler(self.handle_pdata, ["unhandled"])

    def init_subscriptions(self):        
        super().init_subscriptions()
        #self.request_data()        

    def handle_heartbeat(self, message: dict):
        if "params" in message:
            for name, val in message["params"].items():
                if val is not None:
                    [unit, divisor, special_handler] = self.get_param_settings(name).values()
                    if special_handler == "time":
                        # time in minutes
                        h = math.floor(val/60)
                        m = val % 60
                        val = "%02d:%02d" % (h, m)                   
                    if divisor != 1:
                        val = val / divisor
                    self.connector.update(name, val, unit)
                    _LOGGER.debug(f"update received {name}: {val} {unit}")
            self.connector.end_update()

    def detect_param_settings(self, name) -> dict:
        sub_device, param_name = name.split(".") if "." in name else [None, name]
        name_parts = [x.lower() for x in re.sub(r"([A-Z])", r" \1", param_name).split()]
        unit = ""
        divisor = 1
        special_handler = None
        if "watts" in name_parts or "power" in name_parts:
            #divisor = 10
            unit = "W"
        elif "cur" in name_parts:
            #divisor = 10
            unit = "A"
        elif "temp" in name_parts:
            #divisor = 10
            unit = "°C"
        elif "volt" in name_parts:
            #divisor = 10 # ???
            unit = "V"
        elif "brightness" in name_parts:
            #divisor = 10
            unit = "%"
        elif "soc" in name_parts or "soh" in name_parts:
            unit = "%"
        elif "time" in name_parts:
            special_handler = "time"
        return {
            "unit": unit,
            "divisor": divisor,
            "special_handler": special_handler
        }
