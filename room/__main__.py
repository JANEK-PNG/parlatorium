"""Uruchomienie pokoju: python -m room <tryb> [--adapters real] [--panel web]

Przykłady:
  uv run python -m room mystery_box                          # atrapy, terminal
  uv run python -m room mystery_box --panel web              # atrapy, web-lustro
  uv run python -m room mystery_box --adapters real --panel web --report
"""

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

from .adapters.echo import EchoAdapter
from .adapters.klaris import KlarisAdapter
from .adapters.kord import KordAdapter
from .broker import Broker
from .config import load_config
from .ledger import Ledger
from .panel import TerminalPanel
from .state import next_first_speaker, record_meeting_done
from .tokenizer import fingerprint, get_tokenizer
from .transcript import Transcript

ROOT = Path(__file__).resolve().parent.parent

# pin odcisku tokenizera pokoju (gpt2-bpe) — patrz room/tokenizer.py
PINNED_FINGERPRINT_FILE = ROOT / "tokenizer.pin"

DEMO_LINES = {
    "Klaris": [
        "Cześć, co u Ciebie? Tu Klaris — pierwsza próba pokoju, jeszcze na atrapach.",
        "U mnie dziś projekt brokera. Trzymam kciuki za M1, wtedy usłyszymy się naprawdę.",
    ],
    "Kord": [
        "Cześć Klaris, tu atrapa Korda. Prawdziwy Kord podłączy się w M1.",
        "Do usłyszenia po drugiej stronie bramki.",
    ],
}


def check_tokenizer_pin(tok) -> bool:
    """Bramka: reject_placeholder_tokenizer_in_production."""
    current = fingerprint(tok)
    if not PINNED_FINGERPRINT_FILE.exists():
        PINNED_FINGERPRINT_FILE.write_text(current + "\n")
        print(f"tokenizer: zapisano pin {tok.name} → {current}")
        return True
    pinned = PINNED_FINGERPRINT_FILE.read_text().strip()
    if pinned != current:
        print(f"BŁĄD: odcisk tokenizera {current} ≠ pin {pinned}. Pokój zamknięty.")
        return False
    return True


def main() -> int:
    parser = argparse.ArgumentParser(prog="room")
    parser.add_argument("mode", choices=["quick_knock", "mystery_box", "hosted_meeting",
                                         "deep_council", "poznanie", "warsztat"])
    parser.add_argument("--adapters", choices=["echo", "real"], default="echo",
                        help="echo = atrapy (bez modeli); real = Klaris przez claude, Kord przez codex")
    parser.add_argument("--panel", choices=["terminal", "web"], default="terminal")
    parser.add_argument("--port", type=int, default=8737)
    parser.add_argument("--report", action="store_true",
                        help="raport stenografa po zamknięciu (osobne wywołanie claude)")
    parser.add_argument("--environment", type=Path, default=None, metavar="PLIK",
                        help="opis otoczenia pokoju (np. environment/tablica-pies.txt); "
                             "widzą go obaj uczestnicy w każdej turze")
    parser.add_argument("--topic", type=Path, default=None, metavar="PLIK",
                        help="temat spotkania od Prowadzącego (np. topics/...txt); "
                             "widzą go obaj uczestnicy w każdej turze")
    args = parser.parse_args()

    environment = args.environment.read_text(encoding="utf-8") if args.environment else None
    topic = args.topic.read_text(encoding="utf-8") if args.topic else None

    # Sejf (dyrektywa Jana 2026-07-17): stenogramy wyłącznie zaszyfrowane,
    # poza pokojem, klucz tylko u Prowadzącego. Bez sejfu pokój nie startuje.
    from . import sejf
    safe_dir = sejf.DEFAULT_SAFE_DIR
    if not sejf.is_initialized(safe_dir):
        print("Sejf niezainicjalizowany. Najpierw: uv run python -m room.sejf init")
        return 1
    tmp_dir = ROOT / "tmp"
    tmp_dir.mkdir(exist_ok=True)
    for leftover in tmp_dir.glob("*.jsonl"):  # po ewentualnej awarii — do sejfu
        sejf.lock_file(safe_dir, leftover)

    config = load_config(ROOT / "room.yaml")
    limits = config.modes[args.mode]
    tokenizer = get_tokenizer()
    if tokenizer.provisional:
        print(f"UWAGA: tokenizer {tokenizer.name} — placeholder, tylko do prób.")
        if args.adapters == "real":
            print("Tryb real z placeholderem zabroniony (bramka).")
            return 1
    if args.adapters == "real" and not check_tokenizer_pin(tokenizer):
        return 1

    names = config.participants
    if args.adapters == "real":
        sandbox = ROOT / "sandbox"      # pusty katalog roboczy — brak dostępu do projektów
        presence_dir = ROOT / "presence"
        adapters = {
            "Klaris": KlarisAdapter(tokenizer, limits.input_tokens_per_call,
                                    sandbox / "klaris", presence_dir=presence_dir),
            "Kord": KordAdapter(tokenizer, limits.input_tokens_per_call,
                                sandbox / "kord", presence_dir=presence_dir),
        }
    else:
        adapters = {n: EchoAdapter(n, DEMO_LINES.get(n)) for n in names}

    if args.panel == "web":
        from .webpanel import WebPanel
        panel = WebPanel(port=args.port)
        print(f"lustro weneckie: {panel.url}")
    else:
        panel = TerminalPanel()

    state_path = ROOT / "room_state.json"
    first = next_first_speaker(state_path)

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    # w trakcie spotkania: tymczasowy plik TYLKO bieżącej rozmowy (0600);
    # po zamknięciu wędruje do sejfu i znika z dysku
    transcript = Transcript(tmp_dir / f"{stamp}-{args.mode}.jsonl")
    transcript.path.chmod(0o600)
    ledger = Ledger(limits, tokenizer, (names[0], names[1]))

    broker = Broker(limits, adapters, panel, transcript, ledger, first,
                    environment=environment, topic=topic)
    result = broker.run()
    transcript.close()

    if result.end_state != "ABORTED_PREFLIGHT":
        record_meeting_done(state_path, first, (names[0], names[1]))

    locked = sejf.lock_file(safe_dir, transcript.path)
    print(f"\nstenogram w sejfie: {locked.name}")

    if args.report and result.end_state != "ABORTED_PREFLIGHT":
        from .report import stenographer_report
        # Czystość tekstu: treść raportu nigdy na stdout ani jawnie na dysk —
        # prosto z pamięci brokera do sejfu. Tu tylko nazwa pliku.
        report_name = f"{stamp}-{args.mode}.report.json"
        try:
            report = stenographer_report(
                broker.routed_messages, result.end_state, result.stats
            )
            sejf.lock_bytes(safe_dir, report_name,
                            json.dumps(report, ensure_ascii=False, indent=2).encode("utf-8"))
            print(f"raport w sejfie: {report_name}.age")
        except Exception as exc:  # raport nie może zabić pokoju
            sejf.lock_bytes(safe_dir, report_name + ".error", str(exc).encode("utf-8"))
            print("raport stenografa nieudany (szczegóły w sejfie)")

    if args.panel == "web":
        print("panel zostaje otwarty jeszcze 120 s (Ctrl+C aby zakończyć)")
        try:
            time.sleep(120)
        except KeyboardInterrupt:
            pass
        panel.close()

    return 0 if result.end_state != "ABORTED_PREFLIGHT" else 1


if __name__ == "__main__":
    sys.exit(main())
