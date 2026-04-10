# LLM + Tool

Skript:
- zavola LLM
- necha model pouzit tool `get_cnb_exchange_rate`
- tool nacte aktualni kurz z oficialniho kurzovniho listku CNB
- vysledek posle zpet do LLM
- vypise finalni odpoved

## Spusteni

```bash
uv run main.py
```

## Poznamka

V `.env` musi byt:

```bash
OPENAI_API_KEY=tvuj_token
```
