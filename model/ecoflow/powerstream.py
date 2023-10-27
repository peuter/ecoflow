from model.ecoflow.base_device import EcoflowDevice
from model.connector import Connector

from homie.node.node_base import Node_Base
from homie.node.property.property_integer import Property_Integer

import model.protos.powerstream_pb2 as powerstream
import model.protos.wn511_socket_sys_pb2 as wn511
from model.ecoflow.constant import *
import logging
import math
import datetime

_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel(logging.DEBUG)

class Ecoflow_Powerstream(EcoflowDevice):
    def __init__(self, serial: str, user_id: str, stdscr=None):
        super().__init__(serial, user_id, stdscr, uses_protobuf=True)

        # energy values
        self.today_total = None
        self.today_from_battery = None
        self.today_to_battery = None
        self.today_from_solar = None

        self.connector = Connector(self.device_sn, "powerstream", name="Powerstream", screen=stdscr)
        proto_message = powerstream.InverterHeartbeat()
        self.connector.set_proto_message(proto_message)
        self.connector.on("set_request", self.on_set_request)
        self.connector.init_screen([x.name for x in proto_message.DESCRIPTOR.fields])
        self.customize_homie()
        self.connector.start()
        self.default_cmd_func = CmdFuncs.POWERSTREAM
        self.add_cmd_id_handler(self.handle_heartbeat, [CmdIds.HEARTBEAT])
        self.add_cmd_id_handler(self.handle_energy_total_report, [CmdIds.ENERGY_TOTAL_REPORT], CmdFuncs.REPORTS)

    def init_subscriptions(self):        
        super().init_subscriptions()
        self.request_data()

    def customize_homie(self):
        homie = self.connector.homie_device
        if homie is None:
            return

        node = Node_Base(homie, "energy", "Energy", "energy")
        homie.add_node(node)
        _LOGGER.debug(f"node {node.id} has been added")

        self.today_total = Property_Integer(node, "today-total", name="Today total", unit="Wh", value=0, settable=False)
        node.add_property(self.today_total)
        _LOGGER.debug(f"property {self.today_total.name} has been added to node {node.name}")

        self.today_from_battery = Property_Integer(node, "today-from-battery", name="Today from battery", unit="Wh", value=0, settable=False)
        node.add_property(self.today_from_battery)
        _LOGGER.debug(f"property {self.today_from_battery.name} has been added to node {node.name}")

        self.today_to_battery = Property_Integer(node, "today-to-battery", name="Today to battery", unit="Wh", value=0, settable=False)
        node.add_property(self.today_to_battery)
        _LOGGER.debug(f"property {self.today_to_battery.name} has been added to node {node.name}")

        self.today_from_solar = Property_Integer(node, "today-from-solar", name="Today from solar", unit="Wh", value=0, settable=False)
        node.add_property(self.today_from_solar)
        _LOGGER.debug(f"property {self.today_from_solar.name} has been added to node {node.name}")

    def handle_energy_total_report(self, pdata, header):
        # [total, ?, ?, from_bat, pv1?, pv2?]
        sums = [0,0,0,0,0,0]
        type = pdata.watth_item.watth_type
        date = datetime.datetime.utcfromtimestamp(pdata.watth_item.timestamp)
        offset = 0
        idx = 0
        for val in pdata.watth_item.watth:
            offset = math.floor(idx/24)
            sums[offset] += val
            idx+=1

        if self.today_total is not None:
            self.set_today_total(sums[0])

        if self.today_from_battery is not None:
            self.set_today_from_battery(sums[3])
        #print("%s, type: %s, sums: %s" % (date, type, sums))

    def set_today_from_battery(self, val):
        if self.today_from_battery.value != val:
            self.today_from_battery.value = val
            self.update_today_from_solar()

    def set_today_to_battery(self, val):
        if self.today_to_battery.value != val:
            self.today_to_battery.value = val

    def set_today_total(self, val):
        if self.today_total.value != val:
            self.today_total.value = val
            self.update_today_from_solar()

    def update_today_from_solar(self):
        val = self.today_total.value - self.today_from_battery.value
        if self.today_from_solar.value != val:
            self.today_from_solar.value = val            

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
        pdata.permanent_watts = min(round(self.get_value("ratedPower", default=800)*10), max(0, round(power * 10)))
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
