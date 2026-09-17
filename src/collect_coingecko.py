"""
Collect CoinGecko history for the token universe × entry calendar.

For each token: one detail call + one market_chart (days=365) call.
Snapshots and 90-day labels are derived locally. Existing raw JSON is reused
unless --force-refresh is set.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.coingecko_client import CoinGeckoClient
from src import MISSING_NUM, MISSING_STR, ensure_dirs, load_config, write_json


SNAPSHOT_FIELDS = [
    "snapshot_id",
    "coingecko_id",
    "token_symbol",
    "decision_ts",
    "price_usd_t",
    "volume_24h_usd",
    "market_cap_usd",
    "market_cap_rank",
    "category",
    "primary_exchange",
    "hist_prices_30d",
    "ath_change_percentage",
    "price_change_percentage_30d",
    "research_notes",
    "news_score",
    "price_usd_t90",
    "return_90d",
    "positive_90d_return",
]


def parse_date(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc)


def nearest_point(series: list[list[float]], target_ms: int) -> tuple[float, float] | None:
    """Return (timestamp_ms, value) nearest to target_ms, or None if empty."""
    if not series:
        return None
    best = min(series, key=lambda p: abs(int(p[0]) - target_ms))
    return float(best[0]), float(best[1])


def points_between(series: list[list[float]], start_ms: int, end_ms: int) -> list[float]:
    vals = [float(p[1]) for p in series if start_ms <= int(p[0]) <= end_ms]
    return vals


def primary_exchange_from_detail(detail: dict[str, Any]) -> str:
    tickers = detail.get("tickers") or []
    if not tickers:
        return MISSING_STR
    # Prefer highest converted volume if present.
    def vol(t: dict[str, Any]) -> float:
        cv = t.get("converted_volume") or {}
        return float(cv.get("usd") or 0)

    best = max(tickers, key=vol)
    market = best.get("market") or {}
    name = market.get("identifier") or market.get("name") or MISSING_STR
    return str(name) if name else MISSING_STR


def category_from_detail(detail: dict[str, Any]) -> str:
    cats = detail.get("categories") or []
    cats = [c for c in cats if c]
    return str(cats[0]) if cats else MISSING_STR


def build_snapshots_for_coin(
    coin_id: str,
    detail: dict[str, Any],
    chart: dict[str, Any],
    entry_dates: list[str],
    lookback_days: int,
    horizon_days: int,
) -> list[dict[str, Any]]:
    prices = chart.get("prices") or []
    volumes = chart.get("total_volumes") or []
    mcaps = chart.get("market_caps") or []
    symbol = (detail.get("symbol") or coin_id).upper()
    category = category_from_detail(detail)
    exchange = primary_exchange_from_detail(detail)

    rows: list[dict[str, Any]] = []
    for entry in entry_dates:
        t = parse_date(entry)
        t_ms = int(t.timestamp() * 1000)
        t90 = t + timedelta(days=horizon_days)
        t90_ms = int(t90.timestamp() * 1000)
        lookback_start = t - timedelta(days=lookback_days)
        lookback_ms = int(lookback_start.timestamp() * 1000)

        px = nearest_point(prices, t_ms)
        px90 = nearest_point(prices, t90_ms)
        vol = nearest_point(volumes, t_ms)
        mcap = nearest_point(mcaps, t_ms)

        hist = points_between(prices, lookback_ms, t_ms - 1)
        # Prefer one point per calendar day (chart may be hourly for short ranges).
        if len(hist) > lookback_days * 2:
            # downsample by taking evenly spaced
            step = max(1, len(hist) // lookback_days)
            hist = hist[::step][:lookback_days]

        price_t = px[1] if px else MISSING_NUM
        price_t90 = px90[1] if px90 else MISSING_NUM

        if (
            isinstance(price_t, float)
            and isinstance(price_t90, float)
            and price_t not in (MISSING_NUM,)
            and price_t90 not in (MISSING_NUM,)
            and price_t > 0
        ):
            ret = (price_t90 / price_t) - 1.0
            label = 1 if price_t90 > price_t else 0
        else:
            ret = MISSING_NUM
            label = MISSING_NUM

        if hist and price_t != MISSING_NUM and hist[0] > 0:
            pch_30 = (price_t / hist[0] - 1.0) * 100.0
        else:
            pch_30 = MISSING_NUM

        peak = max(hist) if hist else None
        if peak and peak > 0 and price_t != MISSING_NUM:
            ath_chg = (price_t / peak - 1.0) * 100.0
        else:
            ath_chg = MISSING_NUM

        decision_ts = t.strftime("%Y-%m-%dT00:00:00Z")
        snapshot_id = f"{coin_id}_{entry}"

        rows.append(
            {
                "snapshot_id": snapshot_id,
                "coingecko_id": coin_id,
                "token_symbol": symbol,
                "decision_ts": decision_ts,
                "price_usd_t": price_t if px else MISSING_NUM,
                "volume_24h_usd": vol[1] if vol else MISSING_NUM,
                "market_cap_usd": mcap[1] if mcap else MISSING_NUM,
                "market_cap_rank": MISSING_NUM,  # filled later within-universe
                "category": category,
                "primary_exchange": exchange,
                "hist_prices_30d": json.dumps([round(x, 8) for x in hist]),
                "ath_change_percentage": ath_chg if not (isinstance(ath_chg, float) and math.isnan(ath_chg)) else MISSING_NUM,
                "price_change_percentage_30d": pch_30,
                "research_notes": MISSING_STR,
                "news_score": MISSING_NUM,
                "price_usd_t90": price_t90 if px90 else MISSING_NUM,
                "return_90d": ret,
                "positive_90d_return": label,
            }
        )
    return rows


def assign_universe_ranks(rows: list[dict[str, Any]]) -> None:
    """Ordinal market_cap_rank within each decision_ts among collected tokens."""
    by_date: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        by_date.setdefault(r["decision_ts"], []).append(r)
    for group in by_date.values():
        sortable = [
            r
            for r in group
            if isinstance(r["market_cap_usd"], (int, float))
            and r["market_cap_usd"] != MISSING_NUM
        ]
        sortable.sort(key=lambda r: float(r["market_cap_usd"]), reverse=True)
        for i, r in enumerate(sortable, start=1):
            r["market_cap_rank"] = i


def write_snapshots_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=SNAPSHOT_FIELDS)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect CoinGecko token-entry snapshots")
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--limit-tokens", type=int, default=None, help="Debug: first N tokens only")
    parser.add_argument(
        "--force-refresh",
        action="store_true",
        help="Re-fetch from API even when raw JSON already exists",
    )
    parser.add_argument(
        "--from-raw-only",
        action="store_true",
        help="Build snapshots only from existing raw JSON (no API calls)",
    )
    args = parser.parse_args()

    cfg = load_config(args.config)
    ensure_dirs(cfg)

    tokens: list[str] = list(cfg["tokens"])
    if args.limit_tokens:
        tokens = tokens[: args.limit_tokens]

    entry_dates: list[str] = list(cfg["entry_dates"])
    lookback = int(cfg["hist_lookback_days"])
    horizon = int(cfg["label_horizon_days"])

    min_t = min(parse_date(d) for d in entry_dates) - timedelta(days=lookback + 2)
    max_t = max(parse_date(d) for d in entry_dates) + timedelta(days=horizon + 2)
    # Free tier: /market_chart/range is paid-only. Use days=365 (or config).
    chart_days = cfg.get("chart_days", 365)

    client: CoinGeckoClient | None = None
    if not args.from_raw_only:
        client = CoinGeckoClient(cfg["base_url"], float(cfg["rate_limit_seconds"]))
    raw_dir = ROOT / cfg["paths"]["raw_dir"]
    all_rows: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []

    print(
        f"Collecting {len(tokens)} tokens x {len(entry_dates)} dates -> "
        f"{len(tokens) * len(entry_dates)} snapshots",
        flush=True,
    )
    print(f"Needed window {min_t.date()} -> {max_t.date()}; chart_days={chart_days}", flush=True)

    for i, coin_id in enumerate(tokens, start=1):
        detail_path = raw_dir / f"{coin_id}_detail.json"
        chart_path = raw_dir / f"{coin_id}_chart.json"
        reuse = (
            not args.force_refresh
            and detail_path.exists()
            and chart_path.exists()
        )
        print(
            f"[{i}/{len(tokens)}] {coin_id}"
            + (" (reuse raw)" if reuse else (" (from-raw)" if args.from_raw_only else "")),
            flush=True,
        )
        try:
            if reuse or args.from_raw_only:
                if not detail_path.exists() or not chart_path.exists():
                    raise FileNotFoundError(f"missing raw for {coin_id}")
                detail = load_json(detail_path)
                chart = load_json(chart_path)
            else:
                assert client is not None
                detail = client.coin_detail(coin_id)
                write_json(detail_path, detail)
                chart = client.market_chart(coin_id, chart_days)
                write_json(chart_path, chart)
            rows = build_snapshots_for_coin(
                coin_id, detail, chart, entry_dates, lookback, horizon
            )
            all_rows.extend(rows)
        except Exception as exc:  # noqa: BLE001 — log and continue universe
            msg = f"{type(exc).__name__}: {exc}"
            print(f"  ERROR {msg}", flush=True)
            errors.append({"coingecko_id": coin_id, "error": msg})

    assign_universe_ranks(all_rows)
    out_csv = ROOT / cfg["paths"]["snapshots_csv"]
    write_snapshots_csv(out_csv, all_rows)
    write_json(raw_dir / "_collection_errors.json", errors)
    write_json(
        raw_dir / "_collection_meta.json",
        {
            "tokens_requested": tokens,
            "entry_dates": entry_dates,
            "snapshots_written": len(all_rows),
            "errors": len(errors),
            "output": str(out_csv),
        },
    )
    labeled = sum(1 for r in all_rows if r["positive_90d_return"] in (0, 1))
    positives = sum(1 for r in all_rows if r["positive_90d_return"] == 1)
    print(f"Wrote {len(all_rows)} rows -> {out_csv}", flush=True)
    print(f"Labeled: {labeled}; positive_90d_return=1: {positives}", flush=True)
    if errors:
        print(f"Errors: {len(errors)} (see data/raw/_collection_errors.json)", flush=True)


if __name__ == "__main__":
    main()
