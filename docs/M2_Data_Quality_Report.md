# BUA 3336 · Big Data & Data Mining for Business
## M2 — Raw Dataset v1 and Data Quality Report

**Team:** Doge Defenders
**Members and roles:** Data Steward — Daniel Burke · Modeling Lead — Gabriel McLaughlin · AI Auditor — Augusta Domingo · Business Translator — Mason Ocampo
**Author:** Gabriel McLaughlin
**Date:** September 26, 2026

This report describes the data file we collected, what each column means, how we cleaned it, and what we are trying to predict. When a word from class is needed, it is explained the first time it appears.

---

## Part 1 — The dataset

### 1.1 The file we are turning in
The data file is **daily_reports.csv** (`data/processed/daily_reports.csv`).

The notebook that builds it is **M2 collect snapshots** (`notebooks/M2_collect_snapshots.ipynb`). A notebook is a set of steps a computer can run. Running it downloads the project, builds the table, and checks that the file is large enough for the course.

- Project: https://github.com/The0gCarrot/doge-defenders
- Colab (a free website that runs the notebook): https://colab.research.google.com/github/The0gCarrot/doge-defenders/blob/master/notebooks/M2_collect_snapshots.ipynb

Prices come from CoinGecko, a public website that lists cryptocurrency prices. Older days use saved price history. The current practice-trading day uses a live price from CoinGecko. Headlines from the last 10 days come from two free news sources: GDELT, a search tool that tracks news stories from around the world, and Yahoo Finance. We compare the two sources and write one opinion.

### 1.2 What one row means
One row is one **daily report**: one cryptocurrency on one calendar day, recorded at midnight UTC. UTC is the world’s standard clock, so every coin uses the same “today,” no matter where we live.

- Rows in the file: **525**
- Rows after cleaning: **525**. We did not delete any rows.
- Columns: **39**
- Cryptocurrencies: **15**
- Days in the file: **35** (May 24, 2026 through June 26, 2026, plus September 26, 2026)
- Rows where we already know the result 90 days later: **510**
- Rows where that result is still in the future: **15** (September 26 only)

### 1.3 How this version differs from the earlier weekly file
The first draft used one row per coin per week. This version uses one row per coin per day, and it adds a practice portfolio. A practice portfolio is pretend money. No real trades are placed.

- News is real headlines from GDELT and Yahoo. CoinGecko’s old news link no longer works. It returned “page not found.”
- Two facts help the invest decision: how much the price moved over about 30 days, and how far the price is from its recent high.
- The practice portfolio starts with **$1,000** on the newest day in the file. Older days say **N/A** in the portfolio columns. N/A means “not applicable.” We did not pretend to trade those older days.
- If the model says Invest and the score is 94, we put **9.4% of the cash we still have** into that coin. The percent equals the score divided by 10. The model is the set of rules that turns the day’s facts into a score.

---

## Part 2 — Data dictionary

A data dictionary is a list of every column, with a short definition.

When a number is unknown, the cell says **-999**. When words are unknown, the cell says **NULL**. Portfolio columns on days before we started trading say **N/A**. A blank cell is not the same thing as zero.

Column types, from Chapter 2 of the course:

- **Nominal:** a name or a yes/no label. The order of the labels does not matter. Example: BTC and ETH are names, not scores.
- **Ordinal:** a rank or a score. Order matters, but the gaps are not equal dollars. Rank 1 is larger than rank 2, but the dollar gap is not fixed.
- **Interval:** a date or a time.
- **Ratio:** a real amount with a true zero, such as a price in dollars, dollars traded, or a percent change. Zero means none of that thing.

Every count below was measured on the 525-row file dated September 26, 2026.

**report_id** — Type: nominal. Unit: id code. Missing: 0%. Range: 525 different codes, one per coin and day. This is the row’s name, such as bitcoin_2026-05-24.

**coingecko_id** — Type: nominal. Unit: id code. Missing: 0%. Range: 15 names, from bitcoin to pepe. This is CoinGecko’s name for the coin.

**token_symbol** — Type: nominal. Unit: ticker (the short trading symbol). Missing: 0%. Range: 15 tickers (BTC, ETH, SOL, DOGE, ADA, XRP, AVAX, LINK, DOT, LTC, NEAR, ARB, AAVE, UNI, PEPE).

**report_date** — Type: interval. Unit: UTC date and time. Missing: 0%. Range: May 24, 2026 through September 26, 2026, always at midnight UTC. This is the day the row describes.

**price_usd** — Type: ratio. Unit: U.S. dollars. Missing: 0%. Range in this file: about $0.00000235 to $84,317. This is the coin’s price that day.

**return_24h** — Type: ratio. Unit: percent. Missing: 0%. Range: about −22% to +17%. This is how much the price changed over the previous 24 hours.

**volume_24h_usd** — Type: ratio. Unit: U.S. dollars. Missing: 0%. Range: about $26 million to $62 billion. This is how many dollars of the coin were bought and sold in the previous day.

**market_cap_usd** — Type: ratio. Unit: U.S. dollars. Missing: 0%. Range: about $466 million to $1.69 trillion. Market cap is the coin’s total market value that day (price times coins in circulation).

**market_cap_rank** — Type: ordinal. Unit: rank from 1 to 15. Missing: 0%. Range: 1 (largest of our 15 that day) to 15 (smallest). We rank only inside our list of 15 coins, not against every coin in the world.

**category** — Type: nominal. Unit: sector name. Missing: 0%. Four labels: Layer 1 (a base blockchain, such as Bitcoin), Decentralized Finance or DeFi (tools for lending and trading without a bank), Meme, and Smart Contract Platform. This says what kind of project the coin is.

**primary_exchange** — Type: nominal. Unit: exchange name. Missing: 0%. Three names: binance, kucoin, and coinbase_international. An exchange is a marketplace. This column names the well-known exchange with the most dollar trading in that coin.

**momentum_30d_pct** — Type: ratio. Unit: percent. Missing: 0%. Range: about −45% to +160%. This is the percent change versus about 30 days earlier. It is the first fact we use when deciding whether to invest.

**drawdown_from_peak_pct** — Type: ratio. Unit: percent. Missing: 0%. Range: about −45% to +17%. This shows how far the price sits from its high over the prior 30 days. A negative number means the price is below that high. It is the second decision fact.

**press_gdelt** — Type: words, not a number. Unit: headlines. Missing: 58.1% (305 of 525 cells say NULL). When it is filled, it lists news titles from GDELT in the last 10 days.

**press_yahoo** — Type: words, not a number. Unit: headlines. Missing: 94.9% (498 of 525 say NULL). Yahoo mostly has recent stories, so older days are often empty. We leave those cells empty on purpose.

**press_release** — Type: words (several headlines in one cell). Unit: headlines. Missing: 53.7% (282 of 525 say NULL). This is the combined GDELT and Yahoo list for that coin and day.

**press_opinion** — Type: nominal. Unit: label. Missing: 0%. Four labels: none, neutral, bullish, or bearish. Bullish means the headlines sound like good news for the price. Bearish means they sound like bad news. Neutral means the two sources do not point the same way, or the words are mixed. None means we found no headline. This is our single opinion after comparing the two news sources.

**press_conflict** — Type: nominal. Unit: label. Missing: 0%. Labels in this file: none and agree. The rule also allows “disagree,” but no row needed that label. Disagree would mean one source looked like good news and the other looked like bad news.

**news_count_10d** — Type: ratio. Unit: count of headlines. Missing: 0%. Range: 0 to 12. Zero means we found no matching headline. It does not mean we forgot to look.

**news_delta** — Type: ordinal. Unit: points added to the invest score. Missing: 0%. Only three values: −5, 0, or +5. Good news adds 5 points. Bad news subtracts 5. No clear news adds 0.

**news_headlines_10d** — Type: words. Unit: headlines. Missing: 53.7%. This column repeats press_release so older tools can still find the headlines.

**hist_prices_30d** — Type: ratio, with a list inside one cell. Unit: U.S. dollars. Missing: 0%. Each cell holds up to 30 earlier daily prices for that coin.

**price_usd_t90** — Type: ratio. Unit: U.S. dollars. A true price 90 days later is missing for 2.9% of rows (15 of 525). On the 510 finished days, the price 90 days later runs from about $0.00000323 to $81,265. On September 26 the future price does not exist yet, so we do not treat that cell as an answer.

**return_90d** — Type: ratio. Unit: change as a share of the starting price (0.10 means the price rose 10%). Missing: 2.9% (written as −999). On finished days the return runs from about −33% to +190%. This column is part of the answer. We do not use it to make the prediction.

**positive_90d_return** — Type: nominal. Unit: 1 or 0. Missing: 2.9% (written as −999). This is the target, which means the answer we are trying to predict. 1 means the price was higher 90 days later. 0 means it was not.

**base_score** — Type: ratio. Unit: score from 0 to 100. Missing: 0%. Range: about 0.04 to 100. This is the model’s price-only chance that the coin rises over 90 days, written as a score from 0 to 100. News is not included yet.

**invest_score** — Type: ratio. Unit: score from 0 to 100. Missing: 0%. Range: 0 to 100. This is the base score plus the news adjustment (−5, 0, or +5), kept between 0 and 100.

**model_decision** — Type: nominal. Unit: Invest or Skip. Missing: 0%. Invest means the score is 50 or higher. Skip means it is below 50.

**did_invest** — Type: nominal. Unit: 1 or 0. Not used on older days: 97.1% say N/A (510 of 525). 1 means we opened a practice trade that day.

**position_open** — Type: nominal. Unit: 1 or 0. Not used on older days: 97.1% say N/A. 1 means we still hold that practice trade after the row.

**entry_price** — Type: ratio. Unit: U.S. dollars. Empty unless a practice trade is open: 99.4% are N/A or −999. This is the price we pretended to buy at.

**position_days** — Type: ratio. Unit: days held. Not used on older days: 97.1% say N/A. On the day we buy, the value is 0.

**unrealized_pnl_pct** — Type: ratio. Unit: percent gain or loss that is still only on paper. Empty unless a trade is open: 99.4%. On the day we buy, it is 0, because we just bought. “Unrealized” means we have not sold yet, so the gain or loss is not locked in.

**should_close** — Type: nominal. Unit: 1 or 0. Not used on older days: 97.1% say N/A. 1 would mean the rules say to sell.

**did_close** — Type: nominal. Unit: 1 or 0. Not used on older days: 97.1% say N/A. No practice trade has been sold yet, so this is 0 on the current day.

**realized_pnl_pct** — Type: ratio. Unit: percent gain or loss after a sale. Missing: 100%, written as −999, because nothing has been sold yet. “Realized” means the trade is finished and the result is locked in.

**allocation_pct** — Type: ratio. Unit: percent of cash still available. Not used on older days: 97.1% say N/A. On the current day the values run from 0 to about 9.7. A score of 94 means we use 9.4% of the cash we still have.

**position_value_usd** — Type: ratio. Unit: U.S. dollars. Not used on older days: 97.1% say N/A. On the current day a holding is worth about $0 to $97. This is the dollar amount sitting in that coin.

**paper_return_24h** — Type: ratio. Unit: percent. Empty unless that coin’s practice trade is open: 99.4%. While we hold the coin, this column copies that day’s 24-hour price change. On the day we buy, it is 0.

### 2.2 Four special column types the course asks for

- A sentence or headline that stays as words: **press_release**
- A date and time: **report_date**
- A label that describes the whole coin, not just that day: **category**
- Several numbers stored in one cell: **hist_prices_30d**

---

## Part 3 — Data quality report

### 3.1 How many records we had before and after cleaning

| | Before cleaning | After cleaning |
|---|---|---|
| Rows | 525 (15 coins × 35 days) | 525. We deleted 0 rows. |
| Columns | 39 | 39. We deleted 0 columns. |
| Duplicate rows removed | — | 0 |
| Missing values filled in with a guess | — | 0 |

Cleaning here means writing a clear code when a value is missing, and using the same labels everywhere. We did not throw rows away. A day with no news is still a real day, and the course asks for at least 500 rows.

### 3.2 The nine cleaning decisions

**1. What one row is.** One row is one coin on one UTC day. The question for that row is: should the practice portfolio buy that coin on that day?

**2. Duplicates.** A duplicate is a second copy of the same row. Two rows are duplicates when they have the same report_id, which means the same coin and the same day. If we rebuild the file, we keep the newest copy. This file has **0 duplicates**, so we removed **0** rows.

**3. Missing values.** We keep the row and the column. Unknown numbers are −999. Unknown words are NULL. Portfolio columns before the start day are N/A. We do not guess a number to fill the hole. The 15 newest rows stay without an answer, because 90 days have not passed yet.

**4. Outliers.** An outlier is a number that looks extreme, such as a very small meme-coin price or a very large Bitcoin price. We **keep** them. We do not cap them, and we do not delete them. **0** rows were removed for this reason. Those large and small moves are part of the real market, so they belong in the decision.

**5. Values that will not convert.** If a cell should be a number but the text cannot be read as a number, we store −999. We do not store 0. Zero would look like a real price, or like a real return of “no change.”

**6. Text cleanup.** Tickers stay uppercase (BTC). Exchange names stay lowercase (binance). Extra spaces in headlines are removed, and a very long headline is shortened. We do not delete punctuation or accent marks, because that can change what a headline means.

**7. Categories.** CoinGecko sometimes gives several tags for one coin, including tags that are not useful, such as the name of an investment fund. We keep one clear sector: Layer 1, DeFi, Meme, or Smart Contract Platform. We do not give every rare tag its own category.

**8. Dates and time zones.** Every report date is midnight UTC, written as YYYY-MM-DDT00:00:00Z (year-month-day, then T, then midnight, then Z for UTC). We do not save a row if the day is incomplete. Using one clock makes “today” and “90 days later” mean the same thing for every coin.

**9. Scaling and encoding.** Scaling means shrinking very large numbers so a model can compare a $80,000 price with a $1 price without the big number taking over. Encoding means turning a name, such as “Meme,” into numbers. The file we turn in is **not** scaled, and the names are left as words. Only inside the model, and only after we separate the rows used to learn from the rows used to test, we take the logarithm of price, trading volume, and market cap, and then put those columns on a common scale. A logarithm compresses a huge number so that $1, $100, and $10,000 do not overwhelm a small percent change. News points (−5, 0, or +5) are added after that price score. We do not turn category or exchange into number codes in the file we submit.

### 3.3 How we treated missing values
We imputed **0** values. To impute means to fill a hole with a guess, such as the average. We did not do that. Empty headlines stay NULL. Future answers that do not exist yet stay −999. Old portfolio cells stay N/A.

### 3.4 Outliers
We found extreme prices and percent moves, and we **kept all of them**. The rule is simple: if the number is a real market value, it stays. Cutting off Bitcoin’s high price, or a meme coin’s tiny price, would hide the two facts we care about: the 30-day price change, and the distance from the recent high.

### 3.5 Duplicates
A duplicate is a second copy of the same coin on the same day. **0** duplicates were removed.

### 3.6 Is the file large enough? (500 / 10 / 60)

The course calls this an adequacy check. It asks for at least 500 rows, 10 useful columns, and 60 examples of the smaller result. The smaller result is “the price was not higher after 90 days,” because that happened less often than “the price was higher.”

| Requirement | Course minimum | Our file | Result |
|---|---|---|---|
| Rows after cleaning | 500 | 525 | Pass |
| Useful columns | 10 | 15 | Pass |
| Smaller result | 60 | 104 coins that were not higher after 90 days | Pass |

The 15 useful columns are: coin symbol, report date, price, 24-hour return, dollars traded in 24 hours, market value, rank in our list, category, main exchange, 30-day price list, 30-day price change, distance from the recent high, combined headlines, news opinion, and headline count.

Among the 510 rows that already have an answer: **406** went up (79.6%) and **104** did not (20.4%). The 15 September 26 rows are left out of this count because their answer is still −999.

### 3.7 Plan if a requirement is missed later
All three requirements pass now, so we do not need a fix to move forward. If a future version falls under 500 rows with a known answer, or under 60 “not higher” cases, we will add more past days where the price 90 days later is already known. We will still not fill in a missing answer with a guess.

One limit is worth stating even though the file passes. Yahoo is empty on most older days (94.9% NULL), and GDELT sometimes returns nothing when the site is busy. Those cells stay empty. We do not write fake headlines.

---

## Part 4 — What we are predicting (the target)

This section is the course gate. A gate is a required checkpoint. The instructor signs it before later work can count. The target is the answer the model is trying to predict.

### 4.1 The sentence
We are predicting **whether the coin’s price is higher 90 days later** for each **daily report (one coin on one UTC day)**, using only information available at **midnight UTC on that report date**.

### 4.2 The exact rule
The result is **up** (1) when the price about 90 days later is higher than the price on the report date. Otherwise the result is **not up** (0). If the future price is missing, we do not call it up. We ignore trading fees. The 15 rows from September 26, 2026 stay without an answer until 90 days have passed.

### 4.3 How often each result appears
Counted only on the 510 rows that already have an answer:

| Result | Count | Share |
|---|---|---|
| Up after 90 days (1) | 406 | 79.6% |
| Not up after 90 days (0) | 104 | 20.4% |
| September 26 rows, answer not known yet | 15 | not in the percents above |

The smaller result has 104 rows, which is more than the required 60.

### 4.4 Columns that would give away the answer
A leaking column uses information from the future, or it is the answer itself. Using it would be like seeing the test answers before the test. We will not use these columns to make the prediction:

- The price 90 days later
- The 90-day return
- The up-or-not label itself
- The model scores and the Invest or Skip label, because those were built from the answer
- The practice-portfolio columns, because those record what we did after the score

We may use the price, the 24-hour change, dollars traded, market value, rank, category, exchange, the 30-day price change, the distance from the recent high, and headlines from the 10 days ending on the report date.

### 4.5 Instructor sign-off
For the Week 4 studio. Left blank for the instructor.

- Approved as written: ____________
- Approved with changes noted below: ____________
- Not approved — resubmit: ____________
- Instructor signature: ____________    Date: ____________

---

## Part 5 — AI Collaboration Log

These notes come from our Week 3 and Week 4 decision logs. Each note says what we asked an assistant, what it returned, what was wrong, how we checked, and what we changed.

**Exchanges and categories (Week 3).** We asked an assistant to fill in the main exchange and the coin’s category. It picked the trading pair with the biggest reported volume, and it used the first tag on CoinGecko’s list. That made unusual exchanges look like Bitcoin’s home market, and it treated the names of investment funds as if they were business types. We opened the raw exchange lists and checked them by hand. We then kept only well-known exchanges and a short list of real business types. The file now uses Binance, KuCoin, and Coinbase International, and four types: Layer 1, DeFi, Meme, and Smart Contract Platform.

**News source (Weeks 3 and 4).** We asked for headlines from the last 10 days on CoinGecko. The assistant used CoinGecko’s status-update link. Every coin returned “page not found.” We repeated the calls ourselves and saw the same error. We did not make up headlines. The team chose GDELT and Yahoo instead. If those two sources disagree, one sounding like good news and one sounding like bad news, our opinion is neutral and we add 0 points to the score.

**Cleaning choices (Week 4).** We asked for the nine cleaning decisions. The first draft wanted to drop empty columns, cut off extreme prices, and shrink the numbers in the whole file before any rows were set aside for testing. Those choices belong to the team. We kept every row, marked holes as −999, NULL, or N/A, kept extreme prices, and shrank numbers only inside the model, after the learning rows were separated from the test rows. The file matches that decision.

**Practice-trade prices (Week 4).** We asked for today’s price in the practice ledger. The assistant reused a saved CoinGecko file from September 17, so Bitcoin showed about $76,608. A live check the same week showed about $84,000. We compared the dates on the saved file with CoinGecko’s live price page. Today’s row now uses the live price, the dollars traded, the market value, and the 24-hour change. Older days still use the saved history. Portfolio columns before the start day stay N/A. The rule “score divided by 10, as a percent of cash left” was our rule. It was not a default from the assistant.
