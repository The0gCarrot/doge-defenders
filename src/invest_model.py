"""
Train and score invest / skip decisions from market features only.

No research_notes or news_score — model uses CoinGecko snapshot fields only.
Outputs invest_score (0–100) and decision (Invest | Skip).
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import MISSING_NUM, ensure_dirs, load_config, write_json

FEATURE_COLS = [
    "price_usd_t",
    "volume_24h_usd",
    "market_cap_usd",
    "market_cap_rank",
    "ath_change_percentage",
    "price_change_percentage_30d",
]

DECISION_FIELDS = [
    "snapshot_id",
    "coingecko_id",
    "token_symbol",
    "decision_ts",
    "price_usd_t",
    "volume_24h_usd",
    "market_cap_usd",
    "market_cap_rank",
    "ath_change_percentage",
    "price_change_percentage_30d",
    "positive_90d_return",
    "invest_score",
    "decision",
]


def _to_float(val: Any, default: float = float(MISSING_NUM)) -> float:
    try:
        if val is None or val == "" or val == "NULL":
            return default
        return float(val)
    except (TypeError, ValueError):
        return default


def load_snapshots(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def feature_matrix(rows: list[dict[str, str]]) -> tuple[np.ndarray, list[int]]:
    """Build X; return indices of rows with usable features + labeled target."""
    X_list: list[list[float]] = []
    keep: list[int] = []
    for i, r in enumerate(rows):
        feats = [_to_float(r.get(c)) for c in FEATURE_COLS]
        if any(f == float(MISSING_NUM) for f in feats):
            continue
        # log-scale heavy-tailed market size / volume
        feats[0] = np.log1p(max(feats[0], 0.0))
        feats[1] = np.log1p(max(feats[1], 0.0))
        feats[2] = np.log1p(max(feats[2], 0.0))
        X_list.append(feats)
        keep.append(i)
    return np.asarray(X_list, dtype=float), keep


def labeled_xy(rows: list[dict[str, str]]) -> tuple[np.ndarray, np.ndarray, list[int]]:
    X_all, keep = feature_matrix(rows)
    X_rows: list[list[float]] = []
    y_list: list[int] = []
    keep_labeled: list[int] = []
    for local_i, row_i in enumerate(keep):
        label = _to_float(rows[row_i].get("positive_90d_return"))
        if label not in (0.0, 1.0):
            continue
        X_rows.append(X_all[local_i].tolist())
        y_list.append(int(label))
        keep_labeled.append(row_i)
    return np.asarray(X_rows, dtype=float), np.asarray(y_list, dtype=int), keep_labeled


def build_pipeline() -> Pipeline:
    return Pipeline(
        [
            ("scaler", StandardScaler()),
            (
                "clf",
                LogisticRegression(
                    max_iter=1000,
                    class_weight="balanced",
                    random_state=42,
                ),
            ),
        ]
    )


def train_model(rows: list[dict[str, str]]) -> tuple[Pipeline, dict[str, Any]]:
    X, y, _ = labeled_xy(rows)
    if len(y) < 40 or len(set(y)) < 2:
        raise RuntimeError(f"Need labeled rows with both classes; got n={len(y)} classes={set(y)}")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.25, random_state=42, stratify=y
    )
    pipe = build_pipeline()
    pipe.fit(X_train, y_train)
    proba = pipe.predict_proba(X_test)[:, 1]
    pred = (proba >= 0.5).astype(int)
    metrics = {
        "n_train": int(len(y_train)),
        "n_test": int(len(y_test)),
        "pos_rate_train": float(y_train.mean()),
        "accuracy_test": float(accuracy_score(y_test, pred)),
        "roc_auc_test": float(roc_auc_score(y_test, proba)) if len(set(y_test)) > 1 else None,
        "features": FEATURE_COLS,
        "threshold_default": 50.0,
    }
    return pipe, metrics


def score_rows(
    pipe: Pipeline,
    rows: list[dict[str, str]],
    threshold: float = 50.0,
) -> list[dict[str, Any]]:
    X, keep = feature_matrix(rows)
    if len(keep) == 0:
        return []
    proba = pipe.predict_proba(X)[:, 1]
    out: list[dict[str, Any]] = []
    for local_i, row_i in enumerate(keep):
        r = rows[row_i]
        score = float(proba[local_i] * 100.0)
        out.append(
            {
                "snapshot_id": r.get("snapshot_id", ""),
                "coingecko_id": r.get("coingecko_id", ""),
                "token_symbol": r.get("token_symbol", ""),
                "decision_ts": r.get("decision_ts", ""),
                "price_usd_t": r.get("price_usd_t", ""),
                "volume_24h_usd": r.get("volume_24h_usd", ""),
                "market_cap_usd": r.get("market_cap_usd", ""),
                "market_cap_rank": r.get("market_cap_rank", ""),
                "ath_change_percentage": r.get("ath_change_percentage", ""),
                "price_change_percentage_30d": r.get("price_change_percentage_30d", ""),
                "positive_90d_return": r.get("positive_90d_return", ""),
                "invest_score": round(score, 2),
                "decision": "Invest" if score >= threshold else "Skip",
            }
        )
    return out


def latest_per_token(decisions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    best: dict[str, dict[str, Any]] = {}
    for d in decisions:
        tid = d["coingecko_id"]
        prev = best.get(tid)
        if prev is None or d["decision_ts"] > prev["decision_ts"]:
            best[tid] = d
    return sorted(best.values(), key=lambda x: (-x["invest_score"], x["token_symbol"]))


def write_decisions_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=DECISION_FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def run_train_and_score(
    cfg: dict[str, Any] | None = None,
    threshold: float = 50.0,
) -> dict[str, Any]:
    cfg = cfg or load_config()
    ensure_dirs(cfg)
    snap_path = ROOT / cfg["paths"]["snapshots_csv"]
    model_path = ROOT / cfg["paths"].get("model_path", "data/processed/invest_model.joblib")
    metrics_path = ROOT / cfg["paths"].get("model_metrics", "data/processed/model_metrics.json")
    decisions_path = ROOT / cfg["paths"].get("decisions_csv", "data/processed/decisions.csv")
    latest_path = ROOT / cfg["paths"].get("latest_decisions_csv", "data/processed/latest_decisions.csv")

    rows = load_snapshots(snap_path)
    pipe, metrics = train_model(rows)
    metrics["threshold"] = threshold
    joblib.dump(pipe, model_path)
    write_json(metrics_path, metrics)

    decisions = score_rows(pipe, rows, threshold=threshold)
    write_decisions_csv(decisions_path, decisions)
    latest = latest_per_token(decisions)
    write_decisions_csv(latest_path, latest)

    invest_n = sum(1 for d in latest if d["decision"] == "Invest")
    return {
        "snapshots": len(rows),
        "scored": len(decisions),
        "latest_tokens": len(latest),
        "latest_invest": invest_n,
        "metrics": metrics,
        "model_path": str(model_path),
        "decisions_csv": str(decisions_path),
        "latest_decisions_csv": str(latest_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Train invest scorer and write decisions")
    parser.add_argument("--threshold", type=float, default=50.0)
    args = parser.parse_args()
    result = run_train_and_score(threshold=args.threshold)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
