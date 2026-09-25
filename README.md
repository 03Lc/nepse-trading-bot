# NEPSE Trading Bot

Modular **NEPSE Real-Time Market Intelligence and Trading Analysis System**
(research / backtesting / paper-trading foundation).

**Default mode: `paper`.** Live automated retail order execution is **not** currently verified as supported via an official broker/NEPSE trading API. Live mode is blocked in code until that changes.

Do not bypass TMS authentication, CAPTCHA, 2FA, or use unauthorized endpoints.
No profitability claims are made.

**Repository:** https://github.com/03Lc/nepse-trading-bot  
**Full specification:** [docs/SPEC.md](docs/SPEC.md) (includes real-time / low-latency requirements)

---

## Design principles

**FAST + CORRECT + TRACEABLE**

- Prefer official market-data feeds; never claim delayed data is real-time.
- Event-driven, concurrent monitoring of the watchlist (incremental updates).
- Measure latency (data age, processing, alerts); fail closed on stale data.
- Analysis is separate from order execution.
- Never invent missing financial data — metrics carry status (`ok` / `insufficient_data` / `unavailable`).

See [docs/SPEC.md](docs/SPEC.md) for complete requirements.

---

## Status

| Phase | Status |
|-------|--------|
| 0 — Feasibility / regulations | Done |
| 1 — Skeleton, config, logging, hours, costs | Done |
| 2 — Data layer (CSV ingest, clean, SQLite) | Done |
| 3 — Indicators + technical engine | **Done** |
| 4 — Fundamental + valuation engine | **Done** |
| 5 — Market / sector analysis | Next |
| Real-time feed + event pipeline | Planned (see SPEC §2, §5) |
| 6+ — Signal rules, scanner, risk, paper, dashboard | Planned |

---

## Setup

```bash
git clone https://github.com/03Lc/nepse-trading-bot.git
cd nepse-trading-bot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## CLI

```bash
python -m nepse_bot
python -m nepse_bot --check-hours
python -m nepse_bot --estimate-cost 100 500 buy
python scripts/generate_sample_ohlcv.py --symbol NABIL --days 120
python -m nepse_bot --ingest-csv data/samples/NABIL_sample.csv --symbol NABIL
python -m nepse_bot --list-symbols
python -m nepse_bot --analyze-technical --symbol NABIL
python -m nepse_bot --ingest-fundamentals-csv data/samples/NABIL_fundamentals_sample.csv
python -m nepse_bot --analyze-fundamental --symbol NABIL --price 500
```

## Tests

```bash
pytest tests/ -v
```

## Security

Never commit `.env`, passwords, API keys, session cookies, or 2FA secrets.

## Disclaimer

Educational / research use only. Not investment advice. Not affiliated with NEPSE, SEBON, or any broker.
