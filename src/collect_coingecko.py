"""
Collect daily CoinGecko reports for the token universe × calendar days.

One row = one (token, report_date). Includes price, GDELT+Yahoo press (10d),
30d momentum, drawdown-from-peak, return_24h, and 90d labels when available.
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
from src.news_gdelt import GdeltClient, default_gdelt_query
from src.news_reconcile import filter_relevant, reconcile_press
from src.news_yahoo import YahooRssClient


REPORT_FIELDS = [
    "report_id",
    "coingecko_id",
    "token_symbol",
    "report_date",
    "price_usd",
    "return_24h",
    "volume_24h_usd",
    "market_cap_usd",
    "market_cap_rank",
    "category",
    "primary_exchange",
    "momentum_30d_pct",
    "drawdown_from_peak_pct",
    "press_gdelt",
    "press_yahoo",
    "press_release",
    "press_opinion",
    "press_conflict",
    "news_count_10d",
    "news_delta",
    "news_headlines_10d",
    "hist_prices_30d",
    "price_usd_t90",
    "return_90d",
    "positive_90d_return",
    "base_score",
    "invest_score",
    "model_decision",
    "did_invest",
    "position_open",
    "entry_price",
    "position_days",
    "unrealized_pnl_pct",
    "should_close",
    "did_close",
    "realized_pnl_pct",
    "allocation_pct",
    "position_value_usd",
    "paper_return_24h",
]

MAJOR_EXCHANGE_IDS = frozenset(
    {
        "binance",
        "coinbase",
        "coinbase_international",
        "coinbase_exchange",
        "kraken",
        "okex",
        "okx",
        "bybit",
        "bybit_spot",
        "kucoin",
        "bitfinex",
        "bitstamp",
        "gemini",
        "huobi",
        "htx",
        "gate",
        "gate_io",
        "crypto_com",
        "mexc",
        "bitget",
        "uniswap_v3",
        "uniswap",
    }
)

PREFERRED_CATEGORIES = [
    "Meme",
    "Layer 1 (L1)",
    "Decentralized Finance (DeFi)",
    "Decentralized Exchange (DEX)",
    "Lending/Borrowing Protocols",
    "Artificial Intelligence (AI)",
    "Infrastructure",
    "Smart Contract Platform",
]

CATEGORY_SKIP_SUBSTRINGS = (
    "portfolio",
    "index",
    "holdings",
    "ftx",
    "alameda",
    "andreessen",
    "multicoin",
)


def parse_date(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc)


def daily_report_dates(cfg: dict[str, Any]) -> list[str]:
    n = int(cfg.get("daily_report_days", 34))
    end_s = cfg.get("daily_end_date")
    if end_s:
        end = parse_date(str(end_s)).date()
    else:
        end = (datetime.now(timezone.utc) - timedelta(days=int(cfg["label_horizon_days"]))).date()
    start = end - timedelta(days=n - 1)
    out: list[str] = []
    cur = start
    while cur <= end:
        out.append(cur.isoformat())
        cur += timedelta(days=1)
    # Append UTC today so paper portfolio can open on the live 15-token snapshot.
    if cfg.get("include_today", True):
        today = datetime.now(timezone.utc).date().isoformat()
        if today not in out:
            out.append(today)
    return out


def nearest_point(series: list[list[float]], target_ms: int) -> tuple[float, float] | None:
    if not series:
        return None
    best = min(series, key=lambda p: abs(int(p[0]) - target_ms))
    return float(best[0]), float(best[1])


def points_between(series: list[list[float]], start_ms: int, end_ms: int) -> list[float]:
    return [float(p[1]) for p in series if start_ms <= int(p[0]) <= end_ms]


def _ticker_volume_usd(t: dict[str, Any]) -> float:
    cv = t.get("converted_volume") or {}
    return float(cv.get("usd") or 0)


def _ticker_exchange_id(t: dict[str, Any]) -> str:
    market = t.get("market") or {}
    return str(market.get("identifier") or market.get("name") or "").strip().lower()


def _is_major_exchange(exchange_id: str) -> bool:
    if not exchange_id:
        return False
    if exchange_id in MAJOR_EXCHANGE_IDS:
        return True
    base = exchange_id.replace("_spot", "").replace("_futures", "")
    return base in MAJOR_EXCHANGE_IDS


def primary_exchange_from_detail(detail: dict[str, Any]) -> str:
    tickers = detail.get("tickers") or []
    if not tickers:
        return MISSING_STR
    majors = [t for t in tickers if _is_major_exchange(_ticker_exchange_id(t))]
    pool = majors if majors else tickers
    best = max(pool, key=_ticker_volume_usd)
    name = _ticker_exchange_id(best)
    return name if name else MISSING_STR


def _category_is_noise(cat: str) -> bool:
    low = cat.lower()
    return any(s in low for s in CATEGORY_SKIP_SUBSTRINGS)


def category_from_detail(detail: dict[str, Any]) -> str:
    cats = [str(c) for c in (detail.get("categories") or []) if c]
    if not cats:
        return MISSING_STR
    cat_set = set(cats)
    for preferred in PREFERRED_CATEGORIES:
        if preferred in cat_set:
            return preferred
    for cat in cats:
        if not _category_is_noise(cat):
            return cat
    return cats[0]


def empty_paper_fields() -> dict[str, Any]:
    return {
        "base_score": MISSING_NUM,
        "invest_score": MISSING_NUM,
        "model_decision": MISSING_STR,
        "did_invest": 0,
        "position_open": 0,
        "entry_price": MISSING_NUM,
        "position_days": 0,
        "unrealized_pnl_pct": MISSING_NUM,
        "should_close": 0,
        "did_close": 0,
        "realized_pnl_pct": MISSING_NUM,
        "allocation_pct": MISSING_NUM,
        "position_value_usd": MISSING_NUM,
        "paper_return_24h": MISSING_STR,
    }


def build_reports_for_coin(
    coin_id: str,
    detail: dict[str, Any],
    chart: dict[str, Any],
    report_dates: list[str],
    lookback_days: int,
    horizon_days: int,
    news_lookback: int,
    gdelt_articles: list[dict[str, Any]],
    yahoo_items: list[dict[str, Any]],
    display_name: str = "",
) -> list[dict[str, Any]]:
    prices = chart.get("prices") or []
    volumes = chart.get("total_volumes") or []
    mcaps = chart.get("market_caps") or []
    symbol = (detail.get("symbol") or coin_id).upper()
    disp = display_name or symbol
    category = category_from_detail(detail)
    exchange = primary_exchange_from_detail(detail)

    # Precompute yahoo titles by day for filtering
    yahoo_by_ts: list[tuple[datetime, str]] = []
    for it in yahoo_items:
        pub = it.get("published") or ""
        title = str(it.get("title") or "").strip()
        if not title or not pub:
            continue
        if not title_relevant_safe(title, symbol, disp):
            continue
        try:
            ts = datetime.fromisoformat(str(pub))
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            yahoo_by_ts.append((ts, title[:240]))
        except ValueError:
            continue

    gdelt_client = GdeltClient()  # only for window filter helper
    rows: list[dict[str, Any]] = []

    for day in report_dates:
        t = parse_date(day)
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
        if len(hist) > lookback_days * 2:
            step = max(1, len(hist) // lookback_days)
            hist = hist[::step][:lookback_days]

        price_t = px[1] if px else MISSING_NUM
        price_t90 = px90[1] if px90 else MISSING_NUM

        # Don't use a chart point that is more than ~2 days from the report day
        # (stale raw JSON would otherwise price "today" as last chart close).
        if px and abs(int(px[0]) - t_ms) > 2 * 86_400_000:
            price_t = MISSING_NUM

        # Always use ~1 calendar day lookback on the chart (not prior report row).
        px_y = nearest_point(prices, t_ms - 86_400_000)
        if (
            px
            and px_y
            and isinstance(price_t, (int, float))
            and price_t != MISSING_NUM
            and px_y[1] > 0
            and abs(int(px[0]) - t_ms) <= 2 * 86_400_000
        ):
            ret_24h = (price_t / px_y[1] - 1.0) * 100.0
        else:
            ret_24h = MISSING_NUM

        if (
            isinstance(price_t, (int, float))
            and isinstance(price_t90, (int, float))
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
            momentum = (price_t / hist[0] - 1.0) * 100.0
        else:
            momentum = MISSING_NUM

        peak = max(hist) if hist else None
        if peak and peak > 0 and price_t != MISSING_NUM:
            drawdown = (price_t / peak - 1.0) * 100.0
        else:
            drawdown = MISSING_NUM

        g_heads = filter_relevant(
            gdelt_client.headlines_in_window(gdelt_articles, t, news_lookback),
            symbol,
            disp,
        )
        y_start = t - timedelta(days=news_lookback)
        y_end = t + timedelta(days=1)
        y_heads = [title for ts, title in yahoo_by_ts if y_start <= ts <= y_end][:12]
        press = reconcile_press(g_heads, y_heads)

        row = {
            "report_id": f"{coin_id}_{day}",
            "coingecko_id": coin_id,
            "token_symbol": symbol,
            "report_date": f"{day}T00:00:00Z",
            "price_usd": price_t if price_t != MISSING_NUM else MISSING_NUM,
            "return_24h": ret_24h
            if not (isinstance(ret_24h, float) and math.isnan(ret_24h))
            else MISSING_NUM,
            "volume_24h_usd": vol[1] if vol else MISSING_NUM,
            "market_cap_usd": mcap[1] if mcap else MISSING_NUM,
            "market_cap_rank": MISSING_NUM,
            "category": category,
            "primary_exchange": exchange,
            "momentum_30d_pct": momentum
            if not (isinstance(momentum, float) and math.isnan(momentum))
            else MISSING_NUM,
            "drawdown_from_peak_pct": drawdown
            if not (isinstance(drawdown, float) and math.isnan(drawdown))
            else MISSING_NUM,
            "press_gdelt": press["press_gdelt"],
            "press_yahoo": press["press_yahoo"],
            "press_release": press["press_release"],
            "press_opinion": press["press_opinion"],
            "press_conflict": press["press_conflict"],
            "news_count_10d": press["news_count_10d"],
            "news_delta": press["news_delta"],
            "news_headlines_10d": press["press_release"],
            "hist_prices_30d": json.dumps([round(x, 8) for x in hist]),
            "price_usd_t90": price_t90 if px90 else MISSING_NUM,
            "return_90d": ret,
            "positive_90d_return": label,
        }
        row.update(empty_paper_fields())
        rows.append(row)
    return rows


def title_relevant_safe(title: str, symbol: str, display_name: str) -> bool:
    return bool(filter_relevant([title], symbol, display_name))


def assign_universe_ranks(rows: list[dict[str, Any]]) -> None:
    by_date: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        by_date.setdefault(r["report_date"], []).append(r)
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


def write_reports_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=REPORT_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for r in rows:
            writer.writerow(r)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _merge_gdelt_caches(
    news_dir: Path,
    coin_id: str,
    primary: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Union articles from all gdelt_{coin}* cache files (avoid losing older pulls)."""
    merged: list[dict[str, Any]] = list(primary or [])
    seen: set[str] = set()
    for a in merged:
        key = f"{a.get('seendate')}|{a.get('title')}"
        seen.add(key)
    for path in sorted(news_dir.glob(f"gdelt_{coin_id}*.json")):
        try:
            payload = load_json(path)
        except Exception:  # noqa: BLE001
            continue
        if payload.get("error") and not (payload.get("articles") or []):
            continue
        for a in payload.get("articles") or []:
            if not isinstance(a, dict):
                continue
            title = str(a.get("title") or "").strip()
            if not title:
                continue
            key = f"{a.get('seendate')}|{title}"
            if key in seen:
                continue
            seen.add(key)
            merged.append(
                {
                    "title": title,
                    "url": a.get("url") or "",
                    "seendate": a.get("seendate") or "",
                    "source": a.get("source") or a.get("domain") or "gdelt",
                }
            )
    return merged


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect CoinGecko daily reports + press")
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--limit-tokens", type=int, default=None)
    parser.add_argument("--force-refresh", action="store_true")
    parser.add_argument("--from-raw-only", action="store_true")
    parser.add_argument(
        "--skip-news",
        action="store_true",
        help="Skip GDELT/Yahoo fetches (empty press columns)",
    )
    args = parser.parse_args()

    cfg = load_config(args.config)
    ensure_dirs(cfg)

    tokens: list[str] = list(cfg["tokens"])
    if args.limit_tokens:
        tokens = tokens[: args.limit_tokens]

    report_dates = daily_report_dates(cfg)
    lookback = int(cfg["hist_lookback_days"])
    horizon = int(cfg["label_horizon_days"])
    news_lookback = int(cfg.get("news_lookback_days", 10))
    chart_days = cfg.get("chart_days", 365)
    display_names: dict[str, str] = dict(cfg.get("token_display_names") or {})
    yahoo_map: dict[str, str] = dict(cfg.get("yahoo_symbols") or {})

    client: CoinGeckoClient | None = None
    if not args.from_raw_only:
        client = CoinGeckoClient(cfg["base_url"], float(cfg["rate_limit_seconds"]))

    raw_dir = ROOT / cfg["paths"]["raw_dir"]
    news_dir = raw_dir / "news"
    news_dir.mkdir(parents=True, exist_ok=True)

    fetch_news = not args.skip_news
    gdelt = GdeltClient(rate_limit_seconds=5.5, cache_dir=news_dir) if fetch_news else None
    yahoo = YahooRssClient(rate_limit_seconds=1.0, cache_dir=news_dir) if fetch_news else None

    # GDELT range covers full backfill + lookback
    first_day = parse_date(report_dates[0]) - timedelta(days=news_lookback)
    last_day = parse_date(report_dates[-1]) + timedelta(days=1)

    all_rows: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []

    print(
        f"Collecting {len(tokens)} tokens x {len(report_dates)} days -> "
        f"{len(tokens) * len(report_dates)} daily reports "
        f"({report_dates[0]} .. {report_dates[-1]})",
        flush=True,
    )

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

            symbol = (detail.get("symbol") or coin_id).upper()
            display = display_names.get(coin_id, symbol)
            gdelt_articles: list[dict[str, Any]] = []
            yahoo_items: list[dict[str, Any]] = []

            if fetch_news and gdelt is not None and yahoo is not None:
                query = default_gdelt_query(display, symbol)
                if args.force_refresh:
                    for p in news_dir.glob(f"gdelt_{coin_id}*"):
                        p.unlink(missing_ok=True)
                    ysym = yahoo_map.get(coin_id, f"{symbol}-USD")
                    yp = news_dir / f"yahoo_{ysym.replace('/', '_')}.json"
                    if yp.exists():
                        yp.unlink()
                print(f"  news GDELT+Yahoo…", flush=True)
                # Stable cache key per coin; also merge any older dated GDELT caches.
                gdelt_articles = gdelt.search_range(
                    query, first_day, last_day, cache_key=coin_id
                )
                gdelt_articles = _merge_gdelt_caches(news_dir, coin_id, gdelt_articles)
                ysym = yahoo_map.get(coin_id, f"{symbol}-USD")
                yahoo_items = yahoo.fetch_feed(ysym)
                print(
                    f"  gdelt={len(gdelt_articles)} yahoo={len(yahoo_items)}",
                    flush=True,
                )

            rows = build_reports_for_coin(
                coin_id,
                detail,
                chart,
                report_dates,
                lookback,
                horizon,
                news_lookback,
                gdelt_articles,
                yahoo_items,
                display_name=display,
            )
            all_rows.extend(rows)
        except Exception as exc:  # noqa: BLE001
            msg = f"{type(exc).__name__}: {exc}"
            print(f"  ERROR {msg}", flush=True)
            errors.append({"coingecko_id": coin_id, "error": msg})

    # Live CoinGecko /coins/markets for include_today (paper day).
    today = datetime.now(timezone.utc).date().isoformat()
    live_meta: dict[str, Any] = {}
    if cfg.get("include_today", True) and any(
        str(r.get("report_date", ""))[:10] == today for r in all_rows
    ):
        from src.live_prices import apply_live_markets_to_rows, fetch_live_markets

        print(f"Fetching live CoinGecko /coins/markets for {today}…", flush=True)
        try:
            live = fetch_live_markets(cfg)
            n_live = apply_live_markets_to_rows(all_rows, live, day=today)
            live_meta = {
                "asof_utc": datetime.now(timezone.utc).isoformat(),
                "source": "coingecko:/coins/markets",
                "updated_rows": n_live,
            }
            write_json(raw_dir / "_live_prices.json", {"day": today, **live_meta, "markets": live})
            print(f"  Applied live markets to {n_live} today-rows", flush=True)
        except Exception as exc:  # noqa: BLE001
            print(f"  LIVE PRICE ERROR: {exc}", flush=True)
            errors.append({"coingecko_id": "_live_prices", "error": str(exc)})

    assign_universe_ranks(all_rows)
    out_csv = ROOT / cfg["paths"]["daily_reports_csv"]
    write_reports_csv(out_csv, all_rows)
    write_json(raw_dir / "_collection_errors.json", errors)
    write_json(
        raw_dir / "_collection_meta.json",
        {
            "tokens_requested": tokens,
            "report_dates": report_dates,
            "reports_written": len(all_rows),
            "errors": len(errors),
            "output": str(out_csv),
            "news": "gdelt+yahoo" if fetch_news else "skipped",
            "live_prices_today": bool(live_meta),
        },
    )
    labeled = sum(1 for r in all_rows if r["positive_90d_return"] in (0, 1))
    positives = sum(1 for r in all_rows if r["positive_90d_return"] == 1)
    with_news = sum(1 for r in all_rows if int(r["news_count_10d"]) > 0)
    print(f"Wrote {len(all_rows)} rows -> {out_csv}", flush=True)
    print(
        f"Labeled: {labeled}; positive_90d_return=1: {positives}; rows_with_news: {with_news}",
        flush=True,
    )
    if errors:
        print(f"Errors: {len(errors)} (see data/raw/_collection_errors.json)", flush=True)


if __name__ == "__main__":
    main()
