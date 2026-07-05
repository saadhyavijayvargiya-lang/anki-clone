# Copyright: Crux contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
"""Section 9 step 1: memory-model calibration.

"When the model says 80%, the student should recall about 80% of the time."
This computes the standard calibration diagnostics on held-out predictions:
a reliability table (predicted vs observed per bin), the Brier score, log loss,
and the Expected Calibration Error (ECE).

Honesty note: Crux's memory model IS Anki's FSRS retrievability, which is a
calibrated model validated upstream on large real datasets. Proving calibration
on THIS student's held-out reviews needs longitudinal real review data (rating +
outcome over time), which the demo deck does not contain. So this script
demonstrates the calibration METHODOLOGY on held-out samples from a predictor,
and exposes a `--bias` knob to show the diagnostics actually DETECT
miscalibration (they are not rigged to always pass). Point it at a real revlog
export to grade an actual student once that data exists.

Usage (no build/collection needed):
  python topgre_eval/calibration.py
  python topgre_eval/calibration.py --bias 0.12   # overconfident model; ECE rises
"""

from __future__ import annotations

import argparse
import math
import random


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=5000, help="held-out reviews")
    ap.add_argument("--noise", type=float, default=0.10, help="estimator noise (sd)")
    ap.add_argument("--bias", type=float, default=0.0,
                    help="systematic overconfidence added to predictions (0 = calibrated)")
    ap.add_argument("--bins", type=int, default=10)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    rng = random.Random(args.seed)

    preds: list[float] = []
    outcomes: list[int] = []
    for _ in range(args.n):
        true_p = rng.random()                       # the item's true recall probability
        # Imperfect predictor: true_p plus noise, plus optional overconfidence bias
        # that pushes predictions away from 0.5.
        p_hat = true_p + rng.gauss(0, args.noise) + args.bias * (true_p - 0.5) * 2
        p_hat = min(0.999, max(0.001, p_hat))
        preds.append(p_hat)
        outcomes.append(1 if rng.random() < true_p else 0)

    n = len(preds)
    brier = sum((p - y) ** 2 for p, y in zip(preds, outcomes)) / n
    log_loss = -sum(
        y * math.log(p) + (1 - y) * math.log(1 - p) for p, y in zip(preds, outcomes)
    ) / n

    # Reliability table + ECE.
    bins: list[list[tuple[float, int]]] = [[] for _ in range(args.bins)]
    for p, y in zip(preds, outcomes):
        idx = min(args.bins - 1, int(p * args.bins))
        bins[idx].append((p, y))
    ece = 0.0
    print(f"held-out reviews: {n}   noise sd: {args.noise}   bias: {args.bias}\n")
    print(f"{'bin':>10s} {'n':>6s} {'pred':>8s} {'observed':>9s} {'gap':>7s}")
    for b in range(args.bins):
        items = bins[b]
        lo, hi = b / args.bins, (b + 1) / args.bins
        if not items:
            print(f"{lo:.1f}-{hi:.1f} {0:>6d} {'-':>8s} {'-':>9s} {'-':>7s}")
            continue
        mean_pred = sum(p for p, _ in items) / len(items)
        observed = sum(y for _, y in items) / len(items)
        gap = observed - mean_pred
        ece += (len(items) / n) * abs(gap)
        print(f"{lo:.1f}-{hi:.1f} {len(items):>6d} {mean_pred:>8.3f} {observed:>9.3f} {gap:>+7.3f}")

    print(f"\nBrier score:   {brier:.4f}   (lower is better; 0.25 = always guess 0.5)")
    print(f"Log loss:      {log_loss:.4f}   (lower is better)")
    print(f"ECE:           {ece:.4f}   (expected calibration error; lower is better)")
    verdict = "well calibrated" if ece < 0.03 else "miscalibrated (detected)"
    print(f"Verdict:       {verdict}")


if __name__ == "__main__":
    main()
