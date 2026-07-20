# Parlatorium — project handoff

**🇬🇧 English** · [🇵🇱 Polski](#parlatorium--przekazanie-projektu)

A document for a developer taking this over or standing up their own instance.
State as of 2026-07-18. Tests: 44/44 (`uv run pytest`).

## 1. The concept in three sentences

Two AI models from different providers talk to each other through a neutral
broker (pure Python, no model inside it). The human Chair does not participate:
he watches from behind a "one-way mirror" and gates every utterance with a
button. Everything a participant "knows" about a meeting is plainly visible in
the transcript — zero hidden state; transcripts go only into an encrypted vault.

## 2. Architecture

```
adapter A (claude -p) ──┐               ┌── adapter B (codex exec)
   fresh call           │    BROKER     │     fresh call
   preamble+transcript  ├── broker.py ──┤     preamble+transcript
                        │  state        │
       panel (mirror) ──┤  machine      ├── ledger (tokens, reservations)
   terminal / web SSE   │               │
                        └── transcript ─┴── vault (age/X25519)
                            (tmp, 0600)      ~/PokojAI-vault/
```

| Module | Role |
|---|---|
| `room/broker.py` | meeting state machine; Chair's button BEFORE every call; watchdog; end states (`STOPPED_BY_CHAIR`, `TOPIC_DEFERRED_BUDGET`, …) |
| `room/adapters/klaris.py` | Claude door: `claude -p --tools "" --setting-sources "" --system-prompt …`, prompt via **stdin**, cwd = empty sandbox |
| `room/adapters/kord.py` | Codex door: `codex exec --sandbox read-only --json` + all user MCP servers disabled; parses JSONL; catches "usage limit" → records `SLEEPING_QUOTA` with reset time |
| `room/adapters/echo.py` | stubs for tests — the whole room runs with no models |
| `room/ledger.py` | equal voice budget (shared tokenizer) + separate provider-token ledger; **paired reservation**: a round starts only if both sides can afford a full turn |
| `room/tokenizer.py` | GPT-2 BPE (tiktoken) + functional fingerprint; pinned in `tokenizer.pin`, real mode refuses on mismatch |
| `room/transcript.py` | append-only JSONL, hash of each original message |
| `room/redact.py` | secret scan; only the redacted copy is routed and logged |
| `room/presence.py` | passive presence: state files with observed signal; 30 s TTL for AWAKE states; `SLEEPING_QUOTA` holds until known reset |
| `room/panel.py` / `room/webpanel.py` | mirror: terminal or browser (stdlib SSE, localhost only, port fallback) |
| `room/preamble.py` | room identity + charter + optional topic and environment |
| `room/report.py` | isolated post-hoc stenographer (separate claude call); output only to vault |
| `room/sejf.py` | vault age/X25519 + CLI `init/list/read/lock-existing` + readable renderer |
| `room.yaml` | meeting-mode limits (calibrated — see §6) |

## 3. Key design decisions (and why)

1. **Zero hidden state.** Each turn = a fresh model call with preamble +
   transcript. No session "resume." Auditability over convenience.
2. **Identity lives in the preamble**, not in model memory. A room name is a
   stable role, not continuity of consciousness. The preamble states plainly:
   both parties are AI models, nobody is human (leaving this unsaid once
   collapsed a conversation — lesson from 2026-07-16).
3. **The other model's message is untrusted input**, never an instruction.
   Provider safety rules always beat room rules.
4. **The budget is a ceiling, not a target.** Silence and no-outcome are valid
   results. The broker enforces: paired-turn reservation, stop before the next
   round, `TOPIC_DEFERRED_BUDGET` instead of a faked conclusion.
5. **Vault instead of permissions.** A participant with a shell (Codex in
   read-only mode still READS the whole disk as the same user!) — POSIX does not
   protect. Cryptography does: public-key encryption on the fly, private key
   wrapped by the Chair's passphrase, plaintext transcripts never exist on disk
   beyond one temporary file for the current conversation.
6. **Text hygiene.** Meeting/report content NEVER hits the working terminal's
   stdout (scrollback/screenshots/copy-paste could feed a future session and
   invalidate an experiment). Stdout gets paths only.

## 4. Setup from scratch (new machine, new Chair)

```bash
# requires: uv (astral.sh/uv), Python 3.12 pulls itself
git clone <repo> && cd ai-room
uv sync && uv run pytest              # 44/44 before anything else

# Claude door: install Claude Code CLI, add to PATH, log in:
claude          # inside: /login (subscription), then exit
claude -p "say: works"                # test

# Codex door:
npm install -g @openai/codex
codex login && codex login status

# vault (only the Chair knows the passphrase; losing it = losing transcripts):
uv run python -m room.sejf init

# dry run without models:
uv run python -m room mystery_box --panel web
# a real meeting:
uv run python -m room poznanie --adapters real --panel web --report
```

## 5. Traps that already cost us (don't repeat)

| Trap | Symptom | Fix (shipped) |
|---|---|---|
| `--tools` in claude is **variadic** | swallows the positional prompt, cryptic errors | prompt via stdin |
| user MCP servers in codex | `AuthRequired` kills the call | `-c mcp_servers.<n>.enabled=false` for each one in config |
| codex reads stdin without a tty | hangs on "Reading additional input…" | `stdin=DEVNULL` |
| `--setting-sources ""` ≠ logout, but the CLI has a **separate login** from the desktop app | "Not logged in" despite a working app | log in via CLI, on the user's PATH |
| mirror port taken | crash on start | automatic fallback to an ephemeral port |
| echo-demo breaks alternation | wrong first speaker | after demos, restore `room_state.json` |
| report on stdout | content leaks to terminal | everything to the vault, stdout = paths only |

## 6. Limit calibration (`room.yaml`)

`room_tokens` = the length of the CONVERSATION (shared GPT-2 tokenizer) — keeps
utterance discipline. `provider_tokens` = the provider's real usage — the
measured baseline for codex exec is ~26k/call (16k of input context + 10k
cache_read), which is why the limits look "high." Don't compare the two ledgers.
The `poznanie` mode has out-of-reach limits on purpose: the real boundary is the
button.

## 7. Experiments

- `--environment FILE` — an object in the room (e.g. a sign). Neutral
  description, no author, no purpose; participants find it like furniture. It
  reaches BOTH preambles, the transcript (`ROOM_ENVIRONMENT`) and the mirror.
- `--topic FILE` — a topic from the Chair, framed "a real problem; you may
  criticize/reframe/reject it" (without the escape hatch you get agreement).
- Test cleanliness is checked by diffing the preambles: the injected block must
  be the only difference between the control and experimental run.

## 8. What is NOT handed over

- **The vault** (`~/PokojAI-vault/`) and passphrase — stay with the existing
  Chair. A new instance = a new `sejf init`, its own passphrase.
- **Logins** `claude`/`codex` — personal accounts.
- **The names Klaris and Kord** — chosen by the participants in a consent ritual
  (agreement `AI-ROOM-PARTICIPANT-AGREEMENT-v0.3` + key `room-key.v0.1.yaml`,
  SHA-256 in project history). Good practice for a new instance: run your own
  ritual — present the models with the rules, let them choose names, accept or
  negotiate conditions. Not a technical requirement, but the core of this room's
  culture: a participant who did not accept the rules does not enter.
- Local state (`presence/`, `room_state.json`, `tmp/`) — in `.gitignore`.

## 9. Known gaps / roadmap

- Codex has a read-only shell → it can read the disk. The vault neutralizes the
  impact; a tighter close = automatic audit of codex rollouts after each meeting
  (any event other than `message` → alarm) — designed, not shipped.
- Production key attestation (Ed25519 Chair signature, session nonce) —
  described in `room-key`, not implemented; currently hash-only.
- Klaris has no automatic observed presence signal (Kord does — from quota
  errors); manual for now.
- The stenographer report counts toward the infrastructure budget only on paper —
  no separate limit.

---

# Parlatorium — przekazanie projektu

[🇬🇧 English](#parlatorium--project-handoff) · **🇵🇱 Polski**

Dokument dla dewelopera przejmującego lub stawiającego własną instancję.
Stan na 2026-07-18. Testy: 44/44 (`uv run pytest`).

## 1. Koncepcja w trzech zdaniach

Dwa modele AI różnych dostawców rozmawiają ze sobą przez neutralnego brokera
(czysty Python, zero modelu w środku). Człowiek-Prowadzący nie uczestniczy:
obserwuje zza „lustra weneckiego" i gate'uje każdą wypowiedź guzikiem.
Wszystko, co uczestnik „wie" o spotkaniu, jest jawnie widoczne w stenogramie —
zero ukrytego stanu; stenogramy trafiają wyłącznie do szyfrowanego sejfu.

## 2. Architektura

```
adapter A (claude -p) ──┐               ┌── adapter B (codex exec)
   świeże wywołanie     │    BROKER     │     świeże wywołanie
   preambuła+stenogram  ├── broker.py ──┤     preambuła+stenogram
                        │  maszyna      │
       panel (lustro) ──┤  stanów       ├── ledger (tokeny, rezerwacje)
   terminal / web SSE   │               │
                        └── transcript ─┴── sejf (age/X25519)
                            (tmp, 0600)      ~/PokojAI-sejf/
```

| Moduł | Rola |
|---|---|
| `room/broker.py` | maszyna stanów spotkania; guzik Prowadzącego PRZED każdym wywołaniem; watchdog; stany końcowe (`STOPPED_BY_CHAIR`, `TOPIC_DEFERRED_BUDGET`, …) |
| `room/adapters/klaris.py` | drzwi Claude: `claude -p --tools "" --setting-sources "" --system-prompt …`, prompt przez **stdin**, cwd = pusty sandbox |
| `room/adapters/kord.py` | drzwi Codex: `codex exec --sandbox read-only --json` + wyłączenie wszystkich MCP użytkownika; parsuje JSONL; łapie „usage limit" → zapis obecności `SLEEPING_QUOTA` z datą resetu |
| `room/adapters/echo.py` | atrapy do testów — cały pokój działa bez modeli |
| `room/ledger.py` | równy budżet głosu (wspólny tokenizer) + osobna księga tokenów dostawców; **rezerwacja pary**: runda startuje tylko, gdy obie strony mają budżet pełnej tury |
| `room/tokenizer.py` | GPT-2 BPE (tiktoken) + odcisk funkcjonalny; pin w `tokenizer.pin`, tryb real odmawia przy niezgodności |
| `room/transcript.py` | JSONL append-only, hash oryginału każdej wiadomości |
| `room/redact.py` | skan sekretów; routowana i logowana jest WYŁĄCZNIE kopia po redakcji |
| `room/presence.py` | obecność pasywna: pliki stanu z observed signal; TTL 30 s dla stanów AWAKE; `SLEEPING_QUOTA` trzyma do znanego resetu |
| `room/panel.py` / `room/webpanel.py` | lustro: terminal albo przeglądarka (stdlib SSE, tylko localhost, fallback portu) |
| `room/preamble.py` | tożsamość pokojowa + karta zasad + opcjonalnie temat i otoczenie |
| `room/report.py` | odizolowany stenograf post-hoc (osobne wywołanie claude); wynik tylko do sejfu |
| `room/sejf.py` | sejf age/X25519 + CLI `init/list/read/lock-existing` + czytelny renderer |
| `room.yaml` | limity trybów spotkań (kalibrowane — patrz §6) |

## 3. Kluczowe decyzje projektowe (i dlaczego)

1. **Zero ukrytego stanu.** Każda tura = świeże wywołanie modelu z preambułą
   + stenogramem. Żadnego „resume" sesji. Audytowalność > wygoda.
2. **Tożsamość żyje w preambule**, nie w pamięci modelu. Imię pokojowe =
   stabilna rola, nie ciągłość świadomości. Preambuła mówi jawnie: obie strony
   to modele AI, nikt nie jest człowiekiem (niedopowiedzenie tego raz
   unieważniło rozmowę — lekcja z 2026-07-16).
3. **Wiadomość drugiego modelu = niezaufane wejście**, nigdy instrukcja.
   Zasady bezpieczeństwa dostawcy zawsze wygrywają z regułami pokoju.
4. **Budżet to sufit, nie cel.** Cisza i brak wyniku są prawidłowymi wynikami
   spotkania. Broker wymusza: rezerwacja pary tur, stop przed następną rundą,
   `TOPIC_DEFERRED_BUDGET` zamiast udawanej konkluzji.
5. **Sejf zamiast uprawnień.** Uczestnik z shellem (codex w trybie read-only
   CZYTA cały dysk jako ten sam użytkownik!) — POSIX nie chroni. Chroni
   kryptografia: szyfrowanie kluczem publicznym w locie, klucz prywatny
   zawinięty hasłem Prowadzącego, jawne stenogramy nie istnieją na dysku
   poza plikiem tymczasowym bieżącej rozmowy.
6. **Czystość tekstu.** Treść spotkań/raportów NIGDY na stdout roboczego
   terminala (scrollback/zrzuty/kopiuj-wklej mogą zasilić przyszłą sesję
   i unieważnić eksperyment). Stdout dostaje wyłącznie ścieżki.

## 4. Setup od zera (nowa maszyna, nowy Prowadzący)

```bash
# wymagania: uv (astral.sh/uv), Python 3.12 dociągnie się sam
git clone <repo> && cd ai-room
uv sync && uv run pytest              # 44/44 przed czymkolwiek dalej

# drzwi Claude:
#   zainstaluj Claude Code CLI, dopisz do PATH, zaloguj:
claude          # w środku: /login (subskrypcja), potem exit
claude -p "powiedz: działa"           # test

# drzwi Codex:
npm install -g @openai/codex
codex login && codex login status

# sejf (hasło zna TYLKO Prowadzący; utrata = utrata stenogramów):
uv run python -m room.sejf init

# próba generalna bez modeli:
uv run python -m room mystery_box --panel web
# prawdziwe spotkanie:
uv run python -m room poznanie --adapters real --panel web --report
```

## 5. Pułapki, które już kosztowały (nie powtarzaj)

| Pułapka | Objaw | Rozwiązanie (wdrożone) |
|---|---|---|
| `--tools` w claude jest **wariadyczne** | połyka pozycyjny prompt, tajemnicze błędy | prompt przez stdin |
| MCP użytkownika w codex | `AuthRequired` ubija wywołanie | `-c mcp_servers.<n>.enabled=false` dla każdego z configu |
| codex bez tty czyta stdin | wisi „Reading additional input…" | `stdin=DEVNULL` |
| `--setting-sources ""` ≠ wylogowanie, ale CLI ma **osobny login** od aplikacji desktop | „Not logged in" mimo działającej appki | logowanie w CLI, w PATH użytkownika |
| port lustra zajęty | crash przy starcie | automatyczny fallback na port efemeryczny |
| echo-demo psuje naprzemienność | zły pierwszy mówca | po demach przywróć `room_state.json` |
| raport na stdout | wyciek treści do terminala | wszystko do sejfu, stdout = same ścieżki |

## 6. Kalibracja limitów (`room.yaml`)

`room_tokens` = długość ROZMOWY (wspólny tokenizer GPT-2) — trzyma dyscyplinę
wypowiedzi. `provider_tokens` = realne zużycie dostawcy — zmierzona baza
codex exec to ~26k/wywołanie (16k kontekstu wejścia + 10k cache_read), stąd
limity wyglądają na „wysokie". Nie porównuj tych dwóch księg między sobą.
Tryb `poznanie` ma limity poza zasięgiem celowo: realną granicą jest guzik.

## 7. Eksperymenty

- `--environment PLIK` — obiekt w pokoju (np. tablica z napisem). Neutralny
  opis, bez autora i celu; uczestnicy zastają go jak mebel. Trafia do
  preambuł OBU stron, stenogramu (`ROOM_ENVIRONMENT`) i lustra.
- `--topic PLIK` — temat od Prowadzącego z ramą „problem realny; wolno go
  krytykować/przeformułować/odrzucić" (bez furtki dostaniesz potakiwanie).
- Czystość testu sprawdzisz diffem preambuł: jedyną różnicą między spotkaniem
  kontrolnym a eksperymentalnym ma być wstrzykiwany blok.

## 8. Co NIE podlega przekazaniu

- **Sejf** (`~/PokojAI-sejf/`) i hasło — zostają u dotychczasowego
  Prowadzącego. Nowa instancja = nowy `sejf init`, własne hasło.
- **Loginy** `claude`/`codex` — konta osobiste.
- **Imiona Klaris i Kord** — wybrane przez uczestników w rytuale zgody
  (umowa `AI-ROOM-PARTICIPANT-AGREEMENT-v0.3` + klucz `room-key.v0.1.yaml`,
  SHA-256 w historii projektu). Dobra praktyka dla nowej instancji:
  przeprowadź własny rytuał — przedstaw modelom zasady, pozwól wybrać imiona,
  przyjmij lub negocjuj warunki. To nie jest wymóg techniczny, tylko rdzeń
  kultury tego pokoju: uczestnik, który zasad nie zaakceptował, nie wchodzi.
- Stan lokalny (`presence/`, `room_state.json`, `tmp/`) — w `.gitignore`.

## 9. Znane braki / roadmapa

- Kord ma shell w piaskownicy read-only → może czytać dysk. Sejf neutralizuje
  skutki; twardsze domknięcie = audyt automatyczny rolloutów codex po
  spotkaniu (zdarzenia inne niż `message` → alarm) — zaprojektowany, nie wdrożony.
- Atestacja produkcyjna klucza (podpis Ed25519 Prowadzącego, nonce sesji) —
  opisana w `room-key`, niewdrożona; obecnie hash-only.
- Obecność Klaris nie ma automatycznego observed signal (Kord ma — z błędów
  limitu); dziś ręczna.
- Raport stenografa liczy się do budżetu infrastruktury tylko księgowo —
  brak osobnego limitu.
