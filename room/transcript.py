"""Stenogram pokoju: JSONL, append-only, hash każdej wiadomości.

Zasady z klucza:
- full_transcript: local_only, append_only, source_labeled
- must_preserve_original_message_hash: hash liczony z ORYGINAŁU,
  treść zapisywana po redakcji.
Retencja: bezterminowa (decyzja Jana, 15.07.2026).
"""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class Transcript:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self._seq = 0
        # tryb "a": fizycznie tylko dopisujemy
        self._fh = path.open("a", encoding="utf-8")

    def _append(self, entry: dict) -> dict:
        self._seq += 1
        entry = {
            "seq": self._seq,
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            **entry,
        }
        self._fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
        self._fh.flush()
        return entry

    def meta(self, event: str, **fields) -> dict:
        return self._append({"type": "meta", "event": event, **fields})

    def message(
        self,
        author: str,
        redacted_content: str,
        sha256_original: str,
        room_tokens: int,
        provider_usage: dict[str, int],
        redaction_hits: list[str],
        tokenizer_name: str,
    ) -> dict:
        return self._append(
            {
                "type": "message",
                "from": author,
                "content": redacted_content,
                "sha256_original": sha256_original,
                "room_tokens": room_tokens,
                "tokenizer": tokenizer_name,
                "provider_usage": provider_usage,
                "redaction_hits": redaction_hits,
            }
        )

    def close(self) -> None:
        self._fh.close()
