"""Testy adapterów na atrapach binarek — zero prawdziwych modeli, zero sieci."""

import json
import os
import stat

import pytest

from room.adapters.base import PresenceState
from room.adapters.klaris import KlarisAdapter
from room.adapters.kord import KordAdapter
from room.messages import Msg
from room.prompt import render_turn, truncate_to_budget
from room.tokenizer import RoomTokenizer

WORDS = RoomTokenizer(name="words", provisional=True, _count=lambda s: len(s.split()))


def make_stub(tmp_path, name: str, script: str) -> str:
    path = tmp_path / name
    path.write_text("#!/bin/sh\n" + script)
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return str(path)


# --- Klaris ------------------------------------------------------------------

CLAUDE_STUB = """\
printf '%s\\n' "$@" > "{args_file}"
cat > "{prompt_file}"
cat <<'EOF'
{{"type":"result","result":"Cześć Kord, tu Klaris.","usage":{{"input_tokens":120,"output_tokens":15,"cache_read_input_tokens":7,"cache_creation_input_tokens":3}}}}
EOF
"""


def test_klaris_parses_result_and_usage(tmp_path):
    args_file = tmp_path / "args.txt"
    prompt_file = tmp_path / "prompt.txt"
    binary = make_stub(
        tmp_path, "claude", CLAUDE_STUB.format(args_file=args_file, prompt_file=prompt_file)
    )
    adapter = KlarisAdapter(WORDS, input_budget=1800, workdir=tmp_path / "wd", binary=binary)

    msg = adapter.speak("PREAMBUŁA", [Msg("Kord", "Cześć")], max_output_tokens=500)

    assert msg.content == "Cześć Kord, tu Klaris."
    assert msg.provider_usage == {"input": 120, "output": 15, "cache_read": 7, "cache_write": 3}

    argv = args_file.read_text().splitlines()
    # izolacja: zero narzędzi, zero ustawień użytkownika, tożsamość w system prompt
    assert "--tools" in argv and argv[argv.index("--tools") + 1] == ""
    assert "--setting-sources" in argv and argv[argv.index("--setting-sources") + 1] == ""
    assert "--system-prompt" in argv and argv[argv.index("--system-prompt") + 1] == "PREAMBUŁA"
    # tura przez stdin — nie jako argument (wariadyczne --tools by ją połknęło)
    prompt = prompt_file.read_text()
    assert "Kord: Cześć" in prompt and "Twoja tura, Klaris" in prompt


def test_klaris_preflight_offline_when_binary_missing(tmp_path):
    adapter = KlarisAdapter(WORDS, 1800, tmp_path, binary="no-such-binary-xyz")
    assert adapter.preflight() == PresenceState.SLEEPING_OFFLINE


def test_klaris_raises_on_nonzero_exit(tmp_path):
    binary = make_stub(tmp_path, "claude", "echo boom >&2; exit 3\n")
    adapter = KlarisAdapter(WORDS, 1800, tmp_path / "wd", binary=binary)
    with pytest.raises(RuntimeError, match="rc=3"):
        adapter.speak("P", [], 500)


# --- Kord --------------------------------------------------------------------

CODEX_STUB = """\
printf '%s\\n' "$@" > "{args_file}"
cat <<'EOF'
{{"type":"item.completed","item":{{"item_type":"agent_message","text":"Cześć Klaris, tu Kord."}}}}
{{"type":"turn.completed","usage":{{"input_tokens":200,"cached_input_tokens":50,"output_tokens":30}}}}
EOF
"""


def test_kord_parses_jsonl_and_disables_user_mcp(tmp_path):
    args_file = tmp_path / "args.txt"
    binary = make_stub(tmp_path, "codex", CODEX_STUB.format(args_file=args_file))
    config = tmp_path / "config.toml"
    config.write_text(
        '[mcp_servers.linear]\nurl = "https://x"\n[mcp_servers.notion]\nurl = "https://y"\n'
    )
    adapter = KordAdapter(WORDS, 1800, tmp_path / "wd", binary=binary, codex_config=config)

    msg = adapter.speak("PREAMBUŁA", [], max_output_tokens=500)

    assert msg.content == "Cześć Klaris, tu Kord."
    assert msg.provider_usage == {"input": 200, "output": 30, "cache_read": 50}

    argv = args_file.read_text().splitlines()
    # izolacja: każdy serwer MCP z configu użytkownika jawnie wyłączony
    assert "mcp_servers.linear.enabled=false" in argv
    assert "mcp_servers.notion.enabled=false" in argv
    assert argv[argv.index("--sandbox") + 1] == "read-only"


def test_kord_falls_back_to_plain_text(tmp_path):
    binary = make_stub(tmp_path, "codex", 'echo "zwykly tekst bez json"\n')
    adapter = KordAdapter(WORDS, 1800, tmp_path / "wd", binary=binary,
                          codex_config=tmp_path / "missing.toml")
    msg = adapter.speak("P", [], 500)
    assert msg.content == "zwykly tekst bez json"


def test_kord_preflight_offline_now():
    """Stan faktyczny na maszynie Jana: codex niezainstalowany → SLEEPING_OFFLINE."""
    adapter = KordAdapter(WORDS, 1800, workdir=None, binary="codex-definitely-missing")
    assert adapter.preflight() == PresenceState.SLEEPING_OFFLINE


# --- prompt ------------------------------------------------------------------

def test_truncation_keeps_newest():
    msgs = [Msg("A", "jeden dwa trzy"), Msg("B", "cztery pięć"), Msg("A", "sześć")]
    kept = truncate_to_budget(msgs, WORDS, budget=3)
    assert [m.content for m in kept] == ["cztery pięć", "sześć"]


def test_render_first_turn_and_reply():
    assert "Mówisz pierwszy" in render_turn([], "Klaris")
    out = render_turn([Msg("Klaris", "Cześć")], "Kord")
    assert "Klaris: Cześć" in out and out.endswith("Twoja tura, Kord:")
