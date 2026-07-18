"""Drzwi Klaris: headless `claude -p`.

Izolacja per wywołanie:
- --tools ""            → zero narzędzi (mocniejsze niż read-only)
- --setting-sources ""  → bez hooków i ustawień użytkownika
- --system-prompt       → tożsamość pokojowa zamiast domyślnej
- cwd = pusty sandbox   → brak CLAUDE.md i pamięci projektów Jana
"""

import json
import shutil
import subprocess
from pathlib import Path

from .. import presence
from ..messages import Msg
from ..prompt import render_turn, truncate_to_budget
from ..tokenizer import RoomTokenizer
from .base import PresenceState


class KlarisAdapter:
    name = "Klaris"

    def __init__(
        self,
        tokenizer: RoomTokenizer,
        input_budget: int,
        workdir: Path,
        binary: str = "claude",
        timeout: int = 180,
        presence_dir: Path | None = None,
    ):
        self.tokenizer = tokenizer
        self.input_budget = input_budget
        self.workdir = workdir
        self.binary = binary
        self.timeout = timeout
        self.presence_dir = presence_dir

    def preflight(self) -> PresenceState:
        if shutil.which(self.binary) is None:
            return PresenceState.SLEEPING_OFFLINE
        if self.presence_dir:
            observed = presence.current(self.presence_dir, self.name)
            if observed:
                return PresenceState(observed)
        return PresenceState.AWAKE_IDLE

    def speak(self, preamble: str, transcript: list[Msg], max_output_tokens: int) -> Msg:
        visible = truncate_to_budget(transcript, self.tokenizer, self.input_budget)
        turn = render_turn(visible, self.name)
        turn += f"\n(Limit tej tury: około {max_output_tokens} tokenów pokoju.)"

        self.workdir.mkdir(parents=True, exist_ok=True)
        # prompt przez stdin — --tools jest wariadyczne i połknęłoby argument pozycyjny
        cmd = [
            self.binary, "-p",
            "--output-format", "json",
            "--tools", "",
            "--setting-sources", "",
            "--system-prompt", preamble,
        ]
        proc = subprocess.run(
            cmd, cwd=self.workdir, input=turn, capture_output=True, text=True,
            timeout=self.timeout,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"claude -p failed (rc={proc.returncode}): {proc.stderr[:500]}")

        data = json.loads(proc.stdout)
        usage = data.get("usage", {})
        return Msg(
            author=self.name,
            content=(data.get("result") or "").strip(),
            provider_usage={
                "input": usage.get("input_tokens", 0),
                "output": usage.get("output_tokens", 0),
                "cache_read": usage.get("cache_read_input_tokens", 0),
                "cache_write": usage.get("cache_creation_input_tokens", 0),
            },
        )
