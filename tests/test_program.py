import json
import time

import pytest

from tello_flight.engine import FlightEngine
from tello_flight.model import Connection, Telemetry
from tello_flight.program import SPECS, Card, load_program, save_program, validate_program
from tello_flight.transport import SimulatorTransport


class Wire:
    def __init__(self):
        self.sent = []
        self.incoming = []

    def send(self, message):
        self.sent.append(message)

    def poll(self):
        messages, self.incoming = self.incoming, []
        return messages


class Flight:
    def __init__(self, battery=86):
        self.wire = Wire()
        self.engine = FlightEngine(Connection(), self.wire)
        self.now = time.monotonic()
        self.height = 0
        self.battery = battery
        self.engine._update(mode="ready", telemetry=Telemetry.parse(f"h:0;bat:{battery};".encode(), self.now))
        self.engine._last_query = self.now

    def tick(self, seconds=0.1, response=None, heartbeat=True, telemetry=True):
        self.now += seconds
        if heartbeat:
            self.engine._operator_at = self.now
        if response is not None:
            self.wire.incoming.append(("response", response.encode()))
        if telemetry:
            self.wire.incoming.append(("telemetry", f"bat:{self.battery};h:{self.height};".encode()))
        self.engine._tick(self.now)

    def start(self, middle=()):
        self.engine.run_program((Card("takeoff"), *middle, Card("land")))
        self.tick()
        self.tick()
        assert self.wire.sent == ["takeoff"]
        self.height = 80

    @property
    def commands(self):
        return [c for c in self.wire.sent if not c.startswith("rc ")]


@pytest.mark.parametrize("kind", list(SPECS))
def test_every_palette_card_has_a_valid_default_and_sdk_mapping(kind):
    card = Card.default(kind)
    if kind == "wait":
        assert card.command is None
    elif kind.startswith("flip_"):
        assert card.command == "flip " + kind[-1]
    else:
        assert card.command.split()[0] == kind


@pytest.mark.parametrize(
    "kind,value",
    [
        ("up", 19),
        ("forward", 501),
        ("cw", 361),
        ("speed", 9),
        ("wait", 0),
        ("up", True),
        ("forward", 20.5),
        ("land", 1),
        ("unknown", None),
    ],
)
def test_card_parameters_are_rejected_not_silently_clamped(kind, value):
    with pytest.raises(ValueError):
        Card(kind, value)


@pytest.mark.parametrize(
    "cards",
    [
        (),
        (Card("takeoff"),),
        (Card("forward", 100), Card("land")),
        (Card("takeoff"), Card("land"), Card("land")),
        (Card("takeoff"), Card("takeoff"), Card("land")),
    ],
)
def test_invalid_flight_order_cannot_run(cards):
    with pytest.raises(ValueError):
        validate_program(cards)


def test_program_round_trip_preserves_order_parameters_and_incomplete_drafts(tmp_path):
    path = tmp_path / "lesson.json"
    cards = (Card("forward", 240), Card("cw", 180), Card("wait", 4))
    save_program(path, cards)
    assert load_program(path) == cards
    path.write_text(
        json.dumps(
            {
                "format": "tello-flight-program",
                "version": 1,
                "cards": [{"kind": "forward", "value": "100;land"}],
            }
        )
    )
    with pytest.raises(ValueError):
        load_program(path)


def test_oversized_program_rejected(tmp_path):
    path = tmp_path / "huge.json"
    path.write_bytes(b" " * 100_001)
    with pytest.raises(ValueError):
        load_program(path)
    with pytest.raises(ValueError):
        validate_program((Card("takeoff"),) + (Card("wait", 1),) * 99 + (Card("land"),))


def test_parameterized_commands_wait_for_ack_and_land_waits_for_telemetry():
    flight = Flight()
    flight.start((Card("up", 60), Card("forward", 240), Card("cw", 180)))
    flight.tick()
    assert flight.commands == ["takeoff"]
    for expected in ("up 60", "forward 240", "cw 180", "land"):
        flight.tick(response="ok")
        assert flight.commands[-1] == expected
    flight.tick(response="ok")
    assert flight.engine.snapshot().program.status == "running"
    assert flight.engine.snapshot().program.completed == 4
    flight.height = 0
    flight.tick()
    assert flight.engine.snapshot().program.status == "completed"
    assert flight.engine.snapshot().program.completed == 5


def test_wait_card_keeps_hovering_and_does_not_advance_early():
    flight = Flight()
    flight.start((Card("wait", 20),))
    flight.tick(response="ok")
    flight.engine.operator((30, 30, 30, 30))
    for _ in range(19):
        flight.tick(seconds=1)
        assert flight.commands == ["takeoff"]
    assert "rc 0 0 0 0" in flight.wire.sent
    assert not any(c.startswith("rc 30") for c in flight.wire.sent)
    flight.tick(seconds=1.1)
    flight.tick()
    assert flight.commands == ["takeoff", "land"]


def test_movement_timeout_aborts_without_replay_or_next_card():
    flight = Flight()
    flight.start((Card("forward", 500), Card("cw", 90)))
    flight.tick(response="ok")
    flight.tick(seconds=13)
    assert flight.engine.snapshot().program.status == "running"
    flight.tick(seconds=53)
    flight.tick(response="ok")
    assert flight.engine.snapshot().program.status == "failed"
    assert flight.commands.count("forward 500") == 1
    assert "cw 90" not in flight.commands
    assert flight.commands.count("land") == 1


def test_error_response_fails_program_and_discards_remaining_cards():
    flight = Flight()
    flight.start((Card("forward", 100), Card("cw", 90)))
    flight.tick(response="ok")
    flight.tick(response="error out of range")
    flight.tick()
    assert flight.engine.snapshot().program.status == "failed"
    assert "cw 90" not in flight.commands
    assert flight.commands.count("land") == 1


def test_stop_during_movement_never_resumes_after_late_reply():
    flight = Flight()
    flight.start((Card("forward", 100), Card("cw", 90)))
    flight.tick(response="ok")
    flight.engine.stop_program()
    flight.tick()
    flight.tick(response="ok")
    assert flight.engine.snapshot().program.status == "cancelled"
    assert "cw 90" not in flight.commands
    assert flight.commands.count("land") == 1


def test_operator_loss_aborts_a_program_even_during_long_command():
    flight = Flight()
    flight.start((Card("forward", 100), Card("cw", 90)))
    flight.tick(response="ok")
    flight.tick(seconds=2.1, heartbeat=False)
    assert flight.engine.snapshot().program.status == "failed"
    assert "cw 90" not in flight.commands
    assert flight.commands.count("land") == 1


def test_low_battery_aborts_even_before_long_command_acknowledges():
    flight = Flight()
    flight.start((Card("forward", 500), Card("cw", 90)))
    flight.tick(response="ok")
    flight.battery = 14
    flight.tick()
    assert flight.engine.snapshot().program.status == "failed"
    assert "cw 90" not in flight.commands
    assert flight.commands.count("land") == 1


def test_simulated_signal_loss_can_be_injected_while_program_is_running():
    flight = Flight()
    flight.start((Card("wait", 20),))
    flight.tick(response="ok")
    flight.engine.request("simulate_link_loss")
    flight.tick()
    assert flight.wire.signal_lost is True
    flight.tick(seconds=3.1, telemetry=False)
    assert flight.engine.snapshot().program.status == "failed"
    assert flight.commands.count("land") == 1


def test_flip_battery_is_checked_before_start_and_again_at_the_card():
    flight = Flight(battery=49)
    flight.engine.run_program((Card("takeoff"), Card("flip_f"), Card("land")))
    flight.tick()
    assert flight.engine.snapshot().program.status == "failed"
    assert not flight.commands
    flight = Flight()
    flight.start((Card("flip_f"),))
    flight.battery = 49
    flight.tick(response="ok")
    assert flight.engine.snapshot().program.status == "failed"
    assert "flip f" not in flight.commands


def test_landing_ack_with_high_telemetry_eventually_fails_instead_of_hanging():
    flight = Flight()
    flight.start()
    flight.tick(response="ok")
    flight.tick(response="ok")
    flight.tick(seconds=16)
    assert flight.engine.snapshot().program.status == "failed"
    assert flight.engine.snapshot().flight == "unknown"


def test_simulator_applies_distances_rotations_speed_and_flips():
    sim = SimulatorTransport(Connection())
    for command in ("takeoff", "speed 40", "up 60", "forward 100", "cw 90", "forward 200", "flip l"):
        sim.send(command)
    assert sim.height == 140
    assert sim.x == pytest.approx(100)
    assert sim.y == pytest.approx(200)
    assert sim.yaw == 90
    assert sim.speed == 40
    assert sim.flips == 1
    sim.send("land")
    assert not sim.flying and sim.height == 0


def test_threaded_simulator_runs_a_whole_program_without_gui():
    engine = FlightEngine(Connection())
    engine.start()
    try:
        deadline = time.monotonic() + 4
        started = False
        while time.monotonic() < deadline:
            engine.operator()
            state = engine.snapshot()
            if not started and state.mode == "ready" and state.telemetry.received_at:
                engine.run_program((Card("takeoff"), Card("forward", 20), Card("wait", 1), Card("land")))
                started = True
            if state.program.status == "completed":
                break
            time.sleep(0.02)
        assert engine.snapshot().program.status == "completed"
        assert engine.snapshot().flight == "grounded"
        assert engine.snapshot().telemetry.values["sim_x"] == 20
    finally:
        engine.close(force=True)
