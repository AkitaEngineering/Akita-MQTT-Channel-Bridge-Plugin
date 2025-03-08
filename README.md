# Akita MQTT Channel Bridge Plugin (AMCB)

AMCB is a Meshtastic plugin that bridges Meshtastic channels with MQTT servers, allowing each channel to publish data to a different MQTT topic.

## Features

-   **Channel-Specific MQTT:** Allows each Meshtastic channel to have its own MQTT server and topic.
-   **Configurable MQTT Settings:** Loads MQTT settings from a JSON configuration file.
-   **Automatic MQTT Connection:** Automatically connects to MQTT servers on startup.
-   **Message Publishing:** Publishes Meshtastic messages to the configured MQTT topics.
-   **Robust Error Handling:** Includes error handling for file I/O, MQTT connections, and message publishing.
-   **Respects TX Delay:** The plugin will respect the TX delay of the LoRa configuration.

## Installation

1.  Place `amcb.py` in your Meshtastic plugins directory.
2.  Create an `mqtt_config.json` file with your MQTT settings.
3.  Run Meshtastic with the plugin enabled.

## Usage

-   Configure MQTT settings in `mqtt_config.json`.
-   Meshtastic messages are automatically published to the corresponding MQTT topics.

## Configuration (mqtt_config.json)

-   Each channel ID is a key in the JSON object.
-   Each channel's configuration includes:
    -   `host`: The MQTT server hostname or IP address.
    -   `port`: The MQTT server port.
    -   `topic`: The MQTT topic to publish messages to.

## Command-Line Arguments

-   `--config`: Specifies the MQTT configuration file (default: `mqtt_config.json`).

## Dependencies

-   Meshtastic Python API
-   paho-mqtt

## Akita Engineering
This project is developed and maintained by Akita Engineering. We are dedicated to creating innovative solutions for LoRa and Meshtastic networks.
