import paho.mqtt.client as mqtt_client
import logging
import time
import ssl
from model.ecoflow.auth import EcoflowAuthentication

_LOGGER = logging.getLogger(__name__)

ecoflow_client = None

class EcoflowClient:
    def __init__(self, auth: EcoflowAuthentication) -> None:
        self.auth = auth
        self.connected = False
        self.subscriptions = {}

        self.client = mqtt_client.Client(client_id=auth.client_id,
                                         clean_session=True, reconnect_on_failure=True)
        self.client.username_pw_set(self.auth.mqtt_username, self.auth.mqtt_password)
        self.client.tls_set(certfile=None, keyfile=None, cert_reqs=ssl.CERT_REQUIRED)
        self.client.tls_insecure_set(False)
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.on_message = self.on_message

        _LOGGER.info(f"Connecting to MQTT Broker {self.auth.mqtt_url}:{self.auth.mqtt_port}")
        self.client.connect(self.auth.mqtt_url, self.auth.mqtt_port)
        

    def start(self):
        self.client.loop_forever()

    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.connected = True
            _LOGGER.info(f"Connected to Ecoflow MQTT Server")
        elif rc == -1:
            _LOGGER.error("Failed to connect to MQTT: connection timed out")
        elif rc == 1:
            _LOGGER.error("Failed to connect to MQTT: incorrect protocol version")
        elif rc == 2:
            _LOGGER.error("Failed to connect to MQTT: invalid client identifier")
        elif rc == 3:
            _LOGGER.error("Failed to connect to MQTT: server unavailable")
        elif rc == 4:
            _LOGGER.error("Failed to connect to MQTT: bad username or password")
        elif rc == 5:
            _LOGGER.error("Failed to connect to MQTT: not authorised")
        else:
            _LOGGER.error(f"Failed to connect to MQTT: another error occured: {rc}")

        return client
    
    def on_disconnect(self, client, userdata, rc):
        if rc != 0:
            _LOGGER.error(f"Unexpected MQTT disconnection: {rc}. Will auto-reconnect")
            time.sleep(5)
            # self.client.reconnect() ??

    def on_message(self, client, userdata, mqtt_message):
        if mqtt_message.topic in self.subscriptions:
            for device in self.subscriptions[mqtt_message.topic]:
                device.on_message(client, userdata, mqtt_message)
                

    def subscribe(self, topic, device, qos=1):
        self.client.subscribe(topic, qos)
        if topic not in self.subscriptions:
            self.subscriptions[topic] = [device]
        elif device not in self.subscriptions[topic]:
            self.subscriptions[topic].append(device)

    def unsuscribe(self, topic, device):
        if topic in self.subscriptions and device in self.subscriptions[topic]:
            self.subscriptions[topic].remove(device)

    def publish(self, topic, data):
        self.client.publish(topic, data)
    
    def stop(self):
        self.client.loop_stop()
        self.client.disconnect()


def init_client(auth: EcoflowAuthentication):
    global ecoflow_client
    ecoflow_client = EcoflowClient(auth)


def get_client():
    global ecoflow_client
    return ecoflow_client