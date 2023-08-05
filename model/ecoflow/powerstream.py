from model.ecoflow.base_device import EcoflowDevice
from model.connector import Connector

import model.protos.powerstream_pb2 as powerstream
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
        else:
            _LOGGER.error(f"unhandled set_request for {id}")

    def set_output_power(self, power):
        pdata = powerstream.SetValue()
        pdata.value = min(self.get_value("ratedPower", default=800)*10, max(0, round(power * 10)))

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
