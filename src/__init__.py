"""Shared paths, constants, and config loading."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
MISSING_NUM = -999
MISSING_STR = "NULL"


def load_config(path: Path | None = None) -> dict[str, Any]:
    cfg_path = path or (ROOT / "config.yaml")
    with cfg_path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def ensure_dirs(cfg: dict[str, Any]) -> None:
    paths = cfg["paths"]
    for key in ("raw_dir", "processed_dir"):
        (ROOT / paths[key]).mkdir(parents=True, exist_ok=True)
    (ROOT / "data" / "manual").mkdir(parents=True, exist_ok=True)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
