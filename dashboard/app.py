"""
Doge Defenders — Streamlit experiment dashboard.

Paper bankroll $1000 · allocation_pct = invest_score/10 % of remaining cash ·
position_value_usd + paper_return_24h (from return_24h).

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

# Experiment table: price + press + score + paper sizing
VIEW_COLS = [
    "token_symbol",
    "report_date",
    "price_usd",
    "return_24h",
    "press_release",
    "press_opinion",
    "invest_score",
    "model_decision",
    "allocation_pct",
    "position_value_usd",
    "paper_return_24h",
    "momentum_30d_pct",
    "drawdown_from_peak_pct",
]


@st.cache_data(ttl=30)
def load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    # Keep "N/A" as text for historical paper fields
    return pd.read_csv(path, keep_default_na=False, na_values=[""])


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    cfg = load_config()
    paths = cfg["paths"]
    snap_path = ROOT / paths.get("daily_reports_csv", paths["snapshots_csv"])
    decisions_path = ROOT / paths.get("decisions_csv", "data/processed/decisions.csv")
    latest_path = ROOT / paths.get("latest_decisions_csv", "data/processed/latest_decisions.csv")
    metrics_path = ROOT / paths.get("model_metrics", "data/processed/model_metrics.json")
    adequacy_path = ROOT / paths.get("adequacy_report", "data/processed/adequacy_report.json")
    last_query_path = ROOT / paths.get("last_query_json", "data/processed/last_query.json")
    ledger_path = ROOT / paths.get("paper_ledger_csv", "data/processed/paper_ledger.csv")
    bankroll_path = ROOT / paths.get("paper_bankroll_json", "data/processed/paper_bankroll.json")

    start_bal = float(cfg.get("paper_starting_balance", 1000))

    st.title("Doge Defenders")
    st.caption(
        f"Experiment: daily reports + GDELT/Yahoo press → invest score (±5 news) → "
        f"paper bankroll ${start_bal:,.0f} "
        f"(alloc % = score/10 of remaining cash; MTM via return_24h)."
    )

    with st.sidebar:
        st.header("Run query")
        st.write(
            "Rebuild daily reports (prices + news), retrain, apply news overlay, "
            "paper-trade from today’s 15 snapshots."
        )
        threshold = st.slider("Invest score threshold", 30.0, 70.0, 50.0, 1.0)
        force = st.checkbox("Force API refresh (slow)", value=False)
        if st.button("Run query", type="primary", use_container_width=True):
            with st.spinner("Collecting + scoring + paper…"):
                try:
                    if force:
                        result = run_query(force_refresh=True, threshold=threshold)
                    else:
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
                    st.json(result.get("model", result))
                    st.cache_data.clear()
                except Exception as exc:  # noqa: BLE001
                    st.error(f"Query failed: {exc}")

        if st.button("Score + paper only", use_container_width=True):
            with st.spinner("Training + paper trading…"):
                try:
                    result = run_train_and_score(threshold=threshold)
                    st.success("Scored daily reports + paper ledger.")
                    st.json(result)
                    st.cache_data.clear()
                except Exception as exc:  # noqa: BLE001
                    st.error(f"Score failed: {exc}")

        st.divider()
        st.markdown("**Paper rules**")
        st.write(
            f"Start ${start_bal:,.0f}. Invest + score 94 → 9.4% of remaining cash. "
            "Historical rows = N/A. Positions mark with return_24h each run."
        )
        st.markdown("**Tokens**")
        st.write(", ".join(cfg["tokens"]))

    snaps = load_csv(snap_path)
    latest = load_csv(latest_path)
    metrics = load_json(metrics_path)
    adequacy = load_json(adequacy_path)
    last_q = load_json(last_query_path)
    ledger = load_csv(ledger_path)
    bankroll = load_json(bankroll_path)
    if not bankroll:
        bankroll = (last_q.get("model") or {}).get("paper", {}).get("bankroll") or {}

    # Header: experiment bankroll first
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Daily reports", len(snaps) if not snaps.empty else 0)
    if bankroll:
        c2.metric("Cash", f"${float(bankroll.get('cash', 0)):,.2f}")
        c3.metric("Positions $", f"${float(bankroll.get('positions_value', 0)):,.2f}")
        c4.metric("Equity", f"${float(bankroll.get('equity', start_bal)):,.2f}")
    else:
        c2.metric("Cash", f"${start_bal:,.2f}")
        c3.metric("Positions $", "$0.00")
        c4.metric("Equity", f"${start_bal:,.2f}")
    if not ledger.empty and "action" in ledger.columns:
        c5.metric("Paper opens", int((ledger["action"] == "open").sum()))
    else:
        c5.metric("Paper opens", 0)

    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        [
            "Today's paper book",
            "Full daily reports",
            "Paper ledger",
            "Adequacy / model",
            "All scored rows",
        ]
    )

    with tab1:
        st.subheader("Today’s 15 snapshots (experiment view)")
        st.caption(
            "allocation_pct = invest_score/10 (% of remaining cash at open). "
            "position_value_usd = $ in token. paper_return_24h = trade return_24h."
        )
        if snaps.empty:
            st.info("No reports yet.")
        else:
            paper_day = str(bankroll.get("paper_start_date") or "")
            if not paper_day and "report_date" in snaps.columns:
                paper_day = str(snaps["report_date"].astype(str).str[:10].max())
            day_mask = snaps["report_date"].astype(str).str[:10] == paper_day[:10]
            today_df = snaps.loc[day_mask] if paper_day else snaps
            cols = [c for c in VIEW_COLS if c in today_df.columns]
            extra = [
                c
                for c in ("base_score", "news_delta", "press_conflict", "did_invest")
                if c in today_df.columns
            ]
            show = today_df[cols + extra].sort_values(
                ["invest_score", "token_symbol"],
                ascending=[False, True],
            )
            st.dataframe(show, use_container_width=True, hide_index=True, height=520)
            if not show.empty and "position_value_usd" in show.columns:
                pos = pd.to_numeric(show["position_value_usd"], errors="coerce").fillna(0)
                st.write(
                    f"Open notional on {paper_day[:10]}: "
                    f"**${pos.sum():,.2f}** across "
                    f"**{int((pos > 0).sum())}** tokens."
                )

    with tab2:
        if snaps.empty:
            st.warning(f"Missing {snap_path.name} — run the collector.")
        else:
            st.caption("Full history (paper fields = N/A before paper start).")
            st.dataframe(snaps, use_container_width=True, hide_index=True, height=480)

    with tab3:
        st.caption(
            f"Paper portfolio: ${start_bal:,.0f} start. "
            "Score 94 → 9.4% of remaining cash. Ledger = opens/closes only."
        )
        if bankroll:
            b1, b2, b3, b4 = st.columns(4)
            b1.metric("Cash", f"${float(bankroll.get('cash', 0)):,.2f}")
            b2.metric("Positions", f"${float(bankroll.get('positions_value', 0)):,.2f}")
            b3.metric("Equity", f"${float(bankroll.get('equity', 0)):,.2f}")
            b4.metric("Open", bankroll.get("open_positions", 0))
        if ledger.empty:
            st.info("No paper trades yet — run Score + paper.")
        else:
            st.dataframe(ledger, use_container_width=True, hide_index=True, height=420)

    with tab4:
        st.subheader("Adequacy")
        st.json(adequacy or {"hint": "python -m src.adequacy_report"})
        st.subheader("Model metrics")
        st.json(metrics or {})
        st.subheader("Bankroll")
        st.json(bankroll or {})
        st.subheader("Last query")
        st.json(last_q or {})

    with tab5:
        decisions = load_csv(decisions_path)
        if decisions.empty:
            st.info("No scored rows yet.")
        else:
            st.dataframe(decisions, use_container_width=True, hide_index=True, height=420)


if __name__ == "__main__":
    main()
