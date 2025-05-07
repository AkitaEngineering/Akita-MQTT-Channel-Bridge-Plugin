# Akita MQTT Channel Bridge Plugin (AMCB) for Meshtastic


The Akita MQTT Channel Bridge Plugin (AMCB) is an advanced plugin for Meshtastic devices. It allows each Meshtastic channel to publish data to, and optionally receive text messages from, different MQTT servers and topics. This enables highly flexible integration of your mesh network with private servers, IoT platforms, and other backend systems.

## Features

AMCB extends Meshtastic's capabilities with the following features:

* **Channel-Specific MQTT Bridging (Meshtastic -> MQTT):** Each Meshtastic channel can be independently configured to send data to a unique MQTT broker and topic.
* **Bi-directional Text Message Bridging (MQTT -> Meshtastic):** Configure specific MQTT topics to listen on; messages published to these topics will be sent as text messages to your Meshtastic network (either broadcast on a channel or as a Direct Message).
* **Flexible MQTT Server & Topic Configuration:** Easily define MQTT connection parameters (host, port, topic) for each direction.
* **MQTT Authentication:** Supports username and password authentication for MQTT brokers.
* **Configurable MQTT QoS & Retain Flags:** Set MQTT Quality of Service (QoS 0, 1, 2) and the retain flag for messages published from Meshtastic to MQTT.
* **Customizable Payload Format (Meshtastic -> MQTT):** Choose how Meshtastic packet data is formatted for MQTT:
    * `full_packet`: The entire Meshtastic packet dictionary.
    * `decoded_only`: Only the `decoded` portion of the packet.
    * `text_payload_only`: For text messages, sends only the raw text content; for other packet types, falls back to `decoded_only`.
* **Secure MQTT Connections with TLS/SSL:** Configure TLS for encrypted communication with your MQTT broker, including support for CA certificates and client certificate authentication.
* **MQTT Last Will & Testament (LWT) Support:** For each MQTT bridge, configure a "Will" message to be published by the broker if the plugin disconnects unexpectedly. An "online" status message can also be published upon successful connection.
* **Robust Error Handling & Logging:** Comprehensive error handling for file I/O, MQTT connections, JSON processing, and message publishing, with detailed logging.
* **External JSON Configuration:** All MQTT settings are loaded from an `mqtt_config.json` file, making management straightforward.
* **Thread Safety:** Utilizes locks to ensure safe concurrent access to shared resources.
* **Graceful Shutdown:** Ensures MQTT connections are properly closed when the plugin is stopped or Meshtastic shuts down.
* **Respects TX Delay (Partial):** The plugin retrieves the LoRa configuration. Full dynamic queueing to precisely match TX delay for outgoing MQTT-to-Meshtastic messages would require more significant changes to interact deeply with the Meshtastic core transmit queue.

## Why AMCB?

* **Integrate Meshtastic with Existing Infrastructure:** Seamlessly pipe Meshtastic data into systems like Home Assistant, Node-RED, InfluxDB, Grafana, or custom applications.
* **Private Data Handling:** Send your mesh data to your own private MQTT servers, ensuring data privacy and control.
* **Remote Interaction:** Send simple text commands or notifications from your MQTT-enabled systems back into your Meshtastic network.
* **Multi-Channel Segregation:** Keep data from different Meshtastic channels (e.g., public, private, testing) completely separate at the MQTT level.
* **Enhanced Reliability:** Features like LWT and configurable QoS improve the robustness of your data bridge.

## Installation

1. **Place Plugin File:**  
   Place the `amcb.py` file into your Meshtastic plugins directory. The location of this directory can vary depending on your Meshtastic installation (e.g., for `meshtastic-python` CLI, it might be a `plugins` subdirectory in your working directory or a user-specific path). Please refer to the official Meshtastic documentation for plugin locations.

2. **Create Configuration File:**  
   Create an `mqtt_config.json` file in the same directory as `amcb.py` (or in the current working directory where Meshtastic is run). You can copy `mqtt_config.json.example` to `mqtt_config.json` and modify it.

3. **Install Dependencies:**  
   Ensure you have the necessary Python packages installed. The plugin requires `meshtastic` (which you should already have) and `paho-mqtt`.

    ```bash
    pip install paho-mqtt
    ```

    If you are managing dependencies with a `requirements.txt` file for your Meshtastic environment, add `paho-mqtt` to it.

4. **Run Meshtastic:**  
   Start Meshtastic with plugins enabled (this is usually the default behavior). The AMCB plugin will be loaded automatically.

## Configuration (`mqtt_config.json`)

The `mqtt_config.json` file defines how each Meshtastic channel interacts with MQTT. The file consists of a main JSON object where each key is a string representing the Meshtastic **channel index** (e.g., `"0"` for the Primary channel, `"1"` for Secondary, etc.).

Each channel configuration object can contain the following fields:

### General Meshtastic-to-MQTT Settings:

* `host` (string, required): The MQTT server hostname or IP address.
* `port` (integer, required): The MQTT server port (e.g., 1883 for unencrypted, 8883 for TLS).
* `topic` (string, required): The MQTT topic to publish Meshtastic messages to for this channel.
* `username` (string, optional): The MQTT username for authentication.
* `password` (string, optional): The MQTT password for authentication.
* `qos` (integer, optional, default: `0`): The MQTT Quality of Service level (0, 1, or 2) for messages published to MQTT.
* `retain` (boolean, optional, default: `false`): The MQTT retain flag for messages published to MQTT.
* `payload_type` (string, optional, default: `"full_packet"`): Defines the format of the Meshtastic data published to MQTT.
    * `"full_packet"`: Sends the complete Meshtastic packet dictionary as JSON.
    * `"decoded_only"`: Sends only the `decoded` part of the Meshtastic packet as JSON.
    * `"text_payload_only"`: If the Meshtastic packet is a text message, its raw text content is sent. For other packet types, it falls back to sending the `decoded` part.

### TLS/SSL Configuration (Optional):

* `tls` (object, optional): Contains settings for enabling TLS/SSL encrypted MQTT connections.
    * `ca_certs` (string, optional): Path to the Certificate Authority (CA) certificate file for server verification.
    * `certfile` (string, optional): Path to the client's SSL certificate file (if using client certificate authentication).
    * `keyfile` (string, optional): Path to the client's SSL private key file (if using client certificate authentication).
    * *Note:* If `ca_certs` is provided, server certificate validation is enabled. If `certfile` and `keyfile` are provided, client certificate authentication is attempted.

### MQTT Last Will & Testament (LWT) Configuration (Optional):

* `will` (object, optional): Configures the MQTT LWT for this bridge.
    * `topic` (string, required if `will` object is present): The MQTT topic for the LWT message.
    * `payload` (string, optional, default: `"offline"`): The payload of the LWT message.
    * `qos` (integer, optional, default: `0`): The QoS for the LWT message.
    * `retain` (boolean, optional, default: `false`): The retain flag for the LWT message.
    * `online_payload` (string, optional, default: `"online"`): A payload to publish to the `will.topic` when the plugin successfully connects to MQTT.

### MQTT-to-Meshtastic Bridging Configuration (Optional):

* `mqtt_to_meshtastic` (object, optional): Configures the bridge to receive messages from MQTT and send them to Meshtastic.
    * `subscribe_topic` (string, required if `mqtt_to_meshtastic` object is present): The MQTT topic the plugin will subscribe to for receiving messages destined for Meshtastic.
    * `target_channel_index` (integer, optional): The Meshtastic channel index on which to send the received MQTT message. If omitted, defaults to the current bridge's channel index (e.g., if this config is under `"0"`, it defaults to channel 0).
    * `target_node_id` (string, optional): The Meshtastic Node ID (e.g., `"!yournodeid"`) to send the message to as a Direct Message. If `null`, empty, or omitted, the message is broadcast on the `target_channel_index`.

### Example `mqtt_config.json`:

```json
{
    "0": {
        "host": "your.primary-broker.com",
        "port": 1883,
        "topic": "meshtastic/channel0/to_mqtt",
        "username": "user0",
        "password": "password0",
        "qos": 1,
        "retain": false,
        "payload_type": "decoded_only",
        "will": {
            "topic": "meshtastic/bridge/channel0/status",
            "payload": "channel0_bridge_offline",
            "qos": 1,
            "retain": true,
            "online_payload": "channel0_bridge_online"
        },
        "mqtt_to_meshtastic": {
            "subscribe_topic": "meshtastic/channel0/from_mqtt",
            "target_channel_index": 0
        }
    },
    "1": {
        "host": "secure.secondary-broker.org",
        "port": 8883,
        "topic": "meshtastic/channel1/uplink",
        "qos": 2,
        "payload_type": "full_packet",
        "tls": {
            "ca_certs": "/etc/ssl/certs/ca-bundle.crt",
            "certfile": "/opt/meshtastic/certs/client.pem",
            "keyfile": "/opt/meshtastic/certs/client.key"
        },
        "mqtt_to_meshtastic": {
            "subscribe_topic": "meshtastic/channel1/send_dm_to_device",
            "target_node_id": "!abcdef12",
            "target_channel_index": 0 
        }
    },
    "//": "This is a comment line: Channel keys must be strings of channel indices.",
    "//": "For mqtt_to_meshtastic, target_node_id: null or omit for broadcast.",
    "//": "If target_node_id is set, target_channel_index specifies which channel settings..."
}
```

