import time

import pytest

from tello_flight.engine import FlightEngine
from tello_flight.model import Connection, Telemetry, clamp_channels


class Transport:
    def __init__(self):
        self.sent = []
        self.incoming = []

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
    assert engine.snapshot().mode == "uncertain"
    assert engine.snapshot().flight == "unknown"


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
