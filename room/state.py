"""Stan pokoju między spotkaniami: naprzemienność pierwszego mówcy.

Inauguracja: Klaris mówi pierwsza (decyzja Jana, 15.07.2026),
potem automatyczna zmiana co spotkanie.
"""

import json
from pathlib import Path

INITIAL_FIRST_SPEAKER = "Klaris"


def next_first_speaker(state_path: Path) -> str:
    if state_path.exists():
        return json.loads(state_path.read_text(encoding="utf-8"))["next_first_speaker"]
    return INITIAL_FIRST_SPEAKER


def record_meeting_done(state_path: Path, first_speaker: str, participants: tuple[str, str]) -> None:
    other = participants[1] if first_speaker == participants[0] else participants[0]
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps({"next_first_speaker": other}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
