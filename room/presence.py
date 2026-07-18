"""Obecność pasywna: pliki stanu z obserwowanym sygnałem.

Zasady z klucza:
- nigdy nie wywołujemy modelu, żeby sprawdzić czy śpi
- obserwacja ma TTL 30 s (stany AWAKE); wygasła → UNKNOWN/None
- SLEEPING_QUOTA trzyma się do znanego resetu (observed signal,
  np. komunikat błędu dostawcy z dokładną datą)
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

AWAKE_TTL_SECONDS = 30
SLEEP_STATES = {"SLEEPING_QUOTA", "SLEEPING_OFFLINE", "DND"}


def record(
    presence_dir: Path,
    name: str,
    state: str,
    expires_at: datetime | None = None,
    source: str = "",
) -> None:
    presence_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "state": state,
        "observed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "expires_at": expires_at.isoformat(timespec="seconds") if expires_at else None,
        "signal_source": source,
    }
    (presence_dir / f"{name}.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def current(presence_dir: Path, name: str, now: datetime | None = None) -> str | None:
    """Zwraca ważny stan albo None (= brak wiedzy, wygasła obserwacja)."""
    path = presence_dir / f"{name}.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    now = now or datetime.now(timezone.utc)
    observed = datetime.fromisoformat(data["observed_at"])
    expires = datetime.fromisoformat(data["expires_at"]) if data.get("expires_at") else None

    if data["state"] in SLEEP_STATES:
        if expires and now >= expires:
            return None  # sen minął → znów nie wiemy
        return data["state"]

    ttl_end = observed + timedelta(seconds=AWAKE_TTL_SECONDS)
    if now >= (expires or ttl_end):
        return None
    return data["state"]
