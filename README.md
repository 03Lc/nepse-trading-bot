# NEPSE Trading Bot

Modular research / backtesting / paper-trading system for the Nepal Stock Exchange (NEPSE).

**Default mode: `paper`.** Live automated retail order execution is **not** currently verified as supported via an official broker/NEPSE trading API. Live mode is blocked in code until that changes.

Do not bypass TMS authentication, CAPTCHA, 2FA, or use unauthorized endpoints.
No profitability claims are made.

**Repository:** https://github.com/03Lc/nepse-trading-bot

---

## Status

| Phase | Status |
|-------|--------|
| 0 — Feasibility / regulations | Done |
| 1 — Skeleton, config, logging, hours, costs | Done |
| 2 — Data layer (CSV ingest, clean, SQLite) | Done |
| 3 — Indicators + strategies | Next |
| 4+ — Risk, backtest, paper, dashboard | Planned |

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
```

## Tests

```bash
pytest tests/ -v
```

## Security

Never commit `.env`, passwords, API keys, session cookies, or 2FA secrets.

## Disclaimer

Educational / research use only. Not investment advice. Not affiliated with NEPSE, SEBON, or any broker.
