"""
Write today's 15 coin rows from live prices, then rescore and continue the paper book.

This does not rebuild May–June, and it does not invent prices for days that were
missed. A report is only as fresh as the day the job actually runs.
"""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import MISSING_NUM, MISSING_STR, ensure_dirs, load_config
from src.collect_coingecko import (
    REPORT_FIELDS,
    _merge_gdelt_caches,
    empty_paper_fields,
    write_reports_csv,
)
from src.invest_model import run_train_and_score
from src.live_prices import apply_live_markets_to_rows, fetch_live_markets
from src.news_gdelt import GdeltClient, default_gdelt_query
from src.news_reconcile import filter_relevant, reconcile_press
from src.news_yahoo import YahooRssClient


def _reports_path(cfg: dict[str, Any]) -> Path:
    return ROOT / cfg["paths"].get("daily_reports_csv", cfg["paths"]["snapshots_csv"])


def _load_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _day(row: dict[str, Any]) -> str:
    return str(row.get("report_date") or "")[:10]


def _latest_by_coin(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    latest: dict[str, dict[str, str]] = {}
    for row in rows:
        coin = str(row.get("coingecko_id") or "")
        if not coin:
            continue
        prev = latest.get(coin)
        if prev is None or _day(row) > _day(prev):
            latest[coin] = row
    return latest


def _blank_today(prior: dict[str, str], today: str) -> dict[str, Any]:
    """Start from the last real row so category and exchange stay, then clear the answer."""
    coin = str(prior["coingecko_id"])
    row: dict[str, Any] = {field: prior.get(field, "") for field in REPORT_FIELDS}
    row["report_id"] = f"{coin}_{today}"
    row["report_date"] = f"{today}T00:00:00Z"
    row["price_usd_t90"] = MISSING_NUM
    row["return_90d"] = MISSING_NUM
    row["positive_90d_return"] = MISSING_NUM
    row["press_gdelt"] = MISSING_STR
    row["press_yahoo"] = MISSING_STR
    row["press_release"] = MISSING_STR
    row["press_opinion"] = "none"
    row["press_conflict"] = "none"
    row["news_count_10d"] = 0
    row["news_delta"] = 0
    row["news_headlines_10d"] = MISSING_STR
    row.update(empty_paper_fields())
    return row


def _attach_news(
    row: dict[str, Any],
    cfg: dict[str, Any],
    today: datetime,
    gdelt: GdeltClient,
    yahoo: YahooRssClient,
) -> None:
    coin = str(row["coingecko_id"])
    symbol = str(row.get("token_symbol") or coin).upper()
    display = str((cfg.get("token_display_names") or {}).get(coin) or symbol)
    lookback = int(cfg.get("news_lookback_days", 10))
    gdelt_titles: list[str] = []
    yahoo_titles: list[str] = []
    try:
        data, err = gdelt._get_json(
            {
                "query": default_gdelt_query(display, symbol),
                "mode": "ArtList",
                "maxrecords": "40",
                "format": "json",
                "sort": "DateDesc",
                "timespan": "14d",
            },
            retries=1,
            timeout=25,
        )
        if err and not data.get("articles"):
            print(f"  GDELT empty {coin}: {err}", flush=True)
        gdelt_titles = filter_relevant(
            [str(a.get("title") or "") for a in (data.get("articles") or [])],
            symbol,
            display,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"  GDELT skip {coin}: {exc}", flush=True)
        gdelt_titles = []
    if not gdelt_titles and gdelt.cache_dir is not None:
        cached = _merge_gdelt_caches(gdelt.cache_dir, coin, [])
        gdelt_titles = filter_relevant(
            gdelt.headlines_in_window(cached, today, lookback),
            symbol,
            display,
        )
        if gdelt_titles:
            print(f"  GDELT cache {coin}: {len(gdelt_titles)} headlines", flush=True)
    try:
        ysym = str((cfg.get("yahoo_symbols") or {}).get(coin) or f"{symbol}-USD")
        yahoo_titles = filter_relevant(
            yahoo.headlines_in_window(ysym, today, lookback, refresh=True),
            symbol,
            display,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"  Yahoo skip {coin}: {exc}", flush=True)
    press = reconcile_press(gdelt_titles, yahoo_titles)
    row["press_gdelt"] = press["press_gdelt"]
    row["press_yahoo"] = press["press_yahoo"]
    row["press_release"] = press["press_release"]
    row["press_opinion"] = press["press_opinion"]
    row["press_conflict"] = press["press_conflict"]
    row["news_count_10d"] = press["news_count_10d"]
    row["news_delta"] = press["news_delta"]
    row["news_headlines_10d"] = press["press_release"]


def ensure_today_rows(cfg: dict[str, Any], *, with_news: bool = True) -> dict[str, Any]:
    """Add or replace the 15 rows for UTC today. Older days are left as they are."""
    ensure_dirs(cfg)
    path = _reports_path(cfg)
    today = datetime.now(timezone.utc).date().isoformat()
    existing = _load_rows(path)
    kept = [row for row in existing if _day(row) != today]
    priors = _latest_by_coin(kept)
    missing = [coin for coin in cfg["tokens"] if coin not in priors]
    if missing:
        raise RuntimeError(
            "No earlier row to copy category and exchange from: " + ", ".join(missing)
        )

    today_rows = [_blank_today(priors[coin], today) for coin in cfg["tokens"]]
    if with_news:
        stamp = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        news_dir = ROOT / cfg["paths"]["raw_dir"] / "news"
        news_dir.mkdir(parents=True, exist_ok=True)
        gdelt = GdeltClient(rate_limit_seconds=5.5, cache_dir=news_dir)
        yahoo = YahooRssClient(rate_limit_seconds=1.0, cache_dir=news_dir)
        for row in today_rows:
            print(f"News {row['coingecko_id']}…", flush=True)
            _attach_news(row, cfg, stamp, gdelt, yahoo)

    print(f"Live CoinGecko prices for {today}…", flush=True)
    live = fetch_live_markets(cfg)
    updated = apply_live_markets_to_rows(today_rows, live, day=today)
    combined = kept + today_rows
    combined.sort(key=lambda row: (_day(row), str(row.get("token_symbol") or "")))
    write_reports_csv(path, combined)
    return {
        "day": today,
        "rows_before": len(existing),
        "rows_after": len(combined),
        "today_rows": len(today_rows),
        "live_rows": updated,
        "replaced_existing_today": len(existing) - len(kept),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Append UTC today's 15 reports from live prices, then score and paper-trade."
    )
    parser.add_argument(
        "--skip-news",
        action="store_true",
        help="Write today's prices without calling GDELT or Yahoo.",
    )
    parser.add_argument("--threshold", type=float, default=50.0)
    args = parser.parse_args()

    cfg = load_config()
    added = ensure_today_rows(cfg, with_news=not args.skip_news)
    print(
        f"Today {added['day']}: {added['today_rows']} rows, "
        f"{added['live_rows']} with live prices. File now {added['rows_after']} rows.",
        flush=True,
    )
    # Prices were just written. Score and continue the paper book from paper_start_date.
    result = run_train_and_score(cfg, threshold=args.threshold, refresh_live=True)
    paper = result.get("paper") or {}
    print(
        f"Paper cash {paper.get('cash')} | positions {paper.get('open_positions')} | "
        f"equity {paper.get('equity')}",
        flush=True,
    )


if __name__ == "__main__":
    main()
