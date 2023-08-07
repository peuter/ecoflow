from model.ecoflow.base_device import EcoflowDevice
from model.connector import Connector

import model.protos.powerstream_pb2 as powerstream
import model.protos.wn511_socket_sys_pb2 as wn511
from model.ecoflow.constant import *
import logging

_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel(logging.DEBUG)

class Ecoflow_Powerstream(EcoflowDevice):
    def __init__(self, serial: str, user_id: str, stdscr=None):
        super().__init__(serial, user_id, stdscr)

        self.connector = Connector(self.device_sn, "powerstream", screen=stdscr)
        proto_message = powerstream.InverterHeartbeat()
        self.connector.set_proto_message(proto_message)
        self.connector.on("set_request", self.on_set_request)

        self.add_cmd_id_handler(self.handle_heartbeat, [1])

    def init_subscriptions(self):        
        super().init_subscriptions()
        self.request_data()

    def on_set_request(self, id, value):
        _LOGGER.debug(f"received set-request for {id} with value: {value}")
        if id == "permanent-watts":
            if value >= 0 and value <= self.get_value("ratedPower", default=800):
                self.set_output_power(value)
            else:
                _LOGGER.error(f"invalid output power value: {value}")
        elif id == "upper-limit":
            self.set_bat_upper(value)
        elif id == "lower-limit":
            self.set_bat_lower(value)
        elif id == "inv-brightness":
            self.set_brightness(value)
        elif id == "supply-priority":
            self.set_supply_priority(value)
        else:
            _LOGGER.error(f"unhandled set_request for {id}")

    def set_output_power(self, power):
        pdata = wn511.permanent_watts_pack()
        pdata.permanent_watts = min(self.get_value("ratedPower", default=800)*10, max(0, round(power * 10)))
        self.send_set(pdata, CmdIds.SET_PERMANENT_WATTS)

    def set_bat_lower(self, limit):
        pdata = wn511.bat_lower_pack()
        pdata.lower_limit = max(0, min(30, limit))
        self.send_set(pdata, CmdIds.SET_BAT_LOWER)

    def set_bat_upper(self, limit):
        pdata = wn511.bat_upper_pack()
        pdata.upper_limit = max(50, min(100, limit))
        self.send_set(pdata, CmdIds.SET_BAT_UPPER)

    def set_brightness(self, value):
        pdata = wn511.brightness_pack()
        pdata.brightness = max(0, min(100, value))
        self.send_set(pdata, CmdIds.SET_BRIGHTNESS)

    def set_supply_priority(self, value):
        if value >= 0 and value <= 1:
            pdata = powerstream.SetValue()
            pdata.value = value
            self.send_set(pdata, CmdIds.SET_SUPPLY_PRIORITY)        

    def send_set(self, pdata, cmd_id):
        message = powerstream.SendHeaderMsg()
        header = message.msg.add()
        header.src = DEFAULT_SRC
        header.dest = DEFAULT_DEST
        header.cmd_func = CmdFuncs.POWERSTREAM
        header.cmd_id = cmd_id
        header.pdata = pdata.SerializeToString()
        header.data_len = len(header.pdata)
        header.need_ack = 1
        header.seq = self.generate_seq()
        header.device_sn = self.device_sn
        #self.log_raw("SET AC", message.SerializeToString(), message, pdata)
        self.client.publish(self._set_topic, message.SerializeToString())
