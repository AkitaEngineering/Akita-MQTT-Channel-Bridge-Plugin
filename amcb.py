import meshtastic
import meshtastic.plugin
from meshtastic.BROADCAST_ADDR import BROADCAST_ADDR # For sending to all
from meshtastic.util import ps_packet # Potentially useful

import paho.mqtt.client as mqtt
import json
import time
import threading
import logging
import os
import ssl # For TLS context

# Configure logging for the plugin
logger = logging.getLogger(__name__)
if not logger.handlers: # Ensure handler is set up
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

CONFIG_FILENAME = "mqtt_config.json"

class AMCBPlugin(meshtastic.plugin.Plugin):
    """
    Akita MQTT Channel Bridge Plugin (AMCB) - Enhanced
    Bridges Meshtastic channels with MQTT, including bi-directional text messages.
    """

    def __init__(self):
        super().__init__()
        self.mqtt_clients = {}
        self.mqtt_configs = {}
        self.config_lock = threading.Lock()
        self.lora_config = None
        self.running = True
        self.mesh_interface = None # To store the Meshtastic radio interface for sending

        self.plugin_dir = os.path.dirname(os.path.abspath(__file__))
        self.config_file_path = os.path.join(self.plugin_dir, CONFIG_FILENAME)
        if not os.path.exists(self.config_file_path):
            self.config_file_path = os.path.join(os.getcwd(), CONFIG_FILENAME)

    def load_config(self):
        with self.config_lock:
            try:
                logger.info(f"Attempting to load MQTT configuration from: {self.config_file_path}")
                if not os.path.exists(self.config_file_path):
                    logger.error(f"Configuration file {self.config_file_path} not found.")
                    self.mqtt_configs = {}
                    return False

                with open(self.config_file_path, 'r') as f:
                    loaded_json = json.load(f)

                if not isinstance(loaded_json, dict):
                    logger.error("MQTT config root must be a JSON object.")
                    self.mqtt_configs = {}
                    return False

                valid_configs = {}
                for channel_id_str, settings in loaded_json.items():
                    if channel_id_str.startswith("//"): continue # Allow comments

                    # Basic validation
                    if not all(k in settings for k in ["host", "port", "topic"]):
                        logger.warning(f"Skipping channel '{channel_id_str}': missing host, port, or topic.")
                        continue
                    # Further type validation can be added here for new fields

                    try:
                        int(channel_id_str) # Validate channel_id_str is a number
                    except ValueError:
                        logger.warning(f"Skipping channel '{channel_id_str}': Channel ID must be a string representing an integer.")
                        continue
                    
                    # Validate payload_type
                    settings['payload_type'] = settings.get('payload_type', 'full_packet')
                    if settings['payload_type'] not in ['full_packet', 'decoded_only', 'text_payload_only']:
                        logger.warning(f"Channel '{channel_id_str}': Invalid payload_type '{settings['payload_type']}'. Defaulting to 'full_packet'.")
                        settings['payload_type'] = 'full_packet'

                    # Validate TLS settings (basic existence check)
                    if "tls" in settings and not isinstance(settings["tls"], dict):
                        logger.warning(f"Channel '{channel_id_str}': TLS config must be an object. Disabling TLS for this channel.")
                        del settings["tls"]
                    
                    # Validate Will settings
                    if "will" in settings and (not isinstance(settings["will"], dict) or "topic" not in settings["will"]):
                        logger.warning(f"Channel '{channel_id_str}': 'will' config is invalid. Disabling for this channel.")
                        del settings["will"]

                    # Validate mqtt_to_meshtastic settings
                    if "mqtt_to_meshtastic" in settings:
                        m2m_conf = settings["mqtt_to_meshtastic"]
                        if not isinstance(m2m_conf, dict) or "subscribe_topic" not in m2m_conf:
                            logger.warning(f"Channel '{channel_id_str}': 'mqtt_to_meshtastic' config invalid. Disabling for this channel.")
                            del settings["mqtt_to_meshtastic"]
                        else:
                            # Default target_channel_index to the bridge's channel if not specified
                            if "target_channel_index" not in m2m_conf:
                                m2m_conf["target_channel_index"] = int(channel_id_str)


                    valid_configs[channel_id_str] = settings
                
                self.mqtt_configs = valid_configs
                logger.info(f"Successfully loaded {len(self.mqtt_configs)} MQTT configurations.")
                return True

            except Exception as e:
                logger.error(f"Error loading MQTT config: {e}", exc_info=True)
                self.mqtt_configs = {}
            return False

    def connect_mqtt_clients(self):
        with self.config_lock:
            if not self.mqtt_configs:
                logger.info("No MQTT configurations, skipping client connections.")
                return

            for channel_id_str, config in self.mqtt_configs.items():
                if channel_id_str in self.mqtt_clients and self.mqtt_clients[channel_id_str].is_connected():
                    continue # Already connected

                if channel_id_str in self.mqtt_clients: # Cleanup old, disconnected client
                    try:
                        self.mqtt_clients[channel_id_str].loop_stop(force=True) # Stop previous loop
                        self.mqtt_clients[channel_id_str].disconnect()
                    except: pass # Ignore errors during cleanup
                    del self.mqtt_clients[channel_id_str]


                client_id = f"meshtastic-amcb-{channel_id_str}-{int(time.time())}"
                try:
                    if hasattr(mqtt, 'CallbackAPIVersion'): # Paho MQTT v2.x+
                        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, client_id=client_id)
                    else: # Paho MQTT v1.x
                        client = mqtt.Client(client_id=client_id)

                    if "username" in config and "password" in config:
                        client.username_pw_set(config["username"], config["password"])

                    # TLS Configuration
                    if "tls" in config and isinstance(config["tls"], dict):
                        tls_config = config["tls"]
                        ca_certs = tls_config.get("ca_certs")
                        certfile = tls_config.get("certfile")
                        keyfile = tls_config.get("keyfile")
                        
                        if ca_certs or certfile or keyfile: # Only call tls_set if any path is provided
                            try:
                                client.tls_set(ca_certs=ca_certs,
                                               certfile=certfile,
                                               keyfile=keyfile,
                                               cert_reqs=ssl.CERT_REQUIRED if ca_certs else ssl.CERT_NONE,
                                               tls_version=ssl.PROTOCOL_TLS_CLIENT)
                                logger.info(f"Channel '{channel_id_str}': TLS configured. CA: {ca_certs is not None}, Cert/Key: {certfile is not None}")
                            except Exception as e_tls:
                                logger.error(f"Channel '{channel_id_str}': Failed to set TLS: {e_tls}", exc_info=True)


                    # Will Configuration
                    if "will" in config and isinstance(config["will"], dict) and "topic" in config["will"]:
                        will_cfg = config["will"]
                        client.will_set(topic=will_cfg["topic"],
                                        payload=will_cfg.get("payload", "offline"),
                                        qos=will_cfg.get("qos", 0),
                                        retain=will_cfg.get("retain", False))
                        logger.info(f"Channel '{channel_id_str}': MQTT Will configured for topic '{will_cfg['topic']}'.")


                    client.on_connect = self._on_mqtt_connect(channel_id_str, config)
                    client.on_disconnect = self._on_mqtt_disconnect(channel_id_str, config["host"])
                    
                    # Setup for MQTT-to-Meshtastic if configured
                    if "mqtt_to_meshtastic" in config:
                        client.on_message = self._on_message_from_mqtt(channel_id_str)

                    logger.info(f"Connecting to MQTT for channel '{channel_id_str}': {config['host']}:{config['port']}")
                    client.connect(config["host"], config["port"], keepalive=60)
                    client.loop_start()
                    self.mqtt_clients[channel_id_str] = client
                except Exception as e:
                    logger.error(f"Failed to connect MQTT for channel '{channel_id_str}': {e}", exc_info=True)

    def _on_mqtt_connect(self, channel_id_str, bridge_config):
        def on_connect_callback(client, userdata, flags, rc, properties=None):
            if rc == 0:
                logger.info(f"Successfully connected to MQTT for channel '{channel_id_str}' on {bridge_config['host']}.")
                # Publish "online" status if Will is configured
                if "will" in bridge_config and "topic" in bridge_config["will"]:
                    will_cfg = bridge_config["will"]
                    online_payload = will_cfg.get("online_payload", "online")
                    try:
                        client.publish(will_cfg["topic"], online_payload, 
                                       qos=will_cfg.get("qos", 0), retain=will_cfg.get("retain", False))
                        logger.info(f"Channel '{channel_id_str}': Published '{online_payload}' status to '{will_cfg['topic']}'.")
                    except Exception as e_pub:
                        logger.warning(f"Channel '{channel_id_str}': Could not publish online status: {e_pub}")
                
                # Subscribe for MQTT-to-Meshtastic
                if "mqtt_to_meshtastic" in bridge_config:
                    m2m_conf = bridge_config["mqtt_to_meshtastic"]
                    sub_topic = m2m_conf["subscribe_topic"]
                    sub_qos = bridge_config.get("qos", 0) # Use bridge's main QoS for subscription
                    try:
                        client.subscribe(sub_topic, qos=sub_qos)
                        logger.info(f"Channel '{channel_id_str}': Subscribed to MQTT topic '{sub_topic}' (QoS {sub_qos}) for MQTT-to-Meshtastic.")
                    except Exception as e_sub:
                        logger.error(f"Channel '{channel_id_str}': Failed to subscribe to '{sub_topic}': {e_sub}", exc_info=True)
            else:
                reason = mqtt.connack_string(rc) if hasattr(mqtt, 'connack_string') else f"Code {rc}"
                logger.error(f"MQTT connection failed for channel '{channel_id_str}': {reason}")
        return on_connect_callback

    def _on_mqtt_disconnect(self, channel_id_str, host):
        def on_disconnect_callback(client, userdata, rc, properties=None):
            if rc == 0:
                logger.info(f"Gracefully disconnected from MQTT for channel '{channel_id_str}' on {host}.")
            else:
                logger.warning(f"Unexpectedly disconnected from MQTT for channel '{channel_id_str}' on {host}. Code: {rc}. Will attempt to reconnect.")
        return on_disconnect_callback

    def _on_message_from_mqtt(self, src_channel_id_str):
        """Callback for when an MQTT message is received for forwarding to Meshtastic."""
        def on_message_callback(client, userdata, msg):
            try:
                logger.info(f"MQTT message received on topic '{msg.topic}' for bridge channel '{src_channel_id_str}'")
                payload_str = msg.payload.decode('utf-8', errors='replace').strip()
                
                if not payload_str:
                    logger.info("Received empty MQTT payload, not sending to Meshtastic.")
                    return

                if not self.mesh_interface:
                    logger.warning("Mesh interface not available, cannot send MQTT message to Meshtastic.")
                    return

                with self.config_lock: # Access config safely
                    bridge_config = self.mqtt_configs.get(src_channel_id_str)
                    if not bridge_config or "mqtt_to_meshtastic" not in bridge_config:
                        logger.warning(f"No valid MQTT-to-Meshtastic config for bridge '{src_channel_id_str}'. Ignoring MQTT message.")
                        return
                    m2m_config = bridge_config["mqtt_to_meshtastic"]

                target_channel_index = m2m_config.get("target_channel_index", int(src_channel_id_str))
                destination_id = m2m_config.get("target_node_id") or BROADCAST_ADDR # Default to broadcast if null/empty

                # Limit payload length for safety, Meshtastic has packet size limits
                max_len = 200 # Conservative limit
                if len(payload_str) > max_len:
                    payload_str_short = payload_str[:max_len] + "..."
                    logger.warning(f"MQTT payload too long ({len(payload_str)} bytes), truncating to {max_len} for Meshtastic: '{payload_str_short}'")
                    payload_str = payload_str[:max_len]
                else:
                    payload_str_short = payload_str

                logger.info(f"Sending to Meshtastic: '{payload_str_short}' (Dest: '{destination_id}', ChanIdx: {target_channel_index})")
                
                # Make sure mesh_interface is valid and has sendText
                if hasattr(self.mesh_interface, 'sendText'):
                    self.mesh_interface.sendText(
                        text=payload_str,
                        destinationId=destination_id,
                        channelIndex=target_channel_index
                        # wantAck=True could be an option too
                    )
                    logger.debug(f"Message forwarded to Meshtastic network via sendText.")
                else:
                    logger.error("mesh_interface does not have sendText method or is not initialized properly.")

            except Exception as e:
                logger.error(f"Error processing MQTT message for Meshtastic (topic '{msg.topic}'): {e}", exc_info=True)
        return on_message_callback


    def onReceive(self, packet, interface): # Meshtastic to MQTT
        if not self.running: return
        # Store interface if not already stored (needed for sending)
        if not self.mesh_interface and hasattr(interface, '_meshInterface') and interface._meshInterface:
            self.mesh_interface = interface._meshInterface

        logger.debug(f"Raw packet received for MQTT bridge: {packet}")
        if not packet: return

        channel_index = packet.get('channel_index')
        if channel_index is None and packet.get('decoded', {}).get('portnum') not in ['UNKNOWN_APP', None, 0]:
            if packet.get('to') == 0xFFFFFFFF: # BROADCAST_ADDR_INT
                channel_index = 0 # Default to primary for general broadcasts if channel is unclear
            else:
                logger.debug(f"Packet channel index undetermined, not a clear broadcast. Ignoring for MQTT. Pkt: {packet}")
                return
        elif channel_index is None:
            logger.debug(f"Packet channel index undetermined or not user data. Ignoring. Pkt: {packet}")
            return

        channel_id_str = str(channel_index)
        
        with self.config_lock:
            if channel_id_str not in self.mqtt_configs:
                return # No config for this channel
            mqtt_config = self.mqtt_configs[channel_id_str]
            if channel_id_str not in self.mqtt_clients or not self.mqtt_clients[channel_id_str].is_connected():
                logger.warning(f"MQTT client for channel '{channel_id_str}' not ready. Message not sent.")
                return
        
        client = self.mqtt_clients[channel_id_str]
        topic = mqtt_config["topic"]
        qos = mqtt_config.get("qos", 0)
        retain = mqtt_config.get("retain", False)
        payload_type = mqtt_config.get("payload_type", "full_packet")

        try:
            payload_to_publish = None
            if payload_type == "decoded_only":
                payload_to_publish = packet.get('decoded', {})
            elif payload_type == "text_payload_only":
                decoded_part = packet.get('decoded', {})
                if decoded_part.get('portnum') == 'TEXT_MESSAGE_APP' and 'text' in decoded_part:
                    payload_to_publish = decoded_part['text']
                else:
                    payload_to_publish = decoded_part # Fallback
            else: # "full_packet"
                payload_to_publish = packet
            
            if isinstance(payload_to_publish, str):
                message_payload = payload_to_publish.encode('utf-8') # MQTT Paho expects bytes
            else:
                def json_serializer(obj):
                    if isinstance(obj, bytes): return obj.hex()
                    if hasattr(obj, 'DESCRIPTOR'): return str(obj) # Basic protobuf obj handling
                    if isinstance(obj, (int, float, str, list, dict, bool, type(None))): return obj
                    return str(obj) # Fallback for other types
                message_payload = json.dumps(payload_to_publish, default=json_serializer).encode('utf-8')

        except Exception as e:
            logger.error(f"Could not serialize packet for MQTT (channel '{channel_id_str}'): {e}", exc_info=True)
            return

        try:
            logger.info(f"Publishing from Meshtastic chan {channel_index} to MQTT '{topic}' (QoS {qos}, Retain {retain})")
            logger.debug(f"MQTT Payload ({payload_type}) for topic '{topic}': {message_payload.decode('utf-8', 'replace')[:150]}...")
            client.publish(topic, message_payload, qos=qos, retain=retain)
        except Exception as e:
            logger.error(f"Failed to publish to MQTT for channel '{channel_id_str}': {e}", exc_info=True)

    def onConnection(self, interface, topic=None): # Called when radio connects/disconnects
        if hasattr(interface, '_meshInterface') and interface._meshInterface:
            self.mesh_interface = interface._meshInterface # Store for sending
            radio_interface = interface._meshInterface
            if hasattr(radio_interface, 'localNode') and radio_interface.localNode.localConfig:
                logger.info("Meshtastic radio connected. AMCB plugin initializing components.")
                if radio_interface.localNode.has_lora_config:
                    self.lora_config = radio_interface.localNode.lora_config
                    logger.info(f"LoRa Config: Region {self.lora_config.region}, Modem Preset {self.lora_config.modem_preset.name if hasattr(self.lora_config.modem_preset, 'name') else self.lora_config.modem_preset}")
                if self.load_config():
                    self.connect_mqtt_clients()
                return # Successfully handled connection

        # If we reach here, it's likely a disconnect or unable to get meshInterface fully
        is_connected_check = self.mesh_interface and hasattr(self.mesh_interface, 'myInfo') and self.mesh_interface.myInfo is not None
        if not is_connected_check:
            logger.info("Meshtastic radio appears disconnected or not fully initialized.")
            # MQTT clients handle their own reconnections. Explicit disconnects happen in stop().


    def stop(self):
        logger.info("Stopping AMCB Plugin. Disconnecting MQTT clients...")
        self.running = False
        with self.config_lock:
            for channel_id_str, client in self.mqtt_clients.items():
                if client:
                    try:
                        # Publish "offline" will message manually if client is still connected
                        # This is a good gesture but the broker handles the LWT if disconnect is abrupt
                        config = self.mqtt_configs.get(channel_id_str)
                        if config and "will" in config and client.is_connected():
                             will_cfg = config["will"]
                             logger.info(f"Publishing final 'offline' status for channel {channel_id_str} to topic {will_cfg['topic']}")
                             client.publish(will_cfg["topic"], will_cfg.get("payload", "offline"), 
                                            qos=will_cfg.get("qos",0), retain=will_cfg.get("retain", False))
                             time.sleep(0.1) # Brief pause to allow publish

                        client.loop_stop()
                        client.disconnect()
                    except Exception as e:
                        logger.error(f"Error disconnecting MQTT client for channel '{channel_id_str}': {e}", exc_info=True)
            self.mqtt_clients.clear()
        logger.info("AMCB Plugin stopped.")

def createPlugin():
    return AMCBPlugin()

# Standalone Test Block
if __name__ == "__main__":
    log_level = logging.DEBUG
    logging.basicConfig(level=log_level, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger.setLevel(log_level)

    logger.info("AMCB Plugin standalone test mode.")
    
    # IMPORTANT: For actual testing, create a 'mqtt_config.json' next to this script
    # with valid broker details. The example below is conceptual.
    # The plugin will try to load 'mqtt_config.json' from its directory or CWD.
    # Ensure your test mqtt_config.json uses unique topics on public brokers.
    # Example test_config_content (ideally, put this in mqtt_config.json for testing):
    # {
    #     "0": {
    #         "host": "test.mosquitto.org", "port": 1883, "topic": "meshtastic/amcb/test/your_id/ch0/tomqtt",
    #         "qos": 0, "retain": false, "payload_type": "decoded_only",
    #         "will": {"topic": "meshtastic/amcb/test/your_id/ch0/status", "payload": "offline_test", "online_payload": "online_test", "qos": 1, "retain": true},
    #         "mqtt_to_meshtastic": {"subscribe_topic": "meshtastic/amcb/test/your_id/ch0/frommqtt", "target_channel_index": 0}
    #     }
    # }
    # print("Please create a valid mqtt_config.json for standalone testing.")


    plugin_instance = AMCBPlugin()

    class MockMeshInterface: # Basic mock for testing sendText
        def __init__(self):
            self.myInfo = {'my_node_num': 12345678} # Dummy node number
            self.localNode = self # Simplified
            self.has_lora_config = False
            self.lora_config = None
            self.localConfig = True # Mock that config is present

        def sendText(self, text, destinationId=BROADCAST_ADDR, channelIndex=0):
            logger.info(f"[MockMeshInterface.sendText] To: {destinationId}, Chan: {channelIndex}, Text: '{text}'")
            return True # Simulate success

    class MockInterface: # PubSub interface mock
         def __init__(self):
            self._meshInterface = MockMeshInterface()

    logger.info("Simulating radio connection...")
    plugin_instance.onConnection(interface=MockInterface()) # Load config, connect MQTT

    logger.info("Waiting for MQTT connections (5s)...")
    time.sleep(5)

    # Simulate Meshtastic to MQTT
    dummy_packet_ch0 = {
        'fromId': '!dummyuser1', 'toId': '^all', 'channel_index': 0,
        'decoded': {'portnum': 'TEXT_MESSAGE_APP', 'text': 'Hello MQTT from Meshtastic (test ch0)!'}
    }
    logger.info("Simulating Meshtastic packet to MQTT (channel 0)...")
    plugin_instance.onReceive(packet=dummy_packet_ch0, interface=MockInterface())
    time.sleep(1)

    # Simulate MQTT to Meshtastic (if configured in your test mqtt_config.json)
    # This requires an external MQTT client to publish to the 'subscribe_topic'
    logger.info("To test MQTT-to-Meshtastic, publish a message to the configured 'subscribe_topic'.")
    logger.info("Example: mosquitto_pub -h your_broker -t your_subscribe_topic -m 'Hello Meshtastic from MQTT'")
    
    logger.info("Standalone test running for 60s. Press Ctrl+C to stop early.")
    try:
        time.sleep(60)
    except KeyboardInterrupt:
        logger.info("Test interrupted.")
    finally:
        logger.info("Stopping plugin simulation...")
        plugin_instance.stop()
        logger.info("Test finished.")
