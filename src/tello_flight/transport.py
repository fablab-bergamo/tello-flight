"""Plain UDP transport and a deterministic, hardware-free drone simulator."""

import logging
import socket
import time

from .model import Connection

LOG = logging.getLogger(__name__)


class UDPTransport:
    def __init__(self, config: Connection):
        self.config = config
        self.command = None
        self.state = None

    def open(self):
        # A new source port per session keeps old replies out of a new session.
        try:
            self.command = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.command.bind((self.config.local_address, 0))
            self.command.connect((self.config.host, self.config.command_port))
            self.command.setblocking(False)
            self.state = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.state.bind((self.config.local_address, self.config.telemetry_port))
            self.state.setblocking(False)
        except OSError:
            self.close()
            raise

    def send(self, command: str):
        LOG.debug("udp_tx", extra={"data": {"command": command}})
        self.command.send(command.encode("ascii"))

    def poll(self):
        messages = []
        # Bound work per tick; a noisy endpoint cannot starve the control loop.
        for sock, kind in ((self.command, "response"), (self.state, "telemetry")):
            for _ in range(64):
                try:
                    data, peer = sock.recvfrom(65535)
                    if peer[0] == self.config.host:
                        LOG.debug(
                            "udp_rx",
                            extra={"data": {"kind": kind, "payload": data.decode("ascii", "replace")}},
                        )
                        messages.append((kind, data))
                except BlockingIOError:
                    break
        return messages

    def close(self):
        for sock in (self.command, self.state):
            if sock:
                sock.close()


class SimulatorTransport:
    def __init__(self, config: Connection):
        self.config = config
        self.flying = False
        self.height = 0.0
        self.yaw = 0.0
        self.battery = 86.0
        self.rc = (0, 0, 0, 0)
        self.responses = []
        self.last = time.monotonic()
        self.last_state = 0.0
        self.signal_lost = False

    def open(self):
        pass

    def send(self, command):
        LOG.debug("simulator_tx", extra={"data": {"command": command}})
        if self.signal_lost:
            return
        now = time.monotonic()
        if command.startswith("rc "):
            self.rc = tuple(int(v) for v in command.split()[1:])
            return
        if command == "takeoff":
            self.flying, self.height = True, 80.0
        elif command in ("land", "emergency"):
            self.flying, self.height = False, 0.0
            self.rc = (0, 0, 0, 0)
        response = str(int(self.battery)) if command == "battery?" else "ok"
        if command != "emergency":
            self.responses.append((now + 0.12, response.encode()))

    def poll(self):
        if self.signal_lost:
            return []
        now = time.monotonic()
        dt, self.last = min(now - self.last, 0.2), now
        if self.flying:
            self.height = max(20, min(250, self.height + self.rc[2] * dt))
            self.yaw = (self.yaw + self.rc[3] * dt) % 360
            self.battery = max(0, self.battery - dt * 0.07)
        result = [("response", data) for due, data in self.responses if due <= now]
        self.responses = [(due, data) for due, data in self.responses if due > now]
        if now - self.last_state >= 0.1:
            self.last_state = now
            lr, fb, ud, _ = self.rc if self.flying else (0, 0, 0, 0)
            payload = (
                f"bat:{int(self.battery)};h:{int(self.height)};yaw:{self.yaw:.1f};"
                f"pitch:{-fb / 8};roll:{lr / 8};vgx:{fb};vgy:{lr};vgz:{ud};"
                "templ:34;temph:38;tof:80;baro:0;time:0;"
            )
            result.append(("telemetry", payload.encode()))
        return result

    def close(self):
        self.responses.clear()
