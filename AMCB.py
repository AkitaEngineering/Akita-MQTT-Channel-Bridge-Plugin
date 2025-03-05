import meshtastic
import time
import json
import paho.mqtt.client as mqtt
import argparse
import threading
from meshtastic.util import get_lora_config

class AMCB:
    def __init__(self, interface, config_file="mqtt_config.json"):
        self.interface = interface
        self.config_file = config_file
        self.mqtt_clients = {}
        self.lora_config = get_lora_config(interface.meshtastic)
        self.load_config()
        self.connect_mqtt_servers()

    def load_config(self):
        try:
            with open(self.config_file, "r") as f:
                self.config = json.load(f)
        except FileNotFoundError:
            print(f"Config file '{self.config_file}' not found.")
            self.config = {}
        except json.JSONDecodeError:
            print(f"Error decoding config file '{self.config_file}'.")
            self.config = {}

    def connect_mqtt_servers(self):
        for channel_id, mqtt_config in self.config.items():
            try:
                client = mqtt.Client(f"meshtastic_{channel_id}")
                client.on_connect = self.on_mqtt_connect
                client.on_disconnect = self.on_mqtt_disconnect
                client.connect(mqtt_config["host"], mqtt_config["port"], 60)
                client.loop_start()  # Start the MQTT network loop
                self.mqtt_clients[channel_id] = client
            except Exception as e:
                print(f"Error connecting to MQTT for channel {channel_id}: {e}")

    def on_mqtt_connect(self, client, userdata, flags, rc):
        if rc == 0:
            print(f"MQTT connected: {client._client_id}")
        else:
            print(f"MQTT connection failed: {client._client_id}, rc={rc}")

    def on_mqtt_disconnect(self, client, userdata, rc):
        print(f"MQTT disconnected: {client._client_id}, rc={rc}")

    def publish_message(self, channel_id, message):
        if channel_id in self.mqtt_clients:
            try:
                mqtt_config = self.config[channel_id]
                self.mqtt_clients[channel_id].publish(mqtt_config["topic"], json.dumps(message))
            except Exception as e:
                print(f"Error publishing to MQTT for channel {channel_id}: {e}")

    def handle_incoming(self, packet, interface):
        channel_id = str(packet["rxChannel"])
        if channel_id in self.config:
            try:
                decoded = packet["decoded"]["payload"]
                self.publish_message(channel_id, decoded)
            except Exception as e:
                print(f"Error processing packet for MQTT: {e}")

    def onConnection(self, interface, connected):
        if connected:
            print("AMCB: Meshtastic connected.")
        else:
            print("AMCB: Meshtastic disconnected.")

def onReceive(packet, interface):
    amcb.handle_incoming(packet, interface)

def onConnection(interface, connected):
    amcb.onConnection(interface, connected)

def main():
    parser = argparse.ArgumentParser(description="Akita MQTT Channel Bridge Plugin")
    parser.add_argument("--config", default="mqtt_config.json", help="MQTT config file")
    args = parser.parse_args()

    interface = meshtastic.SerialInterface()
    global amcb
    amcb = AMCB(interface, args.config)
    interface.addReceiveCallback(onReceive)
    interface.addConnectionCallback(onConnection)

if __name__ == '__main__':
    main()
