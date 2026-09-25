# NEPSE Trading Bot — Project Specification

This document is the authoritative product/engineering specification.
Implementation phases must conform to it. Where current code is not yet
aligned (e.g. Phase 2 CSV/SQLite only), the gap is intentional and must be
closed before claiming real-time operation.

**Core principle:** FAST + CORRECT + TRACEABLE  
Do not sacrifice data integrity or risk controls only to reduce latency.

---

## 1. Scope and modes

| Mode | Purpose | Order execution |
|------|---------|-----------------|
| research | Offline analysis, data quality | None |
| backtest | Historical simulation | Simulated |
| paper | Live or delayed analysis, simulated fills | Simulated only |
| live | Official broker API only, when verified | Real (disabled until official API exists) |

Default mode: **paper**. Live execution remains blocked until an officially
supported retail trading API is available and authorized. Analysis may run
continuously without enabling execution.

---

## 2. Real-time / low-latency requirements

This bot is intended for **intraday market monitoring** where timely
information matters. The system must be designed for **low latency**, not
periodic batch analysis as the primary path.

### 2.1 Real-time data

- Use the **fastest legitimate, officially available** NEPSE/broker market-data
  feed (licensed NEPSE API, licensed vendor, or broker-provided official feed).
- **Do NOT:**
  - scrape pages repeatedly if an official feed/API exists
  - use artificial polling intervals when streaming is available
  - use stale cached prices for real-time signals
  - pretend delayed data is real-time
- If only delayed data is legitimately available, **clearly display** its
  timestamp and delay (data age).

### 2.2 Concurrent stock monitoring

The scanner must monitor the **entire selected universe concurrently**.

If the watchlist has ~200 stocks, the architecture must **NOT** process:

```text
Stock 1 → wait → Stock 2 → wait → Stock 3 → ...
```

Instead use asynchronous/concurrent processing and **incremental updates**.

When one stock’s price changes:

```text
DATA UPDATE
    ↓
Update only affected calculations
    ↓
Recalculate relevant indicators
    ↓
Run signal / risk rules
    ↓
Generate alert immediately if conditions changed
```

Do **not** unnecessarily recalculate every stock after every single price
update.

### 2.3 Event-driven architecture

Prefer:

```text
Market-data stream
  → Event queue
  → Data processor
  → Indicator engine
  → Signal engine
  → Risk engine
  → Alert engine
```

over:

```text
Timer → Download everything → Analyze everything → Wait → Repeat
```

Use event-driven processing wherever the legitimate data source supports it.
Polling is acceptable only when streaming is not legitimately available, and
must be documented with measured interval and data age.

### 2.4 Parallelism

Use appropriate concurrency:

- `asyncio` for I/O-bound work
- connection pooling where applicable
- efficient in-memory structures for last-price / indicator state
- multiprocessing / worker pools only where CPU-heavy work justifies them
- batch operations where they reduce overhead without harming latency for
  critical paths

Do **not** create hundreds of unnecessary threads or processes.

### 2.5 Latency monitoring

Measure actual latency at every stage:

```text
data_timestamp
  → receive_timestamp
  → processing_start
  → signal_timestamp
  → alert_timestamp
```

Display (at minimum):

- Data age
- Processing latency
- Alert latency
- API / feed latency
- Connection status

**Never claim “real-time” without measuring it.** Benchmark after the
legitimate data source is integrated and report measurements.

### 2.6 Alert priority

Critical events must be processed immediately.

**HIGH priority**

- Breakout / breakdown
- Stop-loss condition
- Major price movement
- Unusual volume
- New all-time or 52-week high / low
- Major market event
- Position risk limit

**NORMAL priority**

- Indicator changes
- Fundamental updates
- Watchlist changes

**LOW priority**

- Periodic summaries
- Dashboard refreshes

### 2.7 Alert deduplication

Do not send the same alert repeatedly every second.

Example: after `BREAKOUT DETECTED`, do not send another identical breakout
alert for the same symbol/condition until:

- the condition resets, or
- a meaningful state change occurs (e.g. new threshold, new session, explicit
  re-arm).

### 2.8 Data integrity

**Speed must never override correctness.**

Every real-time event should carry:

- symbol
- price
- timestamp
- source
- sequence / order information where available

Handle:

- duplicate events
- out-of-order events
- missing events
- connection loss
- reconnection
- stale data

If data becomes stale, the system must **explicitly mark the stock as stale**
and must **not** generate trading signals from old data.

### 2.9 Dashboard (real-time view)

The dashboard should show, at a minimum:

```text
LIVE CONNECTION: ● / ○
DATA AGE:        0.XX sec
SCANNING:        N stocks
SIGNALS:         N
ALERTS:          N
PROCESSING LATENCY: XX ms
```

Per stock:

- PRICE
- CHANGE
- VOLUME
- SIGNAL
- DATA TIMESTAMP
- DATA AGE

### 2.10 Fail-safe behavior

If the real-time feed disconnects:

1. **STOP** generating new real-time trading signals.
2. Display: `⚠ MARKET DATA STALE`
3. Reconnect with controlled exponential backoff.
4. Do **not** make trading decisions using stale prices.

### 2.11 Live trading separation

Keep **real-time analysis** separate from **order execution**.

- The analysis engine may run continuously even when live trading is disabled.
- Live execution must use only an **officially supported** broker/API.
- Must not bypass authentication, rate limits, CAPTCHA, 2FA, security
  controls, or exchange/broker restrictions.

### 2.12 Performance targets

Do **not** promise zero latency.

After the legitimate data source is known, establish measurable targets such
as:

```text
Market event received → signal calculated → alert generated
```

with the lowest practical latency supported by the infrastructure.
Benchmark the actual system and report the measurements.

---

## 3. Target event pipeline (architecture)

```text
┌─────────────────────┐
│ Official market feed │  (stream preferred; poll only if necessary)
└──────────┬──────────┘
           │ ticks / bars / depth (as available)
           ▼
┌─────────────────────┐
│ Event queue          │  prioritized (HIGH > NORMAL > LOW)
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Data processor       │  dedupe, order, stale detection, state update
└──────────┬──────────┘
           │ per-symbol incremental state
           ▼
┌─────────────────────┐
│ Indicator engine     │  update only affected symbols
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│ Signal engine        │  rule-based; no look-ahead
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│ Risk engine          │  limits, kill switch, position checks
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│ Alert engine         │  priority + deduplication + latency metrics
└──────────┬──────────┘
           │
     ┌─────┴─────┐
     ▼           ▼
 Dashboard    Paper / Live adapter
              (live disabled by default)
```

---

## 4. Latency metrics schema (required when live feed is wired)

Each processed event should be able to record:

| Field | Meaning |
|-------|--------|
| `data_timestamp` | Exchange / feed event time |
| `receive_timestamp` | Local time when process received the event |
| `processing_start` | Start of indicator/signal work |
| `signal_timestamp` | When signal decision completed |
| `alert_timestamp` | When alert was emitted (if any) |

Derived:

- **data_age** = now − data_timestamp
- **feed_latency** = receive_timestamp − data_timestamp
- **processing_latency** = signal_timestamp − processing_start
- **alert_latency** = alert_timestamp − data_timestamp (end-to-end)

---

## 5. Current implementation status (honest)

| Requirement | Status as of Phase 2 |
|-------------|----------------------|
| Official streaming feed | **Not integrated** — needs licensed/official source |
| Event queue + incremental indicators | **Not yet** — planned for real-time phases |
| Concurrent universe scanner | **Not yet** |
| Latency metrics end-to-end | **Not yet** |
| Alert priority + dedupe | **Not yet** |
| Stale-data fail-safe | **Not yet** |
| CSV/SQLite historical data layer | **Done** (research / backtest foundation) |
| Market hours + cost model | **Done** |
| Live order execution | **Blocked** by design |

Phase 2 remains a correct foundation for research and backtesting. Real-time
requirements in §2 become mandatory acceptance criteria for the live-monitoring
and paper/scanner phases.

---

## 6. Compliance constraints (unchanged)

- Do not reverse-engineer private TMS endpoints for trading.
- Do not bypass CAPTCHA, 2FA, rate limits, or broker security.
- Do not treat unofficial GitHub/PyPI TMS libraries as authorized.
- Prefer official NEPSE data licensing or licensed vendors for production feeds.
- No profitability claims; strategy edge is empirical.

---

## 7. Document control

- **Path:** `docs/SPEC.md`
- **Owner:** project maintainers
- **Updates:** any change to latency, data source, or execution policy must
  update this file in the same PR/commit series.
