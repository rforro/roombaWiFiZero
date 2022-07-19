import argparse
import json
import logging
from datetime import datetime, timezone
from time import sleep
import signal
from threading import Thread, Event
import socketserver

import paho.mqtt.client as mqtt
from pyroombaadapter import PyRoombaAdapter
from roomba_json_base import json_base

TOPIC = "roomba"
MQTT_USER = "user"
MQTT_PASS = "1234"
SOFTWARE_VERSION = "0.0.1"
PARING_SERVER_PORT = 5678

remove_localIP = "192.168.142.77"


class RoombaFi(Thread):
    def __init__(self, _run_loop, _port, _name):
        super().__init__()
        self.run_loop = _run_loop

        self.doc = json.loads(json_base)
        del self.doc["state"]["reported"]["bin"]
        self.doc["state"]["reported"]["softwareVer"] = SOFTWARE_VERSION
        self.doc["state"]["reported"]["name"] = _name
        self.doc["state"]["reported"]["cap"]["pose"] = 0
        self.doc["state"]["reported"]["cleanMissionStatus"]["cycle"] = "none"
        self.doc["state"]["reported"]["cleanMissionStatus"]["sqft"] = 0

        self.mqtt = mqtt.Client(client_id=_name)
        self.mqtt.username_pw_set(MQTT_USER, MQTT_PASS)
        self.mqtt.on_message = self.on_message

        self.recv_cmd = ""
        self.port = _port

    def on_message(self, client, userdata, msg):
        print(msg.topic + " " + str(msg.payload))
        try:
            cmd_msg = json.loads(msg.payload)
            self.recv_cmd = cmd_msg["command"]
            self.doc["state"]["reported"]["lastCommand"]["command"] = cmd_msg["command"]
            self.doc["state"]["reported"]["lastCommand"]["time"] = cmd_msg["time"]
            self.doc["state"]["reported"]["lastCommand"]["initiator"] = cmd_msg["initiator"]
        except json.JSONDecodeError:
            logging.warning("Cannot decode received JSON payload")

    def _set_phase_stop(self):
        self.doc["state"]["reported"]["cleanMissionStatus"]["phase"] = "stop"
        self.doc["state"]["reported"]["cleanMissionStatus"]["mssnStrtTm"] = 0

    def start(self):
        try:
            adapter = PyRoombaAdapter(self.port)
        except ConnectionError:
            logging.error("Error cannot open serial connection")
            self.run_loop.set()
            raise SystemExit
        if adapter.request_voltage() == 0:
            logging.error("Roomba is probably turned off, cannot continue")
            self.run_loop.set()
            raise SystemExit
        adapter.change_mode_to_passive()
        adapter.start_data_stream(["Charging State", "Battery Charge", "Battery Capacity", "Current"])
        adapter.send_song_cmd(0, 9,
                              [69, 69, 69, 65, 72, 69, 65, 72, 69],
                              [40, 40, 40, 30, 10, 40, 30, 10, 80])
        self._set_phase_stop()

        try:
            self.mqtt.connect(remove_localIP, 1883, 60)
        except ConnectionRefusedError:
            logging.error("Cannot establish mqtt connection")
            self.run_loop.set()
            raise SystemExit
        self.mqtt.loop_start()
        self.mqtt.subscribe("cmd", 1)

        logging.info("RoombaFi initialized")
        while not self.run_loop.is_set():
            stream = adapter.read_data_stream()
            if len(stream) > 0:
                if stream[3] > -50:
                    # roomba is probably charging and docked as well
                    self.doc["state"]["reported"]["cleanMissionStatus"]["phase"] = "charging"
                    self.doc["state"]["reported"]["cleanMissionStatus"]["mssnStrtTm"] = 0
                self.doc["state"]["reported"]["batPct"] = int(100 * stream[1] / stream[2])
            else:
                logging.warning("Warning, stream is empty")

            if self.recv_cmd == "start" or self.recv_cmd == "resume":
                adapter.start_cleaning()
                self.doc["state"]["reported"]["cleanMissionStatus"]["phase"] = "run"
                self.doc["state"]["reported"]["cleanMissionStatus"]["mssnStrtTm"] = int(
                    datetime.now(timezone.utc).timestamp())
            elif self.recv_cmd == "stop" or self.recv_cmd == "pause":
                curr_phase = self.doc["state"]["reported"]["cleanMissionStatus"]["phase"]
                if curr_phase == "run" or curr_phase == "hmUsrDock":
                    adapter.start_cleaning()
                    self._set_phase_stop()
            elif self.recv_cmd == "dock":
                adapter.start_seek_dock()
                self.doc["state"]["reported"]["cleanMissionStatus"]["phase"] = "hmUsrDock"
            elif self.recv_cmd == "find":
                adapter.change_mode_to_safe()
                sleep(1)
                adapter.send_play_cmd(0)
                sleep(4)
                adapter.change_mode_to_passive()
                self._set_phase_stop()

            self.recv_cmd = ""
            self.mqtt.publish(TOPIC, json.dumps(self.doc), qos=1, retain=True)
            sleep(1)

        self.mqtt.disconnect()
        self.mqtt.loop_stop()
        adapter.stop_data_stream()


class MyUDPHandler(socketserver.DatagramRequestHandler):
    ROOMBA_MSG = None

    def handle(self):
        message = self.rfile.readline().strip()
        logging.debug("Client IP:", self.client_address[0], "sent msg:", message)
        try:
            if message.decode() == "irobotmcs":
                self.wfile.write(json.dumps(self.ROOMBA_MSG).encode())
        except UnicodeDecodeError:
            logging.warning("Error while decoding udp datagram")

    def finish(self):
        if self.client_address[0] != "0.0.0.0":
            self.socket.sendto(self.wfile.getvalue(), self.client_address)


class PairingServer(Thread):
    def __init__(self, _run_loop, name):
        super().__init__()
        self.run_loop = _run_loop
        roomba_server_msg = {"ver": "2",
                             "hostname": f"Roomba-{MQTT_USER}",  ## value after "-" is the blid
                             "robotname": name,
                             "ip": remove_localIP,
                             "mac": "xx:xx:xx:xx:xx:xx",
                             "sw": SOFTWARE_VERSION,
                             "sku": "R98----",
                             "proto": "mqtt",
                             "cap": {  # roombapy ignores this content
                                 "pose": 0,
                                 "ota": 2,
                                 "multiPass": 2,
                                 "pp": 0,
                                 "binFullDetect": 0,
                                 "langOta": 1,
                                 "maps": 0,
                                 "edge": 0,
                                 "eco": 0,
                                 "svcConf": 1
                             },
                             }

        class MyUDPHandlerParametrised(MyUDPHandler):
            ROOMBA_MSG = roomba_server_msg

        self.udp_server = socketserver.UDPServer((remove_localIP, PARING_SERVER_PORT), MyUDPHandlerParametrised)

    def run(self):
        logging.info("Paring UDP Server is up and listening")
        Thread(target=self.udp_server.serve_forever).start()
        self.run_loop.wait()
        self.udp_server.shutdown()


if __name__ == '__main__':
    run_loop = Event()


    def signal_term_handler(sigNum, frame):
        run_loop.set()


    signal.signal(signal.SIGTERM, signal_term_handler)
    signal.signal(signal.SIGINT, signal_term_handler)

    parser = argparse.ArgumentParser()
    parser.add_argument("serial", help="Serial connection COM or /dev/tty")
    parser.add_argument("-n", "--name", help="Name for roomba device", default="RoombaWifi")
    args = parser.parse_args()

    server = PairingServer(run_loop, args.name)
    server.start()

    roomba = RoombaFi(run_loop, args.serial, args.name)
    roomba.start()

## TODO raspi hostname has to be roomba-{MQTT_USER} small "r"
