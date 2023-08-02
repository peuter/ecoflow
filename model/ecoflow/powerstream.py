from model.ecoflow.base_device import EcoflowDevice
from model.connectors.powerstream_connector import PowerstreamConnector

import model.protos.platform_pb2 as platform
import model.protos.powerstream_pb2 as powerstream
import model.protos.wn511_socket_sys_pb2 as wn511
import logging
import re
import math
from datetime import datetime

_LOGGER = logging.getLogger(__name__)

class Ecoflow_Powerstream(EcoflowDevice):
    def __init__(self, serial: str, user_id: str, stdscr=None):
        super().__init__(serial, user_id, stdscr)

        self.powerstream = PowerstreamConnector(self.device_sn, stdscr)

        self.add_cmd_id_handler(self.handle_heartbeat, [1, 134])    

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

    def handle_heartbeat(self, pdata, header):
        for descriptor in pdata.DESCRIPTOR.fields:
            val = getattr(pdata, descriptor.name)
            if val is not None:
                [unit, divisor, special_handler] = self.get_param_settings(descriptor.name)
                if special_handler == "time":
                    # time in minutes
                    h = math.floor(val/60)
                    m = val % 60
                    val = "%02d:%02d" % (h, m)
                if divisor != 1:
                    val = val / divisor
                self.powerstream.update(descriptor.name, val, unit)
                _LOGGER.debug(f"update received {descriptor.name}: {val} {unit}")
        self.powerstream.end_update()


    # def decode_proto(self, payload, log_prefix=None):
    #     try:
    #         packet = powerstream.SendHeaderMsg()
    #         packet.ParseFromString(payload)

    #         for message in packet.msg:
    #             pdata = None
    #             dump = True
    #             is_heartbeat = False
    #             handled = False
    #             if message.cmd_id == 1 or message.cmd_id == 134:
    #                 pdata = powerstream.InverterHeartbeat()
    #                 is_heartbeat = True
    #                 handled = True
    #             elif message.cmd_id == 32:
    #                 # 1 grid | 2 plug | 3 to battery (Math.abs) | 4 from battery (Math.abs) | 5 plug single total | 6 plug use time
    #                 pdata = platform.BatchEnergyTotalReport()
    #                 dump = False
    #                 handled = True
    #             elif message.cmd_id == 136 or message.cmd_id == 11:
    #                 pdata = powerstream.SetValue()
    #                 handled = True
    #             elif message.cmd_id == 138:
    #                 pdata = wn511.PowerPack()
    #                 handled = True
    #             elif message.cmd_id in [4]:
    #                 dump = False
    #                 handled = True
                
    #             if pdata is not None:
    #                 pdata.ParseFromString(message.pdata)
    #                 if is_heartbeat:
    #                     if message.device_sn == self.powerstream.serial:
                            
    #                         #print()
    #                         self.powerstream.end_update()
    #                         if self.screen:
    #                             self.screen.addstr(15, 0, "Letztes Update: %s" % datetime.now().strftime("%d.%m.%Y %H:%M:%S"))

    #                 # elif dump:
    #                 #     self.log_raw("UNHANDLED cmd_id: %s" % message.cmd_id, payload, message, pdata=pdata)
    #                 if log_prefix is not None:
    #                     self.log_raw(log_prefix, payload, message, pdata=pdata)
    #             if not handled and dump:
    #                 self.log_raw("UNHANDLED cmd_id: %s" % message.cmd_id, payload, message, pdata=pdata)
    #     except Exception as err:
    #         self.log_raw(f"Unexpected {err=}, {type(err)=}", payload)
    #         raise err        
