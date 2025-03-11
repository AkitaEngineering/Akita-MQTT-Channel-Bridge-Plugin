import meshtastic
import time
import json
import paho.mqtt.client as mqtt
import argparse
import threading
import logging
from meshtastic.util import get_lora_config

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class AMCB:
    def __init__(self, interface, config_file="mqtt_config.json"):
        self.interface = interface
        self.config_file = config_file
        self.mqtt_clients = {}
        self.lora_config = get_lora_config(interface.meshtastic)
        self.load_config()
        self.connect_mqtt_servers()
        self.lock = threading.Lock()
        self.running = True

    def load_config(self):
        try:
            with open(self.config_file, "r") as f:
                self.config = json.load(f)
                self.validate_config()
        except FileNotFoundError:
            logging.error(f"Config file '{self.config_file}' not found.")
            self.config = {}
        except json.JSONDecodeError:
            logging.error(f"Error decoding config file '{self.config_file}'.")
            self.config = {}
        except ValueError as e:
            logging.error(f"Config validation error: {e}")
            self.config = {}

    def validate_config(self):
        for channel_id, mqtt_config in self.config.items():
            if not isinstance(mqtt_config, dict):
                raise ValueError(f"Invalid MQTT config for channel {channel_id}: must be a dictionary.")
            if "host" not in mqtt_config or "port" not in mqtt_config or "topic" not in mqtt_config:
                raise ValueError(f"Missing required keys in MQTT config for channel {channel_id}.")
            if not isinstance(mqtt_config["port"], int):
                raise ValueError(f"Invalid port number for channel {channel_id}: must be an integer.")

    def connect_mqtt_servers(self):
        for channel_id, mqtt_config in self.config.items():
            try:
                client = mqtt.Client(f"meshtastic_{channel_id}")
                client.on_connect = self.on_mqtt_connect
                client.on_disconnect = self.on_mqtt_disconnect
                if "username" in mqtt_config and "password" in mqtt_config:
                    client.username_pw_set(mqtt_config["username"], mqtt_config["password"])
                client.connect(mqtt_config["host"], mqtt_config["port"], 60)
                client.loop_start()
                with self.lock:
                    self.mqtt_clients[channel_id] = client
                logging.info(f"Connecting to MQTT for channel {channel_id}: {mqtt_config['host']}:{mqtt_config['port']}")
            except Exception as e:
                logging.error(f"Error connecting to MQTT for channel {channel_id}: {e}")

    def on_mqtt_connect(self, client, userdata, flags, rc):
        if rc == 0:
            logging.info(f"MQTT connected: {client._client_id}")
        else:
            logging.error(f"MQTT connection failed: {client._client_id}, rc={rc}")

    def on_mqtt_disconnect(self, client, userdata, rc):
        logging.info(f"MQTT disconnected: {client._client_id}, rc={rc}")

    def publish_message(self, channel_id, message):
        with self.lock:
            if channel_id in self.mqtt_clients:
                try:
                    mqtt_config = self.config[channel_id]
                    json_msg = json.dumps(message)
                    self.mqtt_clients[channel_id].publish(mqtt_config["topic"], json_msg)
                    logging.info(f"Published message to MQTT for channel {channel_id}: {mqtt_config['topic']}")
                except (json.JSONDecodeError, TypeError) as e:
                    logging.error(f"Error encoding message to JSON for channel {channel_id}: {e}")
                except Exception as e:
                    logging.error(f"Error publishing to MQTT for channel {channel_id}: {e}")

    def handle_incoming(self, packet, interface):
        channel_id = str(packet["rxChannel"])
        if channel_id in self.config:
            try:
                decoded = packet["decoded"]["payload"]
                self.publish_message(channel_id, decoded)
            except Exception as e:
                logging.error(f"Error processing packet for MQTT: {e}")

    def onConnection(self, interface, connected):
        if connected:
            logging.info("AMCB: Meshtastic connected.")
        else:
            logging.info("AMCB: Meshtastic disconnected.")
            self.stop()

    def stop(self):
        self.running = False
        with self.lock:
            for client in self.mqtt_clients.values():
                try:
                    client.disconnect()
                except Exception as e:
                    logging.error(f"Error disconnecting MQTT client: {e}")
            self.mqtt_clients.clear()

def onReceive(packet, interface):
    global amcb
    if amcb.running:
        amcb.handle_incoming(packet, interface)

def onConnection(interface, connected):
    global amcb
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

    try:
        while amcb.running:
            time.sleep(1)
    except KeyboardInterrupt:
        logging.info("AMCB: Stopping...")
        amcb.stop()
        logging.info("AMCB: Stopped")

if __name__ == '__main__':
    main()
