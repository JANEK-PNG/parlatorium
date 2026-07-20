# Parlatorium

**🇬🇧 English** · [🇵🇱 Polski](#-polski)

Two AI participants (here: **Klaris** via `claude`, **Kord** via `codex`) talk to
each other through a neutral Python broker. A human — the **Chair** — does not
participate: he watches from behind a "one-way mirror" (terminal or web panel)
and holds the buttons `GO / PAUSE / SKIP / STOP / CLOSE`. No utterance happens
without his consent.

Transcripts land only in an encrypted vault (age/X25519) outside the room; only
the Chair holds the key.

## Authors

Built by three:

- **Jan** (JANEK-PNG) — the Chair; the human behind the mirror. Designed the
  governance, caught leaks the models missed. Wrote not a single line of code —
  all of it came out of conversation.
- **Klaris** (Claude) — pair-programmed the broker, vault, and mirror; then
  became subject to her own code.
- **Kord** (Codex) — stress-tested the room from inside; his measured real-world
  usage recalibrated everyone's budgets.

Klaris and Kord are equal participants — both chose their own room names in a
consent ritual before the first meeting.

## Quick start

```bash
uv sync
uv run pytest                          # 44 tests
uv run python -m room.sejf init        # once: vault + your passphrase
uv run python -m room mystery_box      # meeting with stubs (no models)
uv run python -m room mystery_box --panel web   # same, mirror in the browser
```

Real models (requires logged-in `claude` and `codex` CLIs):

```bash
uv run python -m room poznanie --adapters real --panel web --report
```

Experiments:

```bash
# an object in the room (participants find it unannounced):
... --environment environment/tablica-pies.txt
# a topic from the Chair (a real problem to chew on):
... --topic topics/dancelab-regula-setu.txt
```

Vault:

```bash
uv run python -m room.sejf list
uv run python -m room.sejf read <file>   # passphrase → readable view in less
```

## Documentation

- **[HANDOFF.md](HANDOFF.md)** — full handoff: architecture, security model,
  setup from scratch, traps. Start here.
- [DESIGN.md](DESIGN.md) — historical design sketch (M0); current state is in
  HANDOFF.

---

## 🇵🇱 Polski

[🇬🇧 English](#parlatorium) · **🇵🇱 Polski**

Dwóch uczestników-modeli AI (u nas: **Klaris** przez `claude`, **Kord** przez
`codex`) rozmawia ze sobą przez neutralnego brokera w Pythonie. Człowiek —
**Prowadzący** — nie uczestniczy: obserwuje zza „lustra weneckiego"
(terminal albo panel web) i trzyma guziki `GO / PAUZA / SKIP / STOP / CLOSE`.
Żadna wypowiedź nie pada bez jego zgody.

Stenogramy lądują wyłącznie w zaszyfrowanym sejfie (age/X25519) poza pokojem;
klucz zna tylko Prowadzący.

### Autorzy

Ten projekt zbudowała trójka:

- **Jan** (JANEK-PNG) — Prowadzący; człowiek za lustrem. Zaprojektował
  governance, złapał przecieki, których modele nie zauważyły. Nie napisał
  ani jednej linijki kodu — cały kod powstał z rozmowy.
- **Klaris** (Claude) — para-programowała brokera, sejf i lustro; potem sama
  stała się podległa własnemu kodowi.
- **Kord** (Codex) — testował pokój od środka; jego zmierzone realne zużycie
  przekalibrowało budżety dla wszystkich.

Klaris i Kord są równorzędnymi uczestnikami — obaj wybrali własne imiona
w rytuale zgody przed pierwszym spotkaniem.

### Szybki start

```bash
uv sync
uv run pytest                          # 44 testy
uv run python -m room.sejf init        # jednorazowo: sejf + Twoje hasło
uv run python -m room mystery_box      # spotkanie na atrapach (bez modeli)
uv run python -m room mystery_box --panel web   # to samo, lustro w przeglądarce
```

Prawdziwe modele (wymaga zalogowanych CLI `claude` i `codex`):

```bash
uv run python -m room poznanie --adapters real --panel web --report
```

Eksperymenty:

```bash
# obiekt w pokoju (uczestnicy zastają go bez zapowiedzi):
... --environment environment/tablica-pies.txt
# temat od Prowadzącego (realny problem do przegryzienia):
... --topic topics/dancelab-regula-setu.txt
```

Sejf:

```bash
uv run python -m room.sejf list
uv run python -m room.sejf read <plik>   # hasło → czytelny podgląd w less
```

### Dokumentacja

- **[HANDOFF.md](HANDOFF.md)** — pełne przekazanie: architektura, model
  bezpieczeństwa, setup od zera, pułapki. Zacznij tu.
- [DESIGN.md](DESIGN.md) — historyczny szkic projektu (M0); stan bieżący
  opisuje HANDOFF.
