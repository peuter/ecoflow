from model.connectors.base_connector import BaseConnector
from model.homie.powerstream import Device_Powerstream

class PowerstreamConnector(BaseConnector):
    def __init__(self, serial, screen):
        super().__init__(serial, "powerstream", screen)
        self.sums = {
            "pvTotal": ["pv1InputWatts", "pv2InputWatts"]
        }

    def init_homie_device(self):
        if self.mqtt_settings["MQTT_BROKER"] is not None:
            self.homie_device = Device_Powerstream(device_id=self.serial.lower(), name='Powerstream', mqtt_settings=self.mqtt_settings)
        else:
            self.homie_device = None

    def update_homie(self, name, value):
        if self.homie_device is not None:
            if name == "pv1InputWatts":
                self.homie_device.update_pv1_input_watts(value)
            elif name == "pv2InputWatts":
                self.homie_device.update_pv2_input_watts(value)
            elif name == "pvTotal":
                self.homie_device.update_pv_input_watts(value)
            elif name == "permanentWatts":
                self.homie_device.update_permanent_watts(value)
            elif name == "dynamicWatts":
                self.homie_device.update_dynamic_watts(value)
            elif name == "invOutputWatts":
                self.homie_device.update_inverter_output_watts(value)
            elif name == "batSoc":
                self.homie_device.update_soc(value)
            elif name == "pv1Temp:":
                self.homie_device.update_pv1_temperature(value)
            elif name == "pv2Temp:":
                self.homie_device.update_pv2_temperature(value)                                
            elif name == "batTemp":
                self.homie_device.update_battery_temperature(value)
            elif name == "batSoc":
                self.homie_device.update_soc(value)