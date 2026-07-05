# Crux results

Evidence for the Crux claims. Everything here is re-runnable from `topgre_eval/`
(or `cargo test`) with the built env; commands are given so anyone can reproduce.

## Engine tests (7a)

- **Rust:** `cargo test -p anki readiness` -> **12 passed, 0 failed** (queue
  ordering, Wilson interval, give-up/abstain rules, held-out eval beats baseline,
  cram danger ranking, interleaving toggle, performance activation, and more).
- **Python (calls the engine):** `python -m pytest pylib/tests/test_readiness.py`
  -> **2 passed** (points-at-stake queue + triage reorder from Python).

## Score models (section 9)

### Memory calibration (step 1)
```
python topgre_eval/calibration.py            # calibrated
python topgre_eval/calibration.py --bias 0.15  # overconfident -> detected
```
Held-out predictions (5000): calibrated model **ECE 0.026** (Brier 0.176, log
loss 0.560), reliability table predicted ~= observed per bin. An injected
overconfident model is correctly flagged (**ECE 0.066, "miscalibrated"**), so the
diagnostic is not rigged. Note: the memory model itself is Anki's FSRS
(calibrated upstream); this proves the methodology and detection on held-out
samples.

### Performance held-out (step 2)
```
python topgre_eval/perf_eval.py
```
Time-split held-out eval, 108 attempts (train 75 / test 33): the move-aware
model **beats the global-average baseline on log loss (0.600 vs 0.683)**, equal
accuracy (0.879). Lower log loss = better-calibrated probabilities.

## Fairness and thesis tests

### Leakage check (7e): CLEAN
```
python topgre_eval/leakage_check.py
```
Train 12, test 8, threshold 0.8. No test item or near-copy in training.

### Paraphrase / memory-vs-performance (7d): gap +0.254
```
python topgre_eval/paraphrase_test.py
```
30 cards: recall 0.915 vs reworded accuracy 0.661, **gap +0.254**. Performance is
measurably not just Memory. Worst transfer: homeomorphism (+0.45), separation
(+0.42), compactness (+0.40).

### Study-feature ablation (section 8): fair 3-arm test
```
python topgre_eval/ablation.py
python topgre_eval/ablation.py --disc-bonus 0.4
```
Equal study time, 30 seeds. interleaved vs blocked **+2.8 pts** (spacing beats
massing); interleaved vs plain Anki **~0** at defaults (honest null; an edge over
plain requires an explicit discrimination assumption).

## AI card check (7f)
```
python topgre_eval/ai_cardcheck.py
```
Generates cards from one named source (`sample_data/source_topology.txt`) through
the AI proxy, enforces exact `source_quote` traceability, then checks them
against the **50-pair gold set** with a cutoff fixed before looking (0.80). A
representative run: 11 traceable cards -> **6 correct-useful, 4 wrong, 1
correct-but-bad**, pass rate 0.55 (below cutoff), **5 blocked**. The checker
does its job: wrong AI facts are blocked rather than shipped. (Card count varies
per run; the model returns a modest batch per call, accumulated over calls.)

## Benchmark (7h / section 10)
```
python topgre_eval/bench.py --cards 50000
```
On a 50,000-card deck, 50 iterations (p50 / p95 / worst, ms):
- points_at_stake_queue(50): 709.9 / 739.6 / 771.8
- get_readiness (dashboard):  651.8 / 684.8 / 732.2
- record_exam_attempt (write):  1.17 / 1.65 / 1.83
- evaluate_performance_model:   0.22 / 0.28 / 0.42

Vs section-10 targets, honestly: writes and eval are far under budget. The
dashboard/readiness call **meets the first-load target (p95 685ms < 1s)** but
**misses the refresh target (< 500ms)** on 50k cards, because readiness/triage
currently do a full scan of the deck. On the real ~90-card topology deck these
calls are sub-millisecond; the path to < 500ms on 50k is caching or an indexed
mastery query (noted as a follow-up).

## Still pending

- **Sync + conflict test (7b):** setup is done (`SYNC_SETUP.md`, local sync
  server verified); the offline 10+10 and same-card conflict run needs the
  emulator + desktop and is a manual/recorded step.
- **Crash / offline tests (7g).**
- **arm64 real-device build:** code fix committed; blocked by the vendored `.git`
  (see changelog); x86_64 emulator build works.
