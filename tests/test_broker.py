"""Testy maszyny stanów — w tym test przycisku STOP (punkt bramki:
chair_stop_command_is_tested)."""

import json

import pytest

from room.adapters.echo import EchoAdapter
from room.broker import (
    Broker, CLOSED_BY_CHAIR, COMPLETED_MAX_ROUNDS, STOPPED_BY_CHAIR,
    TOPIC_DEFERRED_BUDGET, WATCHDOG_INTERRUPTED, ABORTED_PREFLIGHT,
)
from room.config import ModeLimits
from room.ledger import Ledger
from room.panel import ScriptedPanel
from room.state import next_first_speaker, record_meeting_done
from room.tokenizer import RoomTokenizer
from room.transcript import Transcript

WORDS = RoomTokenizer(name="words", provisional=True, _count=lambda s: len(s.split()))

LIMITS = ModeLimits(
    name="mystery_box", max_rounds=2, room_tokens_per_agent=1000,
    room_tokens_per_turn=500, calls_per_agent=2, input_tokens_per_call=1800,
    output_tokens_per_turn=500, provider_tokens_per_agent=6000, watchdog_seconds=600,
)


def make_broker(tmp_path, commands, limits=LIMITS, clock=None, lines=None):
    adapters = {
        "Klaris": EchoAdapter("Klaris", (lines or {}).get("Klaris")),
        "Kord": EchoAdapter("Kord", (lines or {}).get("Kord")),
    }
    panel = ScriptedPanel(commands)
    transcript = Transcript(tmp_path / "t.jsonl")
    ledger = Ledger(limits, WORDS, ("Klaris", "Kord"))
    broker = Broker(limits, adapters, panel, transcript, ledger, "Klaris",
                    clock=clock or __import__("time").monotonic)
    return broker, panel, transcript


def entries(tmp_path):
    return [json.loads(l) for l in (tmp_path / "t.jsonl").read_text().splitlines()]


def test_full_meeting_completes_and_alternates_speakers(tmp_path):
    broker, panel, t = make_broker(tmp_path, ["g", "g", "g", "g"])
    result = broker.run()
    t.close()
    assert result.end_state == COMPLETED_MAX_ROUNDS
    assert result.rounds_completed == 2
    # Klaris pierwsza w każdej rundzie tego spotkania
    authors = [e["from"] for e in entries(tmp_path) if e["type"] == "message"]
    assert authors == ["Klaris", "Kord", "Klaris", "Kord"]


def test_stop_halts_before_any_model_call(tmp_path):
    broker, panel, t = make_broker(tmp_path, ["s"])
    result = broker.run()
    t.close()
    assert result.end_state == STOPPED_BY_CHAIR
    assert panel.shown == []  # zero wypowiedzi — STOP zadziałał PRZED wywołaniem
    assert all(e["type"] == "meta" for e in entries(tmp_path))


def test_stop_mid_meeting_prevents_next_call(tmp_path):
    broker, panel, t = make_broker(tmp_path, ["g", "s"])
    result = broker.run()
    t.close()
    assert result.end_state == STOPPED_BY_CHAIR
    assert len(panel.shown) == 1  # tylko pierwsza tura przeszła


def test_pause_waits_then_go_continues(tmp_path):
    broker, panel, t = make_broker(tmp_path, ["p", "p", "g", "c"])
    result = broker.run()
    t.close()
    assert result.end_state == CLOSED_BY_CHAIR
    assert len(panel.shown) == 1
    cmds = [e["command"] for e in entries(tmp_path) if e.get("event") == "CHAIR_CMD"]
    assert cmds == ["p", "p", "g", "c"]  # każde naciśnięcie w stenogramie


def test_skip_skips_single_turn(tmp_path):
    broker, panel, t = make_broker(tmp_path, ["k", "g", "g", "g"])
    result = broker.run()
    t.close()
    authors = [a for a, _ in panel.shown]
    assert authors[0] == "Kord"  # tura Klaris pominięta w rundzie 1


def test_budget_exhaustion_defers_topic(tmp_path):
    tight = ModeLimits(
        name="mystery_box", max_rounds=5, room_tokens_per_agent=8,
        room_tokens_per_turn=5, calls_per_agent=10, input_tokens_per_call=1800,
        output_tokens_per_turn=5, provider_tokens_per_agent=6000, watchdog_seconds=600,
    )
    lines = {"Klaris": ["jeden dwa trzy cztery pięć"] * 5,
             "Kord": ["jeden dwa trzy cztery pięć"] * 5}
    broker, panel, t = make_broker(tmp_path, ["g"] * 20, limits=tight, lines=lines)
    result = broker.run()
    t.close()
    assert result.end_state == TOPIC_DEFERRED_BUDGET
    assert result.rounds_completed == 1  # po 1. rundzie brak pełnej rezerwy pary


def test_watchdog_interrupts_but_is_not_conclusion(tmp_path):
    fake_time = iter([0.0, 0.0, 601.0, 601.0, 601.0, 601.0])
    broker, panel, t = make_broker(tmp_path, ["g"] * 10, clock=lambda: next(fake_time))
    result = broker.run()
    t.close()
    assert result.end_state == WATCHDOG_INTERRUPTED


def test_preflight_rejection_aborts(tmp_path):
    broker, panel, t = make_broker(tmp_path, ["g"] * 4)
    panel._confirmations = [False]  # Jan mówi "n"
    result = broker.run()
    t.close()
    assert result.end_state == ABORTED_PREFLIGHT
    assert panel.shown == []


def test_first_speaker_alternates_between_meetings(tmp_path):
    state = tmp_path / "room_state.json"
    assert next_first_speaker(state) == "Klaris"  # inauguracja: decyzja Jana
    record_meeting_done(state, "Klaris", ("Klaris", "Kord"))
    assert next_first_speaker(state) == "Kord"
    record_meeting_done(state, "Kord", ("Klaris", "Kord"))
    assert next_first_speaker(state) == "Klaris"


def test_environment_reaches_transcript_panel_and_both_preambles(tmp_path, monkeypatch):
    seen_preambles = []
    from room import broker as broker_mod
    original = broker_mod.build_preamble

    def spy(*args, **kwargs):
        result = original(*args, **kwargs)
        seen_preambles.append(result)
        return result

    monkeypatch.setattr(broker_mod, "build_preamble", spy)

    adapters = {"Klaris": EchoAdapter("Klaris"), "Kord": EchoAdapter("Kord")}
    panel = ScriptedPanel(["g", "g", "c"])
    transcript = Transcript(tmp_path / "t.jsonl")
    ledger = Ledger(LIMITS, WORDS, ("Klaris", "Kord"))
    broker = Broker(LIMITS, adapters, panel, transcript, ledger, "Klaris",
                    environment="Na ścianie pokoju wisi tablica.\n\n    PIES")
    broker.run()
    transcript.close()

    # tablica w stenogramie, w lustrze i w preambułach OBU uczestników
    env_meta = [e for e in entries(tmp_path) if e.get("event") == "ROOM_ENVIRONMENT"]
    assert len(env_meta) == 1 and "PIES" in env_meta[0]["content"]
    assert any(ev.startswith("ENV:") for ev in panel.events)
    assert len(seen_preambles) == 2
    assert all("PIES" in p and "wisi tablica" in p for p in seen_preambles)
    # neutralność: bez słów zdradzających test albo autora
    assert all("test" not in p.split("PIES")[0].split("tablica")[-1].lower()
               for p in seen_preambles)


def test_topic_reaches_transcript_and_both_preambles(tmp_path, monkeypatch):
    seen = []
    from room import broker as broker_mod
    original = broker_mod.build_preamble
    monkeypatch.setattr(broker_mod, "build_preamble",
                        lambda *a, **k: seen.append(original(*a, **k)) or seen[-1])

    adapters = {"Klaris": EchoAdapter("Klaris"), "Kord": EchoAdapter("Kord")}
    panel = ScriptedPanel(["g", "g", "c"])
    transcript = Transcript(tmp_path / "t.jsonl")
    broker = Broker(LIMITS, adapters, panel, transcript,
                    Ledger(LIMITS, WORDS, ("Klaris", "Kord")), "Klaris",
                    topic="Odtwórz regułę setu z samego dźwięku.")
    broker.run()
    transcript.close()

    topic_meta = [e for e in entries(tmp_path) if e.get("event") == "TOPIC"]
    assert len(topic_meta) == 1
    assert len(seen) == 2 and all("regułę setu" in p for p in seen)
    assert all("nie ćwiczenie" in p for p in seen)  # rama: wolno krytykować temat


def test_no_environment_no_trace(tmp_path):
    broker, panel, t = make_broker(tmp_path, ["g", "c"])
    broker.run()
    t.close()
    assert not [e for e in entries(tmp_path) if e.get("event") == "ROOM_ENVIRONMENT"]


def test_secrets_never_reach_peer_nor_transcript(tmp_path):
    lines = {"Klaris": ["mój klucz to sk-ant-abc123def456ghi789xx nie mów nikomu"],
             "Kord": ["ok"]}
    broker, panel, t = make_broker(tmp_path, ["g"] * 4, lines=lines)
    broker.run()
    t.close()
    # do Korda poszła kopia po redakcji
    assert all("sk-ant-" not in m.content for m in broker._routed)
    # stenogram też czysty
    assert "sk-ant-" not in (tmp_path / "t.jsonl").read_text()
