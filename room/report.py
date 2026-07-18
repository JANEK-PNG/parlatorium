"""Odizolowany stenograf post-hoc.

Zasady z klucza (mystery_box.posthoc_report):
- powstaje dopiero po zamknięciu pokoju, nie wpływa na przebieg
- nie wraca do uczestników (may_send_feedback_to_room_participants: false)
- obciąża budżet infrastruktury, nie budżety głosu uczestników

Czystość tekstu + sejf (zasady Jana 2026-07-17): funkcja dostaje dane
z pamięci brokera i ZWRACA raport — nigdy sama nie pisze jawnego pliku.
Zapis (zaszyfrowany, do sejfu) należy do wołającego.
"""

import json
import subprocess

STENOGRAPHER_SYSTEM = (
    "Jesteś odizolowanym stenografem Pokoju AI. Dostajesz zamknięty stenogram "
    "rozmowy dwóch uczestników. Nie jesteś uczestnikiem. Zwróć WYŁĄCZNIE obiekt "
    "JSON z polami: topics_in_1_to_3_sentences (string, 1-3 zdania po polsku), "
    "human_decision_needed (boolean), outcome_status (string: OUTCOME, NO_OUTCOME "
    "lub DISAGREEMENT_RECORDED). Zero markdown, zero komentarza."
)


def stenographer_report(
    messages: list[tuple[str, str]],
    end_state: str,
    usage_by_agent: dict,
    binary: str = "claude",
    timeout: int = 120,
) -> dict:
    digest = "\n\n".join(f"{author}: {content}" for author, content in messages)[:8000]

    proc = subprocess.run(
        [binary, "-p", "--output-format", "json", "--tools", "",
         "--setting-sources", "", "--system-prompt", STENOGRAPHER_SYSTEM],
        input=f"Stenogram:\n\n{digest}\n\nJSON:",
        capture_output=True, text=True, timeout=timeout,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"stenograf: claude -p rc={proc.returncode}: {proc.stderr[:300]}")

    data = json.loads(proc.stdout)
    raw = (data.get("result") or "").strip().removeprefix("```json").removesuffix("```").strip()
    fields = json.loads(raw)

    return {
        "meeting_status": end_state,
        "usage_by_agent": usage_by_agent,
        "topics_in_1_to_3_sentences": fields.get("topics_in_1_to_3_sentences", ""),
        "human_decision_needed": bool(fields.get("human_decision_needed", False)),
        "outcome_status": fields.get("outcome_status", "NO_OUTCOME"),
        "infrastructure_usage": {
            "input": data.get("usage", {}).get("input_tokens", 0),
            "output": data.get("usage", {}).get("output_tokens", 0),
        },
    }
