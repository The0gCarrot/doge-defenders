# BUA 3336 · Big Data & Data Mining for Business
## M2 — Raw Dataset v1 and Data Quality Report

**Team:** Doge Defenders  
**Members and roles:** Data Steward — Daniel Burke · Modeling Lead — Gabriel McLaughlin · AI Auditor — Augusta Domingo · Business Translator — Mason Ocampo  
**Author:** Gabriel McLaughlin  
**Date:** September 24, 2026

---

## Part 1 — The dataset

### 1.1 The file
We submit **snapshots.csv** as our raw dataset v1.  
The notebook that builds the file end to end is **M2 collect snapshots** (`notebooks/M2_collect_snapshots.ipynb`). It installs dependencies, rebuilds the table from saved CoinGecko pulls (or refreshes the API), prints row counts and class balance, and runs the adequacy check.  
Project repo: https://github.com/The0gCarrot/doge-defenders  
Colab (open and Run all): https://colab.research.google.com/github/The0gCarrot/doge-defenders/blob/master/notebooks/M2_collect_snapshots.ipynb

### 1.2 What one row is, and how many there are
One row is one **snapshot** — one crypto token on one weekly decision date.

- Rows in the raw file: **510**
- Rows after cleaning: **510** (no rows dropped)
- Columns after cleaning: **18**
- Collection window: **Oct 20, 2025** through **Jun 8, 2026** (weekly decision dates in the file; the script that assembled prices ran in September 2026)

### 1.3 What changed since M1
In M1 we still talked about 15-minute prices, DEX dumps, and automated news scrapes. For this file we simplified:

- One row = one token × one weekly decision date, labeled by whether price rose over the next 90 days.
- Source = CoinGecko public market data only.
- We dropped paid on-chain dumps, exchange HTML scrapes, and auto sentiment joins.
- Research notes and news score columns stay in the file for course requirements, but this v1 leaves them empty.
- Count locked at **15 tokens × 34 weeks = 510** snapshots.

---

## Part 2 — Data dictionary

### 2.1 Every column

Missing values: numbers use **-999**; text uses **NULL**. A blank cell never means zero.

Quick scale reminder: **nominal** = a label (name or yes/no); **ordinal** = ordered rank or score; **interval** = date/time; **ratio** = a measurable amount with a true zero (price, volume, percent).

Each column below is listed the same way: name, type, unit, how much is missing, then what it means in plain English.

**Row id** — Type: nominal. Unit: id. Missing: 0%.  
What it is: Unique key for that snapshot. We have 510 different ids.

**CoinGecko id** — Type: nominal. Unit: id. Missing: 0%.  
What it is: CoinGecko’s internal name for the token (e.g. bitcoin, dogecoin). 15 tokens in our list.

**Token ticker** — Type: nominal. Unit: ticker. Missing: 0%.  
What it is: Short market symbol (BTC, ETH, DOGE). 15 tickers.

**Decision date** — Type: interval. Unit: UTC date-time. Missing: 0%.  
What it is: The pretend “buy day” for that row. Ranges from Oct 20, 2025 to Jun 8, 2026.

**Price at decision** — Type: ratio. Unit: USD. Missing: 0%.  
What it is: Token price in dollars on the decision date. About $0.0000028 to $114,419 in our file.

**24h volume** — Type: ratio. Unit: USD. Missing: 0%.  
What it is: How much was traded in the prior day, in dollars. About $36M to $73B.

**Market cap** — Type: ratio. Unit: USD. Missing: 0%.  
What it is: Reported market value of the token. About $519M to $2.3T.

**Cap rank (in our list)** — Type: ordinal. Unit: rank. Missing: 0%.  
What it is: Size order among our 15 tokens on that day (1 = largest, 15 = smallest).

**Token category** — Type: nominal. Unit: sector label. Missing: 0%.  
What it is: Sector tag from CoinGecko (e.g. smart contract platform, DeFi). 6 categories in the file.

**Main exchange** — Type: nominal. Unit: venue name. Missing: 0%.  
What it is: Exchange with the highest USD volume pair that day. 7 venues appear in the file.

**Prior 30 daily prices** — Type: ratio, multi-valued. Unit: list of USD. Missing: 0%.  
What it is: One cell holding the last 30 daily closes before the decision date (a list, not a single number).

**Distance from peak** — Type: ratio. Unit: percent. Missing: 0%.  
What it is: How far price sits from its recent peak. About −49% to +18%.

**30-day price change** — Type: ratio. Unit: percent. Missing: 0%.  
What it is: Percent change over the prior 30 days. About −49% to +80%.

**Research notes** — Type: free text. Unit: text. Missing: 100%.  
What it is: Short human notes about public news. Empty in this version (NULL on every row).

**News score** — Type: ordinal. Unit: 1–5 tone. Missing: 100%.  
What it is: Human rating of news tone (1 = very negative, 5 = very positive). Empty in this version (−999 on every row).

**Price 90 days later** — Type: ratio. Unit: USD. Missing: 0%.  
What it is: Token price 90 days after the decision date. About $0.0000024 to $94,803. Used only to build the label (do not use as a predictor).

**90-day return** — Type: ratio. Unit: share / proportion. Missing: 0%.  
What it is: Percent-style return from decision date to 90 days later. About −65% to +174%. Also label-only (do not use as a predictor).

**Up after 90 days?** — Type: nominal. Unit: 0 or 1. Missing: 0%.  
What it is: Our target. 1 = price rose over 90 days; 0 = it did not.

### 2.2 The four you cannot go back for

- Free-text field → **Research notes**
- Timestamp → **Decision date**
- Attribute above the unit (sector / brand-like label) → **Token category**
- Multi-valued field (a list in one cell) → **Prior 30 daily prices**

---

## Part 3 — Data quality report

### 3.1 The nine decisions

| # | Decision | What we did (with the number) |
|---|---|---|
| 1 | Unit of analysis | One snapshot = one token on one decision date. 510 rows = 15 tokens × 34 weeks. |
| 2 | Duplicates | Checked row id and ticker + decision date. 0 duplicates removed. |
| 3 | Missing values | Market fields from CoinGecko: 0% missing. Research notes: 510 of 510 empty. News score: 510 of 510 coded missing (−999). |
| 4 | Outliers | 0 rows deleted for “weird” prices. Tiny prices (meme coins) and large prices (Bitcoin) both kept. |
| 5 | Type coercion | Prices and volumes stored as numbers; ranks and the yes/no label as integers; the 30-day price list stored as a text list. 510 of 510 rows typed. |
| 6 | Text normalization | Tickers taken as CoinGecko returns them (uppercase). Category and exchange names left as returned. 0 hand rewrites. |
| 7 | Categories | Kept 6 token categories and 7 exchange names; did not merge rare labels. |
| 8 | Dates and time zones | Every decision date set to UTC midnight in standard ISO form. 510 of 510 rows. |
| 9 | Scaling and encoding | None in this submitted file. Any later model scaling is separate and not written back into snapshots.csv. |

### 3.2 Imputation
None. We did not fill in missing research notes or news scores.

### 3.3 What you found that you did not expect
Early exploration showed obscure venues (CoinUp, FameEX, BTCC) as “main exchange,” including for Bitcoin. That was a **collection bug**: we picked the CoinGecko ticker with the absolute highest reported volume. We fixed it to prefer major venues (Binance, Coinbase, KuCoin, etc.) by volume, and to prefer useful category tags (Layer 1, Meme, DeFi) over CoinGecko’s first list item. After rebuild, exchanges are Binance / KuCoin / Coinbase International and Bitcoin is Layer 1 — as expected.

What still looks surprising in the cleaned file: tokens in the **strongest prior-30-day gain quartile** are *less* often up over the next 90 days (~11% hit rate) than tokens in the **weakest** prior-30-day quartile (~37% hit rate). Prior 30-day change and forward 90-day return are negatively correlated (about −0.22) in this sample.

### 3.4 Adequacy against the standard
Checked with our adequacy script on this file (not from memory).

| Requirement | Standard | Our file | Result |
|---|---|---|---|
| Records after cleaning | 500 | 510 | Pass |
| Usable attributes | 10 (at least 3 numeric; enough categorical / binnable) | 11 | Pass |
| Minority-class cases | 60 | 87 | Pass |

The 11 usable fields are: token ticker, decision date, price at decision, 24h volume, market cap, cap rank, token category, main exchange, prior 30 daily prices, distance from peak, and 30-day price change. Research notes and news score are in the file but not counted as usable while fully empty.

### 3.5 If you did not clear the bar
Not applicable — we clear all three bars.

---

## Part 4 — Target definition (GATE)

### 4.1 The sentence
We are predicting **whether the token was up after 90 days** for each **snapshot**, using only information available on the **decision date** (CoinGecko market facts as of that day, not later).

### 4.2 The cutoff
**Up** = price 90 days later is strictly higher than price on the decision date; otherwise **not up**. We ignore fees and slippage in this version. This rule was set in M1 **before** we fit any classifier; labels were then computed from historical closes.

### 4.3 Class balance

| Class | Count | Share of rows |
|---|---|---|
| Majority — not up after 90 days | 423 | 82.9% |
| Minority — up after 90 days | 87 | 17.1% |

### 4.4 Features that would leak
We will not use these as predictors (they are only known after the decision date, or they are the answer itself):

- Price 90 days later  
- 90-day return  
- Up after 90 days? (the target)

Row id and CoinGecko id are keys only, not features.

### 4.5 Sign-off
For Week 4 studio. Leave blank for the instructor.

- Approved as written: ____________  
- Approved with changes noted below: ____________  
- Not approved — resubmit: ____________  
- Instructor signature: ____________  Date: ____________

---

## Part 5 — AI Collaboration Log

(Left blank.)
