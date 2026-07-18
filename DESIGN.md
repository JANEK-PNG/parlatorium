# Pokój AI — projekt brokera (v0.1, do przeglądu)

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
