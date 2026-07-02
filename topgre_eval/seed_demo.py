# Copyright: TopGRE contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
"""Seed a demo TopGRE deck into the desktop profile collection so the dashboard
shows populated scores AND the decision-chain / cram-adjacency feature is
demonstrable.

Each topology skill is modeled as a DECISION CHAIN of linked flashcards
(problem -> problem-type -> the move that solves it), tagged with a shared
`chain::c<N>` tag plus a `step::<i>` tag and the `move::<type>` tag. The cram
session pulls the most dangerous cards AND their chain-mates (adjacent steps).

Run with the app CLOSED:
  out\\pyenv\\Scripts\\python topgre_eval\\seed_demo.py
"""

from __future__ import annotations

import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in ("pylib", "out/pylib"):
    sys.path.insert(0, os.path.join(ROOT, _p))

from anki.collection import Collection, Config  # noqa: E402
from anki import readiness  # noqa: E402

COL_PATH = os.path.join(os.environ["APPDATA"], "Anki2", "User 1", "collection.anki2")

# Each chain: (move_type, [ (front, back) for step 1..N ]) modeling
# problem -> recognize type -> route to move -> execute.
CHAINS: list[tuple[str, list[tuple[str, str]]]] = [
    ("compactness", [
        ("Problem: the image of a compact set under a continuous map. What TYPE?", "A compactness-preservation problem."),
        ("For 'continuous image of compact', which MOVE?", "Continuous image of a compact set is compact."),
        ("Execute: f cts, K compact. Show f(K) compact.", "Cover f(K); pull back to a cover of K; take a finite subcover; push forward."),
    ]),
    ("separation", [
        ("Problem: 'a compact subset of a Hausdorff space is ___'. What TYPE?", "A separation/compact-in-Hausdorff problem."),
        ("Which MOVE handles compact-in-Hausdorff?", "Compact subsets of Hausdorff spaces are closed."),
        ("Execute: separate a point p from compact K.", "For each k, disjoint opens; finite subcover; intersect to get a nbhd of p missing K."),
    ]),
    ("homeomorphism", [
        ("Problem: are (0,1) and [0,1] homeomorphic? What TYPE?", "A topological-invariant problem."),
        ("Which MOVE decides it?", "Compactness is a topological invariant; [0,1] is compact, (0,1) isn't."),
        ("Execute: conclude.", "No homeomorphism exists."),
    ]),
    ("connectedness", [
        ("Problem: image of a connected set under a continuous map. What TYPE?", "A connectedness-preservation problem."),
        ("Which MOVE?", "Continuous image of a connected set is connected."),
        ("Execute: split f(X) into two opens.", "Pull back to a disconnection of X; contradiction."),
    ]),
    ("continuity", [
        ("Problem: prove f is continuous. What TYPE?", "An open-set continuity problem."),
        ("Which MOVE?", "Show the preimage of every open set is open."),
        ("Execute: given open V, describe f^-1(V).", "Show it is open in the domain topology."),
    ]),
    ("bases-subbases", [
        ("Problem: define a topology from a small family. What TYPE?", "A basis/subbasis-generation problem."),
        ("Which MOVE?", "Take the family as a subbasis: finite intersections, then arbitrary unions."),
        ("Execute: check the basis criterion.", "Every point of an intersection of two basis sets lies in a basis set inside it."),
    ]),
    ("interior-closure-boundary", [
        ("Problem: compute the boundary of A. What TYPE?", "A closure/interior/boundary problem."),
        ("Which MOVE?", "Boundary = closure minus interior."),
        ("Execute: find closure and interior, subtract.", "The boundary is what remains."),
    ]),
    ("open-closed-sets", [
        ("Problem: is this set open, closed, both, or neither? What TYPE?", "An open/closed classification problem."),
        ("Which MOVE?", "A set is closed iff it equals its closure; open iff it equals its interior."),
        ("Execute: compare the set to its closure/interior.", "Classify accordingly (clopen if both)."),
    ]),
    ("examples", [
        ("Problem: is every connected space path-connected? What TYPE?", "A counterexample-arsenal problem."),
        ("Which MOVE/example?", "The topologist's sine curve: connected but not path-connected."),
        ("Execute: state why it works.", "Its closure is connected; no path joins the two pieces."),
    ]),
]

# Per-move-type exam accuracy used to seed attempts. Low accuracy => dangerous.
MOVE_ACCURACY = {
    "compactness": 0.30,
    "separation": 0.35,
    "homeomorphism": 0.45,
    "connectedness": 0.50,
    "bases-subbases": 0.55,
    "interior-closure-boundary": 0.60,
    "open-closed-sets": 0.75,
    "continuity": 0.70,
    "examples": 0.85,
}


def main() -> None:
    col = Collection(COL_PATH)
    try:
        try:
            col.set_config_bool(Config.Bool.FSRS, True)
        except Exception as exc:
            print("FSRS enable note:", exc)
            col.set_config("fsrs", True)

        did = col.decks.id("TopGRE Topology")
        col.decks.set_current(did)
        try:
            conf = col.decks.config_dict_for_deck_id(did)
            conf["new"]["perDay"] = 500
            conf["rev"]["perDay"] = 500
            col.decks.save(conf)
        except Exception as exc:
            print("deck limit note:", exc)

        model = col.models.by_name("Basic")
        total = 0
        for ci, (move, steps) in enumerate(CHAINS, start=1):
            for si, (front, back) in enumerate(steps, start=1):
                note = col.new_note(model)
                note["Front"] = front
                note["Back"] = back
                note.tags = [f"move::{move}", f"chain::c{ci}", f"step::{si}"]
                col.add_note(note, did)
                total += 1

        # Real reviews so Memory (FSRS) has data.
        reviewed = 0
        for _ in range(total):
            card = col.sched.getCard()
            if card is None:
                break
            col.sched.answerCard(card, 3)  # Good
            reviewed += 1

        # Exam-style attempts with per-move accuracy -> Performance + danger.
        rng = random.Random(7)
        attempts = 0
        for move, acc in MOVE_ACCURACY.items():
            for _ in range(4):
                col._backend.record_exam_attempt(
                    move_type=move,
                    correct=rng.random() < acc,
                    milliseconds=rng.randint(60000, 180000),
                )
                attempts += 1

        # Demo-friendly give-up thresholds (the real config-tunable keys).
        col.set_config("topgreMinReviews", 20)
        col.set_config("topgreMinAttempts", 20)
        col.set_config("topgreMinCoverage", 0.5)

        triaged = readiness.reorder_new_by_triage(col, 'deck:"TopGRE Topology"')
        col.save()
        print(
            f"seeded {total} cards in {len(CHAINS)} chains | reviewed {reviewed} | "
            f"attempts {attempts} | triaged {triaged}"
        )
    finally:
        col.close()


if __name__ == "__main__":
    main()
