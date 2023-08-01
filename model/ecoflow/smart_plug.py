from model.ecoflow.base_device import EcoflowDevice
from model.connectors.smartplug_connector import SmartplugConnector
import model.protos.platform_pb2 as platform
import model.protos.wn511_socket_sys_pb2 as wn511
import logging
import re
import math
from datetime import datetime

_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel(logging.DEBUG)


class Ecoflow_Smartplug(EcoflowDevice):
    def __init__(self, serial: str, user_id: str, stdscr=None, log_file=None):
        super().__init__(serial, user_id, stdscr, log_file)

        self.connector = SmartplugConnector(self.device_sn, stdscr)

        self.add_cmd_id_handler(self.handle_heartbeat, [1, 134])
        #self.add_cmd_id_handler(self.handle_pdata, ["unhandled"])

    def init_subscriptions(self):        
        super().init_subscriptions()
        self.request_data()        

    def handle_heartbeat(self, pdata, header):
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
                if divisor != 1:
                    val = val / divisor
                self.connector.update(descriptor.name, val, unit)
                _LOGGER.debug(f"update received {descriptor.name}: {val} {unit}")
        self.connector.end_update()
    
    def handle_pdata(self, pdata, header):        
        #_LOGGER.debug(f"HEADER: {header}")
        if pdata is not None:
            _LOGGER.debug(f"DECODED| cmd_func: {header.cmd_func}, cmd_id: {header.cmd_id}, PDATA: {pdata}")
        else:
            _LOGGER.debug(f"cmd_func: {header.cmd_func}, cmd_id: {header.cmd_id}, PDATA: {header.pdata.hex()}")