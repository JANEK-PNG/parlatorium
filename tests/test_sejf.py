"""Testy sejfu: szyfrowanie bez hasła, odczyt tylko z hasłem, brak jawnych śladów."""

import pytest

from room import sejf


def test_roundtrip_and_wrong_password(tmp_path):
    sejf.init_safe(tmp_path, "sekret-jana")

    locked = sejf.lock_bytes(tmp_path, "spotkanie.jsonl", "PIES na tablicy".encode())
    assert locked.exists() and locked.suffix == ".age"
    # szyfrogram nie zawiera jawnej treści
    assert b"PIES" not in locked.read_bytes()

    assert sejf.unlock(tmp_path, "spotkanie.jsonl", "sekret-jana").decode() == "PIES na tablicy"
    with pytest.raises(Exception):
        sejf.unlock(tmp_path, "spotkanie.jsonl", "zle-haslo")


def test_lock_file_removes_plaintext(tmp_path):
    sejf.init_safe(tmp_path, "pw")
    plain = tmp_path / "t.jsonl"
    plain.write_text("tajna rozmowa")
    sejf.lock_file(tmp_path, plain)
    assert not plain.exists()  # jawny oryginał znika
    assert sejf.unlock(tmp_path, "t.jsonl", "pw").decode() == "tajna rozmowa"


def test_encryption_needs_no_password(tmp_path):
    """Pokój szyfruje samym kluczem publicznym — nie zna hasła."""
    sejf.init_safe(tmp_path, "pw")
    (tmp_path / sejf.IDENTITY_FILE).rename(tmp_path / "identity.bak")  # bez klucza prywatnego
    sejf.lock_bytes(tmp_path, "x", b"data")  # nadal działa


def test_reinit_refused(tmp_path):
    sejf.init_safe(tmp_path, "pw")
    with pytest.raises(RuntimeError, match="odciąłby dostęp"):
        sejf.init_safe(tmp_path, "inne")


def test_render_transcript_readable():
    import json
    raw = "\n".join([
        json.dumps({"type": "meta", "event": "OPEN", "mode": "poznanie",
                    "first_speaker": "Kord", "ts": "2026-07-17"}),
        json.dumps({"type": "meta", "event": "ROOM_ENVIRONMENT", "content": "tablica: PIES"}),
        json.dumps({"type": "meta", "event": "CHAIR_CMD", "command": "g"}),
        json.dumps({"type": "message", "from": "Kord", "room_tokens": 42,
                    "content": "Widzę tablicę."}),
        json.dumps({"type": "meta", "event": "CLOSE", "end_state": "CLOSED_BY_CHAIR",
                    "rounds_completed": 6, "duration_seconds": 764,
                    "usage_by_agent": {"Kord": {"room_tokens": 42, "calls": 1,
                                                "provider_tokens": 100}}}),
    ]).encode()
    out = sejf.render("x.jsonl.age", raw).decode()
    assert "q wyjście" in out                 # instrukcja na górze
    assert "POKÓJ OTWARTY" in out and "── Kord" in out
    assert "Widzę tablicę." in out and "KONIEC" in out
    assert '{"type"' not in out               # zero surowego JSON-a


def test_render_report_readable():
    import json
    raw = json.dumps({"meeting_status": "CLOSED_BY_CHAIR", "outcome_status": "NO_OUTCOME",
                      "human_decision_needed": False,
                      "topics_in_1_to_3_sentences": "Rozmowa o tablicy.",
                      "usage_by_agent": {}, "infrastructure_usage": {}}).encode()
    out = sejf.render("x.report.json.age", raw).decode()
    assert "RAPORT STENOGRAFA" in out and "Rozmowa o tablicy." in out


def test_render_falls_back_to_raw():
    assert sejf.render("cokolwiek.bin", b"\x00\x01") == b"\x00\x01"
