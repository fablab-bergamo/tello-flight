"""UI-independent data types and tolerant SDK telemetry parsing."""

import math
import time
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Connection:
    simulator: bool = True
    host: str = "192.168.10.1"
    command_port: int = 8889
    local_address: str = "0.0.0.0"
    telemetry_port: int = 8890
    video_port: int = 11111


@dataclass
class Telemetry:
    values: dict[str, float] = field(default_factory=dict)
    received_at: float = 0.0

    @classmethod
    def parse(cls, payload: bytes, now: float | None = None):
        values = {}
        for item in payload.decode("ascii", errors="ignore").strip().split(";"):
            key, sep, raw = item.partition(":")
            if not sep:
                continue
            try:
                value = float(raw)
                if math.isfinite(value):
                    values[key.strip()] = value
            except ValueError:
                continue
        # Never let a malformed datagram refresh the telemetry watchdog.
        if not {"bat", "h"}.issubset(values) or not 0 <= values["bat"] <= 100:
            return None
        return cls(values, time.monotonic() if now is None else now)

    @property
    def battery(self):
        return self.values.get("bat", 0)

    @property
    def height(self):
        return self.values.get("h", 0) / 100

    @property
    def speed(self):
        return math.hypot(self.values.get("vgx", 0), self.values.get("vgy", 0)) / 100


@dataclass
class ProgramProgress:
    status: str = "idle"
    index: int = -1
    total: int = 0
    completed: int = 0
    detail: str = "Build a flight by adding command cards."
    cards: list[dict] = field(default_factory=list)


@dataclass
class FlightState:
    mode: str = "disconnected"
    flight: str = "grounded"
    telemetry: Telemetry = field(default_factory=Telemetry)
    streaming: bool = False
    message: str = "Choose simulator or connect to your Tello."
    program: ProgramProgress = field(default_factory=ProgramProgress)


def clamp_channels(channels):
    if len(channels) != 4:
        raise ValueError("Four RC channels are required")
    if not all(math.isfinite(float(v)) for v in channels):
        raise ValueError("RC channels must be finite")
    return tuple(max(-100, min(100, int(v))) for v in channels)
