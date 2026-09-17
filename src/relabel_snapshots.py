"""
Recompute 90-day labels from saved raw chart JSON (no new API calls).

Use after adjusting label_horizon_days or fixing nearest-price logic.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import MISSING_NUM, ensure_dirs, load_config
from src.collect_coingecko import (
    SNAPSHOT_FIELDS,
    nearest_point,
    parse_date,
    write_snapshots_csv,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Relabel snapshots from raw charts")
    parser.add_argument("--config", type=Path, default=None)
    args = parser.parse_args()

    cfg = load_config(args.config)
    ensure_dirs(cfg)
    raw_dir = ROOT / cfg["paths"]["raw_dir"]
    snap_path = ROOT / cfg["paths"]["snapshots_csv"]
    horizon = int(cfg["label_horizon_days"])

    if not snap_path.exists():
        raise SystemExit(f"Missing {snap_path}")

    with snap_path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    charts: dict[str, dict] = {}
    updated = 0
    for row in rows:
        cid = row["coingecko_id"]
        if cid not in charts:
            chart_path = raw_dir / f"{cid}_chart.json"
            if not chart_path.exists():
                continue
            charts[cid] = json.loads(chart_path.read_text(encoding="utf-8"))
        prices = charts[cid].get("prices") or []
        t = parse_date(row["decision_ts"][:10])
        t_ms = int(t.timestamp() * 1000)
        t90_ms = int((t + timedelta(days=horizon)).timestamp() * 1000)
        px = nearest_point(prices, t_ms)
        px90 = nearest_point(prices, t90_ms)
        if not px or not px90 or px[1] <= 0:
            row["price_usd_t90"] = str(MISSING_NUM)
            row["return_90d"] = str(MISSING_NUM)
            row["positive_90d_return"] = str(MISSING_NUM)
            continue
        price_t, price_t90 = px[1], px90[1]
        row["price_usd_t"] = str(price_t)
        row["price_usd_t90"] = str(price_t90)
        ret = (price_t90 / price_t) - 1.0
        row["return_90d"] = str(ret)
        row["positive_90d_return"] = "1" if price_t90 > price_t else "0"
        updated += 1

    write_snapshots_csv(snap_path, rows)
    print(f"Relabeled {updated}/{len(rows)} rows -> {snap_path}")


if __name__ == "__main__":
    main()
