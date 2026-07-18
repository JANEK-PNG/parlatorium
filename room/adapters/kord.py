"""Drzwi Korda: `codex exec` w piaskownicy read-only.

Izolacja per wywołanie:
- --sandbox read-only     → brak zapisu i sieci
- cwd = pusty sandbox     → brak dostępu do projektów Jana
- --skip-git-repo-check   → sandbox nie jest repozytorium

Codex nie ma flagi system-prompt w exec, więc preambuła
i stenogram idą w jednym prompcie.
"""

import json
import re
import shutil
import subprocess
import tomllib
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .. import presence
from ..messages import Msg
from ..prompt import render_turn, truncate_to_budget
from ..tokenizer import RoomTokenizer
from .base import PresenceState


class KordAdapter:
    name = "Kord"

    def __init__(
        self,
        tokenizer: RoomTokenizer,
        input_budget: int,
        workdir: Path,
        binary: str = "codex",
        timeout: int = 180,
        codex_config: Path | None = None,
        presence_dir: Path | None = None,
    ):
        self.tokenizer = tokenizer
        self.input_budget = input_budget
        self.workdir = workdir
        self.binary = binary
        self.timeout = timeout
        self.codex_config = codex_config or Path.home() / ".codex" / "config.toml"
        self.presence_dir = presence_dir

    def _mcp_disable_flags(self) -> list[str]:
        """Pokój = zero narzędzi: wyłącz każdy serwer MCP z configu użytkownika."""
        if not self.codex_config.exists():
            return []
        data = tomllib.loads(self.codex_config.read_text(encoding="utf-8"))
        flags: list[str] = []
        for server_name in data.get("mcp_servers", {}):
            flags += ["-c", f"mcp_servers.{server_name}.enabled=false"]
        return flags

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
        prompt = (
            preamble
            + f"\n\n{turn}\n(Limit tej tury: około {max_output_tokens} tokenów pokoju.)"
        )

        self.workdir.mkdir(parents=True, exist_ok=True)
        cmd = [
            self.binary, "exec",
            "--sandbox", "read-only",
            "--skip-git-repo-check",
            *self._mcp_disable_flags(),
            "--json",
            prompt,
        ]
        proc = subprocess.run(
            cmd, cwd=self.workdir, capture_output=True, text=True, timeout=self.timeout,
            stdin=subprocess.DEVNULL,  # bez tty codex czeka na stdin — zamykamy
        )
        if proc.returncode != 0:
            error = self._extract_error(proc.stdout) or proc.stderr[:300]
            self._maybe_record_quota_sleep(error)
            raise RuntimeError(f"codex exec failed (rc={proc.returncode}): {error[:500]}")

        text, usage = self._parse_events(proc.stdout)
        return Msg(author=self.name, content=text.strip(), provider_usage=usage)

    @staticmethod
    def _extract_error(stdout: str) -> str | None:
        for line in stdout.splitlines():
            try:
                event = json.loads(line.strip())
            except json.JSONDecodeError:
                continue
            if event.get("type") == "error" and event.get("message"):
                return event["message"]
        return None

    def _maybe_record_quota_sleep(self, error: str) -> None:
        """Observed signal: komunikat o limicie → SLEEPING_QUOTA do znanego resetu."""
        if not self.presence_dir or "usage limit" not in error.lower():
            return
        until = self._parse_reset(error) or datetime.now(timezone.utc) + timedelta(hours=6)
        presence.record(
            self.presence_dir, self.name, "SLEEPING_QUOTA",
            expires_at=until, source=f"codex exec: {error[:160]}",
        )

    @staticmethod
    def _parse_reset(error: str) -> datetime | None:
        """'try again at Jul 21st, 2026 11:11 PM' → datetime (czas lokalny maszyny)."""
        match = re.search(r"try again at ([A-Za-z]{3} \d{1,2})[a-z]{2}(, \d{4} \d{1,2}:\d{2} [AP]M)", error)
        if not match:
            return None
        try:
            local = datetime.strptime(match.group(1) + match.group(2), "%b %d, %Y %I:%M %p")
            return local.astimezone()  # doprecyzowanie strefy lokalnej
        except ValueError:
            return None

    @staticmethod
    def _parse_events(stdout: str) -> tuple[str, dict[str, int]]:
        """JSONL z codex exec --json: tekst z agent_message, zużycie z turn.completed."""
        text_parts: list[str] = []
        usage: dict[str, int] = {}
        plain_fallback: list[str] = []
        for line in stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                plain_fallback.append(line)
                continue
            item = event.get("item", {})
            if item.get("item_type") == "agent_message" or item.get("type") == "agent_message":
                text_parts.append(item.get("text", ""))
            raw = event.get("usage") or event.get("info", {}).get("usage")
            if raw:
                usage = {
                    "input": raw.get("input_tokens", 0),
                    "output": raw.get("output_tokens", 0),
                    "cache_read": raw.get("cached_input_tokens", 0),
                }
        text = "\n".join(p for p in text_parts if p) or "\n".join(plain_fallback)
        return text, usage
