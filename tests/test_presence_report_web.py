"""Testy M2/M4: obecność, raport stenografa, web-lustro, pin tokenizera."""

import json
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

from room import presence
from room.adapters.base import PresenceState
from room.adapters.kord import KordAdapter
from room.report import stenographer_report
from room.tokenizer import RoomTokenizer, fingerprint, get_tokenizer
from room.webpanel import WebPanel

WORDS = RoomTokenizer(name="words", provisional=True, _count=lambda s: len(s.split()))
NOW = datetime(2026, 7, 16, 12, 0, tzinfo=timezone.utc)


# --- obecność -----------------------------------------------------------------

def test_sleeping_quota_holds_until_reset(tmp_path):
    presence.record(tmp_path, "Kord", "SLEEPING_QUOTA",
                    expires_at=NOW + timedelta(days=5), source="test")
    assert presence.current(tmp_path, "Kord", now=NOW) == "SLEEPING_QUOTA"
    assert presence.current(tmp_path, "Kord", now=NOW + timedelta(days=6)) is None


def test_awake_observation_expires_after_ttl(tmp_path):
    presence.record(tmp_path, "Klaris", "AWAKE_IDLE")
    observed = datetime.now(timezone.utc)
    assert presence.current(tmp_path, "Klaris", now=observed) == "AWAKE_IDLE"
    assert presence.current(tmp_path, "Klaris", now=observed + timedelta(seconds=31)) is None


def test_kord_preflight_reads_presence(tmp_path):
    presence.record(tmp_path, "Kord", "SLEEPING_QUOTA",
                    expires_at=datetime.now(timezone.utc) + timedelta(days=1))
    adapter = KordAdapter(WORDS, 1800, tmp_path / "wd", binary="sh",  # sh zawsze jest
                          codex_config=tmp_path / "none.toml", presence_dir=tmp_path)
    assert adapter.preflight() == PresenceState.SLEEPING_QUOTA


def test_kord_parses_reset_date():
    error = ("You've hit your usage limit. Upgrade to Pro or "
             "try again at Jul 21st, 2026 11:11 PM.")
    reset = KordAdapter._parse_reset(error)
    assert reset is not None
    assert (reset.month, reset.day, reset.year) == (7, 21, 2026)
    assert (reset.hour, reset.minute) == (23, 11)


# --- pin tokenizera -------------------------------------------------------------

def test_fingerprint_stable_and_sensitive():
    assert fingerprint(WORDS) == fingerprint(WORDS)
    other = RoomTokenizer(name="words", provisional=True, _count=lambda s: len(s.split()) + 1)
    assert fingerprint(WORDS) != fingerprint(other)


def test_gpt2_fingerprint_matches_pin_if_present():
    pin_file = Path(__file__).parent.parent / "tokenizer.pin"
    tok = get_tokenizer()
    if tok.provisional or not pin_file.exists():
        return  # pin powstaje przy pierwszym biegu real
    assert fingerprint(tok) == pin_file.read_text().strip()


# --- raport stenografa ----------------------------------------------------------

STENO_STUB = """\
cat > /dev/null
cat <<'EOF'
{"type":"result","result":"{\\"topics_in_1_to_3_sentences\\":\\"Powitanie i próba pokoju.\\",\\"human_decision_needed\\":false,\\"outcome_status\\":\\"NO_OUTCOME\\"}","usage":{"input_tokens":300,"output_tokens":40}}
EOF
"""


def test_stenographer_report_returns_dict_writes_nothing(tmp_path):
    import stat
    stub = tmp_path / "claude"
    stub.write_text("#!/bin/sh\n" + STENO_STUB)
    stub.chmod(stub.stat().st_mode | stat.S_IEXEC)

    report = stenographer_report(
        [("Klaris", "Cześć"), ("Kord", "Cześć, Klaris")],
        end_state="COMPLETED_MAX_ROUNDS", usage_by_agent={"Klaris": {}},
        binary=str(stub),
    )

    assert report["meeting_status"] == "COMPLETED_MAX_ROUNDS"
    assert report["outcome_status"] == "NO_OUTCOME"
    assert report["infrastructure_usage"]["output"] == 40
    # czystość: stenograf niczego nie pisze na dysk — zapis należy do sejfu
    assert list(tmp_path.glob("*.json")) == []


# --- web-lustro -----------------------------------------------------------------

def test_webpanel_serves_page_and_routes_commands():
    panel = WebPanel(port=0)  # port efemeryczny
    try:
        html = urllib.request.urlopen(panel.url + "/", timeout=5).read().decode()
        assert "EKRAN KLARIS" in html and "EKRAN KORDA" in html and "STOP" in html

        req = urllib.request.Request(
            panel.url + "/cmd", data=json.dumps({"cmd": "g"}).encode(),
            method="POST")
        assert urllib.request.urlopen(req, timeout=5).status == 204
        assert panel.command() == "g"  # guzik z HTTP dotarł do brokera

        for answer, expected in (("y", True), ("n", False)):
            req = urllib.request.Request(
                panel.url + "/cmd", data=json.dumps({"cmd": answer}).encode(),
                method="POST")
            urllib.request.urlopen(req, timeout=5)
            assert panel.confirm("Otworzyć?") is expected

        req = urllib.request.Request(
            panel.url + "/cmd", data=json.dumps({"cmd": "rm -rf"}).encode(),
            method="POST")
        try:
            urllib.request.urlopen(req, timeout=5)
            assert False, "śmieciowa komenda przyjęta"
        except urllib.error.HTTPError as e:
            assert e.code == 400
    finally:
        panel.close()
