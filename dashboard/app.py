"""
Doge Defenders — Streamlit project dashboard.

Run:  streamlit run dashboard/app.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import load_config
from src.invest_model import run_train_and_score
from src.run_query import run_query

st.set_page_config(
    page_title="Doge Defenders",
    page_icon=None,
    layout="wide",
)


@st.cache_data(ttl=30)
def load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    cfg = load_config()
    paths = cfg["paths"]
    snap_path = ROOT / paths["snapshots_csv"]
    decisions_path = ROOT / paths.get("decisions_csv", "data/processed/decisions.csv")
    latest_path = ROOT / paths.get("latest_decisions_csv", "data/processed/latest_decisions.csv")
    metrics_path = ROOT / paths.get("model_metrics", "data/processed/model_metrics.json")
    adequacy_path = ROOT / paths.get("adequacy_report", "data/processed/adequacy_report.json")
    last_query_path = ROOT / paths.get("last_query_json", "data/processed/last_query.json")

    st.title("Doge Defenders")
    st.caption(
        "Long-term crypto experiment — CoinGecko snapshots → logistic invest score (no AI notes)."
    )

    with st.sidebar:
        st.header("Run query")
        st.write(
            "Refresh CoinGecko for the 15 tokens, rebuild snapshots, "
            "retrain the model, and re-score Invest / Skip."
        )
        threshold = st.slider("Invest score threshold", 30.0, 70.0, 50.0, 1.0)
        force = st.checkbox("Force API refresh (slow ~5–10 min)", value=True)
        if st.button("Run query", type="primary", use_container_width=True):
            with st.spinner("Collecting + scoring…"):
                try:
                    if force:
                        result = run_query(force_refresh=True, threshold=threshold)
                    else:
                        # Rebuild from raw only, then score
                        old = sys.argv
                        try:
                            sys.argv = ["collect_coingecko", "--from-raw-only"]
                            import src.collect_coingecko as collect

                            collect.main()
                        finally:
                            sys.argv = old
                        result = {
                            "force_refresh": False,
                            "model": run_train_and_score(threshold=threshold),
                        }
                        (ROOT / "data/processed/last_query.json").write_text(
                            json.dumps(result, indent=2), encoding="utf-8"
                        )
                    st.success("Query finished.")
                    st.json(
                        {
                            "snapshots": result.get("model", {}).get("snapshots"),
                            "latest_invest": result.get("model", {}).get("latest_invest"),
                            "metrics": result.get("model", {}).get("metrics"),
                        }
                    )
                    st.cache_data.clear()
                except Exception as exc:  # noqa: BLE001
                    st.error(f"Query failed: {exc}")

        if st.button("Score only (no collect)", use_container_width=True):
            with st.spinner("Training + scoring…"):
                try:
                    result = run_train_and_score(threshold=threshold)
                    st.success("Scored existing snapshots.")
                    st.json(result.get("metrics"))
                    st.cache_data.clear()
                except Exception as exc:  # noqa: BLE001
                    st.error(f"Score failed: {exc}")

        st.divider()
        st.markdown("**Tokens**")
        st.write(", ".join(cfg["tokens"]))

    # --- Overview metrics ---
    snaps = load_csv(snap_path)
    latest = load_csv(latest_path)
    metrics = load_json(metrics_path)
    adequacy = load_json(adequacy_path)
    last_q = load_json(last_query_path)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Snapshots", len(snaps) if not snaps.empty else 0)
    if not snaps.empty and "positive_90d_return" in snaps.columns:
        pos = int((snaps["positive_90d_return"] == 1).sum())
        c2.metric("Positive 90d labels", pos)
    else:
        c2.metric("Positive 90d labels", "—")
    if not latest.empty:
        invest_n = int((latest["decision"] == "Invest").sum())
        c3.metric("Latest Invest calls", invest_n)
    else:
        c3.metric("Latest Invest calls", "—")
    auc = metrics.get("roc_auc_test")
    c4.metric("Model ROC-AUC (test)", f"{auc:.3f}" if isinstance(auc, float) else "—")

    tab1, tab2, tab3, tab4 = st.tabs(
        ["Latest decisions", "All scored snapshots", "Adequacy / model", "Raw snapshots"]
    )

    with tab1:
        st.subheader("Latest decision per token")
        st.write(
            "Invest score = model probability of positive 90-day return × 100. "
            f"Decision uses threshold **{metrics.get('threshold', 50)}**."
        )
        if latest.empty:
            st.info("No decisions yet. Click **Score only** or **Run query** in the sidebar.")
        else:
            show = latest.sort_values("invest_score", ascending=False)
            st.dataframe(
                show[
                    [
                        "token_symbol",
                        "coingecko_id",
                        "decision_ts",
                        "invest_score",
                        "decision",
                        "price_usd_t",
                        "price_change_percentage_30d",
                        "market_cap_rank",
                        "positive_90d_return",
                    ]
                ],
                use_container_width=True,
                hide_index=True,
            )
            invest = show[show["decision"] == "Invest"]
            skip = show[show["decision"] == "Skip"]
            col_a, col_b = st.columns(2)
            with col_a:
                st.markdown("**Invest**")
                st.write(", ".join(invest["token_symbol"].tolist()) or "—")
            with col_b:
                st.markdown("**Skip**")
                st.write(", ".join(skip["token_symbol"].tolist()) or "—")

    with tab2:
        decisions = load_csv(decisions_path)
        if decisions.empty:
            st.info("No scored rows yet.")
        else:
            st.dataframe(decisions, use_container_width=True, hide_index=True, height=420)

    with tab3:
        st.subheader("Adequacy (course bar)")
        if adequacy:
            st.json(adequacy)
        else:
            st.write("Run `python -m src.adequacy_report` to generate.")
        st.subheader("Model metrics")
        if metrics:
            st.json(metrics)
        else:
            st.write("Train via sidebar first.")
        st.subheader("Last query")
        if last_q:
            st.json(last_q)
        else:
            st.write("No query run yet.")

    with tab4:
        if snaps.empty:
            st.warning("Missing snapshots.csv — run the collector.")
        else:
            # Hide empty note columns from the main view; they stay NULL in the file.
            cols = [c for c in snaps.columns if c not in ("research_notes", "news_score")]
            st.dataframe(snaps[cols], use_container_width=True, hide_index=True, height=420)


if __name__ == "__main__":
    main()
