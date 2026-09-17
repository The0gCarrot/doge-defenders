"""Report adequacy vs course bar: 500 records, 10 usable attrs, 60 minority class."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import MISSING_NUM, MISSING_STR, ensure_dirs, load_config, write_json

# Usable attributes (course: varies, coded, not id/constant/near-copy of another).
USABLE_ATTRS = [
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
]


def is_missing(col: str, val: str) -> bool:
    if val is None:
        return True
    s = str(val).strip()
    if s == "" or s == MISSING_STR:
        return True
    if col in {
        "price_usd_t",
        "volume_24h_usd",
        "market_cap_usd",
        "market_cap_rank",
        "ath_change_percentage",
        "price_change_percentage_30d",
        "news_score",
        "price_usd_t90",
        "return_90d",
        "positive_90d_return",
    }:
        try:
            return float(s) == float(MISSING_NUM)
        except ValueError:
            return False
    return False


def attr_usable(rows: list[dict[str, str]], col: str) -> bool:
    values = [r.get(col, "") for r in rows]
    non_missing = [v for v in values if not is_missing(col, v)]
    if len(non_missing) < max(10, int(0.05 * len(rows))):
        return False
    uniq = set(non_missing)
    if len(uniq) < 2:
        return False
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Adequacy report 500/10/60")
    parser.add_argument("--config", type=Path, default=None)
    args = parser.parse_args()

    cfg = load_config(args.config)
    ensure_dirs(cfg)
    snap_path = ROOT / cfg["paths"]["snapshots_csv"]
    if not snap_path.exists():
        raise SystemExit(f"Missing {snap_path}")

    with snap_path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    n = len(rows)
    usable = [c for c in USABLE_ATTRS if attr_usable(rows, c)]
    labels = []
    for r in rows:
        v = str(r.get("positive_90d_return", "")).strip()
        try:
            iv = int(float(v))
        except ValueError:
            continue
        if iv in (0, 1):
            labels.append(iv)
    positives = sum(1 for x in labels if x == 1)
    negatives = sum(1 for x in labels if x == 0)
    minority = min(positives, negatives) if labels else 0

    report = {
        "records": {"value": n, "standard": 500, "ok": n >= 500},
        "usable_attributes": {
            "value": len(usable),
            "standard": 10,
            "ok": len(usable) >= 10,
            "attrs": usable,
        },
        "minority_class_cases": {
            "value": minority,
            "standard": 60,
            "ok": minority >= 60,
            "positives": positives,
            "negatives": negatives,
            "labeled": len(labels),
        },
        "recommendations": [],
    }
    if n < 500:
        report["recommendations"].append(
            "Widen token universe and/or add entry_dates in config.yaml, then re-run collector."
        )
    if len(usable) < 10:
        report["recommendations"].append(
            "Fill research_notes/news_score via append_research_notes.py; check API fields not all missing."
        )
    if minority < 60:
        report["recommendations"].append(
            "Add more tokens/entry dates spanning mixed regimes so positive_90d_return minority clears 60."
        )

    out = ROOT / cfg["paths"]["adequacy_report"]
    write_json(out, report)
    print(json.dumps(report, indent=2))
    print(f"Wrote {out}")
    if not (report["records"]["ok"] and report["usable_attributes"]["ok"] and report["minority_class_cases"]["ok"]):
        sys.exit(2)


if __name__ == "__main__":
    main()
