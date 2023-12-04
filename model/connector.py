import json
import os
import curses

from model.homie.device import Proto_Device, Json_Device
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
        self._start = [-1, -1, -1]
        self.col_width = 40
        self.name = name if name is not None else "Ecoflow device"
        self.show_filter = None
        self.fixed_screen = False

        self.proto_message = None
        self.device_config = None

        self.mqtt_settings = {
            "MQTT_BROKER": os.getenv("HOMIE_MQTT"),
            "MQTT_PORT": int(os.getenv("HOMIE_MQTT_PORT")) if os.getenv("HOMIE_MQTT_PORT") is not None else 1883,
            "MQTT_SHARE_CLIENT": True,
            "MQTT_USERNAME": os.getenv("HOMIE_MQTT_USERNAME"),
            "MQTT_PASSWORD": os.getenv("HOMIE_MQTT_PASSWORD"),
            "MQTT_CLIENT_ID": os.getenv("HOMIE_MQTT_CLIENT_ID")
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

    def set_device_config(self, config):
        self.device_config = config
        if "derived_fields" in config:
            for derived_field in config["derived_fields"]:
                if "operator" not in derived_field or derived_field["operator"] == 0:
                    self.sums[derived_field["field_name"]] = derived_field
        self.init_homie_device()

    def init_homie_device(self):
        if self.mqtt_settings["MQTT_BROKER"] is not None:
            if self.proto_message is not None:
                self.homie_device = Proto_Device(self.proto_message, device_id=self.serial.lower(), name=self.name, mqtt_settings=self.mqtt_settings)
                self.homie_device.on("set_request", self.on_set_request)
            elif self.device_config is not None:
                self.homie_device = Json_Device(self.device_config, device_id=self.serial.lower(), name=self.name, mqtt_settings=self.mqtt_settings)
                self.homie_device.on("set_request", self.on_set_request)
        else:
            self.homie_device = None

    def start(self):
        if self.homie_device is not None:
            self.homie_device.start()
    
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
        name = None
        update_homie = True
        node_name = None
        if type(descriptor) == str:
            name = descriptor
            update_homie = False
        elif type(descriptor) == dict:
            name = descriptor["name"]
            if "node" in descriptor:
                node_name = descriptor["node"]
        else:
            name = descriptor.name
        setattr(self, name, value)
        if unit is not None:
            self.set_unit(name, unit)
        
        self.update_screen(name, display_value=display_value, node_name=node_name)

        for sum_name in self.sums.keys():
            if name in getattr(self.sums[sum_name], "fields"):
                self.update_sum(sum_name)

        if update_homie:
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
        
    def update_screen(self, name, display_value=None, node_name=None):
        if self.screen is not None:
            if not self.fixed_screen and name not in self.screen_settings and self.show_value(name):
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
            display_name = name
            if not name in self.screen_settings and node_name is not None and "%s.%s" % (node_name, name) in self.screen_settings:
                display_name = "%s.%s" % (node_name, name)
            if display_name in self.screen_settings:
                settings = self.screen_settings[display_name]
                self.screen.addstr(settings["y"], settings["x"], "%s: %s     " % (settings["name"], display_value if display_value is not None else self.value_string(name)))

    def init_screen(self, names: list, prefixes=None):
        if self.screen is None:
            return
        names.sort()
        self.fixed_screen = True
        for name in names:
            if name not in self.screen_settings and self.show_value(name):
                # find a free spot
                fixed_column = None
                if prefixes is not None:
                    for [prefix, col] in prefixes.items():
                        if name[0:len(prefix)] == prefix:
                            fixed_column = col
                            break

                [column, row] = self.get_next_spot(column=fixed_column)
                if column >= 0 and row >= 0:
                    settings = {
                        "x": column * self.col_width,
                        "y": row,
                        "name": name
                    }
                    self.screen_settings[name] = settings

    def show_value(self, name):
        if self.show_filter is None:
            return True
        else:
            return self.show_filter(name)

    def get_next_spot(self, column=None):
        if column is None:
            # find first spot in any free column
            column = 1
            while self._start[column] >= curses.LINES-1:
                column += 1
                if column >= curses.COLS-1:
                    return -1, -1
                if column >= len(self._start):
                    self._start.append(-1)

        if column >= len(self._start):
            while column >= len(self._start):
                self._start.append(-1) 
        
        self._start[column] += 1                   
                
        if column * self.col_width >= curses.COLS-1 or self._start[column] >= curses.LINES-1:
            return -1, -1
        return column, self._start[column]
        
    def end_update(self):
        if self.screen is not None:
            self.screen.refresh()