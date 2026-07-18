from room.config import ModeLimits
from room.ledger import Ledger
from room.tokenizer import RoomTokenizer

LIMITS = ModeLimits(
    name="test", max_rounds=2, room_tokens_per_agent=10, room_tokens_per_turn=5,
    calls_per_agent=2, input_tokens_per_call=100, output_tokens_per_turn=5,
    provider_tokens_per_agent=100, watchdog_seconds=60,
)

# 1 słowo = 1 token — przewidywalne testy
WORDS = RoomTokenizer(name="words", provisional=True, _count=lambda s: len(s.split()))


def make_ledger():
    return Ledger(LIMITS, WORDS, ("A", "B"))


def test_round_needs_budget_on_both_sides():
    led = make_ledger()
    assert led.can_start_round()
    led.charge_turn("A", "a b c d e f g h", {})  # 8/10 — została mniej niż pełna tura
    assert not led.can_start_round()  # rezerwacja pary: A nie ma pełnej tury


def test_calls_cap_blocks_round():
    led = make_ledger()
    led.charge_turn("A", "x", {})
    led.charge_turn("A", "x", {})
    assert led.agents["A"].calls == 2
    assert not led.can_start_round()


def test_provider_tokens_counted_with_cache_and_detail():
    led = make_ledger()
    led.charge_turn("A", "x", {"input": 30, "output": 20, "cache_read": 60})
    assert led.agents["A"].provider_tokens == 110  # retries+cache liczą się do totalu
    assert led.agents["A"].provider_detail["cache_read"] == 60
    assert not led.can_start_round()  # 110 > 100 → wyczerpany provider budget


def test_turn_overflow_recorded_not_crashed():
    led = make_ledger()
    tokens = led.charge_turn("A", "jeden dwa trzy cztery pięć sześć", {})
    assert tokens == 6
    assert led.turn_exceeded("A")
