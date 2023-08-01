import os
import json
from model.homie.powerstream import Device_Powerstream

class PowerStream:
    def __init__(self, serial, screen):
        self.serial = serial
        self.units = {}
        self.screen = screen

        self.start_x = 60
        self.start_y = 0

        mqtt_settings = {
            "MQTT_BROKER": os.getenv("HOMIE_MQTT"),
            "MQTT_PORT": int(os.getenv("HOMIE_MQTT_PORT")),
            "MQTT_SHARE_CLIENT": True
        }
        if mqtt_settings["MQTT_BROKER"] is not None:
            self.homie_device = Device_Powerstream(device_id=serial.lower(), name='Powerstream', mqtt_settings=mqtt_settings)
        else:
            self.homie_device = None

        self.sums = {
            "pvTotal": ["pv1InputWatts", "pv2InputWatts"]
        }
        try:
            with open("configs/ncurses.json") as f:
                ncurses_config = json.load(f)
                self.screen_settings = ncurses_config["powerstream"]
        except Exception as err:
            self.screen_settings = {}
            raise

    def close(self):
        if self.homie_device:
            self.homie_device.close()

    def __getattr__(self, name: str):
        if f"_{name}" in self.__dict__:
            return self.__dict__[f"_{name}"]
        return None

    def __setattr__(self, name, value):
        self.__dict__[f"_{name}"] = value

    def set_unit(self, name: str, unit: str):
        self.units[name] = unit

    def get_unit(self, name: str):
        return self.units[name] if name in self.units else None
    
    def value_string(self, name: str):
        value = getattr(self, name)
        unit = self.get_unit(name)
        if unit is not None:
            value = "%s %s" % (value, unit)
        return value
        
    def update(self, name: str, value, unit=None):
        setattr(self, name, value)
        if unit is not None:
            self.set_unit(name, unit)
        
        if self.screen is not None:
            if name not in self.screen_settings:
                # find a free spot
                settings = {
                    "x": self.start_x,
                    "y": self.start_y,
                    "name": name
                }
                self.start_y += 1
                self.screen_settings[name] = settings

            settings = self.screen_settings[name]
            self.screen.addstr(settings["y"], settings["x"], "%s: %s     " % (settings["name"], self.value_string(name)))

        for sum_name in self.sums.keys():
            if name in self.sums[sum_name]:
                self.update_sum(sum_name)

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

    def update_sum(self, sum_name):
        sum = 0
        unit = None
        for name in self.sums[sum_name]:
            val = getattr(self, name)
            if val is None:
                continue
            sum += val
            if unit is None:
                unit = self.get_unit(name)
        self.update(sum_name, round(sum, 1), unit)
            
    def end_update(self):
        if self.screen is not None:
            self.screen.refresh()
