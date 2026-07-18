"""Typy wiadomości krążących w pokoju."""

from dataclasses import dataclass, field


@dataclass
class Msg:
    author: str
    content: str
    # tokeny raportowane przez dostawcę: input/output/cache_read/cache_write
    provider_usage: dict[str, int] = field(default_factory=dict)
