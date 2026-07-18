"""Lustro weneckie: panel obserwatora + guzik Prowadzącego.

Tryb krokowy (M0): przed KAŻDĄ wypowiedzią broker pyta o komendę.
Nic nie leci bez [g] Jana.
"""

from typing import Protocol

VALID = {"g", "p", "s", "k", "c"}
PROMPT = "guzik  [g]o  [p]auza  [s]top  [k]skip  [c]lose > "


class PanelProtocol(Protocol):
    def show_message(self, author: str, content: str, room_tokens: int) -> None: ...
    def show_event(self, text: str) -> None: ...
    def show_environment(self, content: str) -> None: ...
    def command(self) -> str: ...
    def confirm(self, question: str) -> bool: ...


class TerminalPanel:
    def show_message(self, author: str, content: str, room_tokens: int) -> None:
        bar = "─" * 60
        print(f"\n{bar}\n■ EKRAN {author}  ({room_tokens} room_tokens)\n{bar}")
        print(content)

    def show_event(self, text: str) -> None:
        print(f"\n· {text}")

    def show_environment(self, content: str) -> None:
        bar = "═" * 60
        print(f"\n{bar}\n■ W POKOJU (widzą to obaj uczestnicy)\n{bar}\n{content}")

    def command(self) -> str:
        while True:
            cmd = input(PROMPT).strip().lower()
            if cmd in VALID:
                return cmd
            print("  nieznana komenda")

    def confirm(self, question: str) -> bool:
        return input(f"{question} [y/n] > ").strip().lower() == "y"


class ScriptedPanel:
    """Panel do testów: odgrywa listę komend zamiast czekać na klawiaturę."""

    def __init__(self, commands: list[str], confirmations: list[bool] | None = None):
        self._commands = list(commands)
        self._confirmations = list(confirmations or [True])
        self.shown: list[tuple[str, str]] = []
        self.events: list[str] = []

    def show_message(self, author: str, content: str, room_tokens: int) -> None:
        self.shown.append((author, content))

    def show_event(self, text: str) -> None:
        self.events.append(text)

    def show_environment(self, content: str) -> None:
        self.events.append(f"ENV:{content[:40]}")

    def command(self) -> str:
        if not self._commands:
            return "c"  # skończył się scenariusz → zamknij spotkanie
        return self._commands.pop(0)

    def confirm(self, question: str) -> bool:
        if not self._confirmations:
            return True
        return self._confirmations.pop(0)
