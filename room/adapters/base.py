"""Wspólny kontrakt adaptera — jedyne, co broker wie o uczestniku."""

from enum import Enum
from typing import Protocol

from ..messages import Msg


class PresenceState(str, Enum):
    AWAKE_IDLE = "AWAKE_IDLE"
    AWAKE_BUSY = "AWAKE_BUSY"
    DND = "DND"
    SLEEPING_QUOTA = "SLEEPING_QUOTA"
    SLEEPING_OFFLINE = "SLEEPING_OFFLINE"
    UNKNOWN = "UNKNOWN"


class Adapter(Protocol):
    name: str

    def preflight(self) -> PresenceState:
        """Pasywny odczyt stanu. Nigdy nie wywołuje modelu (never_probe...)."""
        ...

    def speak(
        self, preamble: str, transcript: list[Msg], max_output_tokens: int
    ) -> Msg:
        """Jedna tura. Świeże wywołanie: preambuła + stenogram, zero ukrytego stanu."""
        ...
