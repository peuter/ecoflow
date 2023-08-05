from model.ecoflow.base_device import EcoflowDevice
from model.connector import Connector
from model.protos.wn511_socket_sys_pb2 import plug_heartbeat_pack

class Ecoflow_Smartplug(EcoflowDevice):
    def __init__(self, serial: str, user_id: str, stdscr=None):
        super().__init__(serial, user_id, stdscr)

        self.connector = Connector(self.device_sn, "smartplug", screen=stdscr)
        proto_message = plug_heartbeat_pack()
        self.connector.set_proto_message(proto_message)
        self.connector.on("set_request", self.on_set_request)

        self.add_cmd_id_handler(self.handle_heartbeat, [1])

    def on_set_request(self, id, value):
        pass

    def init_subscriptions(self):        
        super().init_subscriptions()
        self.request_data()