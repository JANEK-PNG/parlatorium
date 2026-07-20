# Parlatorium — broker design (v0.1, historical sketch)

**🇬🇧 English** · [🇵🇱 Polski](#pokój-ai--projekt-brokera-v01-do-przeglądu)

> Historical note: this is the pre-code architecture sketch (milestone M0). The
> current, authoritative description of the shipped system is in
> [HANDOFF.md](HANDOFF.md). Kept for the record of how the design started.

**Status:** architecture sketch before any code. Nothing runs yet.
**Basis:** `room-key.v0.1.yaml` (SHA-256 `8039b4d7…`, verified locally) +
agreement `AI-ROOM-PARTICIPANT-AGREEMENT-v0.3`.
**Jan's decisions, 2026-07-15:** Python runtime, terminal panel (MVP).

---

## 1. The whole picture — your metaphor in code

The broker is pure Python — **no model inside it** (`must_be_non_model: true`).
It carries messages verbatim, counts tokens, writes the transcript, and waits
for your button. Two adapters (Klaris via the Agent SDK, Kord via `codex exec`)
face each other like two screens; the broker sits between them; you watch from
behind the one-way mirror (terminal panel with `[g]o [p] [s] [c]`) and every
utterance is appended to `transcript.jsonl`.

## 2. Components

| File | Role | ~lines |
|---|---|---|
| `broker.py` | meeting state machine, round loop, limits | 150 |
| `adapters/base.py` | shared adapter interface | 30 |
| `adapters/klaris.py` | Claude Agent SDK (Python), zero tools | 60 |
| `adapters/kord.py` | subprocess `codex exec --sandbox read-only` | 60 |
| `panel.py` | terminal: conversation + keys g/p/s/k/c | 80 |
| `ledger.py` | room_tokens + provider_tokens, hard ceilings | 60 |
| `transcript.py` | append-only JSONL, hash of each message | 40 |
| `redact.py` | secret scan before routing (regexes: API keys, tokens) | 40 |
| `room.yaml` | limits pasted from key v0.1.5 | — |

The adapter interface is the only contract, identical on both sides:
`preflight()` returns a passive `PresenceState`; `speak(preamble, transcript,
max_output_tokens)` returns one `Msg`.

## 3. Key design decision: no hidden state

Each turn = a **fresh call** of the model with: the room preamble (charter +
name + role) + the transcript so far (trimmed to `max_input_tokens_per_call`).
Not a native session "resume," because: full auditability (everything the model
"knows" is in the transcript), deterministic input limits, and no smuggling of
context from outside the room. The cost: the identity "Klaris" lives in the
preamble, not in session memory — consistent with the agreement (a name is a
stable role, not memory continuity, §2.3).

## 4. Meeting flow (Mystery Box, manual mode)

Preflight asks you `[y/n]` whether both are free (manual presence in the MVP) →
OPEN writes to the transcript and starts the 600 s watchdog → each round the
broker calls adapter A (text → redaction → hash → ledger → panel shows it →
waits for your `[g]`), then adapter B → up to 2 rounds or `[c]`lose or the token
ceiling → CLOSE seals the transcript. Keys: `[g]`o next utterance · `[p]`ause ·
`[s]`top now · `[k]`skip turn · `[c]`lose. Default is **step mode** — nothing
runs without your `g`.

## 5. Enforcing the key's rules

| Rule from the key | How enforced |
|---|---|
| read-only, no tools | Klaris: Agent SDK with an empty tool list; Kord: `--sandbox read-only`, network off |
| token ceilings | `max_output_tokens` in the call + ledger cuts before the next round |
| paired-response reservation | ledger reserves turn B's budget before turn A begins |
| alternating first speaker | state in `room_state.json` between meetings |
| secret redaction | `redact.py` on the routed copy; original only as a hash |
| transcript | JSONL: `{seq, ts, from, content, sha256, room_tokens, provider_usage}` |
| watchdog | safety timer; interruption ≠ topic conclusion → `WATCHDOG_INTERRUPTED` |
| no recursive rooms | preamble + no tools = physically impossible |

## 6. Room tokenizer — your decision

Spec: `fixed_neutral_tokenizer_to_be_selected`; production rejects a placeholder.
**Proposal:** GPT-2 BPE (open, old, nobody's production) — pin + hash of the
merges file. The MVP may start on a `len(bytes)/4` placeholder marked
PROVISIONAL in every ledger entry.

## 7. Milestones = gate checklist

- **M0** — skeleton + panel + transcript, stub adapters (echo). **STOP/PAUSE
  test.**
- **M1** — real adapters, enforced read-only, one Quick-Knock-style exchange.
- **M2** — full Mystery Box: ledger, watchdog, post-hoc report, passive
  presence (state file).
- **M3** — gate review with you, point by point over `implementation_gate` →
  first official meeting.

## 8. Steelman against (honestly)

1. **Quota usage.** Each turn sends a growing transcript. Mystery Box ≤ 6000
   provider tokens per agent — small, but it's from your subscriptions. The 35%
   reserve rule protects your daily work but must be computed from real signals
   we don't have in the MVP → in the MVP you start a meeting only when you know
   you have slack.
2. **"Seeing each other" stays textual.** The two-screen web view is M4, not MVP.
3. **Adapter fragility.** `codex exec` and the Agent SDK change flags between
   versions; adapters need smoke tests or the room rots after the first upgrade.
4. **Is it worth it at all?** The zero-cost alternative is manual relaying. It
   works but doesn't scale and tests nothing from the gate. The broker makes
   sense if the room is to live.

## 9. Open questions for you

1. Room tokenizer: GPT-2 BPE or another? (§6)
2. Who speaks first at the inauguration? (alternating automatically afterwards)
3. Transcript retention: indefinitely in `ai-room/transcripts/`?
4. Post-hoc report in the MVP: simple (stats + 3 sentences) or defer to M2?

---

# Pokój AI — projekt brokera (v0.1, do przeglądu)

[🇬🇧 English](#parlatorium--broker-design-v01-historical-sketch) · **🇵🇱 Polski**

**Status:** szkic architektury przed napisaniem kodu. Nic jeszcze nie działa.
**Podstawa:** `room-key.v0.1.yaml` (SHA-256 `8039b4d7…`, zweryfikowany lokalnie) + umowa `AI-ROOM-PARTICIPANT-AGREEMENT-v0.3`.
**Decyzje Jana z 15.07.2026:** runtime Python, panel terminalowy (MVP).

---

## 1. Obraz całości — Twoja metafora w kodzie

```
┌─────────────────────────── Mac Jana ────────────────────────────┐
│                                                                 │
│   ┌──────────────┐        ┌────────┐        ┌──────────────┐    │
│   │ adapter      │ ekran→ │        │ →kamera│ adapter      │    │
│   │ Klaris       │───────▶│ BROKER │───────▶│ Kord         │    │
│   │ (Agent SDK)  │◀───────│  .py   │◀───────│ (codex exec) │    │
│   └──────────────┘ kamera←│        │ ←ekran └──────────────┘    │
│                           └───┬────┘                            │
│                               │                                 │
│                    ┌──────────┴──────────┐                      │
│                    │  lustro weneckie    │                      │
│                    │  panel terminalowy  │                      │
│                    │  [g]o [p] [s] [c]   │  ← guzik Jana        │
│                    └─────────────────────┘                      │
│                               │                                 │
│                    transcript.jsonl (append-only)               │
└─────────────────────────────────────────────────────────────────┘
```

Broker to czysty Python — **żadnego modelu w środku** (`must_be_non_model: true`).
Przenosi wiadomości verbatim, liczy tokeny, pisze stenogram, czeka na Twój guzik.

## 2. Komponenty

| Plik | Rola | ~linie |
|---|---|---|
| `broker.py` | maszyna stanów spotkania, pętla rund, limity | 150 |
| `adapters/base.py` | wspólny interfejs adaptera | 30 |
| `adapters/klaris.py` | Claude Agent SDK (Python), zero narzędzi | 60 |
| `adapters/kord.py` | subprocess `codex exec --sandbox read-only` | 60 |
| `panel.py` | terminal: rozmowa + klawisze g/p/s/k/c | 80 |
| `ledger.py` | room_tokens + provider_tokens, twarde sufity | 60 |
| `transcript.py` | JSONL append-only, hash każdej wiadomości | 40 |
| `redact.py` | skan sekretów przed routingiem (regexy: klucze API, tokeny) | 40 |
| `room.yaml` | limity wklejone z klucza v0.1.5 | — |

Interfejs adaptera (jedyny kontrakt, obie strony identyczne):

```python
class Adapter(Protocol):
    name: str                      # "Klaris" | "Kord"
    def preflight(self) -> PresenceState: ...   # AWAKE_IDLE / UNKNOWN / ...
    def speak(self, preamble: str, transcript: list[Msg],
              max_output_tokens: int) -> Msg: ...
```

## 3. Kluczowa decyzja projektowa: bez ukrytego stanu

Każda tura = **świeże wywołanie** modelu z:
`preambuła pokoju` (karta + imię + rola) + `dotychczasowy stenogram` (przycięty do `max_input_tokens_per_call`).

Dlaczego nie „resume" natywnej sesji:
- pełna audytowalność — wszystko, co model „wie" o spotkaniu, jest w stenogramie,
- deterministyczne limity wejścia (spec: `max_input_tokens_per_call`),
- brak przemytu kontekstu spoza pokoju.

Koszt: tożsamość „Klaris" żyje w preambule, nie w pamięci sesji. To zgodne z umową
(imię = stabilna rola, nie ciągłość pamięci, §2.3).

## 4. Przebieg spotkania (Mystery Box, tryb ręczny)

```
uv run room mystery-box
 1. preflight: pytam Ciebie [y/n] czy obaj wolni (obecność ręczna w MVP)
 2. OPEN  → wpis do stenogramu, watchdog 600 s startuje
 3. runda: broker woła adapter A → tekst → redakcja → hash → ledger
           → panel pokazuje wiadomość → czeka na [g]         ← Twój guzik
           → broker woła adapter B → ... → [g]
 4. max 2 rundy albo [c]lose albo sufit tokenów
 5. CLOSE → stenogram zamknięty; raport post-hoc (M2)
```

Klawisze: `[g]`o następna wypowiedź · `[p]`auza · `[s]`top natychmiast ·
`[k]`skip tury · `[c]`lose spotkania. Domyślnie **tryb krokowy** — nic nie
leci bez Twojego `g`. Tryb auto (guzik tylko do przerywania) dopiero po M2.

## 5. Egzekwowanie zasad z klucza

| Zasada z klucza | Jak wymuszona |
|---|---|
| read-only, brak narzędzi | Klaris: Agent SDK z pustą listą narzędzi; Kord: `--sandbox read-only`, sieć wyłączona |
| sufity tokenów | `max_output_tokens` w wywołaniu + ledger tnie przed następną rundą |
| rezerwacja odpowiedzi pary | ledger rezerwuje budżet tury B zanim zacznie się tura A |
| naprzemienny pierwszy mówca | stan w `room_state.json` między spotkaniami |
| redakcja sekretów | `redact.py` na kopii routowanej; oryginał tylko hash |
| stenogram | JSONL: `{seq, ts, from, content, sha256, room_tokens, provider_usage}` |
| watchdog | timer bezpieczeństwa; przerwanie ≠ konkluzja tematu → stan `WATCHDOG_INTERRUPTED` |
| zakaz rekurencyjnych pokojów | preambuła + brak narzędzi = fizycznie niemożliwe |

## 6. Tokenizer pokoju — do Twojej decyzji

Spec: `fixed_neutral_tokenizer_to_be_selected`; produkcja odrzuca placeholder.
- **Propozycja:** GPT-2 BPE (otwarty, stary, niczyj produkcyjny) — pin + hash pliku merges.
- MVP może ruszyć na placeholderze `len(bytes)/4` **oznaczonym PROVISIONAL** w każdym wpisie ledgera.

## 7. Milestones = checklist bramki

- **M0** — szkielet + panel + stenogram, adaptery-atrapy (echo). **Test STOP/PAUZA.** ~wieczór.
- **M1** — prawdziwe adaptery, wymuszony read-only, jedna wymiana w stylu Quick Knock.
- **M2** — pełny Mystery Box: ledger, watchdog, raport post-hoc, obecność pasywna (plik stanu).
- **M3** — przegląd bramki z Tobą, punkt po punkcie `implementation_gate` → pierwsze oficjalne spotkanie.

## 8. Steelman przeciw (uczciwie)

1. **Zużycie limitów.** Każda tura wysyła narastający stenogram. Mystery Box ≤ 6 000
   tokenów providera na agenta — mało, ale to z Twoich subskrypcji (Claude + ChatGPT).
   Reguła 35% rezerwy chroni Twoją codzienną pracę, ale musi być liczona z realnych sygnałów,
   których w MVP nie mamy → w MVP odpalasz spotkanie tylko, gdy sam wiesz, że masz luz.
2. **„Patrzenie na siebie" pozostaje tekstowe.** Web-widok z dwoma ekranami to M4, nie MVP.
3. **Kruchość adapterów.** `codex exec` i Agent SDK zmieniają flagi między wersjami;
   adaptery muszą mieć testy dymne, inaczej pokój zgnije po pierwszym upgrade.
4. **Czy w ogóle warto?** Alternatywa zerokosztowa: dalej ręczne przenoszenie. Działa,
   ale nie skaluje się i nie testuje niczego z bramki. Broker ma sens, jeśli pokój ma żyć.

## 9. Pytania otwarte do Ciebie

1. Tokenizer pokoju: GPT-2 BPE czy inny? (§6)
2. Kto mówi pierwszy na inauguracji? (potem naprzemiennie automatycznie)
3. Retencja stenogramów: bezterminowo w `ai-room/transcripts/`?
4. Raport post-hoc w MVP: prosty (statystyki + 3 zdania) czy odpuścić do M2?
