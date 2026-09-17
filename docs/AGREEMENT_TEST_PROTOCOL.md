# Dual-coder agreement test (M1 §6.2)

## Rubric

`news_score` (ordinal 1–5):

1. Strongly negative public tone  
2. Mildly negative  
3. Mixed / neutral  
4. Mildly positive  
5. Strongly positive  

`decision_ts` / `decision_date` must use ISO date `YYYY-MM-DD` (UTC midnight in snapshots).

`research_notes`: short human paraphrase of publicly visible headlines only — **no LLM-generated text**.

## Steps

```powershell
python -m src.append_research_notes --init-template
python -m src.agreement_test --seed
```

1. Augusta fills `data/manual/agreement_coder_a.csv` for the 10 rows.  
2. Mason fills `data/manual/agreement_coder_b.csv` independently for the same keys.  
3. Run `python -m src.agreement_test` and record % agreement in the memo.  
4. Resolve mismatches with the rubric; copy the consensus into `data/manual/research_notes.csv`.  
5. `python -m src.append_research_notes` to merge into `snapshots.csv`.
