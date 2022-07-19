# roombaWiFiZero

Proof of concept, emulation of the original Roomba firmware so it can be added to 3rd party Smarthome platforms, which offers support for new models WiFi Roomba.

## Motivation
Thanks to service port on Roombas, we can easily connect a Microcontroller and add WiFi controllability to older models. The currently offered solution uses an ESP8266 microcontroller which connects over MQTT to Homeassistant. This makes it not only incompatible with other home automation systems but makes it dependent on MQTT. If we could emulate the behaviour of modern Roombas WiFi on board using some microcontroller, we could achieve compatibility with virtually ani 3rd party smarthome system.

Following points have to be taken during implenation into account:

- The actual communication with Roomba is based on MQTT protocol. The Roomba vacuum runs an MQTT broker with TLS enabled. This has to be emulated.  
- UDP server which listens for broadcasts and expects the Roomba magic constant `irobotmcs`, has to run constantly. It provides blid (MQTT brokers username) and IP address to connect to. The rest of information (like Roombas capabilities) is basically worthless.

## Proposed solution
Install Mosquitto a MQTT broker into some microcomputer like Raspberry Pi and this Python script, which starts the UDP server for pairing and takes over the communication with Roomba vacuum.

## Hardware prerequisites
- Any Raspberry Pi or comparable microcomputer, preferably Raspberry Pi Zero 2 W
- Step-Down voltage regulator
- various Resistors


## How to install
foo bar

## Contributions
Any contributions to this project are welcomed, just create a PR.

## Thanks to
- Atsushi Sakai who wrote [PyRoombaAdapter](https://github.com/AtsushiSakai/PyRoombaAdapter)
