"""CLI entry point — see README for full usage."""

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
from nepse_bot.providers.base import HistoricalDataProvider
from nepse_bot.scanner.engine import ConcurrentScanner
from nepse_bot.backtesting.engine import BacktestEngine
from nepse_bot.paper_trading.broker import PaperBroker
from nepse_bot.risk.manager import RiskManager, RiskConfig
from nepse_bot.dashboard.app import write_scan_dashboard
from nepse_bot.alerts.base import AlertManager, ConsoleAlertBackend
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
    parser.add_argument("--scan", action="store_true")
    parser.add_argument("--symbols", default=None)
    parser.add_argument("--max-workers", type=int, default=8)
    parser.add_argument("--backtest", action="store_true")
    parser.add_argument("--paper-buy", nargs=3, metavar=("SYMBOL", "QTY", "PRICE"))
    parser.add_argument("--write-dashboard", action="store_true")
    args = parser.parse_args()

    settings = get_settings(reload=True)
    setup_logging(level=settings.log_level, log_dir=settings.log_dir)
    log = get_logger("cli")
    log.info("NEPSE Bot | mode=%s | live_allowed=%s", settings.bot_mode, settings.is_live_allowed())

    actions = [
        args.check_hours, args.estimate_cost, args.ingest_csv, args.list_symbols,
        args.analyze_technical, args.analyze_fundamental, args.ingest_fundamentals_csv,
        args.analyze_market, args.ingest_benchmark_csv, args.analyze_signal,
        args.scan, args.backtest, args.paper_buy,
    ]
    if args.show_config or not any(actions):
        market = settings.market()
        print("--- Config snapshot ---")
        print(f"  mode          : {settings.bot_mode}")
        print(f"  live allowed  : {settings.is_live_allowed()}")
        print(f"  continuous    : {market.get('continuous_open')} – {market.get('continuous_close')}")
        print("-----------------------")

    if args.check_hours:
        hours = MarketHours.from_config(settings.market())
        now = hours.now()
        print(f"Now (NPT): {now} open={hours.is_open(now)}")

    if args.estimate_cost:
        qty_s, price_s, side = args.estimate_cost
        b = TransactionCostModel.from_config(settings.costs()).estimate(int(qty_s), float(price_s), side)
        for k, v in b.as_dict().items():
            print(f"  {k}: {v}")

    db_path = args.db or str(Path(settings.data_dir) / "nepse_ohlcv.db")
    fund_db = args.fund_db or str(Path(settings.data_dir) / "nepse_fundamentals.db")
    bench_db = args.benchmark_db or str(Path(settings.data_dir) / "nepse_benchmarks.db")

    if args.ingest_csv:
        n = MarketDataRepository(db_path=db_path).ingest(
            CSVHistoricalLoader(Path(args.ingest_csv), default_symbol=args.symbol), symbol=args.symbol
        )
        print(f"Ingested {n} rows")

    if args.list_symbols:
        repo = MarketDataRepository(db_path=db_path)
        for s in repo.list_symbols():
            print(f"  {s}: {repo.bar_count(s)} bars")

    if args.analyze_technical and args.symbol:
        bars = MarketDataRepository(db_path=db_path).get_bars(args.symbol)
        if not bars.empty:
            for line in TechnicalEngine().compute(bars, symbol=args.symbol).summary_lines():
                print(line)

    if args.ingest_fundamentals_csv:
        store = FundamentalStore(db_path=fund_db)
        print("Ingested", load_fundamentals_csv(args.ingest_fundamentals_csv, store), "fundamental rows")

    if args.analyze_fundamental and args.symbol:
        for line in FundamentalEngine(FundamentalStore(db_path=fund_db)).compute(
            args.symbol, price=args.price
        ).summary_lines():
            print(line)

    if args.ingest_benchmark_csv:
        bstore = BenchmarkStore(db_path=bench_db)
        print("Ingested", load_benchmark_csv(args.ingest_benchmark_csv, bstore, benchmark_id=args.benchmark_id), "bars")

    if args.analyze_market and args.symbol:
        bars = MarketDataRepository(db_path=db_path).get_bars(args.symbol)
        if not bars.empty:
            for line in MarketAnalysisEngine(BenchmarkStore(db_path=bench_db)).analyze_symbol(
                args.symbol, bars, sector=args.sector
            ).summary_lines():
                print(line)

    if args.analyze_signal and args.symbol:
        bars = MarketDataRepository(db_path=db_path).get_bars(args.symbol)
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
            if tech is not None and not bars.empty:
                mkt = MarketAnalysisEngine(BenchmarkStore(db_path=bench_db)).analyze_symbol(
                    args.symbol, bars, sector=args.sector
                )
        except Exception:
            pass
        for line in SignalEngine(_load_signal_config()).evaluate(
            args.symbol, technical=tech, fundamental=fund, market=mkt, price=args.price
        ).summary_lines():
            print(line)

    if args.scan:
        provider = HistoricalDataProvider(MarketDataRepository(db_path=db_path))
        symbols = [s.strip().upper() for s in args.symbols.split(",")] if args.symbols else provider.list_symbols()
        if not symbols:
            print("No symbols — ingest OHLCV or pass --symbols")
        else:
            report = ConcurrentScanner(
                provider,
                fundamental_store=FundamentalStore(db_path=fund_db),
                benchmark_store=BenchmarkStore(db_path=bench_db),
                alert_manager=AlertManager([ConsoleAlertBackend()]),
                max_workers=args.max_workers,
                rule_config=_load_signal_config(),
            ).scan(symbols)
            for line in report.summary_lines():
                print(line)
            if args.write_dashboard:
                print("Dashboard:", write_scan_dashboard(report))

    if args.backtest and args.symbol:
        bars = MarketDataRepository(db_path=db_path).get_bars(args.symbol)
        if bars.empty:
            print("No bars")
        else:
            for line in BacktestEngine(rule_config=_load_signal_config()).run(
                bars, symbol=args.symbol
            ).summary_lines():
                print(line)

    if args.paper_buy:
        sym, qty_s, px_s = args.paper_buy
        order = PaperBroker(RiskManager(RiskConfig())).submit(sym, "buy", int(qty_s), float(px_s))
        print(f"Paper order: {order.status} id={order.id} reason={order.reason}")

    log.info("CLI finished")


if __name__ == "__main__":
    main()
