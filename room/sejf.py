"""Sejf na stenogramy — poza pokojem, klucz tylko u Prowadzącego.

Model zagrożeń: uczestnik z shellem w piaskownicy read-only może czytać
cały dysk jako ten sam użytkownik. Uprawnienia POSIX go nie zatrzymają —
zatrzymuje go kryptografia (age / X25519):

- spotkanie szyfruje KLUCZEM PUBLICZNYM (recipient.txt) — bez hasła,
  pokój nigdy nie zna sekretu;
- klucz prywatny leży w sejfie wyłącznie zawinięty hasłem Prowadzącego
  (identity.age); jawny klucz prywatny nigdy nie dotyka dysku;
- odczyt: hasło → odwinięcie klucza w pamięci → deszyfracja → `less`
  (bez śladu w scrollbacku po wyjściu).

Utrata hasła = stenogramy nieodzyskiwalne. Nie ma tylnej furtki.
"""

import argparse
import getpass
import json
import subprocess
import sys
import textwrap
from pathlib import Path

from pyrage import decrypt as age_decrypt
from pyrage import encrypt as age_encrypt
from pyrage import passphrase as age_passphrase
from pyrage import x25519

DEFAULT_SAFE_DIR = Path.home() / "PokojAI-sejf"
RECIPIENT_FILE = "recipient.txt"
IDENTITY_FILE = "identity.age"


def is_initialized(safe_dir: Path = DEFAULT_SAFE_DIR) -> bool:
    return (safe_dir / RECIPIENT_FILE).exists() and (safe_dir / IDENTITY_FILE).exists()


def init_safe(safe_dir: Path, pw: str) -> None:
    if is_initialized(safe_dir):
        raise RuntimeError(
            "Sejf już zainicjalizowany. Nowy klucz odciąłby dostęp do starych plików."
        )
    safe_dir.mkdir(parents=True, exist_ok=True)
    safe_dir.chmod(0o700)
    identity = x25519.Identity.generate()
    (safe_dir / IDENTITY_FILE).write_bytes(
        age_passphrase.encrypt(str(identity).encode("utf-8"), pw)
    )
    (safe_dir / RECIPIENT_FILE).write_text(str(identity.to_public()) + "\n")


def lock_bytes(safe_dir: Path, name: str, data: bytes) -> Path:
    """Szyfruje dane do sejfu kluczem publicznym. Bez hasła — pokój tego używa."""
    recipient = x25519.Recipient.from_str(
        (safe_dir / RECIPIENT_FILE).read_text().strip()
    )
    out = safe_dir / f"{name}.age"
    out.write_bytes(age_encrypt(data, [recipient]))
    return out


def lock_file(safe_dir: Path, path: Path, delete_original: bool = True) -> Path:
    out = lock_bytes(safe_dir, path.name, path.read_bytes())
    if delete_original:
        path.unlink()
    return out


def unlock(safe_dir: Path, name: str, pw: str) -> bytes:
    identity_blob = (safe_dir / IDENTITY_FILE).read_bytes()
    identity = x25519.Identity.from_str(
        age_passphrase.decrypt(identity_blob, pw).decode("utf-8")
    )
    target = safe_dir / name if name.endswith(".age") else safe_dir / f"{name}.age"
    return age_decrypt(target.read_bytes(), [identity])


# --- CLI Prowadzącego: python -m room.sejf {init,list,read,lock-existing} ----

def _cmd_init(safe_dir: Path) -> int:
    print("Inicjalizacja sejfu. Hasło znasz tylko Ty; jego utrata = utrata stenogramów.")
    pw = getpass.getpass("hasło sejfu: ")
    if pw != getpass.getpass("powtórz hasło: "):
        print("Hasła różne. Przerwano.")
        return 1
    if not pw:
        print("Puste hasło niedozwolone.")
        return 1
    init_safe(safe_dir, pw)
    print(f"Sejf gotowy: {safe_dir}")
    return 0


def _cmd_list(safe_dir: Path) -> int:
    for f in sorted(safe_dir.glob("*.age")):
        if f.name != IDENTITY_FILE:
            print(f.name)
    return 0


# --- formatowanie podglądu ---------------------------------------------------

_BOLD, _DIM, _RESET = "\033[1m", "\033[2m", "\033[0m"
_COLORS = {"Klaris": "\033[33m", "Kord": "\033[36m"}  # żółty / cyjan
_WIDTH = 88

_HELP = (
    f"{_DIM}q wyjście · ↑↓ spacja przewijanie · /tekst szukaj · n następne · "
    f"G koniec · g początek{_RESET}\n" + "─" * _WIDTH + "\n"
)


def _wrap(text: str) -> str:
    out = []
    for line in text.splitlines() or [""]:
        out.extend(textwrap.wrap(line, _WIDTH) or [""])
    return "\n".join(out)


def _render_transcript(data: bytes) -> bytes:
    lines = [_HELP]
    try:
        entries = [json.loads(l) for l in data.decode("utf-8").splitlines() if l.strip()]
    except (json.JSONDecodeError, UnicodeDecodeError):
        return data
    for e in entries:
        event = e.get("event")
        if event == "OPEN":
            lines.append(
                f"{_BOLD}POKÓJ OTWARTY{_RESET} · {e.get('mode')} · "
                f"pierwszy mówca: {e.get('first_speaker')} · {e.get('ts', '')}\n"
            )
        elif event == "PREFLIGHT":
            states = ", ".join(f"{k}={v}" for k, v in e.get("states", {}).items())
            lines.append(f"{_DIM}obecność: {states}{_RESET}\n")
        elif event == "TOPIC":
            lines.append(f"{_BOLD}■ TEMAT OD PROWADZĄCEGO:{_RESET}\n{e.get('content', '')}\n")
        elif event == "ROOM_ENVIRONMENT":
            lines.append(f"{_BOLD}■ W POKOJU:{_RESET}\n{e.get('content', '')}\n")
        elif event == "CHAIR_CMD":
            lines.append(f"{_DIM}· guzik: {e.get('command')}{_RESET}\n")
        elif event == "CLOSE":
            lines.append("─" * _WIDTH + "\n")
            lines.append(
                f"{_BOLD}KONIEC{_RESET} · {e.get('end_state')} · "
                f"rundy: {e.get('rounds_completed', '?')} · "
                f"czas: {e.get('duration_seconds', '?')} s\n"
            )
            for agent, usage in (e.get("usage_by_agent") or {}).items():
                lines.append(
                    f"{_DIM}  {agent}: {usage.get('room_tokens')} room_tokens · "
                    f"{usage.get('calls')} wywołań · "
                    f"{usage.get('provider_tokens')} provider_tokens{_RESET}\n"
                )
        elif e.get("type") == "message":
            who = e.get("from", "?")
            color = _COLORS.get(who, "")
            lines.append(
                f"\n{color}{_BOLD}── {who}{_RESET}{color} · "
                f"{e.get('room_tokens')} rt ──{_RESET}\n"
            )
            lines.append(_wrap(e.get("content", "")) + "\n")
    return "".join(lines).encode("utf-8")


def _render_report(data: bytes) -> bytes:
    try:
        r = json.loads(data)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return data
    lines = [
        _HELP,
        f"{_BOLD}RAPORT STENOGRAFA{_RESET}\n\n",
        f"status spotkania:  {r.get('meeting_status')}\n",
        f"wynik:             {r.get('outcome_status')}\n",
        f"decyzja człowieka: {'TAK' if r.get('human_decision_needed') else 'nie'}\n\n",
        f"{_BOLD}tematy:{_RESET}\n{_wrap(r.get('topics_in_1_to_3_sentences', ''))}\n\n",
        f"{_BOLD}zużycie:{_RESET}\n",
    ]
    for agent, usage in (r.get("usage_by_agent") or {}).items():
        lines.append(f"{_DIM}  {agent}: {usage}{_RESET}\n")
    lines.append(f"{_DIM}  stenograf: {r.get('infrastructure_usage')}{_RESET}\n")
    return "".join(lines).encode("utf-8")


def render(name: str, data: bytes) -> bytes:
    if ".report.json" in name:
        return _render_report(data)
    if name.removesuffix(".age").endswith(".jsonl"):
        return _render_transcript(data)
    return data


def _cmd_read(safe_dir: Path, name: str) -> int:
    pw = getpass.getpass("hasło sejfu: ")
    try:
        data = unlock(safe_dir, name, pw)
    except Exception:
        print("Nie udało się odszyfrować (złe hasło albo uszkodzony plik).")
        return 1
    # less na alt-screen: po wyjściu treść znika z terminala (czystość tekstu)
    subprocess.run(["less", "-R"], input=render(name, data))
    return 0


def _cmd_lock_existing(safe_dir: Path, transcripts_dir: Path) -> int:
    if not is_initialized(safe_dir):
        print("Najpierw: python -m room.sejf init")
        return 1
    count = 0
    for pattern in ("*.jsonl", "*.report.json", "*.report-error"):
        for f in sorted(transcripts_dir.glob(pattern)):
            lock_file(safe_dir, f, delete_original=True)
            count += 1
    print(f"Zamknięto w sejfie i usunięto jawne oryginały: {count} plików.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="room.sejf")
    parser.add_argument("command", choices=["init", "list", "read", "lock-existing"])
    parser.add_argument("name", nargs="?", help="plik do odczytu (dla `read`)")
    parser.add_argument("--safe-dir", type=Path, default=DEFAULT_SAFE_DIR)
    args = parser.parse_args()

    if args.command == "init":
        return _cmd_init(args.safe_dir)
    if args.command == "list":
        return _cmd_list(args.safe_dir)
    if args.command == "read":
        if not args.name:
            print("Podaj nazwę pliku: python -m room.sejf read <plik>")
            return 1
        return _cmd_read(args.safe_dir, args.name)
    if args.command == "lock-existing":
        return _cmd_lock_existing(
            args.safe_dir, Path(__file__).resolve().parent.parent / "transcripts"
        )
    return 1


if __name__ == "__main__":
    sys.exit(main())
