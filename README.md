# NEPSE Trading Bot

Modular **NEPSE Real-Time Market Intelligence and Trading Analysis System**.

**Default mode: `paper`.** Live execution is **blocked** until an officially supported API exists.

Do not bypass TMS authentication, CAPTCHA, 2FA, or use unauthorized endpoints.
No profitability claims are made.

**Repository:** https://github.com/03Lc/nepse-trading-bot  
**Spec:** [docs/SPEC.md](docs/SPEC.md)

---

## Status

| Phase | Status |
|-------|--------|
| 0–6 — Research stack through signal engine | **Done** |
| 7 — Concurrent scanner | **Done** |
| 8 — Backtesting | **Done** |
| 9 — Risk management | **Done** |
| 10 — Paper trading | **Done** |
| 11 — Dashboard (HTML) | **Done** |
| 12 — Alerts (console / Telegram env) | **Done** |
| 13 — Data providers (historical/mock; official TBD) | **Done** |
| 14 — Extended tests | **Done** |
| 15 — Live execution | **Blocked** |

---

## Setup

```bash
git clone https://github.com/03Lc/nepse-trading-bot.git
cd nepse-trading-bot
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## CLI (selected)

```bash
python -m nepse_bot --ingest-csv data/samples/NABIL_sample.csv --symbol NABIL
python -m nepse_bot --analyze-signal --symbol NABIL
python -m nepse_bot --scan --write-dashboard
python -m nepse_bot --backtest --symbol NABIL
python -m nepse_bot --paper-buy NABIL 10 500
pytest tests/ -v
```

## Security

Never commit `.env`, API keys, passwords, cookies, or 2FA secrets.

## Disclaimer

Educational / research only. Not investment advice. Not affiliated with NEPSE, SEBON, or any broker.
