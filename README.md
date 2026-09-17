# Doge Defenders — long-term crypto strategy experiment

Class project (BUA 3336): labeled **token-entry snapshots** from CoinGecko, scored by a logistic model that outputs an **invest score** (probability of positive 90-day return × 100) and **Invest / Skip**.

## Unit of analysis

One row = one **snapshot** = one `(token, decision date T)`.

**Label:** `positive_90d_return = 1` iff USD price at T+90d > price at T.

**Target volume:** 15 tokens × 34 weekly entry dates = **510** snapshots.

## Setup

```powershell
cd "C:\Users\gabri\OneDrive\Documents\toddarbbott\school project doge defender"
python -m pip install -r requirements.txt
```

Optional: set `COINGECKO_API_KEY` for a demo key. The collector sleeps `rate_limit_seconds` between calls.

## Dashboard (primary UI)

```powershell
streamlit run dashboard/app.py
```

- **Run query** — force-refresh CoinGecko for all 15 tokens, rebuild `snapshots.csv`, retrain the model, write invest decisions (slow: rate-limited API).
- **Score only** — train/score from existing snapshots (fast).
- Uncheck force refresh to rebuild from cached `data/raw/` JSON only, then score.

Model features (no research notes): `price_usd_t`, `volume_24h_usd`, `market_cap_usd`, `market_cap_rank`, `ath_change_percentage`, `price_change_percentage_30d`.

## CLI pipeline

```powershell
# Collect (reuses raw unless --force-refresh)
python -m src.collect_coingecko

# Train + score Invest/Skip
python -m src.invest_model

# Full refresh then score (same as dashboard Run query)
python -m src.run_query

# Rebuild from raw only, then score
python -m src.run_query --no-refresh

# Adequacy 500 / 10 / 60
python -m src.adequacy_report
```

## Layout

| Path | Purpose |
|---|---|
| `dashboard/app.py` | Streamlit project dashboard |
| `config.yaml` | Tokens, entry dates, model paths |
| `docs/M1_Data_Acquisition_Plan.md` | M1 memo |
| `docs/CODEBOOK.md` | Schema + scales |
| `data/raw/` | CoinGecko JSON |
| `data/processed/snapshots.csv` | Labeled snapshots |
| `data/processed/decisions.csv` | All scored rows |
| `data/processed/latest_decisions.csv` | Latest score per token |
| `data/processed/invest_model.joblib` | Trained logistic pipeline |
| `src/invest_model.py` | Train + score |
| `src/run_query.py` | Collect → score orchestrator |

## Provenance notes

- Primary source: CoinGecko REST API only (no HTML scrape).
- Decision model uses market fields only — no AI-generated notes or prices.
- No PII.
- Sampling biases: CoinGecko listing + survivorship (see M1 Part 3).

## Team roles (from charter)

| Member | Role |
|---|---|
| Daniel Burke | Data Steward |
| Gabriel McLaughlin | Modeling Lead |
| Augusta Domingo | AI Auditor |
| Mason Ocampo | Business Translator |
