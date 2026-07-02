# Copyright: TopGRE contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
"""Challenge 7d - the paraphrase test (the headline test of the spiky thesis).

For each card we have: the student's recall on the card itself, and their
accuracy on 2 reworded exam-style questions testing the same idea. If recall and
reworded accuracy are basically the same, the "performance" signal is just the
"memory" signal in disguise and the bridge hasn't been built. We report the GAP.

Reads sample_data/paraphrase.csv with columns:
  card_id, move_type, recall, reworded_accuracy   (recall/accuracy in [0,1])

Usage:
  out\\pyenv\\Scripts\\python topgre_eval\\paraphrase_test.py
"""

from __future__ import annotations

import csv
import statistics
from pathlib import Path

HERE = Path(__file__).parent


def main() -> None:
    rows = []
    with open(HERE / "sample_data" / "paraphrase.csv", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows.append(row)

    recall = [float(r["recall"]) for r in rows]
    perf = [float(r["reworded_accuracy"]) for r in rows]
    gaps = [rc - pf for rc, pf in zip(recall, perf)]

    mean_recall = statistics.mean(recall)
    mean_perf = statistics.mean(perf)
    mean_gap = statistics.mean(gaps)

    print(f"cards: {len(rows)}")
    print(f"mean card recall:          {mean_recall:.3f}")
    print(f"mean reworded accuracy:    {mean_perf:.3f}")
    print(f"memory->performance GAP:   {mean_gap:+.3f}  (recall - reworded)")
    print()
    # Per move-type gap (which moves transfer worst to new questions?)
    by_move: dict[str, list[float]] = {}
    for r, g in zip(rows, gaps):
        by_move.setdefault(r["move_type"], []).append(g)
    print("gap by move-type (higher = memorized but can't apply):")
    for mt, gs in sorted(by_move.items(), key=lambda kv: -statistics.mean(kv[1])):
        print(f"  {mt:26s} {statistics.mean(gs):+.3f}  (n={len(gs)})")

    print()
    if mean_gap > 0.1:
        print(
            "RESULT: a real gap exists - students recall the card but miss reworded "
            "questions. Performance is NOT just memory; the bridge is measurable."
        )
    else:
        print(
            "RESULT: gap is small - the performance model may be copying the memory "
            "model. Reported honestly (this would weaken the thesis)."
        )


if __name__ == "__main__":
    main()
