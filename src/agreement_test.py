"""
Dual-coder agreement test helper (M1 Part 6.2).

Two members independently fill data/manual/agreement_coder_a.csv and
agreement_coder_b.csv for the same 10 snapshot keys. This script compares
news_score and research_notes and prints agreement stats.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import ensure_dirs, load_config

FIELDS = ["coingecko_id", "decision_date", "research_notes", "news_score", "coder"]


def load(path: Path) -> dict[tuple[str, str], dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return {
            (r["coingecko_id"].strip(), r["decision_date"].strip()): r
            for r in csv.DictReader(f)
        }


def seed_from_notes(notes_path: Path, out_a: Path, out_b: Path) -> None:
    if not notes_path.exists():
        raise SystemExit(f"Missing {notes_path}; run append_research_notes.py --init-template")
    with notes_path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))[:10]
    for path, coder in ((out_a, "coder_a"), (out_b, "coder_b")):
        if path.exists():
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS)
            w.writeheader()
            for r in rows:
                w.writerow(
                    {
                        "coingecko_id": r["coingecko_id"],
                        "decision_date": r["decision_date"],
                        "research_notes": "",
                        "news_score": "",
                        "coder": coder,
                    }
                )
        print(f"Seeded {path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare dual-coder agreement on 10 snapshots")
    parser.add_argument("--seed", action="store_true", help="Create empty coder A/B templates")
    args = parser.parse_args()

    cfg = load_config()
    ensure_dirs(cfg)
    manual = ROOT / "data" / "manual"
    notes = ROOT / cfg["paths"]["research_notes_csv"]
    path_a = manual / "agreement_coder_a.csv"
    path_b = manual / "agreement_coder_b.csv"

    if args.seed:
        seed_from_notes(notes, path_a, path_b)
        return

    if not path_a.exists() or not path_b.exists():
        raise SystemExit("Missing coder files. Run with --seed first, then fill both CSVs.")

    a = load(path_a)
    b = load(path_b)
    keys = sorted(set(a) & set(b))
    if len(keys) < 10:
        print(f"WARNING: only {len(keys)} shared keys (want 10)")

    score_match = 0
    note_exact = 0
    compared = 0
    mismatches: list[str] = []
    for key in keys:
        ra, rb = a[key], b[key]
        sa, sb = (ra.get("news_score") or "").strip(), (rb.get("news_score") or "").strip()
        na, nb = (ra.get("research_notes") or "").strip(), (rb.get("research_notes") or "").strip()
        if not sa or not sb:
            continue
        compared += 1
        if sa == sb:
            score_match += 1
        else:
            mismatches.append(f"{key}: scores {sa} vs {sb}")
        if na == nb:
            note_exact += 1

    print(f"Shared keys: {len(keys)}")
    print(f"news_score compared: {compared}; matches: {score_match}")
    if compared:
        print(f"news_score agreement: {score_match / compared:.0%}")
    print(f"research_notes exact matches: {note_exact}/{compared or 0}")
    if mismatches:
        print("Mismatches:")
        for m in mismatches:
            print(f"  {m}")
    else:
        print("No news_score mismatches among compared rows.")
    print(
        "Protocol: lock ISO 8601 UTC on decision_ts; news_score rubric 1=strongly negative … 5=strongly positive."
    )


if __name__ == "__main__":
    main()
