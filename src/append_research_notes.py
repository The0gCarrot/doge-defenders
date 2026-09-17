"""
Merge human-only research_notes and news_score into snapshots.csv.

Join key: (coingecko_id, decision_date) where decision_date is YYYY-MM-DD
from decision_ts.

Never invent notes with an LLM — paste human observations only.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import MISSING_NUM, MISSING_STR, ensure_dirs, load_config
from src.collect_coingecko import SNAPSHOT_FIELDS, write_snapshots_csv


NOTES_FIELDS = [
    "coingecko_id",
    "decision_date",
    "research_notes",
    "news_score",
    "coder",
]


def decision_date(decision_ts: str) -> str:
    return decision_ts[:10]


def load_notes(path: Path) -> dict[tuple[str, str], dict[str, str]]:
    if not path.exists():
        return {}
    out: dict[tuple[str, str], dict[str, str]] = {}
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            key = (row["coingecko_id"].strip(), row["decision_date"].strip())
            out[key] = row
    return out


def ensure_notes_template(path: Path, snapshots: list[dict[str, str]]) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    # Seed first 10 snapshots for the agreement test / starter batch.
    sample = snapshots[:10]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=NOTES_FIELDS)
        writer.writeheader()
        for s in sample:
            writer.writerow(
                {
                    "coingecko_id": s["coingecko_id"],
                    "decision_date": decision_date(s["decision_ts"]),
                    "research_notes": "",
                    "news_score": "",
                    "coder": "",
                }
            )
    print(f"Created notes template with {len(sample)} starter rows -> {path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge human research notes into snapshots")
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument(
        "--init-template",
        action="store_true",
        help="Create data/manual/research_notes.csv from first 10 snapshots if missing",
    )
    args = parser.parse_args()

    cfg = load_config(args.config)
    ensure_dirs(cfg)

    snap_path = ROOT / cfg["paths"]["snapshots_csv"]
    notes_path = ROOT / cfg["paths"]["research_notes_csv"]

    if not snap_path.exists():
        raise SystemExit(f"Missing snapshots: {snap_path}. Run collect_coingecko.py first.")

    with snap_path.open(newline="", encoding="utf-8") as f:
        snapshots = list(csv.DictReader(f))

    if args.init_template or not notes_path.exists():
        ensure_notes_template(notes_path, snapshots)

    notes = load_notes(notes_path)
    merged = 0
    for row in snapshots:
        key = (row["coingecko_id"], decision_date(row["decision_ts"]))
        note = notes.get(key)
        if not note:
            continue
        text = (note.get("research_notes") or "").strip()
        score_raw = (note.get("news_score") or "").strip()
        if text:
            row["research_notes"] = text
            merged += 1
        else:
            row["research_notes"] = row.get("research_notes") or MISSING_STR
        if score_raw:
            try:
                score = int(score_raw)
                if score < 1 or score > 5:
                    raise ValueError("news_score must be 1–5")
                row["news_score"] = str(score)
            except ValueError as exc:
                raise SystemExit(f"Bad news_score for {key}: {exc}") from exc
        # leave existing -999 if blank

    # Normalize empties
    for row in snapshots:
        if not row.get("research_notes"):
            row["research_notes"] = MISSING_STR
        if row.get("news_score") in ("", None):
            row["news_score"] = str(MISSING_NUM)

    write_snapshots_csv(snap_path, snapshots)
    print(f"Merged notes into {merged} snapshot rows -> {snap_path}")
    print(f"Notes file: {notes_path} ({len(notes)} keyed rows)")


if __name__ == "__main__":
    main()
