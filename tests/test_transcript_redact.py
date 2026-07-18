import json

from room.redact import redact
from room.transcript import Transcript, sha256_text


def test_redact_catches_api_keys_and_bearer():
    text = "mój klucz: sk-ant-abc123def456ghi789 oraz Bearer abcdef1234567890XYZW"
    clean, hits = redact(text)
    assert "sk-ant-" not in clean
    assert "Bearer abcdef" not in clean
    assert "anthropic-key" in hits and "bearer" in hits


def test_redact_clean_text_untouched():
    text = "zwykła rozmowa o architekturze brokera"
    clean, hits = redact(text)
    assert clean == text and hits == []


def test_transcript_appends_sequentially_with_original_hash(tmp_path):
    path = tmp_path / "t.jsonl"
    t = Transcript(path)
    original = "sekret: sk-ant-abc123def456ghi789xx"
    clean, hits = redact(original)
    t.meta("OPEN", mode="test")
    t.message(
        author="A", redacted_content=clean, sha256_original=sha256_text(original),
        room_tokens=5, provider_usage={"output": 9}, redaction_hits=hits,
        tokenizer_name="words",
    )
    t.meta("CLOSE", end_state="X")
    t.close()

    lines = [json.loads(l) for l in path.read_text().splitlines()]
    assert [e["seq"] for e in lines] == [1, 2, 3]  # monotoniczny append
    msg = lines[1]
    assert "sk-ant-" not in msg["content"]  # log tylko po redakcji
    assert msg["sha256_original"] == sha256_text(original)  # hash z oryginału


def test_transcript_survives_reopen_as_append(tmp_path):
    path = tmp_path / "t.jsonl"
    t1 = Transcript(path)
    t1.meta("OPEN")
    t1.close()
    t2 = Transcript(path)
    t2.meta("OPEN")
    t2.close()
    assert len(path.read_text().splitlines()) == 2  # nic nie nadpisane
