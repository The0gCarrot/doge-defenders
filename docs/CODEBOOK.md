# Doge Defenders — dataset schema & codebook

**Unit of analysis:** one **snapshot** = one (token, decision time T) pair.  
**Missing values:** numeric `-999`, string `NULL`. Blank ≠ zero.  
**Label:** `positive_90d_return` = 1 iff `price_usd_t90 > price_usd_t`.

## Columns

| Column | In usable-10? | Scale | Source |
|---|---|---|---|
| snapshot_id | no (id) | nominal | script |
| coingecko_id | no (id) | nominal | config / API |
| token_symbol | yes | nominal | API |
| decision_ts | yes (timestamp) | interval | entry calendar |
| price_usd_t | yes | ratio | API history |
| volume_24h_usd | yes | ratio | API |
| market_cap_usd | yes | ratio | API |
| market_cap_rank | yes | ordinal | Rank by `market_cap_usd` within our token universe at that `decision_ts` (1 = largest) |
| category | yes (above-unit) | nominal | API coin detail |
| primary_exchange | yes (above-unit) | nominal | API tickers |
| hist_prices_30d | yes (multi-valued) | ratio multi | API chart |
| ath_change_percentage | yes | ratio | % below peak USD close in the chart window through T |
| price_change_percentage_30d | yes | ratio | Derived from first hist close vs `price_usd_t` |
| research_notes | yes (free-text) | free-text | human only |
| news_score | yes | ordinal 1–5 | human only |
| price_usd_t90 | no (label input) | ratio | API history |
| return_90d | no (derived) | ratio | script |
| positive_90d_return | target | nominal binary | script |

Usable attributes counted toward the course “10”:  
`token_symbol`, `decision_ts`, `price_usd_t`, `volume_24h_usd`, `market_cap_usd`, `market_cap_rank`, `category`, `primary_exchange`, `hist_prices_30d`, `ath_change_percentage`, `price_change_percentage_30d`, `research_notes`, `news_score` (≥10).

Row IDs, pure label columns, and near-copy derivatives do not count toward the ten.
