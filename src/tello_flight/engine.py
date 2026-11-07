"""One worker owns flight state, sockets, scheduling, and the operator watchdog."""

import logging
import threading
import time
from collections import deque
from copy import deepcopy
from queue import Empty, Full, Queue

from .model import Connection, FlightState, Telemetry, clamp_channels
from .transport import SimulatorTransport, UDPTransport

LOG = logging.getLogger(__name__)
INPUT_LEASE = 0.35
OPERATOR_TIMEOUT = 2.0
TELEMETRY_TIMEOUT = 3.0


class FlightEngine:
    def __init__(self, config: Connection, transport=None):
        self.config = config
        self.transport = transport or (
            SimulatorTransport(config) if config.simulator else UDPTransport(config)
        )
        self._state = FlightState()
        self._lock = threading.Lock()
        self._events = deque(maxlen=300)
        self._requests = Queue(maxsize=16)
        self._quit = threading.Event()
        self._emergency = threading.Event()
        self._land = threading.Event()
        self._thread = None
        self._channels = (0, 0, 0, 0)
        self._intent_at = 0.0
        self._operator_at = time.monotonic()
        self._pending = None
        self._fault = False
        self._last_rc = 0.0
        self._last_query = 0.0
        self._last_telemetry_log = 0.0
        self._sent_at = 0.0
        self._watchdog_landed = False

    def snapshot(self):
        with self._lock:
            return deepcopy(self._state)

    def events(self):
        with self._lock:
            result = list(self._events)
            self._events.clear()
            return result

    def _update(self, **changes):
        with self._lock:
            for key, value in changes.items():
                setattr(self._state, key, value)

    def _event(self, message):
        LOG.info(message)
        with self._lock:
            self._events.append((time.time(), message))
            self._state.message = message

    def start(self):
        if self._thread is not None:
            raise RuntimeError("Create a new engine for each connection")
        self._thread = threading.Thread(target=self._run, name="tello-control", daemon=True)
        self._thread.start()

    def operator(self, channels=(0, 0, 0, 0)):
        with self._lock:
            self._channels = clamp_channels(channels)
            self._intent_at = self._operator_at = time.monotonic()

    def neutral(self):
        with self._lock:
            self._channels = (0, 0, 0, 0)
            self._intent_at = 0.0

    def request(self, command):
        if command == "emergency":
            self._emergency.set()
        elif command == "land":
            self.neutral()
            self._land.set()
        elif command in ("takeoff", "streamon", "streamoff", "battery?", "simulate_link_loss"):
            try:
                self._requests.put_nowait(command)
            except Full:
                self._event("Command queue full; request rejected")
        else:
            raise ValueError("Unsupported command")

    def close(self, force=False):
        state = self.snapshot()
        if not force and state.flight != "grounded" and state.mode != "disconnected":
            raise RuntimeError("Land before disconnecting; flight status is not grounded")
        self._quit.set()
        if self._thread:
            self._thread.join(timeout=2)
        LOG.info("session_closed", extra={"data": {"forced": force}})

    def _clear_requests(self):
        while True:
            try:
                self._requests.get_nowait()
            except Empty:
                return

    def _send(self, command, now):
        self.transport.send(command)
        self._sent_at = now
        self._event(f"Sent: {command}")
        timeout = 12 if command in ("takeoff", "land") else 5
        self._pending = (command, now + timeout)

    def _uncertain(self, message):
        self._fault = True
        self._pending = None
        self._clear_requests()
        self.neutral()
        changes = {"mode": "uncertain"}
        if self.snapshot().flight != "grounded":
            changes["flight"] = "unknown"
        self._update(**changes)
        self._event(message)

    def _response(self, data):
        response = data.decode("ascii", errors="replace").strip()
        if self._fault or not self._pending:
            LOG.debug("unmatched_response", extra={"data": {"payload": response}})
            return  # Late/unmatched replies must never complete another action.
        command, _ = self._pending
        LOG.info(
            "command_result",
            extra={
                "data": {
                    "command": command,
                    "response": response,
                    "elapsed_seconds": time.monotonic() - self._sent_at,
                }
            },
        )
        self._pending = None
        self._event(f"{command}: {response}")
        if response.lower() != "ok" and command != "battery?":
            if command == "command":
                self._uncertain("SDK handshake rejected; reconnect")
            elif command in ("takeoff", "land"):
                self._update(flight="unknown")
                self._uncertain("Flight command rejected; verify drone before reconnecting")
            return
        if command == "command":
            self._update(mode="ready")
        elif command == "takeoff":
            self._update(flight="airborne")
        elif command == "land":
            # Grounded only after fresh low-height telemetry too.
            self._update(flight="landing")
        elif command in ("streamon", "streamoff"):
            self._update(streaming=command == "streamon")

    def _tick(self, now):
        if self._emergency.is_set():
            self._emergency.clear()
            self._land.clear()
            self.transport.send("emergency")
            self._uncertain("EMERGENCY motor cut sent; inspect drone and reconnect")
            self._update(flight="unknown")
            self._watchdog_landed = True
            return
        for kind, data in self.transport.poll():
            if kind == "response":
                self._response(data)
            else:
                telemetry = Telemetry.parse(data, now)
                if telemetry:
                    self._update(telemetry=telemetry)
                    if now - self._last_telemetry_log >= 1:
                        self._last_telemetry_log = now
                        LOG.debug("telemetry", extra={"data": telemetry.values})
                    if self.snapshot().flight == "landing" and telemetry.height <= 0.1 and not self._pending:
                        self._update(flight="grounded")
        state = self.snapshot()
        if self._pending and now >= self._pending[1]:
            self._uncertain(
                f"{self._pending[0]} timed out; outcome unknown. Reconnect before further flight."
            )
            state = self.snapshot()
        with self._lock:
            channels = self._channels if now - self._intent_at < INPUT_LEASE else (0, 0, 0, 0)
            operator_age = now - self._operator_at
        age = now - state.telemetry.received_at
        flying = state.flight != "grounded"
        stale = age > TELEMETRY_TIMEOUT
        if flying and not self._watchdog_landed and (operator_age > OPERATOR_TIMEOUT or stale or self._fault):
            self._watchdog_landed = True
            self.transport.send("rc 0 0 0 0")
            self.transport.send("land")
            self._uncertain("Control/telemetry lost: landing requested once; verify drone physically")
            return
        if self._land.is_set():
            self._land.clear()
            self._clear_requests()
            self.transport.send("rc 0 0 0 0")
            if self._pending or self._fault:
                self._watchdog_landed = True
                self.transport.send("land")
                self._uncertain("Priority landing sent; acknowledgement cannot be correlated. Verify drone.")
            else:
                self._update(flight="landing")
                self._send("land", now)
            return
        if self._fault:
            return
        if flying and now - self._last_rc >= 0.05 and not self._pending:
            self._last_rc = now
            if state.flight == "airborne" and not stale:
                self.transport.send("rc " + " ".join(map(str, channels)))
        if self._pending or state.mode != "ready":
            return
        try:
            command = self._requests.get_nowait()
        except Empty:
            if now - self._last_query >= 5 and not stale and not flying:
                self._last_query = now
                self._send("battery?", now)
            return
        if command == "simulate_link_loss":
            if self.config.simulator:
                self.transport.signal_lost = True
                self._event("Simulator: signal loss injected. Reconnect to restore.")
            return
        if command == "battery?" and flying:
            self._event("Battery query skipped during flight; use telemetry")
            return
        if command == "takeoff":
            if state.flight != "grounded" or stale or state.telemetry.battery < 25:
                self._event("Takeoff rejected: need grounded state, fresh telemetry, and battery >= 25%")
                return
            self._watchdog_landed = False
            self._update(flight="taking off")
        if command.startswith("stream") and state.flight != "grounded":
            self._event("Change video streaming while grounded")
            return
        self._send(command, now)

    def _run(self):
        try:
            LOG.info(
                "session_start",
                extra={
                    "data": {
                        "simulator": self.config.simulator,
                        "host": self.config.host,
                        "local_address": self.config.local_address,
                    }
                },
            )
            self._update(mode="connecting")
            self.transport.open()
            self._send("command", time.monotonic())
            while not self._quit.wait(0.01):
                self._tick(time.monotonic())
        except Exception as exc:
            LOG.exception("control_worker_failed")
            self._uncertain(f"Connection error: {exc}")
            # Best effort only: a failed Wi-Fi link cannot guarantee delivery.
            if self.snapshot().flight != "grounded":
                try:
                    self.transport.send("land")
                except OSError:
                    LOG.warning("failsafe_landing_send_failed", exc_info=True)
        finally:
            if self.snapshot().streaming and self.snapshot().flight == "grounded":
                try:
                    self.transport.send("streamoff")
                except OSError:
                    LOG.debug("streamoff_on_close_failed", exc_info=True)
            self.transport.close()
            if not self._fault:
                self._update(mode="disconnected", streaming=False)
