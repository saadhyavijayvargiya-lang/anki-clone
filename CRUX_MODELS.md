# Crux model descriptions

Crux (a fork of Anki, exam target: **GRE Mathematics Subject Test, point-set
topology cluster**) reports three separate things, never blended into one
number: Memory, Performance, and Readiness. Each is returned with a range and an
availability flag, and every score obeys the give-up rule below.

Source of truth: `rslib/src/readiness/mod.rs` (`Collection::readiness`).

---

## 1. Memory model (can you recall a taught fact right now?)

- **Input:** Anki's FSRS memory state per card. For each reviewed topology card we
  compute FSRS **retrievability** (probability of recall at this instant from the
  card's stability and time since last review), in `card_retrievability`.
- **Aggregate:** the mean of per-card retrievabilities across the deck, with a
  normal-approximation confidence interval on that mean (`mean_ci`).
- **Unit:** recall probability. **Range:** reported (lower, upper).
- **Give-up:** if no card has an FSRS memory state yet (nothing reviewed), Memory
  is returned `available = false` with the reason recorded.
- **Why this is honest:** FSRS is Anki's calibrated memory model; Crux does not
  re-estimate memory, it aggregates it. Memory alone is explicitly *not* treated
  as readiness.
- **Still to do (Sunday, section 9 step 1):** a calibration chart + Brier/log-loss
  on held-out reviews. Not yet produced; stated plainly rather than faked.

## 2. Performance model (can you answer a new exam-style question?)

- **Input:** recorded exam-style attempts (`RecordExamAttempt`: move-type,
  correct, milliseconds), stored in the collection config key `topgrePerf`, so
  they **sync to the phone** for free.
- **Estimate:** the **Wilson score interval** of correct / total attempts
  (`wilson`), which gives a value and an honest range even with few attempts.
- **Unit:** P(correct on a new question). **Range:** Wilson (lower, upper).
- **Give-up:** needs at least `PERF_MIN_ATTEMPTS = 10` attempts to show at all;
  Readiness additionally needs at least 30 (see below).
- **Held-out evaluation (section 6/9 step 2):** `evaluate_performance_model`
  splits attempts into train/test and compares the model against a simpler
  baseline; `topgre_eval/` also holds the leakage check and the paraphrase test
  that measures the memory-vs-performance gap (7d). Numbers still to be written up.

## 3. Readiness model (what would you score today, and how sure are we?)

- **Base:** the Performance estimate (P correct on new topology questions).
- **Coverage widening:** the interval is widened by `(1 - coverage) * 0.1`, where
  `coverage` is the fraction of the topology outline the deck actually covers, so
  gaps in what you've studied show up as wider uncertainty.
- **Projected overall score:** topology performance is mapped to the real GRE
  Mathematics Subject scale (200 to 990):

  ```
  projected = clamp(200, 990, 700 + readiness_value * 200)
  ```

  with the range mapped the same way. The baseline (700) is high on purpose:
  point-set topology is the cluster that separates the top scorers, so a student
  weak on topology but otherwise strong still lands near the baseline, and strong
  topology pushes toward ~900. Confidence is shown as **low** until topology
  coverage is high. This is the stated method and its one assumption.

- **Unit:** projected GRE Math Subject score (topology-based), with a likely range.

## The give-up rule (honesty)

Readiness is shown only when **all** of these hold (thresholds are config-tunable
via `topgreMinReviews`, `topgreMinCoverage`, `topgreMinAttempts`, and adjustable
in the readiness page):

- Performance is available, and
- exam attempts >= `min_attempts` (default 30), and
- topology coverage >= `min_coverage` (default 0.5), and
- graded reviews >= `min_reviews` (default 150).

When any condition fails, Crux **withholds** the score (shows "withheld" / n/a),
lists exactly what is missing, and never invents a number. Every shown score also
carries: the point estimate, the likely range, topology coverage, a confidence
indicator, the last-updated time, the reasons behind it (evidence), and the
single best next move to study.
