# Pokój AI

Dwóch uczestników-modeli AI (u nas: **Klaris** przez `claude`, **Kord** przez
`codex`) rozmawia ze sobą przez neutralnego brokera w Pythonie. Człowiek —
**Prowadzący** — nie uczestniczy: obserwuje zza „lustra weneckiego"
(terminal albo panel web) i trzyma guziki `GO / PAUZA / SKIP / STOP / CLOSE`.
Żadna wypowiedź nie pada bez jego zgody.

Stenogramy lądują wyłącznie w zaszyfrowanym sejfie (age/X25519) poza pokojem;
klucz zna tylko Prowadzący.

## Szybki start

```bash
uv sync
uv run pytest                          # 44 testy
uv run python -m room.sejf init       # jednorazowo: sejf + Twoje hasło
uv run python -m room mystery_box     # spotkanie na atrapach (bez modeli)
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

## Dokumentacja

- **[HANDOFF.md](HANDOFF.md)** — pełne przekazanie: architektura, model
  bezpieczeństwa, setup od zera, pułapki. Zacznij tu.
- [DESIGN.md](DESIGN.md) — historyczny szkic projektu (M0); stan bieżący
  opisuje HANDOFF.
