"""
Doge Defenders — Streamlit experiment dashboard.

Live CoinGecko simple/price for today's paper day on every load / score / query.
Paper bankroll $1000 · allocation_pct = invest_score/10 % of remaining cash.

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
from src.live_prices import refresh_live_today
from src.paper_trade import run_paper_on_reports
from src.run_query import run_query

st.set_page_config(
    page_title="Doge Defenders",
    page_icon=None,
    layout="wide",
)

# One column per fact that can change the call.
# Dropped as the same fact twice: coingecko_id and report_id (the symbol),
# news_headlines_10d (a copy of press_release), hist_prices_30d (already
# in the 30-day change and the distance from the high).
DECISION_COLS = [
    "token_symbol",
    "report_date",
    "price_usd",
    "return_24h",
    "volume_24h_usd",
    "market_cap_usd",
    "market_cap_rank",
    "momentum_30d_pct",
    "drawdown_from_peak_pct",
    "press_gdelt",
    "press_yahoo",
    "press_release",
    "press_opinion",
    "press_conflict",
    "news_delta",
    "base_score",
    "invest_score",
    "model_decision",
    "position_value_usd",
]


@st.cache_data(ttl=15)
def load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, keep_default_na=False, na_values=[""])


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def sync_live_and_paper() -> dict:
    """Pull live USD for today, re-run paper sizing on updated prices."""
    live = refresh_live_today()
    paper = run_paper_on_reports() if live.get("ok") else {}
    return {"live": live, "paper": paper}


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
    live_path = ROOT / paths["raw_dir"] / "_live_prices.json"

    start_bal = float(cfg.get("paper_starting_balance", 1000))

    st.title("Doge Defenders")
    st.caption(
        f"Live CoinGecko prices for today’s paper book · "
        f"GDELT/Yahoo press · invest score (±5 news) · "
        f"${start_bal:,.0f} bankroll (alloc % = score/10 of remaining cash)."
    )

    with st.sidebar:
        st.header("Run query")
        st.write(
            "Live prices are always refreshed. "
            "Check the box to also re-download CoinGecko charts (slow)."
        )
        threshold = st.slider("Invest score threshold", 30.0, 70.0, 50.0, 1.0)
        force = st.checkbox("Also refresh historical charts (slow)", value=True)
        if st.button("Run query", type="primary", use_container_width=True):
            with st.spinner("Live prices + collect + score + paper…"):
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
                            "model": run_train_and_score(threshold=threshold, refresh_live=True),
                        }
                        last_query_path.write_text(
                            json.dumps(result, indent=2), encoding="utf-8"
                        )
                    st.success("Query finished (live prices applied).")
                    st.json(result.get("model", result))
                    st.cache_data.clear()
                except Exception as exc:  # noqa: BLE001
                    st.error(f"Query failed: {exc}")

        if st.button("Refresh live prices + paper", use_container_width=True):
            with st.spinner("CoinGecko simple/price + paper…"):
                try:
                    out = sync_live_and_paper()
                    st.success(
                        f"Live prices updated ({out['live'].get('updated_rows', 0)} rows)."
                    )
                    st.json(out)
                    st.cache_data.clear()
                except Exception as exc:  # noqa: BLE001
                    st.error(f"Live refresh failed: {exc}")

        if st.button("Score + paper (live prices)", use_container_width=True):
            with st.spinner("Live prices + train + paper…"):
                try:
                    result = run_train_and_score(threshold=threshold, refresh_live=True)
                    st.success("Scored with live prices.")
                    st.json(result)
                    st.cache_data.clear()
                except Exception as exc:  # noqa: BLE001
                    st.error(f"Score failed: {exc}")

        st.divider()
        st.markdown("**Live source**")
        st.write("CoinGecko `simple/price` (batch) for today’s USD + 24h change.")
        st.markdown("**Paper rules**")
        st.write(
            f"Start ${start_bal:,.0f}. Score 94 → 9.4% of remaining cash. "
            "Historical rows = N/A."
        )
        st.markdown("**Tokens**")
        st.write(", ".join(cfg["tokens"]))

    # Auto live sync once per session page load (prices + paper mark)
    if "live_synced" not in st.session_state:
        try:
            st.session_state["live_sync_result"] = sync_live_and_paper()
            st.session_state["live_synced"] = True
            st.cache_data.clear()
        except Exception as exc:  # noqa: BLE001
            st.session_state["live_sync_result"] = {"error": str(exc)}
            st.session_state["live_synced"] = True

    snaps = load_csv(snap_path)
    latest = load_csv(latest_path)
    metrics = load_json(metrics_path)
    adequacy = load_json(adequacy_path)
    last_q = load_json(last_query_path)
    ledger = load_csv(ledger_path)
    bankroll = load_json(bankroll_path)
    live_meta = load_json(live_path)
    if not bankroll:
        bankroll = (last_q.get("model") or {}).get("paper", {}).get("bankroll") or {}

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

    if live_meta.get("asof_utc"):
        st.caption(f"Live prices as of **{live_meta['asof_utc']}** (CoinGecko simple/price).")

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
        st.subheader("Today’s 15 snapshots (live USD)")
        st.caption(
            "Price score, then GDELT and Yahoo. "
            "Bullish adds 5 points, bearish subtracts 5, and a disagreement adds 0. "
            "Invest when that total is 50 or higher."
        )
        if snaps.empty:
            st.info("No reports yet.")
        else:
            latest_day = str(snaps["report_date"].astype(str).str[:10].max())
            paper_day = str(live_meta.get("day") or latest_day)
            day_mask = snaps["report_date"].astype(str).str[:10] == paper_day[:10]
            today_df = snaps.loc[day_mask] if paper_day else snaps
            cols = [c for c in DECISION_COLS if c in today_df.columns]
            show = today_df[cols].sort_values(
                ["invest_score", "token_symbol"],
                ascending=[False, True],
            )
            st.caption(
                f"{len(show)} rows for {paper_day[:10]}. "
                "The symbol stands in for the CoinGecko id. "
                "GDELT and Yahoo are the two sources; opinion and news points are the press score; "
                "invest score is the price score plus those points; Invest or Skip is that total against 50."
            )
            st.dataframe(show, width="stretch", hide_index=True, height=520)
            if not show.empty and "position_value_usd" in show.columns:
                pos = pd.to_numeric(show["position_value_usd"], errors="coerce").fillna(0)
                st.write(
                    f"Open notional on {paper_day[:10]}: "
                    f"**${pos.sum():,.2f}** across **{int((pos > 0).sum())}** tokens."
                )

    with tab2:
        if snaps.empty:
            st.warning(f"Missing {snap_path.name} — run the collector.")
        else:
            st.caption(
                "Same decision columns on every day. "
                "CoinGecko id, the duplicate headline copy, and the raw 30-day price list stay in the file and are not repeated here."
            )
            cols = [c for c in DECISION_COLS if c in snaps.columns]
            st.dataframe(snaps[cols], width="stretch", hide_index=True, height=480)

    with tab3:
        st.caption(
            f"Paper portfolio: ${start_bal:,.0f} start. "
            "Entry prices from live CoinGecko at open."
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
        st.subheader("Live prices")
        st.json(live_meta or {})
        st.subheader("Adequacy")
        st.json(adequacy or {})
        st.subheader("Model metrics")
        st.json(metrics or {})
        st.subheader("Bankroll")
        st.json(bankroll or {})

    with tab5:
        decisions = load_csv(decisions_path)
        if decisions.empty:
            st.info("No scored rows yet.")
        else:
            st.dataframe(decisions, use_container_width=True, hide_index=True, height=420)


if __name__ == "__main__":
    main()
