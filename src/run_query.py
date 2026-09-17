"""
End-to-end refresh: CoinGecko collect (force) → train/score invest model.

Used by the Streamlit dashboard Run Query button.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import ensure_dirs, load_config, write_json
from src.invest_model import run_train_and_score


def run_collect(force_refresh: bool = True) -> dict[str, Any]:
    """Invoke collector in-process so dashboard gets return status."""
    # Import here to avoid circular imports at module load.
    from src.collect_coingecko import main as _unused  # noqa: F401
    import src.collect_coingecko as collect

    cfg = load_config()
    ensure_dirs(cfg)

    # Reuse collect.main logic via constructing argv
    argv = ["--force-refresh"] if force_refresh else []
    old = sys.argv
    try:
        sys.argv = ["collect_coingecko", *argv]
        collect.main()
    finally:
        sys.argv = old

    meta_path = ROOT / cfg["paths"]["raw_dir"] / "_collection_meta.json"
    if meta_path.exists():
        return json.loads(meta_path.read_text(encoding="utf-8"))
    return {"snapshots_written": "unknown"}


def run_query(force_refresh: bool = True, threshold: float = 50.0) -> dict[str, Any]:
    started = datetime.now(timezone.utc).isoformat()
    collect_meta = run_collect(force_refresh=force_refresh)
    model_result = run_train_and_score(threshold=threshold)
    finished = datetime.now(timezone.utc).isoformat()
    payload = {
        "started_utc": started,
        "finished_utc": finished,
        "force_refresh": force_refresh,
        "collect": collect_meta,
        "model": model_result,
    }
    cfg = load_config()
    out = ROOT / cfg["paths"].get("last_query_json", "data/processed/last_query.json")
    write_json(out, payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh CoinGecko data then score invest model")
    parser.add_argument(
        "--no-refresh",
        action="store_true",
        help="Skip API refresh; rebuild from existing raw JSON then score",
    )
    parser.add_argument("--threshold", type=float, default=50.0)
    args = parser.parse_args()

    if args.no_refresh:
        # Rebuild snapshots from raw without API, then score
        old = sys.argv
        try:
            sys.argv = ["collect_coingecko", "--from-raw-only"]
            import src.collect_coingecko as collect

            collect.main()
        finally:
            sys.argv = old
        result = {
            "started_utc": datetime.now(timezone.utc).isoformat(),
            "force_refresh": False,
            "model": run_train_and_score(threshold=args.threshold),
        }
        write_json(ROOT / "data/processed/last_query.json", result)
        print(json.dumps(result, indent=2))
        return

    result = run_query(force_refresh=True, threshold=args.threshold)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
