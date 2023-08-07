from model.ecoflow.base_device import EcoflowDevice
from model.connector import Connector
from model.protos.wn511_socket_sys_pb2 import plug_switch_message, plug_heartbeat_pack, brightness_pack, max_watts_pack
from model.protos.powerstream_pb2 import SendHeaderMsg 
from model.ecoflow.constant import *

class Ecoflow_Smartplug(EcoflowDevice):
    def __init__(self, serial: str, user_id: str, stdscr=None):
        super().__init__(serial, user_id, stdscr)

        self.connector = Connector(self.device_sn, "smartplug", screen=stdscr)
        proto_message = plug_heartbeat_pack()
        self.connector.set_proto_message(proto_message)
        self.connector.on("set_request", self.on_set_request)

        self.add_cmd_id_handler(self.handle_heartbeat, [1])

    def on_set_request(self, id, value):
        if id == "switch":
            self.set_plug_switch(value)
        elif id == "max-watts":
            self.set_brightness(value)
        elif id == "brightness":
            self.set_brightness(value)

    def init_subscriptions(self):        
        super().init_subscriptions()
        self.request_data()

    def set_brightness(self, value):
        pdata = brightness_pack()
        pdata.lower_limit = max(0, min(100, value))
        self.send_set(pdata, CmdIds.SET_PLUG_BRIGHTNESS)

    def set_max_watts(self, value):
        pdata = max_watts_pack()
        pdata.max_watts = max(0, min(PLUG_MAX_WATTS_LIMIT, value))
        self.send_set(pdata, CmdIds.SET_PLUG_BRIGHTNESS)        

    def set_plug_switch(self, on: bool):
        pdata = plug_switch_message()
        pdata.plug_switch = 1 if on is True else 0

        self.send_set(pdata, CmdIds.SET_PLUG_SWITCH)      

    def send_set(self, pdata, cmd_id):
        message = SendHeaderMsg()
        header = message.msg.add()
        header.src = DEFAULT_SRC
        header.dest = DEFAULT_DEST
        header.cmd_func = CmdFuncs.SMART_PLUG
        header.cmd_id = cmd_id
        header.pdata = pdata.SerializeToString()
        header.data_len = len(header.pdata)
        header.need_ack = 1
        header.seq = self.generate_seq()
        header.device_sn = self.device_sn
        #self.log_raw("SET AC", message.SerializeToString(), message, pdata)
        self.client.publish(self._set_topic, message.SerializeToString())
