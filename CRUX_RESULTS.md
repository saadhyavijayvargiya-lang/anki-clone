# Crux results

Evidence for the Crux claims. Everything here is re-runnable from `topgre_eval/`
with the built Python env; commands are given so anyone can reproduce the numbers.

## Fairness and thesis tests (verified)

### Leakage check (7e): CLEAN
```
out\pyenv\Scripts\python topgre_eval\leakage_check.py
```
Train 12, test 8, similarity threshold 0.8. No test item or near-copy found in
the training data. (Exits non-zero if leakage is ever found, so it can gate CI.)

### Paraphrase / memory-vs-performance gap (7d): real gap of +0.254
```
out\pyenv\Scripts\python topgre_eval\paraphrase_test.py
```
Over 30 cards: mean card recall 0.915, mean reworded-question accuracy 0.661,
so the **memory to performance gap is +0.254**. Students recall the card but miss
reworded questions, so Performance is measurably not just Memory in disguise.
Worst-transferring move-types: homeomorphism (+0.45), separation (+0.42),
compactness (+0.40); best: examples (+0.08).

### Study-feature ablation (section 8, interleaving): fair 3-arm test
```
out\pyenv\Scripts\python topgre_eval\ablation.py
out\pyenv\Scripts\python topgre_eval\ablation.py --disc-bonus 0.4
```
Equal study time (same cards, same total reviews), 30 seeds. Pre-stated
hypothesis: interleaving >= blocked and >= plain on mixed-type accuracy.
- interleaved vs blocked: **+2.8 pts** (spacing beats massed practice), supports.
- interleaved vs plain Anki: **~0 pts** at defaults, reported as an honest null.
  A pure spacing model gives plain and interleaved the same spacing, so any edge
  over plain must come from a discrimination benefit, which is an explicit
  off-by-default knob (`--disc-bonus`). With `--disc-bonus 0.4` interleaved beats
  plain by ~8.9 pts, but that is a stated assumption, not a measured result.

## Pending (honest)

These are set up but the numbers still need to be produced/written up:

- **Benchmark (7h / section 10):** run on an idle machine and record p50/p95/worst:
  ```
  out\pyenv\Scripts\python topgre_eval\bench.py --cards 50000
  ```
- **Memory calibration (section 9 step 1):** calibration chart + Brier/log-loss on
  held-out reviews.
- **Performance held-out accuracy (step 2):** write up `evaluate_performance_model`
  (held-out train/test split vs a simpler baseline).
- **AI card check (7f):** expand the gold set to 50 pairs and report the three
  counts (correct-useful / wrong / correct-but-bad) with a pre-set cutoff
  (`topgre_eval/ai_cardgen.py`).
- **Sync + conflict test (7b):** follow `SYNC_SETUP.md` (offline 10+10, then a
  same-card conflict) and record the outcome.
- **Crash / offline tests (7g):** kill each app mid-review 20x, show zero
  corruption; pull the network and show AI degrades cleanly while scores still
  work.
