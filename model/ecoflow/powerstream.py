from model.ecoflow.base_device import EcoflowDevice
from model.powerstream import PowerStream

import model.protos.platform_pb2 as platform
import model.protos.powerstream_pb2 as powerstream
import model.protos.wn511_socket_sys_pb2 as wn511
import logging
import re
import math
from datetime import datetime

_LOGGER = logging.getLogger(__name__)

class Ecoflow_Powerstream(EcoflowDevice):
    def __init__(self, serial: str, user_id: str, stdscr=None, log_file=None):
        super().__init__(serial, stdscr, log_file)

        self.powerstream = PowerStream(self.device_sn, stdscr)

        self._data_topic = f"/app/device/property/{self.device_sn}"
        self._set_topic = f"/app/{user_id}/{self.device_sn}/thing/property/set"
        self._set_reply_topic = f"/app/{user_id}/{self.device_sn}/thing/property/set_reply"
        self._get_topic = f"/app/{user_id}/{self.device_sn}/thing/property/get"
        self._get_reply_topic = f"/app/{user_id}/{self.device_sn}/thing/property/get_reply"

        self.init_subscriptions()

    def init_subscriptions(self):        
        self.client.subscribe(self._data_topic, self)
        self.client.subscribe(self._set_topic, self)
        self.client.subscribe(self._set_reply_topic, self)
        self.client.subscribe(self._get_topic, self)
        self.client.subscribe(self._get_reply_topic, self)
        _LOGGER.info("subscriptions initialized")
        self.request_data()

    def request_data(self):
        message = powerstream.SendHeaderMsg()
        header = message.msg.add()
        setattr(header, "from", "Android")
        header.seq = 381471004
        self.client.publish(self._get_topic, message.SerializeToString())

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

    def on_message(self, client, userdata, mqtt_message):
        try:
            # payload = message.payload.decode("utf-8")
            # raw = json.loads(payload)

            if mqtt_message.topic == self._data_topic:
                self.decode_message(mqtt_message.payload)
            elif mqtt_message.topic == self._set_topic:
                    self.decode_message(mqtt_message.payload, log_prefix="SET")
            elif mqtt_message.topic == self._set_reply_topic:
                self.log_raw("SET REPLY", mqtt_message.payload)
            elif mqtt_message.topic == self._get_topic:
                self.log_raw("GET", mqtt_message.payload)                
            elif mqtt_message.topic == self._get_reply_topic:
                self.decode_message(mqtt_message.payload, log_prefix="GET REPLY")
        except UnicodeDecodeError as error:
            _LOGGER.error(f"UnicodeDecodeError: {error}. Ignoring message and waiting for the next one.")

    def decode_message(self, payload, log_prefix=None):
        try:
            msg = payload.decode("utf-8")
            if log_prefix is not None:
                self.raw_file.write("%s:\n%s\n" % (log_prefix, msg))
            return
        except:
            self.decode_proto(payload, log_prefix=log_prefix)


    def decode_proto(self, payload, log_prefix=None):
        try:
            packet = powerstream.SendHeaderMsg()
            packet.ParseFromString(payload)

            for message in packet.msg:
                pdata = None
                dump = True
                is_heartbeat = False
                handled = False
                if message.cmd_id == 1 or message.cmd_id == 134:
                    pdata = powerstream.InverterHeartbeat()
                    is_heartbeat = True
                    handled = True
                elif message.cmd_id == 32:
                    # 1 grid | 2 plug | 3 to battery (Math.abs) | 4 from battery (Math.abs) | 5 plug single total | 6 plug use time
                    pdata = platform.BatchEnergyTotalReport()
                    dump = False
                    handled = True
                elif message.cmd_id == 136 or message.cmd_id == 11:
                    pdata = powerstream.SetValue()
                    handled = True
                elif message.cmd_id == 138:
                    pdata = wn511.PowerPack()
                    handled = True
                elif message.cmd_id in [4]:
                    dump = False
                    handled = True
                
                if pdata is not None:
                    pdata.ParseFromString(message.pdata)
                    if is_heartbeat:
                        if message.device_sn == self.powerstream.serial:
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
                                    elif descriptor.name in ["batSoc", "lowerLimit", "upperLimit"]:
                                        unit = "%"
                                    if divisor != 1:
                                        val = val / divisor
                                    self.powerstream.update(descriptor.name, val, unit)
                            #print()
                            self.powerstream.end_update()
                            if self.screen:
                                self.screen.addstr(15, 0, "Letztes Update: %s" % datetime.now().strftime("%d.%m.%Y %H:%M:%S"))

                    # elif dump:
                    #     self.log_raw("UNHANDLED cmd_id: %s" % message.cmd_id, payload, message, pdata=pdata)
                    if log_prefix is not None:
                        self.log_raw(log_prefix, payload, message, pdata=pdata)
                if not handled and dump:
                    self.log_raw("UNHANDLED cmd_id: %s" % message.cmd_id, payload, message, pdata=pdata)
        except Exception as err:
            self.log_raw(f"Unexpected {err=}, {type(err)=}", payload)
            raise err        
