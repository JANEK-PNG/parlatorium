"""Ledger tokenów: równy budżet głosu + oddzielna księga dostawców.

Zasady z klucza:
- budget_is_ceiling_not_target
- paired_response_budget_reserved_before_first_turn: runda startuje tylko,
  gdy OBAJ uczestnicy mają budżet na swoją turę
- stop_before_next_paired_round + finish_reserved_paired_response
"""

from dataclasses import dataclass, field

from .config import ModeLimits
from .tokenizer import RoomTokenizer


@dataclass
class AgentLedger:
    room_tokens: int = 0
    calls: int = 0
    provider_tokens: int = 0
    turn_overflows: int = 0
    provider_detail: dict[str, int] = field(default_factory=dict)


class Ledger:
    def __init__(self, limits: ModeLimits, tokenizer: RoomTokenizer, agents: tuple[str, str]):
        self.limits = limits
        self.tokenizer = tokenizer
        self.agents = {name: AgentLedger() for name in agents}

    # --- rezerwacja pary ---------------------------------------------------
    def can_start_round(self) -> bool:
        """Runda rusza tylko, gdy obie strony mają pełną turę budżetu i wolne wywołanie."""
        return all(
            self._remaining_room(a) >= self.limits.room_tokens_per_turn
            and self.agents[a].calls < self.limits.calls_per_agent
            and self._remaining_provider(a) > 0
            for a in self.agents
        )

    def _remaining_room(self, agent: str) -> int:
        return self.limits.room_tokens_per_agent - self.agents[agent].room_tokens

    def _remaining_provider(self, agent: str) -> int:
        return self.limits.provider_tokens_per_agent - self.agents[agent].provider_tokens

    # --- księgowanie tury ---------------------------------------------------
    def charge_turn(self, agent: str, text: str, provider_usage: dict[str, int]) -> int:
        """Księguje turę. Zwraca room_tokens. Nadwyżkę ponad sufit tury odnotowuje."""
        ledger = self.agents[agent]
        tokens = self.tokenizer.count(text)
        ledger.room_tokens += tokens
        ledger.calls += 1
        # retries i cache liczą się do totalu (count_retries_and_cache_in_total)
        ledger.provider_tokens += sum(provider_usage.values())
        for key, val in provider_usage.items():
            ledger.provider_detail[key] = ledger.provider_detail.get(key, 0) + val
        if tokens > self.limits.room_tokens_per_turn:
            ledger.turn_overflows += 1
        return tokens

    def turn_exceeded(self, agent: str) -> bool:
        return self.agents[agent].turn_overflows > 0

    def exhausted(self, agent: str) -> bool:
        return (
            self._remaining_room(agent) <= 0
            or self.agents[agent].calls >= self.limits.calls_per_agent
            or self._remaining_provider(agent) <= 0
        )

    def stats(self) -> dict:
        return {
            agent: {
                "room_tokens": led.room_tokens,
                "calls": led.calls,
                "provider_tokens": led.provider_tokens,
                "provider_detail": led.provider_detail,
                "turn_overflows": led.turn_overflows,
            }
            for agent, led in self.agents.items()
        }
