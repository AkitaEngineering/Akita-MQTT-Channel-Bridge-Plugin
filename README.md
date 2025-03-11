# Akita MQTT Channel Bridge Plugin (AMCB)

AMCB is a Meshtastic plugin that bridges Meshtastic channels with MQTT servers, allowing each channel to publish data to a different MQTT topic.

## Features

* **Channel-Specific MQTT:** Allows each Meshtastic channel to have its own MQTT server and topic.
* **Configurable MQTT Settings:** Loads MQTT settings from a JSON configuration file.
* **Automatic MQTT Connection:** Automatically connects to MQTT servers on startup.
* **Message Publishing:** Publishes Meshtastic messages to the configured MQTT topics.
* **Robust Error Handling:** Includes error handling for file I/O, MQTT connections, JSON encoding, and message publishing.
* **Configuration Validation:** Validates the MQTT configuration data to prevent runtime errors.
* **MQTT Authentication:** Supports MQTT authentication (username and password).
* **Graceful MQTT Disconnection:** Gracefully closes MQTT connections when the plugin is stopped.
* **Keyboard Interrupt Handling:** Handles keyboard interrupts for graceful plugin shutdown.
* **Thread Safety:** Uses locks to ensure thread safety when accessing shared resources.
* **Respects TX Delay (Partial):** Gets the LoRa config, queueing to respect TX delay would require more significant changes.

## Installation

1.  Place `amcb.py` in your Meshtastic plugins directory.
2.  Create an `mqtt_config.json` file with your MQTT settings.
3.  Install the required Python packages: `meshtastic`, `paho-mqtt`.
4.  Run Meshtastic with the plugin enabled.

## Usage

1.  Configure MQTT settings in `mqtt_config.json`.
2.  Meshtastic messages are automatically published to the corresponding MQTT topics.
3.  Use Ctrl+C to stop the plugin gracefully.

## Configuration (`mqtt_config.json`)

Each channel ID is a key in the JSON object. Each channel's configuration includes:

* `host`: The MQTT server hostname or IP address.
* `port`: The MQTT server port.
* `topic`: The MQTT topic to publish messages to.
* `username` (optional): The MQTT username.
* `password` (optional): The MQTT password.

Example `mqtt_config.json`:

```json
{
    "0": {
        "host": "[mqtt.example.com](https://www.google.com/search?q=mqtt.example.com)",
        "port": 1883,
        "topic": "meshtastic/channel0"
    },
    "1": {
        "host": "[mqtt.example.com](https://www.google.com/search?q=mqtt.example.com)",
        "port": 1883,
        "topic": "meshtastic/channel1",
        "username": "mqttuser",
        "password": "mqttpassword"
    }
}
