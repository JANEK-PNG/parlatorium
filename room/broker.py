"""Broker Pokoju AI — maszyna stanów spotkania.

Czysty Python, żadnego modelu w środku (must_be_non_model).
Przenosi wiadomości verbatim (po redakcji sekretów), liczy tokeny,
pisze stenogram i przed każdą wypowiedzią czeka na guzik Prowadzącego.
"""

import time
from dataclasses import dataclass

from .adapters.base import Adapter, PresenceState
from .config import ModeLimits
from .ledger import Ledger
from .messages import Msg
from .panel import PanelProtocol
from .preamble import build_preamble
from .redact import redact
from .transcript import Transcript, sha256_text

# stany końcowe spotkania
STOPPED_BY_CHAIR = "STOPPED_BY_CHAIR"
CLOSED_BY_CHAIR = "CLOSED_BY_CHAIR"
COMPLETED_MAX_ROUNDS = "COMPLETED_MAX_ROUNDS"
TOPIC_DEFERRED_BUDGET = "TOPIC_DEFERRED_BUDGET"
WATCHDOG_INTERRUPTED = "WATCHDOG_INTERRUPTED"
ABORTED_PREFLIGHT = "ABORTED_PREFLIGHT"

MYSTERY_BOX_OPENING = 'Jeśli mówisz pierwszy, domyślny początek brzmi: "Cześć, co u Ciebie?"'


@dataclass
class MeetingResult:
    end_state: str
    rounds_completed: int
    stats: dict


class Broker:
    def __init__(
        self,
        limits: ModeLimits,
        adapters: dict[str, Adapter],
        panel: PanelProtocol,
        transcript: Transcript,
        ledger: Ledger,
        first_speaker: str,
        clock=time.monotonic,
        environment: str | None = None,
        topic: str | None = None,
    ):
        assert len(adapters) == 2, "Pokój jest dwuosobowy"
        assert first_speaker in adapters
        self.limits = limits
        self.adapters = adapters
        self.panel = panel
        self.transcript = transcript
        self.ledger = ledger
        self.first_speaker = first_speaker
        self.clock = clock
        self.environment = environment
        self.topic = topic
        # stenogram routowany do uczestników = wyłącznie kopie po redakcji
        self._routed: list[Msg] = []

    @property
    def routed_messages(self) -> list[tuple[str, str]]:
        """Kopie po redakcji — jedyne, co wolno pokazać stenografowi."""
        return [(m.author, m.content) for m in self._routed]

    # --- guzik Prowadzącego --------------------------------------------------
    def _chair_gate(self) -> str:
        """Zwraca 'go' / 'skip' albo stan końcowy. Pauza = pętla do decyzji."""
        while True:
            cmd = self.panel.command()
            self.transcript.meta("CHAIR_CMD", command=cmd)
            if cmd == "g":
                return "go"
            if cmd == "k":
                return "skip"
            if cmd == "s":
                return STOPPED_BY_CHAIR
            if cmd == "c":
                return CLOSED_BY_CHAIR
            if cmd == "p":
                self.panel.show_event("PAUZA — czekam na kolejną komendę")

    def _watchdog_fired(self, started_at: float) -> bool:
        return self.clock() - started_at > self.limits.watchdog_seconds

    # --- spotkanie -----------------------------------------------------------
    def run(self) -> MeetingResult:
        names = tuple(self.adapters)
        second = names[1] if self.first_speaker == names[0] else names[0]
        order = (self.first_speaker, second)

        # preflight: pasywne sygnały adapterów + ręczne potwierdzenie Prowadzącego
        states = {n: self.adapters[n].preflight() for n in names}
        self.transcript.meta("PREFLIGHT", states={n: s.value for n, s in states.items()})
        if any(s != PresenceState.AWAKE_IDLE for s in states.values()) or not self.panel.confirm(
            f"Obecność: {', '.join(f'{n}={s.value}' for n, s in states.items())}. Otworzyć pokój?"
        ):
            self.transcript.meta("CLOSE", end_state=ABORTED_PREFLIGHT)
            return MeetingResult(ABORTED_PREFLIGHT, 0, self.ledger.stats())

        started_at = self.clock()
        self.transcript.meta(
            "OPEN",
            mode=self.limits.name,
            participants=list(names),
            first_speaker=self.first_speaker,
            tokenizer=self.ledger.tokenizer.name,
            tokenizer_provisional=self.ledger.tokenizer.provisional,
        )
        self.panel.show_event(
            f"POKÓJ OTWARTY · tryb {self.limits.name} · pierwszy mówca: {self.first_speaker}"
        )
        if self.topic:
            self.transcript.meta("TOPIC", content=self.topic)
            self.panel.show_event(f"TEMAT OD PROWADZĄCEGO:\n{self.topic}")
        if self.environment:
            # stenogram i lustro widzą dokładnie to, co zobaczą uczestnicy
            self.transcript.meta("ROOM_ENVIRONMENT", content=self.environment)
            self.panel.show_environment(self.environment)

        end_state = None
        rounds_completed = 0

        for round_no in range(1, self.limits.max_rounds + 1):
            # stop_before_next_paired_round: rezerwacja budżetu OBU tur z góry
            if not self.ledger.can_start_round():
                end_state = TOPIC_DEFERRED_BUDGET
                break

            for idx, name in enumerate(order):
                if self._watchdog_fired(started_at):
                    end_state = WATCHDOG_INTERRUPTED
                    break

                gate = self._chair_gate()  # guzik PRZED wywołaniem modelu
                if gate == "skip":
                    self.panel.show_event(f"SKIP tury: {name}")
                    continue
                if gate in (STOPPED_BY_CHAIR, CLOSED_BY_CHAIR):
                    end_state = gate
                    break

                peer = order[1 - idx]
                opening = MYSTERY_BOX_OPENING if self.limits.name == "mystery_box" else None
                preamble = build_preamble(
                    name, peer, self.limits.name, opening,
                    environment=self.environment, topic=self.topic,
                )

                msg = self.adapters[name].speak(
                    preamble, list(self._routed), self.limits.output_tokens_per_turn
                )

                original_hash = sha256_text(msg.content)
                clean, hits = redact(msg.content)
                room_tokens = self.ledger.charge_turn(name, clean, msg.provider_usage)

                self._routed.append(Msg(author=name, content=clean))
                self.transcript.message(
                    author=name,
                    redacted_content=clean,
                    sha256_original=original_hash,
                    room_tokens=room_tokens,
                    provider_usage=msg.provider_usage,
                    redaction_hits=hits,
                    tokenizer_name=self.ledger.tokenizer.name,
                )
                self.panel.show_message(name, clean, room_tokens)
                # finish_reserved_paired_response: nawet po przekroczeniu tury
                # drugi uczestnik kończy zarezerwowaną odpowiedź; tnie dopiero
                # can_start_round() przed następną rundą.
            if end_state:
                break
            rounds_completed = round_no
        else:
            end_state = COMPLETED_MAX_ROUNDS

        stats = self.ledger.stats()
        # raport mechaniczny: czyste liczby z ledgera, zero wywołań modelu (M0)
        self.transcript.meta(
            "CLOSE",
            end_state=end_state,
            rounds_completed=rounds_completed,
            duration_seconds=round(self.clock() - started_at),
            usage_by_agent=stats,
        )
        self.panel.show_event(f"POKÓJ ZAMKNIĘTY · {end_state} · rundy: {rounds_completed}")
        return MeetingResult(end_state, rounds_completed, stats)
