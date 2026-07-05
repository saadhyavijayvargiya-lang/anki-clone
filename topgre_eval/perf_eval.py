# Copyright: Crux contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
"""Section 9 step 2: held-out evaluation of the Performance model.

Seeds a temp collection with exam-style attempts (per-move accuracy so there is
real signal), then calls the engine's held-out evaluator
(evaluate_performance_model), which splits the attempts into train/test, fits the
per-move Performance model on train, and compares it against a simpler baseline
on the held-out test set (log loss + accuracy).

Self-contained: uses its own temp collection, no build or profile needed.
  out\\pyenv\\Scripts\\python topgre_eval\\perf_eval.py
"""

from __future__ import annotations

import os
import random
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in ("pylib", "qt", "out/pylib", "out/qt"):
    sys.path.insert(0, os.path.join(ROOT, _p))

from anki.collection import Collection  # noqa: E402

# Per-move true accuracy: gives the model something to learn that a global-mean
# baseline cannot capture (moves differ), so beating the baseline is meaningful.
MOVE_ACC = {
    "compactness": 0.30,
    "separation": 0.35,
    "homeomorphism": 0.45,
    "connectedness": 0.50,
    "bases-subbases": 0.55,
    "interior-closure-boundary": 0.60,
    "continuity": 0.70,
    "open-closed-sets": 0.75,
    "examples": 0.85,
}


def main() -> None:
    rng = random.Random(3)
    tmp = tempfile.mkdtemp()
    col = Collection(os.path.join(tmp, "perf.anki2"))
    try:
        attempts = 0
        for move, acc in MOVE_ACC.items():
            for _ in range(12):
                col._backend.record_exam_attempt(
                    move_type=move,
                    correct=rng.random() < acc,
                    milliseconds=rng.randint(60000, 180000),
                )
                attempts += 1
        print(f"seeded {attempts} exam attempts across {len(MOVE_ACC)} move-types\n")

        r = col._backend.evaluate_performance_model(search="")
        print("held-out performance evaluation:")
        print(f"  available:         {r.available}")
        print(f"  train / test:      {r.train_count} / {r.test_count}")
        print(f"  model    log loss: {r.model_log_loss:.4f}")
        print(f"  baseline log loss: {r.baseline_log_loss:.4f}")
        print(f"  model    accuracy: {r.model_accuracy:.3f}")
        print(f"  baseline accuracy: {r.baseline_accuracy:.3f}")
        print(f"  beats baseline:    {r.beats_baseline}")
        if r.note:
            print(f"  note:              {r.note}")
    finally:
        col.close()


if __name__ == "__main__":
    main()
