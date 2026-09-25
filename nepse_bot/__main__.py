"""
CLI entry point.

Usage:
  python -m nepse_bot --analyze-signal --symbol NABIL --price 500
  (see README for full command list)
"""

from __future__ import annotations

import argparse
from pathlib import Path

import yaml

from nepse_bot.config import get_settings
from nepse_bot.data.ingestion.csv_loader import CSVHistoricalLoader
from nepse_bot.data.repository import MarketDataRepository
from nepse_bot.market.costs import TransactionCostModel
from nepse_bot.market.hours import MarketHours
from nepse_bot.indicators.engine import TechnicalEngine
from nepse_bot.fundamentals.engine import FundamentalEngine
from nepse_bot.fundamentals.loader import load_fundamentals_csv
from nepse_bot.fundamentals.store import FundamentalStore
from nepse_bot.market_analysis.engine import MarketAnalysisEngine
from nepse_bot.market_analysis.benchmarks import BenchmarkStore
from nepse_bot.market_analysis.loader import load_benchmark_csv
from nepse_bot.signals.engine import SignalEngine
from nepse_bot.signals.rules import RuleConfig
from nepse_bot.monitoring import setup_logging, get_logger


def _load_signal_config() -> RuleConfig:
    ypath = Path("config/default.yaml")
    if ypath.exists():
        data = yaml.safe_load(ypath.read_text()) or {}
        return RuleConfig.from_dict(data.get("signals"))
    return RuleConfig()


def main() -> None:
    parser = argparse.ArgumentParser(description="NEPSE Bot utilities")
    parser.add_argument("--check-hours", action="store_true")
    parser.add_argument("--estimate-cost", nargs=3, metavar=("QTY", "PRICE", "SIDE"))
    parser.add_argument("--show-config", action="store_true")
    parser.add_argument("--ingest-csv", metavar="PATH")
    parser.add_argument("--symbol")
    parser.add_argument("--list-symbols", action="store_true")
    parser.add_argument("--db", default=None)
    parser.add_argument("--analyze-technical", action="store_true")
    parser.add_argument("--analyze-fundamental", action="store_true")
    parser.add_argument("--ingest-fundamentals-csv", metavar="PATH")
    parser.add_argument("--price", type=float, default=None)
    parser.add_argument("--fund-db", default=None)
    parser.add_argument("--analyze-market", action="store_true")
    parser.add_argument("--ingest-benchmark-csv", metavar="PATH")
    parser.add_argument("--benchmark-id", default="NEPSE")
    parser.add_argument("--benchmark-db", default=None)
    parser.add_argument("--sector", default=None)
    parser.add_argument("--analyze-signal", action="store_true")
    args = parser.parse_args()

    settings = get_settings(reload=True)
    logger = setup_logging(level=settings.log_level, log_dir=settings.log_dir)
    log = get_logger("cli")
    log.info("NEPSE Bot v0.1.0 | mode=%s | live_allowed=%s", settings.bot_mode, settings.is_live_allowed())

    no_action = not any([
        args.check_hours, args.estimate_cost, args.ingest_csv, args.list_symbols,
        args.analyze_technical, args.analyze_fundamental, args.ingest_fundamentals_csv,
        args.analyze_market, args.ingest_benchmark_csv, args.analyze_signal,
    ])
    if args.show_config or no_action:
        market = settings.market()
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
        print("\n--- Cost estimate ---")
        for k, v in breakdown.as_dict().items():
            print(f"  {k:16s}: {v}")

    db_path = args.db or str(Path(settings.data_dir) / "nepse_ohlcv.db")
    fund_db = args.fund_db or str(Path(settings.data_dir) / "nepse_fundamentals.db")
    bench_db = args.benchmark_db or str(Path(settings.data_dir) / "nepse_benchmarks.db")

    if args.ingest_csv:
        loader = CSVHistoricalLoader(Path(args.ingest_csv), default_symbol=args.symbol)
        repo = MarketDataRepository(db_path=db_path)
        n = repo.ingest(loader, symbol=args.symbol)
        print(f"\nIngested {n} rows into {db_path}")
        print(f"Symbols: {repo.list_symbols()}")

    if args.list_symbols:
        repo = MarketDataRepository(db_path=db_path)
        print(f"\nDB: {db_path}")
        for s in repo.list_symbols():
            print(f"  {s}: {repo.bar_count(s)} bars")

    if args.analyze_technical:
        if not args.symbol:
            print("ERROR: --analyze-technical requires --symbol")
        else:
            bars = MarketDataRepository(db_path=db_path).get_bars(args.symbol)
            if bars.empty:
                print(f"No bars for {args.symbol}")
            else:
                snap = TechnicalEngine().compute(bars, symbol=args.symbol)
                print()
                for line in snap.summary_lines():
                    print(line)

    if args.ingest_fundamentals_csv:
        store = FundamentalStore(db_path=fund_db)
        n = load_fundamentals_csv(args.ingest_fundamentals_csv, store)
        print(f"\nIngested {n} fundamental rows into {fund_db}")
        for p in store.list_profiles():
            print(f"  {p.symbol}: sector={p.sector.value}")

    if args.analyze_fundamental:
        if not args.symbol:
            print("ERROR: --analyze-fundamental requires --symbol")
        else:
            snap = FundamentalEngine(FundamentalStore(db_path=fund_db)).compute(
                args.symbol, price=args.price
            )
            print()
            for line in snap.summary_lines():
                print(line)

    if args.ingest_benchmark_csv:
        bstore = BenchmarkStore(db_path=bench_db)
        n = load_benchmark_csv(args.ingest_benchmark_csv, bstore, benchmark_id=args.benchmark_id)
        print(f"\nIngested {n} benchmark bars for {args.benchmark_id}")
        print(f"Benchmarks: {bstore.list_benchmarks()}")

    if args.analyze_market:
        if not args.symbol:
            print("ERROR: --analyze-market requires --symbol")
        else:
            bars = MarketDataRepository(db_path=db_path).get_bars(args.symbol)
            if bars.empty:
                print(f"No OHLCV for {args.symbol}")
            else:
                sector = args.sector
                if sector is None:
                    try:
                        prof = FundamentalStore(db_path=fund_db).get_profile(args.symbol)
                        if prof:
                            sector = prof.sector.value
                    except Exception:
                        pass
                snap = MarketAnalysisEngine(BenchmarkStore(db_path=bench_db)).analyze_symbol(
                    args.symbol, bars, sector=sector
                )
                print()
                for line in snap.summary_lines():
                    print(line)

    if args.analyze_signal:
        if not args.symbol:
            print("ERROR: --analyze-signal requires --symbol")
        else:
            repo = MarketDataRepository(db_path=db_path)
            bars = repo.get_bars(args.symbol)
            tech = TechnicalEngine().compute(bars, symbol=args.symbol) if not bars.empty else None
            fund = None
            try:
                fund = FundamentalEngine(FundamentalStore(db_path=fund_db)).compute(
                    args.symbol, price=args.price or (tech.price if tech else None)
                )
            except Exception:
                pass
            mkt = None
            try:
                sector = args.sector
                if sector is None:
                    try:
                        prof = FundamentalStore(db_path=fund_db).get_profile(args.symbol)
                        if prof:
                            sector = prof.sector.value
                    except Exception:
                        pass
                if tech is not None and not bars.empty:
                    mkt = MarketAnalysisEngine(BenchmarkStore(db_path=bench_db)).analyze_symbol(
                        args.symbol, bars, sector=sector
                    )
            except Exception:
                pass
            report = SignalEngine(_load_signal_config()).evaluate(
                args.symbol, technical=tech, fundamental=fund, market=mkt, price=args.price
            )
            print()
            for line in report.summary_lines():
                print(line)

    log.info("CLI finished")


if __name__ == "__main__":
    main()
