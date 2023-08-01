import logging
from model.ecoflow.mqtt_client import get_client

_LOGGER = logging.getLogger(__name__)

class EcoflowDevice:
    def __init__(self, serial: str, stdscr=None, log_file=None):
        self.screen = stdscr
        self.raw_file = log_file
        self.client = get_client()
        self.device_sn = serial

    def init_subscriptions(self):
        pass


    def on_message(self, client, userdata, mqtt_message):
        pass

    def log_raw(self, prefix, payload, message=None, pdata=None):
        if self.raw_file is not None:
            self.raw_file.write("\n\n%s:\n%s" % (prefix, payload.hex()))
            if pdata is not None:
                self.raw_file.write("\nMESSAGE:\n%s" % message)
            if pdata is not None:
                self.raw_file.write("\nPDATA:\n%s" % pdata)
            self.raw_file.flush()        
