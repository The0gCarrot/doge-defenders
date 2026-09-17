# BUA 3336 — BIG DATA & DATA MINING FOR BUSINESS
## M1 — Data Acquisition Plan and Provenance Memo

**Team name:** Doge Defenders  
**Members and roles:** Data Steward: Daniel Burke · Modeling Lead: Gabriel McLaughlin · AI Auditor: Augusta Domingo · Business Translator: Mason Ocampo  
**Author of this memo:** Gabriel McLaughlin  
**Date:** 09/17/2026

---

## Part 1 — Business question

### 1.1 The question
Can an AI agent, using only free public APIs and features available at purchase time, select cryptocurrency tokens that achieve a positive return over a subsequent 90-day holding window more often than chance?

### 1.2 Unit of analysis
One row in our dataset is one **snapshot**.

### 1.3 The decision this informs, and who makes it
A cryptocurrency portfolio manager uses the model to decide whether to allocate long-term capital to a specific digital asset at a given decision date, or to bypass it to avoid sustained drawdowns.

### 1.4 Target variable
`positive_90d_return`: whether the token’s USD price at decision time T+90 days is strictly greater than its USD price at T, judged only from CoinGecko market data available for dates ≤ T when features are recorded. Fees and slippage are treated as zero in v1.

---

## Part 2 — Data acquisition plan

### 2.1 Primary source and collection route
CoinGecko Public API (`api.coingecko.com/api/v3`): `/coins/markets`, `/coins/{id}`, and `/coins/{id}/market_chart?vs_currency=usd&days=365` for historical daily closes (the `/market_chart/range` and `days=max` routes require a paid plan; we stay on the free chart endpoint). Collection is automated via a rate-limited Python script; no page scraping of CoinGecko HTML.

### 2.2 Secondary sources, and the key you will join on
Human-logged research notes and an ordinal news score, joined on (`coingecko_id`, `decision_date`). No automated news scrape in v1.

### 2.3 Fields you need, and where each comes from
- `token_symbol`, `price_usd_t`, `volume_24h_usd`, `market_cap_usd`, `market_cap_rank`, `category`, `primary_exchange`, `hist_prices_30d`, `ath_change_percentage`, `price_change_percentage_30d` — CoinGecko API  
- `decision_ts` — collection / entry calendar (ISO 8601 UTC)  
- `research_notes`, `news_score` — manual logging by team members  
- `price_usd_t90`, `return_90d`, `positive_90d_return` — derived from CoinGecko historical prices at T and T+90d  

### 2.4 Expected volume, and how we arrived at that estimate
Target = 500 snapshots. Arithmetic: **15 tokens × 34 weekly entry dates = 510 snapshots**. Entry dates (2025-10-20 through 2026-06-08) sit inside CoinGecko’s free-tier 365-day chart window and are at least 90 days before collection day so labels exist. Each (token, entry date) is one row (one snapshot).

### 2.5 Collection timeline
- **2026-09-17 — Daniel Burke:** freeze token universe in `config.yaml`; run CoinGecko bulk pull into `data/raw/`.  
- **2026-09-17–09-19 — Gabriel McLaughlin:** validate entry calendar, compute T / T+90d labels, track adequacy (500 / 10 / 60).  
- **2026-09-18 — Augusta Domingo + Mason Ocampo:** dual-code 10 snapshots for agreement test; Mason fills `research_notes` / `news_score` batches.  
- **By end of Week 3:** all raw and processed files local; `data/processed/snapshots.csv` complete.

---

## Part 3 — Provenance memo

**Population:** Non-stable cryptocurrency tokens with public USD markets that a retail portfolio manager might consider for a 90-day hold.  
**Sampling frame:** Tokens indexed by CoinGecko’s public market endpoints during our pulls.  
**Sample:** 510 token-entry snapshots (15 tokens × 34 entry dates), plus human notes on a coded subset.

### 3.1 What population does your sample actually represent?
The sample represents established, publicly listed tokens that CoinGecko indexes with usable history. It excludes private sales, stealth launches, and micro-caps that never meet indexer thresholds. Primary bias: **survivorship / listing bias** — tokens that rug, delist, or never list leave little or no complete history.

### 3.2 The four questions
1. **Who could never appear?** Tokens on private networks only, unlisted contracts, or assets whose liquidity vanished before indexing.  
2. **Who chose to be there?** Projects and venues that list on public exchanges and tracking platforms CoinGecko covers.  
3. **Who dropped out?** Rug-pulled, delisted, or dead-pool assets scrubbed before full history was recorded.  
4. **When was it collected?** Features and labels are built from historical CoinGecko series; collection scripting runs September 2026. Market regime in the chosen entry window may not generalize to other cycles.

---

## Part 4 — Ethics and compliance

### 4.1 Terms of service and rate limits
We use CoinGecko’s official public REST API only. We respect documented rate limits (public/demo tier: ~15 seconds between calls in our collector; we use `/market_chart?days=365` because `/market_chart/range` and `days=max` exceed the free plan). We do not scrape CoinGecko HTML or bypass anti-bot controls. Human research notes are manual observation of publicly visible headlines, not automated harvesting of blocked sites.

### 4.2 Confirmations
- No personally identifying data is being collected.  
- We record only public market behaviour — what any person with API access could observe.  
- No AI-generated records, in any form (prices, notes, or labels).

### 4.3 Survey instrument
Not applicable.

---

## Part 5 — AI Collaboration Log

Our team narrowed from three questions to one. The business question we will explore: can an AI agent create a profitable long-term cryptocurrency investment strategy using free public APIs and basic agentic coding?

The alternatives were shinier and possibly a more exciting experiment. However, when looking deeper into what it would require to run our experiment we ran into heavy overhead costs for institution-level compute power.

At first ChatGPT voted to experiment with the short-term arbitrage strategy (capturing fees between decentralized and centralized finance). When we audited this response with Claude, the Anthropic model showed that this experiment could be done but not done well without spending tens of thousands up front for hardware. The second question did not fully meet relevancy, leading us and our AI collaboration to select our final question.

---

## Part 6 — Codebook

| Variable | Definition | Scale | Permitted values | How it is recorded |
|---|---|---|---|---|
| token_symbol | Ticker symbol for the asset | Nominal | Alphanumeric ticker | CoinGecko API `symbol` |
| decision_ts | UTC time of the simulated purchase decision | Interval | ISO 8601 UTC | Entry calendar / script |
| price_usd_t | USD spot (or daily close) at T | Ratio | ≥ 0; missing = -999 | CoinGecko historical / markets |
| volume_24h_usd | 24h traded volume in USD at or nearest T | Ratio | ≥ 0; missing = -999 | CoinGecko API |
| market_cap_usd | Reported market cap in USD at or nearest T | Ratio | ≥ 0; missing = -999 | CoinGecko API |
| market_cap_rank | Rank by market cap at or nearest T | Ordinal | Positive integers; missing = -999 | CoinGecko API |
| category | CoinGecko category / sector label for the token | Nominal | Category string; missing = NULL | CoinGecko `/coins/{id}` (above unit) |
| primary_exchange | Primary venue hosting a liquid market for the token | Nominal | Exchange id/name; missing = NULL | CoinGecko tickers metadata (above unit) |
| hist_prices_30d | List of daily USD closes for the 30 days strictly before T | Ratio, multi-valued | Zero or more numbers | CoinGecko market chart |
| ath_change_percentage | % distance from all-time high at or nearest T | Ratio | Real number; missing = -999 | CoinGecko API |
| price_change_percentage_30d | % price change over prior 30 days at T | Ratio | Real number; missing = -999 | CoinGecko API |
| research_notes | Short human notes on public project/news context at T | Free-text (nominal) | Unrestricted text; missing = NULL | Manual team logging only |
| news_score | Human ordinal judgment of news tone at T | Ordinal | 1–5; missing = -999 | Manual team coding |
| positive_90d_return | 1 if price(T+90d) > price(T), else 0 | Nominal (binary) | 0, 1; missing = -999 | Derived from CoinGecko history |

### 6.1 Missing-value convention
Numeric missing = `-999`. String missing = `NULL`. Blank never means zero.

### 6.2 The agreement test
Two members independently coded the same 10 snapshots (notes + news_score + timestamp format). Timestamp truncation differed once; we locked ISO 8601 UTC (`YYYY-MM-DDTHH:MM:SSZ`) and re-checked to 100% agreement on format. News_score ties broken by written rubric (1=strongly negative … 5=strongly positive).

---

## Part 7 — Adequacy against the standard

| Requirement | Standard | Collected so far | Projected by Week 3 |
|---|---|---|---|
| Records | 500 | 510 | 510 |
| Usable attributes | 10 | 11 (API fields; human notes on 10-row pilot) | 11+ |
| Minority-class cases | 60 | 87 (`positive_90d_return=1`) | 87 |

### 7.1 If you will not clear the bar
Not applicable — first labeled pull clears all three bars (510 records, 11 usable API attributes, 87 minority-class positives). Human `research_notes` / `news_score` will expand on the 10-row agreement pilot through Week 3.
