"""
Paper-trading execution on daily reports.

Bankroll starts at paper_starting_balance (default $1000).
Portfolio starts on paper_start_date (default: UTC today).
Rows before that day get paper fields = N/A and never enter the ledger.

Allocation (1B): if model says Invest and score=94 → allocate 9.4% of
*remaining cash* (allocation_pct = invest_score / 10).

Each run marks open positions with return_24h (paper_return_24h) and updates
position_value_usd. Close on Skip / stop / take-profit / max hold.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import MISSING_NUM, MISSING_STR, ensure_dirs, load_config, write_json
from src.collect_coingecko import REPORT_FIELDS, write_reports_csv

PAPER_NA = "N/A"
PAPER_COLS = [
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


def _f(val: Any, default: float = float(MISSING_NUM)) -> float:
    try:
        if val is None or val == "" or val == MISSING_STR or val == PAPER_NA:
            return default
        return float(val)
    except (TypeError, ValueError):
        return default


def _row_date(r: dict[str, Any]) -> str:
    return str(r.get("report_date") or "")[:10]


def resolve_paper_start_date(
    cfg: dict[str, Any],
    rows: list[dict[str, Any]],
) -> str:
    """
    Return YYYY-MM-DD when paper trading begins.
    Config paper_start_date: 'today' | 'latest' | explicit date.
    If 'today' but no rows exist for UTC today, fall back to the latest report_date
    so the portfolio can still open on the newest 15-token snapshot.
    """
    dates = sorted({_row_date(r) for r in rows if _row_date(r)})
    latest = dates[-1] if dates else datetime.now(timezone.utc).date().isoformat()
    raw = str(cfg.get("paper_start_date", "today")).strip().lower()
    if raw in ("", "today"):
        today = datetime.now(timezone.utc).date().isoformat()
        if today in dates:
            return today
        return latest
    if raw == "latest":
        return latest
    return str(cfg.get("paper_start_date")).strip()[:10]


def _set_paper_na(r: dict[str, Any]) -> None:
    for c in PAPER_COLS:
        r[c] = PAPER_NA


def _alloc_pct_from_score(score: float) -> float:
    """Score 94 → 9.4 (% of remaining cash)."""
    if score <= 0 or score == float(MISSING_NUM):
        return 0.0
    return round(score / 10.0, 4)


def apply_paper_trading(
    rows: list[dict[str, Any]],
    *,
    starting_balance: float,
    stop_loss_pct: float,
    take_profit_pct: float,
    max_hold_days: int,
    paper_start_date: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """
    Shared bankroll across tokens. Process calendar days in order.
    Returns (rows, ledger, summary).
    """
    start = paper_start_date[:10]

    # Pre-mark historical
    by_day: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        day = _row_date(r)
        if day < start:
            _set_paper_na(r)
            continue
        by_day.setdefault(day, []).append(r)

    cash = float(starting_balance)
    # token_id -> open position state
    open_pos: dict[str, dict[str, Any]] = {}
    ledger: list[dict[str, Any]] = []

    for day in sorted(by_day.keys()):
        day_rows = by_day[day]
        # Stable order for closes; opens sorted by score later
        day_rows.sort(key=lambda r: str(r.get("token_symbol") or ""))

        # --- Mark-to-market + exits for existing positions ---
        for r in day_rows:
            tid = str(r["coingecko_id"])
            price = _f(r.get("price_usd"))
            decision = str(r.get("model_decision") or MISSING_STR)
            score = _f(r.get("invest_score"), 0.0)
            ret24 = _f(r.get("return_24h"), 0.0)
            if ret24 == float(MISSING_NUM):
                ret24 = 0.0

            if tid not in open_pos:
                continue

            pos = open_pos[tid]
            pos["hold_days"] = int(pos.get("hold_days", 0)) + 1
            # Paper return this run = market return_24h
            if pos["hold_days"] == 1 and pos.get("just_opened"):
                # Opened earlier same day loop shouldn't happen; hold_days starts 0 at open
                pass
            pos["value"] = float(pos["value"]) * (1.0 + ret24 / 100.0)
            entry = float(pos["entry_price"])
            unrealized = (price / entry - 1.0) * 100.0 if entry > 0 and price > 0 else float(MISSING_NUM)

            stop = unrealized != float(MISSING_NUM) and unrealized <= stop_loss_pct
            take = unrealized != float(MISSING_NUM) and unrealized >= take_profit_pct
            time_exit = pos["hold_days"] >= max_hold_days
            skip_exit = decision == "Skip"
            should_close = stop or take or time_exit or skip_exit

            if should_close:
                cash += float(pos["value"])
                reason = (
                    "stop"
                    if stop
                    else "take_profit"
                    if take
                    else "max_hold"
                    if time_exit
                    else "model_skip"
                )
                ledger.append(
                    {
                        "coingecko_id": tid,
                        "token_symbol": r["token_symbol"],
                        "action": "close",
                        "report_date": r["report_date"],
                        "price": price,
                        "entry_price": entry,
                        "hold_days": pos["hold_days"],
                        "pnl_pct": round(unrealized, 4)
                        if unrealized != float(MISSING_NUM)
                        else MISSING_NUM,
                        "allocation_pct": pos.get("allocation_pct", 0),
                        "dollars": round(float(pos["value"]), 4),
                        "cash_after": round(cash, 4),
                        "reason": reason,
                        "invest_score": score,
                        "paper_return_24h": round(ret24, 4),
                    }
                )
                r["did_invest"] = 0
                r["did_close"] = 1
                r["should_close"] = 1
                r["position_open"] = 0
                r["entry_price"] = MISSING_NUM
                r["position_days"] = 0
                r["unrealized_pnl_pct"] = (
                    round(unrealized, 4) if unrealized != float(MISSING_NUM) else MISSING_NUM
                )
                r["realized_pnl_pct"] = (
                    round(unrealized, 4) if unrealized != float(MISSING_NUM) else MISSING_NUM
                )
                r["allocation_pct"] = pos.get("allocation_pct", 0)
                r["position_value_usd"] = 0.0
                r["paper_return_24h"] = round(ret24, 4)
                del open_pos[tid]
            else:
                r["did_invest"] = 0
                r["did_close"] = 0
                r["should_close"] = 0
                r["position_open"] = 1
                r["entry_price"] = entry
                r["position_days"] = pos["hold_days"]
                r["unrealized_pnl_pct"] = (
                    round(unrealized, 4) if unrealized != float(MISSING_NUM) else MISSING_NUM
                )
                r["realized_pnl_pct"] = MISSING_NUM
                r["allocation_pct"] = pos.get("allocation_pct", 0)
                r["position_value_usd"] = round(float(pos["value"]), 4)
                r["paper_return_24h"] = round(ret24, 4)
                pos["just_opened"] = False

        # --- New opens: Invest only, highest score first (uses remaining cash) ---
        candidates = []
        for r in day_rows:
            tid = str(r["coingecko_id"])
            if tid in open_pos:
                continue
            # Skip rows already filled by close branch above without open
            if r.get("did_close") == 1:
                # already set fields
                continue
            decision = str(r.get("model_decision") or MISSING_STR)
            score = _f(r.get("invest_score"), 0.0)
            price = _f(r.get("price_usd"))
            if decision == "Invest" and price > 0 and score > 0:
                candidates.append(r)
            else:
                # flat / skip
                r["did_invest"] = 0
                r["did_close"] = 0
                r["should_close"] = 0
                r["position_open"] = 0
                r["entry_price"] = MISSING_NUM
                r["position_days"] = 0
                r["unrealized_pnl_pct"] = MISSING_NUM
                r["realized_pnl_pct"] = MISSING_NUM
                r["allocation_pct"] = 0.0
                r["position_value_usd"] = 0.0
                r["paper_return_24h"] = PAPER_NA

        candidates.sort(key=lambda r: _f(r.get("invest_score"), 0.0), reverse=True)

        for r in candidates:
            tid = str(r["coingecko_id"])
            if tid in open_pos:
                continue
            score = _f(r.get("invest_score"), 0.0)
            price = _f(r.get("price_usd"))
            alloc = _alloc_pct_from_score(score)
            dollars = cash * (alloc / 100.0)
            if dollars <= 0 or cash <= 0:
                r["did_invest"] = 0
                r["did_close"] = 0
                r["should_close"] = 0
                r["position_open"] = 0
                r["entry_price"] = MISSING_NUM
                r["position_days"] = 0
                r["unrealized_pnl_pct"] = MISSING_NUM
                r["realized_pnl_pct"] = MISSING_NUM
                r["allocation_pct"] = alloc
                r["position_value_usd"] = 0.0
                r["paper_return_24h"] = PAPER_NA
                continue

            cash -= dollars
            open_pos[tid] = {
                "value": dollars,
                "entry_price": price,
                "hold_days": 0,
                "allocation_pct": alloc,
                "just_opened": True,
            }
            ledger.append(
                {
                    "coingecko_id": tid,
                    "token_symbol": r["token_symbol"],
                    "action": "open",
                    "report_date": r["report_date"],
                    "price": price,
                    "entry_price": price,
                    "hold_days": 0,
                    "pnl_pct": 0.0,
                    "allocation_pct": alloc,
                    "dollars": round(dollars, 4),
                    "cash_after": round(cash, 4),
                    "reason": "model_invest",
                    "invest_score": score,
                    "paper_return_24h": 0.0,
                }
            )
            r["did_invest"] = 1
            r["did_close"] = 0
            r["should_close"] = 0
            r["position_open"] = 1
            r["entry_price"] = price
            r["position_days"] = 0
            r["unrealized_pnl_pct"] = 0.0
            r["realized_pnl_pct"] = MISSING_NUM
            r["allocation_pct"] = alloc
            r["position_value_usd"] = round(dollars, 4)
            r["paper_return_24h"] = 0.0  # no prior day for this paper trade yet

    positions_value = sum(float(p["value"]) for p in open_pos.values())
    summary = {
        "cash": round(cash, 4),
        "positions_value": round(positions_value, 4),
        "equity": round(cash + positions_value, 4),
        "open_positions": len(open_pos),
        "starting_balance": starting_balance,
        "paper_start_date": start,
    }
    return rows, ledger, summary


def merge_scores_into_reports(
    reports: list[dict[str, Any]],
    decisions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_key: dict[str, dict[str, Any]] = {}
    for d in decisions:
        rid = str(d.get("report_id") or d.get("snapshot_id") or "")
        if not rid:
            rid = f"{d.get('coingecko_id')}_{str(d.get('decision_ts') or d.get('report_date') or '')[:10]}"
        by_key[rid] = d
        date = str(d.get("decision_ts") or d.get("report_date") or "")[:10]
        by_key[f"{d.get('coingecko_id')}_{date}"] = d

    for r in reports:
        date = str(r.get("report_date") or "")[:10]
        key = str(r.get("report_id") or "")
        d = by_key.get(key) or by_key.get(f"{r.get('coingecko_id')}_{date}")
        if d:
            r["base_score"] = d.get("base_score", MISSING_NUM)
            r["invest_score"] = d.get("invest_score", MISSING_NUM)
            r["model_decision"] = d.get("decision", MISSING_STR)
            if "news_delta" in d:
                r["news_delta"] = d.get("news_delta", r.get("news_delta", 0))
        else:
            r["base_score"] = MISSING_NUM
            r["invest_score"] = MISSING_NUM
            r["model_decision"] = MISSING_STR
    return reports


def run_paper_on_reports(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or load_config()
    ensure_dirs(cfg)
    path = ROOT / cfg["paths"]["daily_reports_csv"]
    with path.open(newline="", encoding="utf-8") as f:
        rows = [dict(r) for r in csv.DictReader(f)]

    for r in rows:
        for k in (
            "price_usd",
            "invest_score",
            "momentum_30d_pct",
            "drawdown_from_peak_pct",
            "return_24h",
        ):
            if k in r:
                r[k] = _f(r[k], r.get(k, MISSING_NUM))  # type: ignore[arg-type]

    start = resolve_paper_start_date(cfg, rows)
    starting = float(cfg.get("paper_starting_balance", 1000))
    rows, ledger, summary = apply_paper_trading(
        rows,
        starting_balance=starting,
        stop_loss_pct=float(cfg.get("paper_stop_loss_pct", -15)),
        take_profit_pct=float(cfg.get("paper_take_profit_pct", 25)),
        max_hold_days=int(cfg.get("paper_max_hold_days", 90)),
        paper_start_date=start,
    )
    write_reports_csv(path, rows)

    ledger_path = ROOT / cfg["paths"].get("paper_ledger_csv", "data/processed/paper_ledger.csv")
    ledger_fields = [
        "coingecko_id",
        "token_symbol",
        "action",
        "report_date",
        "price",
        "entry_price",
        "hold_days",
        "pnl_pct",
        "allocation_pct",
        "dollars",
        "cash_after",
        "reason",
        "invest_score",
        "paper_return_24h",
    ]
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with ledger_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=ledger_fields)
        w.writeheader()
        for e in ledger:
            w.writerow(e)

    n_active = sum(1 for r in rows if _row_date(r) >= start and r.get("did_invest") != PAPER_NA)
    opens = sum(1 for e in ledger if e["action"] == "open")
    closes = sum(1 for e in ledger if e["action"] == "close")

    bankroll_path = ROOT / cfg["paths"].get(
        "paper_bankroll_json", "data/processed/paper_bankroll.json"
    )
    write_json(bankroll_path, summary)

    return {
        "reports": len(rows),
        "paper_start_date": start,
        "paper_active_rows": n_active,
        "ledger_events": len(ledger),
        "opens": opens,
        "closes": closes,
        "bankroll": summary,
        "daily_reports_csv": str(path),
        "paper_ledger_csv": str(ledger_path),
        "paper_bankroll_json": str(bankroll_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply paper trading to daily reports")
    args = parser.parse_args()
    _ = args
    result = run_paper_on_reports()
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
