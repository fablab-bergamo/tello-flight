import time

import pytest

from tello_flight.engine import FlightEngine
from tello_flight.model import Connection, Telemetry, clamp_channels


class Transport:
    def __init__(self):
        self.sent = []
        self.incoming = []
        self.resets = 0

    def reset_command_channel(self):
        self.resets += 1

    def send(self, command):
        self.sent.append(command)

    def poll(self):
        incoming, self.incoming = self.incoming, []
        return incoming


def ready():
    transport = Transport()
    engine = FlightEngine(Connection(), transport)
    now = time.monotonic()
    engine._update(mode="ready", telemetry=Telemetry.parse(b"bat:86;h:0;", now))
    engine._last_query = now
    engine.operator()
    return engine, transport, now


def test_parser_rejects_corruption_without_refreshing_freshness():
    assert Telemetry.parse(b"garbage;h:NaN;bat:90;") is None
    assert Telemetry.parse(b"h:0;bat:101;") is None
    assert Telemetry.parse(b"h:0;bat:inf;") is None
    state = Telemetry.parse(b"bat:90;h:120;vgx:30;vgy:40;unknown:abc;", 10)
    assert state.received_at == 10
    assert state.height == 1.2
    assert state.speed == 0.5


def test_channel_validation():
    assert clamp_channels((1000, -200, 4.5, 0)) == (100, -100, 4, 0)
    with pytest.raises(ValueError):
        clamp_channels((1, 2, 3))
    with pytest.raises(ValueError):
        clamp_channels((0, 0, float("nan"), 0))


@pytest.mark.parametrize("battery,age", [(24, 0), (86, 4)])
def test_takeoff_requires_battery_and_fresh_telemetry(battery, age):
    engine, transport, now = ready()
    engine._update(telemetry=Telemetry.parse(f"bat:{battery};h:0;".encode(), now - age))
    engine.request("takeoff")
    engine._tick(now)
    assert "takeoff" not in transport.sent


def test_discrete_commands_serialize_and_late_reply_cannot_rearm():
    engine, transport, now = ready()
    engine.request("streamon")
    engine.request("takeoff")
    engine._tick(now)
    engine._tick(now + 0.1)
    assert transport.sent == ["streamon"]
    engine._tick(now + 5.1)
    assert engine.snapshot().mode == "uncertain"
    transport.incoming.append(("response", b"ok"))
    engine.request("takeoff")
    engine._tick(now + 5.2)
    assert "takeoff" not in transport.sent
    assert engine.snapshot().mode == "uncertain"


def test_input_expiry_neutralizes_before_operator_watchdog_lands_once():
    engine, transport, now = ready()
    engine._update(flight="airborne")
    engine.operator((20, 0, 0, 0))
    engine._tick(now + 0.1)
    assert transport.sent[-1] == "rc 20 0 0 0"
    engine._tick(now + 0.5)
    assert transport.sent[-1] == "rc 0 0 0 0"
    engine._tick(now + 2.1)
    engine._tick(now + 2.2)
    assert transport.sent.count("land") == 1
    assert engine.snapshot().flight == "unknown"


def test_stale_telemetry_blocks_flight_even_with_operator_heartbeat():
    engine, transport, now = ready()
    engine._update(flight="airborne", telemetry=Telemetry.parse(b"h:80;bat:80;", now - 4))
    engine.operator((0, 20, 0, 0))
    engine._tick(now)
    assert transport.sent == ["rc 0 0 0 0", "land"]
    assert engine.snapshot().mode == "uncertain"


def test_motor_cut_preempts_pending_command_and_clears_queue():
    engine, transport, now = ready()
    engine.request("takeoff")
    engine._tick(now)
    engine.request("streamon")
    engine.request("land")
    engine.request("emergency")
    engine._tick(now + 0.1)
    engine._tick(now + 0.2)
    assert transport.sent[-1] == "emergency"
    assert "land" not in transport.sent
    assert engine.snapshot().mode == "uncertain"
    assert engine._requests.empty()
    with pytest.raises(RuntimeError):
        engine.close()


def test_landing_ack_alone_does_not_claim_grounded():
    engine, transport, now = ready()
    engine._update(flight="airborne", telemetry=Telemetry.parse(b"h:80;bat:80;", now))
    engine.request("land")
    engine._tick(now)
    transport.incoming.append(("response", b"ok"))
    engine._tick(now + 0.1)
    assert engine.snapshot().flight == "landing"
    transport.incoming.append(("telemetry", b"h:0;bat:80;"))
    engine._tick(now + 0.2)
    assert engine.snapshot().flight == "grounded"


def test_takeoff_timeout_does_not_retry_movement_and_late_ack_is_ignored():
    engine, transport, now = ready()
    engine.request("takeoff")
    engine._tick(now)
    engine._tick(now + 12.1)
    transport.incoming.append(("response", b"ok"))
    engine._tick(now + 12.2)
    assert transport.sent.count("takeoff") == 1
    assert transport.sent.count("land") == 1
    assert engine.snapshot().flight == "unknown"
    assert engine.snapshot().mode == "uncertain"


def test_priority_landing_during_takeoff_quarantines_acknowledgements():
    engine, transport, now = ready()
    engine.request("takeoff")
    engine._tick(now)
    engine.request("land")
    engine._tick(now + 0.1)
    transport.incoming.append(("response", b"ok"))
    engine._tick(now + 0.2)
    assert transport.sent.count("land") == 1
    assert engine.snapshot().mode == "landing"
    assert engine.snapshot().flight == "landing"
    assert transport.resets == 0


def test_interrupted_takeoff_recovers_after_stable_touchdown_and_new_handshake():
    engine, transport, now = ready()

    def tick(seconds, height, tof, vgz=0, response=None):
        engine._operator_at = now + seconds
        transport.incoming.append(("telemetry", f"bat:86;h:{height};tof:{tof};vgz:{vgz};".encode()))
        if response:
            transport.incoming.append(("response", response))
        engine._tick(now + seconds)

    engine.request("takeoff")
    engine._tick(now)
    tick(1, 70, 80)
    engine.request("land")
    tick(1.1, 70, 80)
    # A repeated click does not send land again or postpone recovery.
    engine.request("land")
    tick(1.2, 70, 80, response=b"ok")
    assert engine.snapshot().mode == "landing"
    assert transport.sent.count("land") == 1
    tick(2, 0, 10)
    tick(2.5, 30, 40)  # A single low reading cannot confirm touchdown.
    tick(3, 0, 10)
    tick(3.5, 0, 10)
    engine.request("takeoff")  # Requests made while recovering are discarded.
    tick(4.1, 0, 10, response=b"ok")
    assert engine.snapshot().mode == "connecting"
    assert engine.snapshot().flight == "grounded"
    assert transport.resets == 1
    assert transport.sent[-1] == "command"
    assert transport.sent.count("takeoff") == 1
    tick(4.2, 0, 10, response=b"ok")
    assert engine.snapshot().mode == "ready"
    engine.request("takeoff")
    tick(4.3, 0, 10)
    assert transport.sent.count("takeoff") == 2


@pytest.mark.parametrize("payload", [
    b"bat:86;h:0;",  # Missing range and vertical speed.
    b"bat:86;h:0;tof:230;vgz:0;",  # Low reported height while still above the floor.
    b"bat:86;h:0;tof:10;vgz:20;",  # Still descending.
])
def test_priority_landing_does_not_recover_from_unreliable_ground_readings(payload):
    engine, transport, now = ready()
    engine._update(flight="airborne", telemetry=Telemetry.parse(b"bat:86;h:70;", now))
    engine._send("battery?", now)
    engine.request("land")
    engine._tick(now)
    for seconds in (0.1, 1.5):
        transport.incoming.append(("telemetry", payload))
        engine._tick(now + seconds)
    assert engine.snapshot().mode == "landing"
    assert transport.resets == 0


def test_priority_landing_requires_observed_flight_and_has_a_deadline():
    engine, transport, now = ready()
    engine.request("takeoff")
    engine._tick(now)
    engine.request("land")
    engine._tick(now + 0.1)
    for seconds in (1, 2.5, 15.2):
        transport.incoming.append(("telemetry", b"bat:86;h:0;tof:10;vgz:0;"))
        engine._tick(now + seconds)
    assert transport.resets == 0
    assert engine.snapshot().mode == "uncertain"
    assert "Landing not confirmed" in engine.snapshot().message


def test_priority_landing_does_not_count_a_telemetry_gap_as_stable_ground():
    engine, transport, now = ready()
    engine._update(flight="airborne", telemetry=Telemetry.parse(b"bat:86;h:70;", now))
    engine._send("battery?", now)
    engine.request("land")
    engine._tick(now)
    for seconds in (0.1, 4):
        transport.incoming.append(("telemetry", b"bat:86;h:0;tof:10;vgz:0;"))
        engine._tick(now + seconds)
    assert transport.resets == 0
    assert engine.snapshot().mode == "landing"


def test_invalid_command_cannot_reach_transport():
    engine, transport, _ = ready()
    with pytest.raises(ValueError):
        engine.request("flip f")
    assert not transport.sent


def test_simulator_takeoff_land_and_shutdown():
    engine = FlightEngine(Connection())
    engine.start()

    def wait_for(predicate):
        end = time.monotonic() + 2
        while time.monotonic() < end:
            engine.operator()
            if predicate(engine.snapshot()):
                return
            time.sleep(0.02)
        pytest.fail("Simulator did not reach expected state")

    try:
        wait_for(lambda s: s.mode == "ready" and s.telemetry.received_at)
        engine.request("takeoff")
        wait_for(lambda s: s.flight == "airborne")
        engine.request("land")
        wait_for(lambda s: s.flight == "grounded")
    finally:
        engine.close(force=True)
    assert not engine._thread.is_alive()
