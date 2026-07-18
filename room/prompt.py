"""Budowa wejścia dla uczestnika: stenogram → tekst tury.

Sufit wejścia (input_tokens_per_call) egzekwowany przez przycinanie
najstarszych wypowiedzi — model zawsze widzi najnowszy kontekst.
"""

from .messages import Msg
from .tokenizer import RoomTokenizer


def truncate_to_budget(msgs: list[Msg], tokenizer: RoomTokenizer, budget: int) -> list[Msg]:
    kept: list[Msg] = []
    used = 0
    for msg in reversed(msgs):  # od najnowszych
        cost = tokenizer.count(msg.content)
        if used + cost > budget:
            break
        kept.append(msg)
        used += cost
    return list(reversed(kept))


def render_turn(msgs: list[Msg], speaker: str) -> str:
    if not msgs:
        return f"Pokój jest otwarty. Mówisz pierwszy. Twoja tura, {speaker}:"
    lines = [f"{m.author}: {m.content}" for m in msgs]
    return "Dotychczasowa rozmowa:\n\n" + "\n\n".join(lines) + f"\n\nTwoja tura, {speaker}:"
