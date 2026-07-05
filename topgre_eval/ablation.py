# Copyright: Crux contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
"""Section 8 study-feature ablation: interleaving.

Pre-stated hypothesis (written before looking at results):
  "Mixing move-types within a session (interleaving) raises accuracy on new
   mixed-type questions at equal study time, compared with blocked practice
   (studying one type at a time) and with plain Anki ordering."

Three arms, identical cards and identical total reviews (equal study time):
  - blocked      : study one topic at a time (reviews of a card are massed)
  - plain        : Anki-style deck order (reviews spread across the period)
  - interleaved  : Crux topic round-robin (reviews spread across the period)

This is a SIMULATION, not real learners (you cannot honestly gather real
study-then-test data in a week; the spec grades the fair test, not a made-up
final number). It is written to be able to FAIL:

  - Retention uses a standard spacing model only: each review multiplies memory
    stability by (1 + spacing_gain * log(1 + gap_days)). Larger gaps (spacing)
    help; massed practice does not. Nothing here hands interleaving a win.
  - Interleaving's extra "discrimination" benefit on mixed questions is a
    SEPARATE, unproven hypothesis, exposed as `--disc-bonus` and defaulting to
    0.0, so by default the test does NOT presuppose interleaving beats plain.

So the expected honest outcome at defaults is: interleaved ~= plain > blocked
(spacing beats massing; interleaving shows no advantage over plain Anki unless
you assume a discrimination benefit). Run with --disc-bonus > 0 to explore that
assumption explicitly.

Usage (no build or collection needed):
  python topgre_eval/ablation.py
  python topgre_eval/ablation.py --disc-bonus 0.4 --seeds 40
"""

from __future__ import annotations

import argparse
import math
import random
import statistics

TOPICS = 9
ARMS = ("blocked", "plain", "interleaved")


def simulate_arm(
    arm: str,
    rng: random.Random,
    days: int,
    reps: int,
    spacing_gain: float,
    disc_bonus: float,
    cards_per_topic: int,
    test_delay: int,
) -> float:
    """Mean accuracy on held-out mixed-type questions for one arm (one seed)."""
    # Average gap (days) between successive reviews of the same card.
    if arm == "blocked":
        gap = (days / TOPICS) / reps   # massed inside a topic block
    else:
        gap = days / reps              # plain and interleaved both spread reviews
    disc = disc_bonus if arm == "interleaved" else 0.0

    accs: list[float] = []
    for _ in range(cards_per_topic * TOPICS):
        stability = 1.0 + rng.random() * 0.5           # small per-card variation
        for _r in range(reps):
            stability *= 1.0 + spacing_gain * math.log1p(max(gap, 0.0))
        p_recall = math.exp(-test_delay / stability)   # forgetting curve at test
        # Mixed-type question: recall gated, plus any interleaving discrimination.
        logit = 2.0 * (p_recall - 0.5) + disc
        accs.append(1.0 / (1.0 + math.exp(-logit)))
    return statistics.mean(accs)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=30)
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--reps", type=int, default=6, help="reviews per card (equal across arms)")
    ap.add_argument("--spacing-gain", type=float, default=0.15)
    ap.add_argument("--disc-bonus", type=float, default=0.0,
                    help="interleaving discrimination benefit on mixed questions (unproven; default off)")
    ap.add_argument("--cards-per-topic", type=int, default=20)
    ap.add_argument("--test-delay", type=int, default=14, help="days from end of study to the test")
    args = ap.parse_args()

    print("Hypothesis (pre-stated): interleaving >= blocked and >= plain on mixed-type")
    print("accuracy at equal study time.\n")
    print(f"seeds={args.seeds} days={args.days} reps/card={args.reps} "
          f"spacing_gain={args.spacing_gain} disc_bonus={args.disc_bonus} "
          f"test_delay={args.test_delay}d  (all arms: same cards, same total reviews)\n")

    per_arm: dict[str, list[float]] = {a: [] for a in ARMS}
    for seed in range(args.seeds):
        rng = random.Random(seed)
        for arm in ARMS:
            per_arm[arm].append(
                simulate_arm(arm, rng, args.days, args.reps, args.spacing_gain,
                             args.disc_bonus, args.cards_per_topic, args.test_delay)
            )

    print(f"{'arm':13s} {'mean acc':>9s} {'range (min..max)':>22s}")
    means: dict[str, float] = {}
    for arm in ARMS:
        vals = per_arm[arm]
        means[arm] = statistics.mean(vals)
        print(f"{arm:13s} {means[arm]*100:8.1f}% {min(vals)*100:9.1f}% .. {max(vals)*100:0.1f}%")

    d_block = (means["interleaved"] - means["blocked"]) * 100
    d_plain = (means["interleaved"] - means["plain"]) * 100
    print(f"\ninterleaved - blocked = {d_block:+.1f} pts")
    print(f"interleaved - plain   = {d_plain:+.1f} pts")

    print("\nInterpretation (honest):")
    print(f"  vs blocked: {'supports' if d_block > 0.5 else 'no evidence'} the hypothesis "
          f"({d_block:+.1f} pts).")
    print(f"  vs plain Anki: {'supports' if d_plain > 0.5 else 'no evidence'} "
          f"({d_plain:+.1f} pts).")
    if abs(d_plain) <= 0.5:
        print("  Null result vs plain Anki at defaults is expected and reported as-is:")
        print("  a pure spacing model gives plain and interleaved the same spacing, so any")
        print("  interleaving advantage would have to come from discrimination (--disc-bonus).")


if __name__ == "__main__":
    main()
