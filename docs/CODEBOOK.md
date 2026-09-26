# Doge Defenders — daily report schema & codebook

**Unit of analysis:** one **daily report** = one (token, calendar day).  
**Missing values:** numeric `-999`, string `NULL`. Blank ≠ zero.  
**Label:** `positive_90d_return` = 1 iff price 90 days later > price on report day.  
**Volume target:** 15 tokens × 34 days = **510** rows.

## Invest score (2B overlay)
1. `base_score` = P(positive_90d_return) × 100 from price features only (logistic).  
2. `news_delta` ∈ {−5, 0, +5} from reconciled GDELT + Yahoo press opinion.  
3. `invest_score` = clamp(`base_score` + `news_delta`, 0, 100). Invest if ≥ 50.

## Press reconciliation
- GDELT Doc API + Yahoo Finance RSS, 10-day lookback.  
- Same stance → that opinion; one empty → trust non-empty; bullish vs bearish → **neutral** (`news_delta=0`, `press_conflict=disagree`).

## Columns

| Column | Notes |
|---|---|
| token_symbol / report_date / price_usd | identity + price |
| return_24h | % vs prior day |
| press_release / press_gdelt / press_yahoo | headlines |
| press_opinion / press_conflict / news_delta | reconciled stance |
| momentum_30d_pct / drawdown_from_peak_pct | decision factors |
| base_score / invest_score / model_decision | scoring |
| paper fields | did_invest, position_open, unrealized_pnl_pct, did_close, … |

## Paper rules
- Bankroll starts at **$1000** (`paper_starting_balance`).  
- Portfolio starts on **UTC today** (`paper_start_date: today`).  
- Rows **before** that day: paper fields = `N/A` (not in the ledger).  
- **Allocate:** if Invest and score = 94 → **9.4% of remaining cash** (`allocation_pct = invest_score / 10`).  
- **position_value_usd:** dollars in that token; **paper_return_24h:** that trade’s `return_24h` when a position is open.  
- **Close** when Skip, stop −15%, take-profit +25%, or hold ≥ 90 days.
