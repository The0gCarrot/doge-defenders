"""One-shot builder for notebooks/M2_collect_snapshots.ipynb (Colab-ready)."""

from __future__ import annotations

import json
from pathlib import Path


def md(text: str) -> dict:
    lines = text.strip("\n").split("\n")
    return {
        "cell_type": "markdown",
        "metadata": {},
        "source": [ln + "\n" for ln in lines],
    }


def code(text: str) -> dict:
    lines = text.strip("\n").split("\n")
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [ln + "\n" for ln in lines],
    }


cells = [
    md(
        """# Doge Defenders — M2 data collection (Google Colab)

**Course:** BUA 3336 · **Team:** Doge Defenders
**What this does:** clone the project, pull CoinGecko market history for 15 tokens × 34 weekly decision dates, write `snapshots.csv`, print counts, run the 500 / 10 / 60 adequacy check.

Use **Runtime → Run all**. Optional: set a CoinGecko demo key if you hit rate limits."""
    ),
    md("## 1) Clone the project into this Colab runtime"),
    code(
        """from pathlib import Path
import os
import sys
import subprocess

REPO_URL = "https://github.com/The0gCarrot/doge-defenders.git"
REPO_DIR = Path("/content/doge-defenders")

if not REPO_DIR.exists():
    subprocess.check_call(["git", "clone", "--depth", "1", REPO_URL, str(REPO_DIR)])
else:
    subprocess.check_call(["git", "-C", str(REPO_DIR), "pull", "--ff-only"])

os.chdir(REPO_DIR)
if str(REPO_DIR) not in sys.path:
    sys.path.insert(0, str(REPO_DIR))

REPO_ROOT = REPO_DIR
print("REPO_ROOT", REPO_ROOT.resolve())
print("config.yaml exists:", (REPO_ROOT / "config.yaml").exists())"""
    ),
    md("## 2) Install Python packages"),
    code(
        """subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "-r", "requirements.txt"])
print("Dependencies installed.")"""
    ),
    md(
        """## 3) Optional CoinGecko API key

Leave blank to use the free public tier (slower; ~15s between calls).
If you have a demo key, paste it below or store a Colab Secret named `COINGECKO_API_KEY`."""
    ),
    code(
        """COINGECKO_API_KEY = ""

try:
    from google.colab import userdata

    secret = userdata.get("COINGECKO_API_KEY")
    if secret:
        COINGECKO_API_KEY = secret
except Exception:
    pass

if COINGECKO_API_KEY:
    os.environ["COINGECKO_API_KEY"] = COINGECKO_API_KEY
    print("COINGECKO_API_KEY is set.")
else:
    print("No API key — using public rate limits (collection takes a while).")"""
    ),
    md(
        """## 4) Collect snapshots (end to end)

`FORCE_REFRESH = True` hits CoinGecko (needed on Colab because raw JSON is not stored in GitHub).
Expect several minutes (rate limits; 15 tokens × detail + chart calls)."""
    ),
    code(
        """FORCE_REFRESH = True
FROM_RAW_ONLY = False

cmd = [sys.executable, "-m", "src.collect_coingecko"]
if FORCE_REFRESH:
    cmd.append("--force-refresh")
elif FROM_RAW_ONLY:
    cmd.append("--from-raw-only")

print("Running:", " ".join(cmd))
subprocess.check_call(cmd)"""
    ),
    md("## 5) Inspect the dataset"),
    code(
        """import pandas as pd

snap_path = REPO_ROOT / "data" / "processed" / "snapshots.csv"
df = pd.read_csv(snap_path)

print("File:", snap_path)
print("Rows:", len(df))
print("Columns:", len(df.columns))
print("Columns:", list(df.columns))
print("Decision date range:", df["decision_ts"].min(), "→", df["decision_ts"].max())
print("Duplicate (ticker, date) rows:", int(df.duplicated(["token_symbol", "decision_ts"]).sum()))
print()
print("Label balance (1 = up after 90 days):")
print(df["positive_90d_return"].value_counts().to_string())
print()
df.head(5)"""
    ),
    md("## 6) Adequacy check (500 records / 10 usable attributes / 60 minority class)"),
    code(
        """subprocess.check_call([sys.executable, "-m", "src.adequacy_report"])
report_path = REPO_ROOT / "data" / "processed" / "adequacy_report.json"
print(report_path.read_text(encoding="utf-8"))"""
    ),
    md("## 7) Download snapshots.csv for M2 submission"),
    code(
        """from google.colab import files

out = REPO_ROOT / "data" / "processed" / "snapshots.csv"
print("Downloading", out)
files.download(str(out))"""
    ),
    md(
        """## Done

Attach the downloaded `snapshots.csv` to your M2 submission.
Share this Colab with **Anyone with the link (viewer)** and paste the URL into M2 section 1.1."""
    ),
]

nb = {
    "nbformat": 4,
    "nbformat_minor": 5,
    "metadata": {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python"},
        "colab": {"provenance": [], "toc_visible": True},
    },
    "cells": cells,
}

root = Path(__file__).resolve().parents[1]
out = root / "notebooks" / "M2_collect_snapshots.ipynb"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(nb, indent=1), encoding="utf-8")
print(f"Wrote {out} ({out.stat().st_size} bytes)")
