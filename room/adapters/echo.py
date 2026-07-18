"""Adapter-atrapa do M0: odgrywa przygotowane kwestie, zero sieci, zero modeli.

Służy do testowania brokera, panelu, ledgera i przycisku STOP
zanim podłączymy prawdziwe modele (M1).
"""

from ..messages import Msg
from .base import PresenceState


class EchoAdapter:
    def __init__(self, name: str, lines: list[str] | None = None):
        self.name = name
        self._lines = list(lines or [])
        self._i = 0

    def preflight(self) -> PresenceState:
        return PresenceState.AWAKE_IDLE

    def speak(self, preamble: str, transcript, max_output_tokens: int) -> Msg:
        if self._i < len(self._lines):
            text = self._lines[self._i]
        else:
            text = f"({self.name}, atrapa) tura {self._i + 1} — echo bez treści."
        self._i += 1
        # atrapa raportuje zmyślone, małe zużycie
        usage = {"input": len(preamble) // 4, "output": len(text) // 4}
        return Msg(author=self.name, content=text, provider_usage=usage)
