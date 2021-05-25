# roombaWiFiZero

Proof of concept of emulating the original Roomba firmware. Thanks to service port on roombas, we can easily add WiFi to older models. The currently preffered method is to flash custom firmware into some microcontroller like esp8266 and connect to Homeassistant over MQTT. This makes it incompatible with other home automation systems. If we could emulate the behaviour of roombas with wifi using some microcontroller, we could achieve compatibility with virtually ani 3rd party software.
