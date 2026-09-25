"""Lightweight HTML dashboard (Phase 11)."""

from __future__ import annotations

from pathlib import Path

from nepse_bot.scanner.engine import ScanReport


def render_scan_html(report: ScanReport, title: str = "NEPSE Scanner") -> str:
    rows = []
    for r in report.results:
        if r.error:
            rows.append(f"<tr><td>{r.symbol}</td><td colspan='5'>ERROR: {r.error}</td></tr>")
            continue
        sig = r.signal
        if not sig:
            continue
        rows.append(
            f"<tr><td>{r.symbol}</td><td>{sig.price}</td><td>{sig.state.value}</td>"
            f"<td>{sig.passed}</td><td>{sig.failed}</td><td>{r.latency_ms:.1f}</td></tr>"
        )
    body = "\n".join(rows) or "<tr><td colspan='6'>No results</td></tr>"
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>{title}</title>
<style>
body {{ font-family: system-ui, sans-serif; margin: 24px; background: #0b1220; color: #e8eef7; }}
h1 {{ font-size: 1.4rem; }}
.meta {{ color: #9fb3c8; margin-bottom: 16px; }}
table {{ border-collapse: collapse; width: 100%; }}
th, td {{ border: 1px solid #243044; padding: 8px 10px; text-align: left; }}
th {{ background: #152033; }}
tr:nth-child(even) {{ background: #121a2a; }}
</style></head>
<body>
<h1>{title}</h1>
<div class="meta">symbols={report.symbols_scanned} · errors={report.errors} · total_ms={report.total_ms:.1f} · as_of={report.as_of.isoformat()} · mode=PAPER</div>
<table>
<thead><tr><th>Stock</th><th>Price</th><th>Signal</th><th>Passed</th><th>Failed</th><th>Latency ms</th></tr></thead>
<tbody>
{body}
</tbody></table>
<p class="meta">Educational research UI — not investment advice. Live trading disabled.</p>
</body></html>
"""


def write_scan_dashboard(report: ScanReport, path: str | Path = "data/storage/dashboard_scan.html") -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_scan_html(report), encoding="utf-8")
    return path
