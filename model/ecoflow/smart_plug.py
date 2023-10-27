from model.ecoflow.base_device import EcoflowDevice
from model.connector import Connector
from model.protos.wn511_socket_sys_pb2 import plug_switch_message, plug_heartbeat_pack, brightness_pack, max_watts_pack
from model.protos.powerstream_pb2 import SendHeaderMsg 
from model.ecoflow.constant import *
import logging
from model.utils.interval import InvervalTimer

_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel(logging.DEBUG)

class Ecoflow_Smartplug(EcoflowDevice):
    def __init__(self, serial: str, user_id: str, stdscr=None, is_simulated=False):
        super().__init__(serial, user_id, stdscr=stdscr, is_simulated=is_simulated, uses_protobuf=True)
        self.default_cmd_func = CmdFuncs.SMART_PLUG
        self.connector = Connector(self.device_sn, "smartplug", name="Smart-Plug", screen=stdscr)
        proto_message = self.get_pdata_message(CmdFuncs.SMART_PLUG, CmdIds.PLUG_HEARTBEAT)
        self.connector.set_proto_message(proto_message)
        self.connector.on("set_request", self.on_set_request)
        self.connector.start()

        self.add_cmd_id_handler(self.handle_heartbeat, [CmdIds.PLUG_HEARTBEAT])

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


class Simulated_Ecoflow_Smartplug(Ecoflow_Smartplug):
    def __init__(self, serial: str, user_id: str, stdscr=None):
        super().__init__(serial, user_id, stdscr=stdscr, is_simulated=True)

        self._states = {
            "err_code": 0,
            "warn_code": 0,
            "country": 0,
            "town" : 0,
            "max_cur": 0,
            "temp": 29,
            "freq" : 50,
            "current": 0,
            "volt": 240,
            "watts": 0,
            "switch": 1,
            "brightness": 500,
            "max_watts": PLUG_MAX_WATTS_LIMIT,
            "heartbeat_frequency": 10,
            "mesh_enable": False 
        }
        self.uses_protobuf = True
        self._changed = []

        self.add_cmd_id_handler(self.handle_data_request, [0])

        self._timer = InvervalTimer(self._states["heartbeat_frequency"], self.flush_changes)
        _LOGGER.debug(f"starting timer with {self._states['heartbeat_frequency']} seconds interval.")
        self._timer.start()

    def init_subscriptions(self):        
        self.client.subscribe(self._set_topic, self)
        self.client.subscribe(self._get_topic, self)

    def handle_data_request(self, pdata, header):
        pdata = plug_heartbeat_pack()
        for name, value in self._states.entries():
            setattr(pdata, name, value)
        self.send_heartbeat(pdata)

    def set_watts(self, watts):
        if self._states["watts"] != watts:
            self._states["watts"] = watts * 10            
            self._changed.append("watts")

    def flush_changes(self):
        pdata = plug_heartbeat_pack()
        _LOGGER.debug(f"flushing {len(self._changed)} changes")
        for name in self._changed:
            setattr(pdata, name, self._states[name])
        self._changed.clear()
        self.send_heartbeat(pdata, is_reply=False)


    def send_heartbeat(self, pdata, is_reply=True):
        message = SendHeaderMsg()
        header = message.msg.add()
        header.src = DEFAULT_DEST
        header.dest = DEFAULT_SRC
        header.d_src = 1
        header.d_dest = 1
        header.cmd_func = CmdFuncs.SMART_PLUG
        header.cmd_id = CmdIds.PLUG_HEARTBEAT
        header.pdata = pdata.SerializeToString()
        header.data_len = len(header.pdata)
        header.need_ack = 1
        header.version = 3
        header.payload_ver = 3
        header.seq = self.generate_seq()
        header.device_sn = self.device_sn
        #self.log_raw("SET AC", message.SerializeToString(), message, pdata)
        self.client.publish(self._get_reply_topic if is_reply else self._data_topic, message.SerializeToString())

        
