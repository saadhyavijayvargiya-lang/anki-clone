# Copyright: TopGRE contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
"""Challenge 7h - one-command benchmark (+ section 10 speed targets).

Builds a synthetic deck and times the TopGRE engine calls, reporting
p50 / p95 / worst for each (one hand-picked number does not count).

Usage (from repo root, with the built env):
  out\\pyenv\\Scripts\\python topgre_eval\\bench.py            # 2000 cards (quick)
  out\\pyenv\\Scripts\\python topgre_eval\\bench.py --cards 50000
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in ("pylib", "qt", "out/pylib", "out/qt"):
    sys.path.insert(0, os.path.join(ROOT, _p))

from anki.collection import Collection  # noqa: E402

MOVES = [
    "compactness", "connectedness", "separation", "continuity",
    "homeomorphism", "examples", "open-closed-sets",
    "interior-closure-boundary", "bases-subbases",
]


def stats(ms: list[float]) -> tuple[float, float, float]:
    s = sorted(ms)
    n = len(s)
    return s[int(0.50 * (n - 1))], s[int(0.95 * (n - 1))], s[-1]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cards", type=int, default=2000)
    ap.add_argument("--iters", type=int, default=50)
    args = ap.parse_args()

    tmp = tempfile.mkdtemp()
    col = Collection(os.path.join(tmp, "bench.anki2"))
    model = col.models.by_name("Basic")
    did = col.decks.id("TopGRE")

    print(f"building deck: {args.cards} cards ...")
    t0 = time.time()
    for i in range(args.cards):
        note = col.new_note(model)
        note["Front"] = f"trigger {i}"
        note["Back"] = f"move {i}"
        note.tags = [f"move::{MOVES[i % len(MOVES)]}"]
        col.add_note(note, did)
    print(f"  built in {time.time() - t0:.1f}s")

    for i in range(40):
        col._backend.record_exam_attempt(
            move_type=MOVES[i % len(MOVES)], correct=(i % 3 != 0), milliseconds=1500
        )

    def bench(label: str, fn) -> None:
        fn()  # warmup
        ms = []
        for _ in range(args.iters):
            t = time.perf_counter()
            fn()
            ms.append((time.perf_counter() - t) * 1000.0)
        p50, p95, worst = stats(ms)
        print(f"{label:30s} p50={p50:8.2f}ms  p95={p95:8.2f}ms  worst={worst:8.2f}ms")

    print(f"\ntiming over {args.iters} iterations:")
    bench("points_at_stake_queue(50)", lambda: col._backend.points_at_stake_queue(search="", limit=50))
    bench("get_readiness (dashboard)", lambda: col._backend.get_readiness(search=""))
    bench("record_exam_attempt (write)", lambda: col._backend.record_exam_attempt(move_type="compactness", correct=True, milliseconds=1000))
    bench("evaluate_performance_model", lambda: col._backend.evaluate_performance_model(search=""))

    col.close()
    print("\ndone.")


if __name__ == "__main__":
    main()
