"""Validated, serializable command cards for single-drone sequential programming."""

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class CardSpec:
    title: str
    symbol: str
    command: str | None
    color: str
    unit: str = ""
    minimum: int = 0
    maximum: int = 0
    default: int | None = None
    parameter: str = ""


SPECS = {
    "takeoff": CardSpec("Take off", "↑", "takeoff", "#6de5d2"),
    "land": CardSpec("Land", "↓", "land", "#6de5d2"),
    "up": CardSpec("Fly up", "↑", "up", "#76baff", "cm", 20, 500, 50, "Height change"),
    "down": CardSpec("Fly down", "↓", "down", "#76baff", "cm", 20, 500, 50, "Height change"),
    "forward": CardSpec("Fly forward", "↑", "forward", "#76baff", "cm", 20, 500, 100, "Distance"),
    "back": CardSpec("Fly backward", "↓", "back", "#76baff", "cm", 20, 500, 100, "Distance"),
    "left": CardSpec("Fly left", "←", "left", "#76baff", "cm", 20, 500, 100, "Distance"),
    "right": CardSpec("Fly right", "→", "right", "#76baff", "cm", 20, 500, 100, "Distance"),
    "cw": CardSpec("Turn clockwise", "↻", "cw", "#c5a5ff", "°", 1, 360, 90, "Angle"),
    "ccw": CardSpec("Turn counterclockwise", "↺", "ccw", "#c5a5ff", "°", 1, 360, 90, "Angle"),
    "flip_f": CardSpec("Flip forward", "↗", "flip f", "#f4acbe"),
    "flip_b": CardSpec("Flip backward", "↙", "flip b", "#f4acbe"),
    "flip_l": CardSpec("Flip left", "↶", "flip l", "#f4acbe"),
    "flip_r": CardSpec("Flip right", "↷", "flip r", "#f4acbe"),
    "speed": CardSpec("Set speed", "»", "speed", "#ffc780", "cm/s", 10, 100, 30, "Speed"),
    "wait": CardSpec("Wait / hover", "Ⅱ", None, "#ffc780", "s", 1, 60, 2, "Duration"),
}


@dataclass(frozen=True)
class Card:
    kind: str
    value: int | None = None

    def __post_init__(self):
        if not isinstance(self.kind, str) or self.kind not in SPECS:
            raise ValueError("Unknown command card")
        spec = SPECS[self.kind]
        if spec.default is None:
            if self.value is not None:
                raise ValueError(f"{spec.title} has no parameter")
        elif type(self.value) is not int or not spec.minimum <= self.value <= spec.maximum:
            raise ValueError(f"{spec.title}: enter {spec.minimum}–{spec.maximum} {spec.unit}")

    @classmethod
    def default(cls, kind):
        if kind not in SPECS:
            raise ValueError("Unknown command card")
        return cls(kind, SPECS[kind].default)

    @property
    def command(self):
        spec = SPECS[self.kind]
        if spec.command is None:
            return None
        return spec.command if self.value is None else f"{spec.command} {self.value}"

    @property
    def label(self):
        spec = SPECS[self.kind]
        return spec.title if self.value is None else f"{spec.title} · {self.value} {spec.unit}"

    @property
    def timeout(self):
        # 500 cm at minimum speed can take 50 seconds; keepalive/GUI timing is separate.
        return 65 if self.kind in ("up", "down", "forward", "back", "left", "right") else 15


def validate_cards(cards):
    cards = tuple(cards)
    if len(cards) > 100:
        raise ValueError("A program can contain at most 100 cards")
    for card in cards:
        if not isinstance(card, Card):
            raise ValueError("Programs must contain command cards")
        card.__post_init__()
    return cards


def validate_program(cards):
    cards = validate_cards(cards)
    if len(cards) < 2 or cards[0].kind != "takeoff" or cards[-1].kind != "land":
        raise ValueError("Start with Take off and finish with Land")
    if any(card.kind in ("takeoff", "land") for card in cards[1:-1]):
        raise ValueError("Take off belongs first and Land belongs last")
    return cards


def save_program(path, cards):
    cards = validate_cards(cards)  # Save incomplete drafts; validate flight order only on Run.
    path = Path(path)
    document = {"format": "tello-flight-program", "version": 1, "cards": [asdict(c) for c in cards]}
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")


def load_program(path):
    path = Path(path)
    if path.stat().st_size > 100_000:
        raise ValueError("Program file is too large")
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
        if (
            not isinstance(document, dict)
            or document.get("format") != "tello-flight-program"
            or type(document.get("version")) is not int
            or document["version"] != 1
            or not isinstance(document.get("cards"), list)
        ):
            raise ValueError("Unsupported program file")
        return validate_cards(Card(**item) for item in document["cards"])
    except (TypeError, KeyError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid program file") from exc


def example_program():
    return (
        Card("takeoff"),
        Card("up", 50),
        Card("forward", 100),
        Card("cw", 90),
        Card("wait", 2),
        Card("land"),
    )


@dataclass(frozen=True)
class RunProgram:
    cards: tuple[Card, ...]
