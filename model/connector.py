import json
import os
import curses

from model.homie.device import Proto_Device
import model.protos.options_pb2 as options
from model.utils.event_emitter import EventEmitter
from model.utils.settings import Settings

class Connector(EventEmitter):
    def __init__(self, serial, type, name=None, screen=None):
        EventEmitter.__init__(self)
        self.serial = serial
        self.units = {}
        self.screen = screen
        self.sums = {}
        self.start_x = 0
        self.start_y = 0
        self.col_width = 40
        self.name = name if name is not None else "Ecoflow device"

        self.proto_message = None

        self.mqtt_settings = {
            "MQTT_BROKER": os.getenv("HOMIE_MQTT"),
            "MQTT_PORT": int(os.getenv("HOMIE_MQTT_PORT")),
            "MQTT_SHARE_CLIENT": True
        }

        try:
            curses_file = os.path.join(Settings.arg("config_folder"), "ncurses.json")
            self.screen_settings = {}
            if os.path.exists(curses_file):
                with open(curses_file) as f:
                    ncurses_config = json.load(f)
                    if type in ncurses_config:
                        self.screen_settings = ncurses_config[type]
                        self.start_x = self.col_width*2
                        
        except Exception as err:
            raise

    def set_proto_message(self, message):
        self.proto_message = message
        for derived_field in self.proto_message.DESCRIPTOR.GetOptions().Extensions[options.derived_field]:
            if not hasattr(derived_field, "operator") or getattr(derived_field, "operator") == 0:
                self.sums[derived_field.field_name] = derived_field
        self.init_homie_device()

    def init_homie_device(self):
        if self.mqtt_settings["MQTT_BROKER"] is not None and self.proto_message is not None:
            self.homie_device = Proto_Device(self.proto_message, device_id=self.serial.lower(), name=self.name, mqtt_settings=self.mqtt_settings)
            self.homie_device.on("set_request", self.on_set_request)
        else:
            self.homie_device = None
    
    def on_set_request(self, id, value):
        # just forward this event
        self.emit("set_request", id, value)

    def update_homie(self, value, descriptor=None, node_name=None, id=None, name=None):
        if self.homie_device is not None:
            self.homie_device.update(value, descriptor=descriptor, node_name=node_name, id=id, name=name)

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
    
    def update_status(self, status: int):
        if self.homie_device is not None:
            self.homie_device.update_status(status)
    
    def update(self, descriptor, value, unit=None, display_value=None):
        name = descriptor.name
        setattr(self, name, value)
        if unit is not None:
            self.set_unit(name, unit)
        
        self.update_screen(name, display_value=display_value)

        for sum_name in self.sums.keys():
            if name in getattr(self.sums[sum_name], "fields"):
                self.update_sum(sum_name)

        self.update_homie(value, descriptor=descriptor) 

    def update_sum(self, sum_name):
        sum = 0
        unit = None
        derived_field = self.sums[sum_name]
        for name in getattr(derived_field, "fields"):
            val = getattr(self, name)
            if val is None:
                continue
            sum += val
            if unit is None:
                unit = self.get_unit(name)
        value = round(sum, 1)
        setattr(self, sum_name, value)
        if unit is not None:
            self.set_unit(name, unit)
        self.update_homie(value, name=sum_name, node_name=getattr(derived_field, "node"))

        self.update_screen(sum_name)
        
    def update_screen(self, name, display_value=None):
        if self.screen is not None:
            if name not in self.screen_settings:
                # find a free spot                
                if self.start_y+1 >= curses.LINES-1:
                    self.start_x += self.col_width
                    self.start_y = 0
                if self.start_x < curses.COLS-1 and self.start_y < curses.LINES-1:
                    settings = {
                        "x": self.start_x,
                        "y": self.start_y,
                        "name": name
                    }
                    self.start_y += 1
                    self.screen_settings[name] = settings

            if name in self.screen_settings:
                settings = self.screen_settings[name]
                self.screen.addstr(settings["y"], settings["x"], "%s: %s     " % (settings["name"], display_value if display_value is not None else self.value_string(name)))

    def end_update(self):
        if self.screen is not None:
            self.screen.refresh()