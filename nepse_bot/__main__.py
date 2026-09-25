"""
CLI entry point.

Usage:
  python -m nepse_bot
  python -m nepse_bot --check-hours
  python -m nepse_bot --estimate-cost 100 500 buy
  python -m nepse_bot --ingest-csv data/samples/NABIL_sample.csv --symbol NABIL
  python -m nepse_bot --list-symbols
"""

from __future__ import annotations

import argparse
from pathlib import Path

from nepse_bot.config import get_settings
from nepse_bot.data.ingestion.csv_loader import CSVHistoricalLoader
from nepse_bot.data.repository import MarketDataRepository
from nepse_bot.market.costs import TransactionCostModel
from nepse_bot.market.hours import MarketHours
from nepse_bot.monitoring import setup_logging, get_logger


def main() -> None:
    parser = argparse.ArgumentParser(description="NEPSE Bot utilities")
    parser.add_argument("--check-hours", action="store_true")
    parser.add_argument("--estimate-cost", nargs=3, metavar=("QTY", "PRICE", "SIDE"))
    parser.add_argument("--show-config", action="store_true")
    parser.add_argument("--ingest-csv", metavar="PATH")
    parser.add_argument("--symbol")
    parser.add_argument("--list-symbols", action="store_true")
    parser.add_argument("--db", default=None)
    args = parser.parse_args()

    settings = get_settings(reload=True)
    logger = setup_logging(level=settings.log_level, log_dir=settings.log_dir)
    log = get_logger("cli")
    log.info("NEPSE Bot v0.1.0 | mode=%s | live_allowed=%s", settings.bot_mode, settings.is_live_allowed())

    no_action = not any([args.check_hours, args.estimate_cost, args.ingest_csv, args.list_symbols])
    if args.show_config or no_action:
        market = settings.market()
        risk = settings.risk()
        print("--- Config snapshot ---")
        print(f"  mode          : {settings.bot_mode}")
        print(f"  timezone      : {settings.timezone}")
        print(f"  continuous    : {market.get('continuous_open')} – {market.get('continuous_close')}")
        print(f"  live allowed  : {settings.is_live_allowed()}")
        print("-----------------------")

    if args.check_hours:
        hours = MarketHours.from_config(settings.market())
        now = hours.now()
        print(f"\nNow (NPT)     : {now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        print(f"Trading day   : {hours.is_trading_day(now)}")
        print(f"Market open   : {hours.is_open(now)}")
        print(f"Next open     : {hours.next_open(now)}")
        print(f"Next close    : {hours.next_close(now)}")

    if args.estimate_cost:
        qty_s, price_s, side = args.estimate_cost
        model = TransactionCostModel.from_config(settings.costs())
        breakdown = model.estimate(int(qty_s), float(price_s), side)
        print(f"\n--- Cost estimate ---")
        for k, v in breakdown.as_dict().items():
            print(f"  {k:16s}: {v}")

    db_path = args.db or str(Path(settings.data_dir) / "nepse_ohlcv.db")

    if args.ingest_csv:
        loader = CSVHistoricalLoader(Path(args.ingest_csv), default_symbol=args.symbol)
        repo = MarketDataRepository(db_path=db_path)
        n = repo.ingest(loader, symbol=args.symbol)
        print(f"\nIngested {n} rows into {db_path}")
        print(f"Symbols: {repo.list_symbols()}")

    if args.list_symbols:
        repo = MarketDataRepository(db_path=db_path)
        symbols = repo.list_symbols()
        print(f"\nDB: {db_path}")
        for s in symbols:
            print(f"  {s}: {repo.bar_count(s)} bars")

    log.info("CLI finished")


if __name__ == "__main__":
    main()
