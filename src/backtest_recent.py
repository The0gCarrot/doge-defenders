"""
Backtest the current invest rule on the most recent days.

Walk backward from UTC today until there are at least 500 rows (15 coins).
Train on the older labeled file, then score this window. Paper-trade from the
first day of the window with the same $1,000 rules.

The 90-day result is not in this file: those future prices do not exist yet.
"""

from __future__ import annotations

import csv
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import MISSING_NUM, ensure_dirs, load_config, write_json
from src.coingecko_client import CoinGeckoClient
from src.collect_coingecko import assign_universe_ranks, build_reports_for_coin
from src.invest_model import load_reports, merge_scores_into_reports, score_rows, train_model
from src.live_prices import apply_live_markets_to_rows, fetch_live_markets
from src.news_gdelt import GdeltClient, _normalize_articles, default_gdelt_query
from src.news_yahoo import YahooRssClient
from src.paper_trade import apply_paper_trading

# Columns that only restate another column, or that do not change the invest decision.
# Kept out of the delivered file.
CONDENSED_FIELDS = [
    "token_symbol",
    "report_date",
    "price_usd",
    "return_24h",
    "volume_24h_usd",
    "market_cap_usd",
    "market_cap_rank",
    "momentum_30d_pct",
    "drawdown_from_peak_pct",
    "press_opinion",
    "base_score",
    "invest_score",
    "model_decision",
    "did_invest",
    "allocation_pct",
    "position_value_usd",
    "paper_return_24h",
    "unrealized_pnl_pct",
    "realized_pnl_pct",
]


def backtest_dates(today: datetime, coins: int, minimum_rows: int = 500) -> list[str]:
    """Oldest day first. 15 coins x 34 days = 510, the smallest window over 500."""
    days_needed = (minimum_rows + coins - 1) // coins
    end = today.date()
    start = end - timedelta(days=days_needed - 1)
    out: list[str] = []
    cur = start
    while cur <= end:
        out.append(cur.isoformat())
        cur += timedelta(days=1)
    return out


def _symbol(cfg: dict[str, Any], coin_id: str) -> str:
    yahoo = str((cfg.get("yahoo_symbols") or {}).get(coin_id) or "")
    if "-" in yahoo:
        return yahoo.split("-", 1)[0].upper()
    return coin_id[:4].upper()


def _gdelt_articles(
    client: GdeltClient,
    query: str,
    start: datetime,
    end: datetime,
) -> list[dict[str, Any]]:
    data, err = client._get_json(
        {
            "query": query,
            "mode": "ArtList",
            "maxrecords": "75",
            "format": "json",
            "sort": "DateDesc",
            "timespan": "70d",
        },
        retries=1,
        timeout=25,
    )
    articles = _normalize_articles(list(data.get("articles") or []), start, end)
    if err and not articles:
        print(f"  GDELT empty: {err}", flush=True)
    return articles


def collect_window(cfg: dict[str, Any], dates: list[str]) -> list[dict[str, Any]]:
    client = CoinGeckoClient(cfg["base_url"], float(cfg["rate_limit_seconds"]))
    raw_dir = ROOT / cfg["paths"]["raw_dir"]
    news_dir = raw_dir / "news"
    news_dir.mkdir(parents=True, exist_ok=True)
    gdelt = GdeltClient(rate_limit_seconds=5.5, cache_dir=news_dir)
    yahoo = YahooRssClient(rate_limit_seconds=1.0, cache_dir=news_dir)
    names: dict[str, str] = dict(cfg.get("token_display_names") or {})
    yahoo_map: dict[str, str] = dict(cfg.get("yahoo_symbols") or {})
    lookback = int(cfg["hist_lookback_days"])
    horizon = int(cfg["label_horizon_days"])
    news_lookback = int(cfg.get("news_lookback_days", 10))
    window_start = datetime.strptime(dates[0], "%Y-%m-%d").replace(tzinfo=timezone.utc) - timedelta(
        days=news_lookback
    )
    window_end = datetime.strptime(dates[-1], "%Y-%m-%d").replace(tzinfo=timezone.utc) + timedelta(days=1)

    rows: list[dict[str, Any]] = []
    tokens = list(cfg["tokens"])
    for i, coin_id in enumerate(tokens, start=1):
        print(f"[{i}/{len(tokens)}] {coin_id}", flush=True)
        chart = client.market_chart(coin_id, 120)
        write_json(raw_dir / f"{coin_id}_chart_backtest.json", chart)
        symbol = _symbol(cfg, coin_id)
        display = names.get(coin_id, symbol)
        detail = {"symbol": symbol, "categories": [], "tickers": []}
        print("  news…", flush=True)
        articles = _gdelt_articles(
            gdelt,
            default_gdelt_query(display, symbol),
            window_start,
            window_end,
        )
        ysym = yahoo_map.get(coin_id, f"{symbol}-USD")
        try:
            yahoo_items = yahoo.fetch_feed(ysym)
        except Exception as exc:  # noqa: BLE001
            print(f"  Yahoo skip: {exc}", flush=True)
            yahoo_items = []
        rows.extend(
            build_reports_for_coin(
                coin_id,
                detail,
                chart,
                dates,
                lookback,
                horizon,
                news_lookback,
                articles,
                yahoo_items,
                display_name=display,
            )
        )
    return rows


def write_condensed(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CONDENSED_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in CONDENSED_FIELDS})


def main() -> None:
    cfg = load_config()
    ensure_dirs(cfg)
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    dates = backtest_dates(today, len(cfg["tokens"]), 500)
    print(
        f"Window {dates[0]} .. {dates[-1]} "
        f"({len(dates)} days x {len(cfg['tokens'])} coins = {len(dates) * len(cfg['tokens'])} rows)",
        flush=True,
    )

    rows = collect_window(cfg, dates)
    today_s = today.date().isoformat()
    print("Live prices for today…", flush=True)
    live = fetch_live_markets(cfg)
    apply_live_markets_to_rows(rows, live, day=today_s)
    # Rank is inside this 15-coin set, same definition the model was trained on.
    # A missing rank makes the scorer skip the row.
    assign_universe_ranks(rows)

    history_path = ROOT / cfg["paths"]["daily_reports_csv"]
    history = load_reports(history_path)
    pipe, metrics = train_model(history)
    print(
        f"Trained on {metrics['n_train']} older labeled rows, "
        f"checked on {metrics['n_test']} (accuracy {metrics['accuracy_test']:.3f}).",
        flush=True,
    )
    decisions = score_rows(pipe, rows, threshold=float(cfg.get("invest_threshold", 50)))
    rows = merge_scores_into_reports(rows, decisions)

    start = dates[0]
    rows, _ledger, summary = apply_paper_trading(
        rows,
        starting_balance=float(cfg.get("paper_starting_balance", 1000)),
        stop_loss_pct=float(cfg.get("paper_stop_loss_pct", -15)),
        take_profit_pct=float(cfg.get("paper_take_profit_pct", 25)),
        max_hold_days=int(cfg.get("paper_max_hold_days", 90)),
        paper_start_date=start,
    )
    rows.sort(key=lambda row: (str(row.get("report_date") or ""), str(row.get("token_symbol") or "")))

    out = ROOT / "data" / "processed" / "backtest_from_today.csv"
    downloads = Path(r"C:\Users\gabri\Downloads\backtest_from_today.csv")
    write_condensed(out, rows)
    write_condensed(downloads, rows)
    invests = sum(1 for row in rows if str(row.get("model_decision")) == "Invest")
    print(f"Wrote {len(rows)} rows, {invests} Invest decisions.", flush=True)
    print(
        f"Paper book from {start}: cash {summary['cash']}, "
        f"positions {summary['positions_value']}, equity {summary['equity']}, "
        f"open {summary['open_positions']}.",
        flush=True,
    )
    print(f"File: {downloads}", flush=True)


if __name__ == "__main__":
    main()
