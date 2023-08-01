import logging

import model.protos.platform_pb2 as platform
import model.protos.powerstream_pb2 as powerstream
import model.protos.wn511_socket_sys_pb2 as wn511

from model.ecoflow.mqtt_client import get_client

_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel(logging.DEBUG)

class EcoflowDevice:
    def __init__(self, serial: str, user_id=str, stdscr=None, log_file=None):
        self.screen = stdscr
        self.raw_file = log_file
        self.client = get_client()
        self.device_sn = serial

        self.handlers = {}
        self.pdata_decoders = {
            2: {
                1: wn511.plug_heartbeat_pack(),
                134: wn511.plug_heartbeat_pack(),
            },
            20: {
                1: powerstream.InverterHeartbeat(),
                129: powerstream.SetValue(),
                134: powerstream.InverterHeartbeat(),
            },
            32: {
                11: powerstream.SetValue(),
            },
            254: {
                32: platform.BatchEnergyTotalReport()
            },            
            # 136: powerstream.SetValue(),
            # 138: wn511.PowerPack()
        }   

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

    def request_data(self):
        message = powerstream.SendHeaderMsg()
        header = message.msg.add()
        setattr(header, "from", "Android")
        header.seq = 381471004
        self.client.publish(self._get_topic, message.SerializeToString())        

    def on_message(self, client, userdata, mqtt_message):
        try:
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
            else:
                _LOGGER.error(f"message for unhandled topic arrived {mqtt_message.topic}")
        except UnicodeDecodeError as error:
            _LOGGER.error(f"UnicodeDecodeError: {error}. Ignoring message and waiting for the next one.")


    def add_cmd_id_handler(self, handler, cmd_ids):
        for cmd_id in cmd_ids:
            if cmd_id not in self.handlers:
                self.handlers[cmd_id] = []
            self.handlers[cmd_id].append(handler)

    def get_pdata_decoder(self, header):
        if header.cmd_func in self.pdata_decoders:
            if header.cmd_id in self.pdata_decoders[header.cmd_func]:
                return self.pdata_decoders[header.cmd_func][header.cmd_id]

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
                pdata = self.get_pdata_decoder(message)                

                if pdata is not None:
                    _LOGGER.debug(f"{self.device_sn} decoder found for cmd_func {message.cmd_func} cmd_id {message.cmd_id}")
                    pdata.ParseFromString(message.pdata)
                handled = False
                if message.cmd_id in self.handlers:
                    handled = True
                    for handler in self.handlers[message.cmd_id]:
                        handler(pdata, message)
                elif "unhandled" in self.handlers:
                    handled = True
                    for handler in self.handlers["unhandled"]:
                        handler(pdata, message)
                if "*" in self.handlers:
                    handled = True
                    for handler in self.handlers["*"]:
                        handler(pdata, message)
                if not handled:
                    _LOGGER.info(f"{self.device_sn} no handler registered for cmd_func {message.cmd_func} cmd_id {message.cmd_id}")
                
        except Exception as err:
            self.log_raw(f"Unexpected {err=}, {type(err)=}", payload)
            raise err    
        
    def decode_pdata(self, header):
        pass

    def log_raw(self, prefix, payload, message=None, pdata=None):
        if self.raw_file is not None:
            self.raw_file.write("\n\n%s:\n%s" % (prefix, payload.hex()))
            if pdata is not None:
                self.raw_file.write("\nMESSAGE:\n%s" % message)
            if pdata is not None:
                self.raw_file.write("\nPDATA:\n%s" % pdata)
            self.raw_file.flush()        
