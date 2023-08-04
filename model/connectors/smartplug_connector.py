from model.connectors.base_connector import BaseConnector
#from model.homie.powerstream import Device_Powerstream

class SmartplugConnector(BaseConnector):
    def __init__(self, serial, screen):
        super().__init__(serial, "smartplug", screen)

    # def init_homie_device(self):
    #     if self.mqtt_settings["MQTT_BROKER"] is not None:
    #         self.homie_device = Device_Powerstream(device_id=self.serial.lower(), name='Powerstream', mqtt_settings=self.mqtt_settings)
    #     else:
    #         self.homie_device = None

    def update_homie(self, value, descriptor=None, node_name=None, id=None, name=None):
        if self.homie_device is not None:
            pass