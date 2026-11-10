"""One worker owns flight state, sockets, scheduling, and the operator watchdog."""

import logging
import threading
import time
from collections import deque
from copy import deepcopy
from dataclasses import asdict
from queue import Empty, Full, Queue

from .model import Connection, FlightState, ProgramProgress, Telemetry, clamp_channels
from .program import RunProgram, validate_program
from .transport import SimulatorTransport, UDPTransport

LOG = logging.getLogger(__name__)
INPUT_LEASE = 0.35
OPERATOR_TIMEOUT = 2.0
TELEMETRY_TIMEOUT = 3.0
LANDING_SETTLE_TIME = 1.0
PRIORITY_LANDING_TIMEOUT = 15.0


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
        self._signal_loss = threading.Event()
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
        self._program_cards = ()
        self._program_cursor = 0
        self._program_wait_until = None
        self._program_pending = False
        self._program_landing = False
        self._program_landing_deadline = 0.0
        self._priority_landing_deadline = 0.0
        self._landing_airborne_seen = False
        self._landing_ground_since = None

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
        elif command == "simulate_link_loss":
            if self.config.simulator:
                self._signal_loss.set()
        elif command in ("takeoff", "streamon", "streamoff", "battery?"):
            if self.snapshot().program.status == "running":
                self._event("Manual command rejected while a program is running")
                return
            try:
                self._requests.put_nowait(command)
            except Full:
                self._event("Command queue full; request rejected")
        else:
            raise ValueError("Unsupported command")

    def run_program(self, cards):
        cards = validate_program(cards)
        if self.snapshot().program.status == "running":
            raise ValueError("A program is already running")
        try:
            self._requests.put_nowait(RunProgram(cards))
        except Full as exc:
            raise ValueError("Command queue full; try again") from exc

    def stop_program(self):
        self.request("land")

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

    def _send(self, command, now, timeout=None):
        self.transport.send(command)
        self._sent_at = now
        self._event(f"Sent: {command}")
        timeout = timeout if timeout is not None else (12 if command in ("takeoff", "land") else 5)
        self._pending = (command, now + timeout)

    def _uncertain(self, message):
        self._priority_landing_deadline = 0.0
        self._finish_program("failed", message)
        self._fault = True
        self._pending = None
        self._clear_requests()
        self.neutral()
        changes = {"mode": "uncertain"}
        if self.snapshot().flight != "grounded":
            changes["flight"] = "unknown"
        self._update(**changes)
        self._event(message)

    def _observe_priority_landing(self, telemetry, now):
        if telemetry.height > 0.2:
            self._landing_airborne_seen = True
        # Height alone can read zero before takeoff or near the floor. Require
        # an observed flight followed by sustained low range and vertical speed.
        grounded = (
            self._landing_airborne_seen
            and 0 <= telemetry.height <= 0.1
            and 0 < telemetry.values.get("tof", 1000) <= 20
            and abs(telemetry.values.get("vgz", 1000)) <= 5
        )
        if not grounded:
            self._landing_ground_since = None
            return
        if self._landing_ground_since is None:
            self._landing_ground_since = now

    def _finish_program(self, status, detail):
        if not self._program_cards:
            return
        progress = self.snapshot().program
        progress.status, progress.detail = status, detail
        self._update(program=progress)
        self._program_cards = ()
        self._program_pending = self._program_landing = False
        self._program_wait_until = None
        LOG.info("program_finished", extra={"data": asdict(progress)})
        self._event(detail)

    def _complete_card(self):
        self._program_cursor += 1
        self._program_pending = self._program_landing = False
        self._program_wait_until = None
        progress = self.snapshot().program
        progress.completed = self._program_cursor
        self._update(program=progress)
        LOG.info("program_card_completed", extra={"data": {"index": self._program_cursor - 1}})
        if self._program_cursor == len(self._program_cards):
            self._finish_program("completed", "Program complete — all cards finished")

    def _start_program(self, cards, now):
        state = self.snapshot()
        progress = ProgramProgress(status="running", total=len(cards), cards=[asdict(c) for c in cards])
        reason = ""
        if state.mode != "ready" or state.flight != "grounded":
            reason = "Connect and land before running a program"
        elif now - state.telemetry.received_at > TELEMETRY_TIMEOUT or state.telemetry.battery < 25:
            reason = "Need fresh telemetry and at least 25% battery"
        elif now - self._operator_at > OPERATOR_TIMEOUT:
            reason = "Keep the application in focus before running"
        elif any(c.kind.startswith("flip_") for c in cards) and state.telemetry.battery < 50:
            reason = "Flip cards require at least 50% battery"
        if reason:
            progress.status, progress.detail = "failed", reason
            self._update(program=progress)
            self._event(reason)
            return
        self._clear_requests()
        self.neutral()
        self._watchdog_landed = False
        self._program_cards = cards
        self._program_cursor = 0
        self._program_wait_until = None
        self._program_pending = self._program_landing = False
        self._update(program=progress)
        LOG.info("program_started", extra={"data": {"cards": progress.cards}})
        self._event(f"Program started — {len(cards)} cards")

    def _advance_program(self, now):
        if self._pending or not self._program_cards:
            return
        state = self.snapshot()
        if state.telemetry.battery < 15:
            self._uncertain("Low battery: program aborted; landing requested")
            return
        if self._program_landing:
            if state.flight == "grounded":
                self._complete_card()
            elif now > self._program_landing_deadline:
                self._uncertain("Landing not confirmed by telemetry; program aborted")
            return
        if self._program_wait_until is not None:
            if now >= self._program_wait_until:
                self._complete_card()
            elif now - self._last_rc >= 0.05:
                self.transport.send("rc 0 0 0 0")
                self._last_rc = now
            return
        card = self._program_cards[self._program_cursor]
        progress = state.program
        progress.index, progress.detail = self._program_cursor, card.label
        self._update(program=progress)
        LOG.info("program_card_started", extra={"data": {"index": self._program_cursor, **asdict(card)}})
        self._event(f"Card {self._program_cursor + 1}/{len(self._program_cards)}: {card.label}")
        if card.kind.startswith("flip_") and state.telemetry.battery < 50:
            self._uncertain("Battery below 50%: flip cancelled; program aborted")
            return
        if card.kind == "wait":
            self._program_wait_until = now + card.value
            self.transport.send("rc 0 0 0 0")
            self._last_rc = now
            return
        if card.kind == "takeoff":
            self._update(flight="taking off")
        elif card.kind == "land":
            self._update(flight="landing")
            self._program_landing_deadline = now + card.timeout
        elif state.flight != "airborne":
            self._uncertain("Drone is not airborne: program aborted")
            return
        self._program_pending = True
        self._send(card.command, now, card.timeout)

    def _response(self, data):
        response = data.decode("ascii", errors="replace").strip()
        if self._fault or not self._pending:
            LOG.debug("unmatched_response", extra={"data": {"payload": response}})
            return  # Late/unmatched replies must never complete another action.
        command, _ = self._pending
        program_command = self._program_pending
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
            if program_command:
                self._uncertain(f"Card rejected ({command}: {response}); program aborted")
            elif command == "command":
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
        if program_command:
            if command == "land":
                self._program_landing = True
            else:
                self._complete_card()

    def _tick(self, now):
        if self._priority_landing_deadline:
            self._land.clear()  # The first request already initiated landing.
        if self._signal_loss.is_set():
            self._signal_loss.clear()
            self.transport.signal_lost = True
            self._event("Simulator: signal loss injected. Reconnect to restore.")
        if self._land.is_set():
            self._finish_program("cancelled", "Program stopped — landing requested")
        if self._emergency.is_set():
            self._finish_program("cancelled", "Program cancelled by motor cut")
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
                    previous = self.snapshot().telemetry
                    self._update(telemetry=telemetry)
                    if now - self._last_telemetry_log >= 1:
                        self._last_telemetry_log = now
                        LOG.debug("telemetry", extra={"data": telemetry.values})
                    if self._priority_landing_deadline:
                        if now - previous.received_at > TELEMETRY_TIMEOUT:
                            self._landing_ground_since = None
                        self._observe_priority_landing(telemetry, now)
                    elif self.snapshot().flight == "landing" and telemetry.height <= 0.1 and not self._pending:
                        self._update(flight="grounded")
        state = self.snapshot()
        if (
            self._priority_landing_deadline
            and now < self._priority_landing_deadline
            and self._landing_ground_since is not None
            and state.telemetry.received_at - self._landing_ground_since >= LANDING_SETTLE_TIME
        ):
            # Drain this entire poll before replacing the socket: none of its
            # old replies may acknowledge the new handshake.
            self.transport.reset_command_channel()
            self._priority_landing_deadline = 0.0
            self._fault = False
            self._clear_requests()
            self._update(mode="connecting", flight="grounded")
            self._event("Landing observed; restoring command connection")
            self._send("command", now)
            state = self.snapshot()
        if self._priority_landing_deadline and now >= self._priority_landing_deadline:
            self._uncertain("Landing not confirmed; inspect drone and reconnect")
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
        low_battery = bool(self._program_cards) and state.telemetry.battery < 15
        if (
            flying
            and not self._watchdog_landed
            and (operator_age > OPERATOR_TIMEOUT or stale or self._fault or low_battery)
        ):
            self._watchdog_landed = True
            self.transport.send("rc 0 0 0 0")
            self.transport.send("land")
            self._uncertain(
                "Low battery: program aborted; landing requested once"
                if low_battery
                else "Control/telemetry lost: landing requested once; verify drone physically"
            )
            return
        if self._land.is_set():
            self._land.clear()
            self._clear_requests()
            if self._priority_landing_deadline:
                return  # Repeated clicks must not restart landing or its deadline.
            self.transport.send("rc 0 0 0 0")
            if self._pending and not self._fault and state.mode == "ready":
                self.transport.send("land")
                self._pending = None
                self._fault = True  # Ignore ambiguous replies until the channel is replaced.
                self._watchdog_landed = True
                self._priority_landing_deadline = now + PRIORITY_LANDING_TIMEOUT
                self._landing_airborne_seen = state.telemetry.height > 0.2
                self._landing_ground_since = None
                self._update(mode="landing", flight="landing")
                self._event("Landing requested; waiting for grounded telemetry")
            elif self._pending or self._fault:
                self._watchdog_landed = True
                self.transport.send("land")
                self._uncertain("Priority landing sent; acknowledgement cannot be correlated. Verify drone.")
            else:
                self._update(flight="landing")
                self._send("land", now)
            return
        if self._fault:
            return
        if self._program_cards:
            self._advance_program(now)
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
        if isinstance(command, RunProgram):
            self._start_program(command.cards, now)
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
            self._finish_program("cancelled", "Program cancelled: session closed")
            if self.snapshot().streaming and self.snapshot().flight == "grounded":
                try:
                    self.transport.send("streamoff")
                except OSError:
                    LOG.debug("streamoff_on_close_failed", exc_info=True)
            self.transport.close()
            if not self._fault:
                self._update(mode="disconnected", streaming=False)
