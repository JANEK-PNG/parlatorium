"""Redakcja sekretów przed routingiem.

Broker routuje i loguje WYŁĄCZNIE kopię oczyszczoną (klucz:
route_and_log_redacted_copy_only). Oryginał zostawia po sobie tylko hash.
"""

import re

# (etykieta, wzorzec) — świadomie zachłanne; lepiej zaczernić za dużo niż wypuścić sekret
PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("anthropic-key", re.compile(r"sk-ant-[A-Za-z0-9_-]{10,}")),
    ("openai-key", re.compile(r"sk-[A-Za-z0-9_-]{20,}")),
    ("aws-key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("github-token", re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}")),
    ("slack-token", re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}")),
    ("bearer", re.compile(r"(?i)bearer\s+[A-Za-z0-9._~+/=-]{16,}")),
    ("generic-assignment", re.compile(
        r"(?i)(api[_-]?key|secret|token|password|passwd)\s*[:=]\s*\S{8,}"
    )),
    ("private-key-block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
]


def redact(text: str) -> tuple[str, list[str]]:
    """Zwraca (kopia_oczyszczona, lista_etykiet_trafień)."""
    hits: list[str] = []
    clean = text
    for label, pattern in PATTERNS:
        if pattern.search(clean):
            hits.append(label)
            clean = pattern.sub(f"[REDACTED:{label}]", clean)
    return clean, hits
