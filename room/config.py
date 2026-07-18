"""Wczytanie limitów pokoju z room.yaml."""

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class ModeLimits:
    name: str
    max_rounds: int
    room_tokens_per_agent: int
    room_tokens_per_turn: int
    calls_per_agent: int
    input_tokens_per_call: int
    output_tokens_per_turn: int
    provider_tokens_per_agent: int
    watchdog_seconds: int


@dataclass(frozen=True)
class RoomConfig:
    participants: tuple[str, ...]
    modes: dict[str, ModeLimits]


def load_config(path: Path) -> RoomConfig:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    modes = {
        name: ModeLimits(name=name, **vals) for name, vals in raw["modes"].items()
    }
    return RoomConfig(participants=tuple(raw["participants"]), modes=modes)
