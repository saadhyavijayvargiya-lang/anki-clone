# TopGRE evaluation & benchmark harness

Reproducible scripts backing the assignment's "fair tests others can re-run"
requirement and challenges 7d (paraphrase), 7e (leakage), 7h (benchmark), plus
the speed targets in section 10.

All scripts are deterministic given their inputs. Run them with the project's
built Python environment from the repo root:

```
out\pyenv\Scripts\python topgre_eval\bench.py
out\pyenv\Scripts\python topgre_eval\paraphrase_test.py
out\pyenv\Scripts\python topgre_eval\leakage_check.py
```

## What each script does

- `bench.py` (7h + section 10) — builds a synthetic deck and times the TopGRE
  engine calls (`points_at_stake_queue`, `get_readiness`, `record_exam_attempt`),
  reporting p50 / p95 / worst for each. Use `--cards 50000` for the full target
  deck; default is 2000 for a quick run.
- `paraphrase_test.py` (7d) — the headline test of the spiky thesis. Compares
  per-card recall against accuracy on reworded exam-style questions and reports
  the memory-vs-performance GAP. Reads `sample_data/paraphrase.csv`. If the gap
  is ~0, the performance model is just copying memory (we report it either way).
- `leakage_check.py` (7e) — scans training data for any test item or near-copy
  (exact/normalized match + token Jaccard >= 0.8) and prints a clean/dirty
  verdict. Reads `sample_data/train.jsonl` and `sample_data/test.jsonl`.

## Held-out Performance eval (in Rust)

The held-out model-vs-baseline evaluation lives in the engine itself
(`rslib/src/readiness/mod.rs::performance_eval`, RPC `EvaluatePerformanceModel`)
so it runs on real synced attempt data. It time-splits attempts 70/30 and
compares the move-aware model against a global-average baseline by log loss.
Covered by `cargo test -p anki readiness`
(`held_out_eval_beats_baseline_when_move_type_carries_signal`).

## Study-feature A/B (interleaving)

Hypothesis (pre-registered): interleaving confusable topology move-types within
a session raises accuracy on NEW mixed-type questions at equal study time vs
blocked practice. The engine lever is the `topgreInterleaving` config flag,
which reorders the points-at-stake queue (interleaved vs blocked); see
`rslib/src/readiness/mod.rs` and the `interleaving_toggle_changes_queue_grouping`
test. The three-arm comparison (full / feature-off / plain Anki) is run on the
same learners, questions, and time budget.
