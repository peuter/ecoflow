from model.connectors.base_connector import BaseConnector
from model.homie.device import Proto_Device

from model.protos.powerstream_pb2 import InverterHeartbeat
import model.protos.options_pb2 as options

class PowerstreamConnector(BaseConnector):
    def __init__(self, serial, screen):
        super().__init__(serial, "powerstream", screen)
        self.message = InverterHeartbeat()
        for derived_field in self.message.DESCRIPTOR.GetOptions().Extensions[options.derived_field]:
            if not hasattr(derived_field, "operator") or getattr(derived_field, "operator") == 0:
                self.sums[derived_field.field_name] = derived_field
        # self.sums = {
        #     "pvTotal": ["pv1InputWatts", "pv2InputWatts"]
        # }
        self.init_homie_device()

    def init_homie_device(self):
        if self.mqtt_settings["MQTT_BROKER"] is not None:
            self.homie_device = Proto_Device(self.message, device_id=self.serial.lower(), name='Powerstream', mqtt_settings=self.mqtt_settings)
        else:
            self.homie_device = None

    def update_homie(self, value, descriptor=None, node_name=None, id=None, name=None):
        if self.homie_device is not None:
            self.homie_device.update(value, descriptor=descriptor, node_name=node_name, id=id, name=name)