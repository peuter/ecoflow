from model.ecoflow.base_device import EcoflowDevice
from model.connectors.powerstream_connector import PowerstreamConnector

import model.protos.powerstream_pb2 as powerstream
import logging

_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel(logging.DEBUG)

class Ecoflow_Powerstream(EcoflowDevice):
    def __init__(self, serial: str, user_id: str, stdscr=None):
        super().__init__(serial, user_id, stdscr)

        self.connector = PowerstreamConnector(self.device_sn, stdscr)

        self.add_cmd_id_handler(self.handle_heartbeat, [1])

    def init_subscriptions(self):        
        super().init_subscriptions()
        self.request_data()

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
