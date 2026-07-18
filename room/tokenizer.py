"""Tokenizer pokoju.

Decyzja Jana (15.07.2026): GPT-2 BPE — otwarty, historyczny, nie jest
produkcyjnym tokenizerem żadnego z dostawców uczestników.

Fallback: len(bytes)/4 oznaczony PROVISIONAL. Bramka wdrożeniowa odrzuca
placeholder w produkcji (reject_placeholder_tokenizer_in_production).
"""

import hashlib
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class RoomTokenizer:
    name: str
    provisional: bool
    _count: Callable[[str], int]

    def count(self, text: str) -> int:
        return self._count(text)


# Sondy odcisku: zmiana tokenizera niemal na pewno zmienia któryś wynik.
# To odcisk funkcjonalny (liczby tokenów), nie hash plików BPE — wystarczający
# strażnik na M2; pełny hash merges/vocab przy przeglądzie bramki.
_PROBES = (
    "Cześć, co u Ciebie?",
    "Równy budżet głosu liczony wspólnym tokenizerem Pokoju.",
    "The quick brown fox jumps over the lazy dog 1234567890.",
    "zażółć gęślą jaźń — ąćęłńóśźż",
    "TOPIC_DEFERRED_BUDGET · STALE_RESULT · AWAKE_IDLE",
)


def fingerprint(tok: RoomTokenizer) -> str:
    counts = "|".join(str(tok.count(p)) for p in _PROBES)
    return hashlib.sha256(f"{tok.name}:{counts}".encode("utf-8")).hexdigest()[:16]


def get_tokenizer() -> RoomTokenizer:
    try:
        import tiktoken

        enc = tiktoken.get_encoding("gpt2")
        return RoomTokenizer(
            name="gpt2-bpe", provisional=False, _count=lambda s: len(enc.encode(s))
        )
    except Exception:
        return RoomTokenizer(
            name="bytes/4-PROVISIONAL",
            provisional=True,
            _count=lambda s: max(1, len(s.encode("utf-8")) // 4),
        )
