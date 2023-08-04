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
    def __init__(self, serial: str, user_id: str, stdscr=None):
        super().__init__(serial, user_id, stdscr)

        self.connector = SmartplugConnector(self.device_sn, stdscr)

        self.add_cmd_id_handler(self.handle_heartbeat, [1])

    def init_subscriptions(self):        
        super().init_subscriptions()
        self.request_data()