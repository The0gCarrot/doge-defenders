"""
Always-live CoinGecko market data for the paper / dashboard day.

Uses /coins/markets (one batch call) to patch today's rows:
price_usd, volume_24h_usd, market_cap_usd, return_24h, momentum_30d_pct,
and recompute universe market_cap_rank for that day.
"""

from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src import MISSING_NUM, ensure_dirs, load_config, write_json
from src.coingecko_client import CoinGeckoClient
from src.collect_coingecko import REPORT_FIELDS, assign_universe_ranks, write_reports_csv

ROOT = Path(__file__).resolve().parents[1]


def fetch_live_markets(cfg: dict[str, Any] | None = None) -> dict[str, dict[str, Any]]:
    cfg = cfg or load_config()
    client = CoinGeckoClient(cfg["base_url"], float(cfg.get("rate_limit_seconds", 15)))
    return client.markets_live(list(cfg["tokens"]))


def apply_live_markets_to_rows(
    rows: list[dict[str, Any]],
    live: dict[str, dict[str, Any]],
    *,
    day: str | None = None,
) -> int:
    """Overwrite live market fields for rows on `day` (default UTC today)."""
    target = day or datetime.now(timezone.utc).date().isoformat()
    n = 0
    for r in rows:
        if str(r.get("report_date") or "")[:10] != target[:10]:
            continue
        cid = str(r.get("coingecko_id") or "")
        if cid not in live:
            continue
        m = live[cid]
        if m.get("price_usd") is not None:
            r["price_usd"] = m["price_usd"]
        if m.get("volume_24h_usd") is not None:
            r["volume_24h_usd"] = m["volume_24h_usd"]
        if m.get("market_cap_usd") is not None:
            r["market_cap_usd"] = m["market_cap_usd"]
        if m.get("return_24h") is not None:
            r["return_24h"] = m["return_24h"]
        if m.get("momentum_30d_pct") is not None:
            r["momentum_30d_pct"] = m["momentum_30d_pct"]
            # Drawdown proxy: 0 if up over 30d, else the 30d move (negative)
            mom = float(m["momentum_30d_pct"])
            r["drawdown_from_peak_pct"] = min(0.0, mom)
        n += 1
    # Recompute ordinal ranks among today's universe
    today_rows = [r for r in rows if str(r.get("report_date") or "")[:10] == target[:10]]
    if today_rows:
        assign_universe_ranks(today_rows)
    return n


def refresh_live_today(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    Fetch live markets and patch daily_reports.csv for UTC today.
    Call before scoring / paper trading / dashboard display.
    """
    cfg = cfg or load_config()
    ensure_dirs(cfg)
    path = ROOT / cfg["paths"].get("daily_reports_csv", cfg["paths"]["snapshots_csv"])
    if not path.exists():
        return {"ok": False, "error": f"missing {path}", "updated": 0}

    with path.open(newline="", encoding="utf-8") as f:
        rows = [dict(r) for r in csv.DictReader(f)]

    today = datetime.now(timezone.utc).date().isoformat()
    has_today = any(str(r.get("report_date") or "")[:10] == today for r in rows)
    if not has_today:
        return {
            "ok": False,
            "error": f"no rows for {today}; run collector with include_today",
            "updated": 0,
            "day": today,
        }

    live = fetch_live_markets(cfg)
    updated = apply_live_markets_to_rows(rows, live, day=today)
    write_reports_csv(path, rows)

    raw_dir = ROOT / cfg["paths"]["raw_dir"]
    # Compact prices dict for dashboard caption
    prices = {
        cid: {
            "usd": m.get("price_usd"),
            "usd_24h_change": m.get("return_24h"),
        }
        for cid, m in live.items()
    }
    payload = {
        "asof_utc": datetime.now(timezone.utc).isoformat(),
        "day": today,
        "updated_rows": updated,
        "source": "coingecko:/coins/markets",
        "prices": prices,
        "markets": live,
    }
    write_json(raw_dir / "_live_prices.json", payload)
    return {"ok": True, "asof_utc": payload["asof_utc"], "day": today, "updated_rows": updated, "prices": prices}
