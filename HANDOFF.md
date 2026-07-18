# Pokój AI — przekazanie projektu

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
