# Copyright: Crux contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
"""Seed a demo Crux deck into the desktop profile collection so the dashboard
shows populated scores AND the decision-chain / cram-adjacency feature is
demonstrable.

Each topology skill is modeled as a DECISION CHAIN of linked flashcards
(problem -> problem-type -> the move that solves it), tagged with a shared
`chain::c<N>` tag plus a `step::<i>` tag and the `move::<type>` tag. The cram
session pulls the most dangerous cards AND their chain-mates (adjacent steps).

The script is deterministic: it removes any prior demo deck and resets recorded
exam attempts, so re-running gives the same populated state instead of piling up
duplicates.

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

COL_PATH = os.path.join(os.environ["APPDATA"], "Anki2", "User 1", "collection.anki2")
DECK_NAME = "Crux Topology"
LEGACY_DECK_NAMES = ["TopGRE Topology"]
PERF_KEY = "topgrePerf"

# Each chain: (move_type, [ (front, back) for step 1..N ]) modeling
# problem -> recognize type -> route to the move -> execute. Content is real
# point-set topology at GRE Mathematics Subject Test level.
CHAINS: list[tuple[str, list[tuple[str, str]]]] = [
    # ---- compactness -------------------------------------------------------
    ("compactness", [
        ("Problem: the image of a compact set under a continuous map. What TYPE?", "A compactness-preservation problem."),
        ("For 'continuous image of compact', which MOVE?", "Continuous image of a compact set is compact."),
        ("Execute: f continuous, K compact. Show f(K) compact.", "Cover f(K); pull back to a cover of K; take a finite subcover; push forward."),
    ]),
    ("compactness", [
        ("Problem: a closed subset C of a compact space K. Is C compact? What TYPE?", "A compactness-inheritance problem."),
        ("Which MOVE handles a closed subset of a compact space?", "A closed subset of a compact space is compact."),
        ("Execute: given an open cover of C.", "Add the open set X minus C; get a finite subcover of K; drop that one set."),
    ]),
    ("compactness", [
        ("Problem: is a subset of R^n compact? What TYPE?", "A Heine-Borel classification problem."),
        ("Which MOVE decides compactness in R^n?", "Heine-Borel: in R^n, compact iff closed and bounded."),
        ("Execute: check the two conditions.", "Show the set is closed and bounded, then conclude compact."),
    ]),
    ("compactness", [
        ("Problem: does a continuous real function on [a,b] attain a maximum? What TYPE?", "An extreme-value / compactness problem."),
        ("Which MOVE guarantees a max and min?", "Continuous image of a compact set is compact, hence closed and bounded in R."),
        ("Execute: conclude for f on [a,b].", "f([a,b]) is compact in R, so it contains its sup and inf; the max and min are attained."),
    ]),
    # ---- separation --------------------------------------------------------
    ("separation", [
        ("Problem: 'a compact subset of a Hausdorff space is ___'. What TYPE?", "A separation / compact-in-Hausdorff problem."),
        ("Which MOVE handles compact-in-Hausdorff?", "Compact subsets of Hausdorff spaces are closed."),
        ("Execute: separate a point p from compact K.", "For each k, take disjoint opens; finite subcover; intersect to get a neighborhood of p missing K."),
    ]),
    ("separation", [
        ("Problem: two distinct points in a Hausdorff space. What can you build? What TYPE?", "A Hausdorff separation problem."),
        ("Which MOVE is the definition you invoke?", "Hausdorff: distinct points have disjoint open neighborhoods."),
        ("Execute: use it to show limits are unique.", "If a net had two limits, separate them by disjoint opens for a contradiction."),
    ]),
    ("separation", [
        ("Problem: is every metric space Hausdorff? What TYPE?", "A metric-to-separation problem."),
        ("Which MOVE proves it?", "Use open balls of radius d(x,y)/2 around each point."),
        ("Execute: show the two balls are disjoint.", "Any common point would violate the triangle inequality."),
    ]),
    # ---- homeomorphism -----------------------------------------------------
    ("homeomorphism", [
        ("Problem: are (0,1) and [0,1] homeomorphic? What TYPE?", "A topological-invariant problem."),
        ("Which MOVE decides it?", "Compactness is a topological invariant; [0,1] is compact, (0,1) is not."),
        ("Execute: conclude.", "No homeomorphism exists."),
    ]),
    ("homeomorphism", [
        ("Problem: are R and R^2 homeomorphic? What TYPE?", "A remove-a-point invariant problem."),
        ("Which MOVE distinguishes them?", "Removing a point disconnects R but not R^2; connectedness of the complement is invariant."),
        ("Execute: conclude.", "R minus a point is disconnected, R^2 minus a point is connected, so they are not homeomorphic."),
    ]),
    ("homeomorphism", [
        ("Problem: to show two spaces are NOT homeomorphic, what do you look for? What TYPE?", "An invariant-checklist problem."),
        ("Which MOVE / checklist applies?", "Find a topological invariant that differs (compactness, connectedness, number of components, Euler characteristic)."),
        ("Execute: pick one invariant that differs.", "Exhibit one property preserved by homeomorphism that one space has and the other lacks."),
    ]),
    # ---- connectedness -----------------------------------------------------
    ("connectedness", [
        ("Problem: image of a connected set under a continuous map. What TYPE?", "A connectedness-preservation problem."),
        ("Which MOVE?", "Continuous image of a connected set is connected."),
        ("Execute: split f(X) into two opens.", "Pull back to a disconnection of X; contradiction."),
    ]),
    ("connectedness", [
        ("Problem: which subsets of R are connected? What TYPE?", "A classification-of-connected-sets problem."),
        ("Which MOVE / fact?", "The connected subsets of R are exactly the intervals."),
        ("Execute: show a non-interval is disconnected.", "If a<c<b are in the set but c is not, split by (-inf,c) and (c,inf)."),
    ]),
    ("connectedness", [
        ("Problem: a path-connected space. Is it connected? What TYPE?", "A path-connected-implies-connected problem."),
        ("Which MOVE?", "Path-connected implies connected."),
        ("Execute: assume a disconnection.", "A path between the two pieces would give a disconnection of [0,1], which is connected."),
    ]),
    ("connectedness", [
        ("Problem: prove the intermediate value theorem topologically. What TYPE?", "A connectedness-application problem."),
        ("Which MOVE?", "Continuous image of the connected interval [a,b] is connected, hence an interval."),
        ("Execute: conclude IVT.", "Since f([a,b]) is an interval containing f(a) and f(b), it contains every value between them."),
    ]),
    # ---- continuity --------------------------------------------------------
    ("continuity", [
        ("Problem: prove a map f is continuous. What TYPE?", "An open-set continuity problem."),
        ("Which MOVE?", "Show the preimage of every open set is open."),
        ("Execute: given open V, describe f^-1(V).", "Show it is open in the domain topology."),
    ]),
    ("continuity", [
        ("Problem: f: X->Y and g: Y->Z continuous. Is g of f continuous? What TYPE?", "A composition-of-continuous problem."),
        ("Which MOVE?", "Composition of continuous maps is continuous."),
        ("Execute: check a preimage.", "(g of f)^-1(W) = f^-1(g^-1(W)), open as a preimage of an open set."),
    ]),
    ("continuity", [
        ("Problem: f defined piecewise on two closed sets that cover X. Continuous? What TYPE?", "A pasting-lemma problem."),
        ("Which MOVE?", "Pasting lemma: if X = A union B with A, B closed and the pieces agree on the overlap and are each continuous, f is continuous."),
        ("Execute: verify the hypotheses.", "Check A, B closed, both restrictions continuous, and they match on A intersect B."),
    ]),
    # ---- bases-subbases ----------------------------------------------------
    ("bases-subbases", [
        ("Problem: define a topology from a small family of sets. What TYPE?", "A basis/subbasis-generation problem."),
        ("Which MOVE?", "Take the family as a subbasis: finite intersections, then arbitrary unions."),
        ("Execute: check the basis criterion.", "Every point of an intersection of two basis sets lies in a basis set inside it."),
    ]),
    ("bases-subbases", [
        ("Problem: is a family B a basis for a topology? What TYPE?", "A basis-criterion problem."),
        ("Which MOVE?", "B is a basis iff it covers X and for x in B1 cap B2 there is B3 with x in B3 subset of B1 cap B2."),
        ("Execute: verify the two conditions.", "Check the cover condition and the intersection-refinement condition."),
    ]),
    ("bases-subbases", [
        ("Problem: describe open sets in a product X x Y. What TYPE?", "A product-topology basis problem."),
        ("Which MOVE?", "Basis for the product = products U x V of opens; general opens are unions of these."),
        ("Execute: write a basic open set.", "U x V with U open in X and V open in Y."),
    ]),
    # ---- interior-closure-boundary ----------------------------------------
    ("interior-closure-boundary", [
        ("Problem: compute the boundary of A. What TYPE?", "A closure/interior/boundary problem."),
        ("Which MOVE?", "Boundary = closure minus interior."),
        ("Execute: find closure and interior, subtract.", "The boundary is what remains."),
    ]),
    ("interior-closure-boundary", [
        ("Problem: compute the closure of A. What TYPE?", "A closure-via-limit-points problem."),
        ("Which MOVE?", "Closure = A union its limit points; equivalently the smallest closed set containing A."),
        ("Execute: test a candidate point x.", "x is in the closure iff every open neighborhood of x meets A."),
    ]),
    ("interior-closure-boundary", [
        ("Problem: is A dense in X? What TYPE?", "A denseness problem."),
        ("Which MOVE?", "A is dense iff its closure is all of X, iff every nonempty open set meets A."),
        ("Execute: check Q in R.", "Every open interval contains a rational, so Q is dense in R."),
    ]),
    # ---- open-closed-sets --------------------------------------------------
    ("open-closed-sets", [
        ("Problem: is this set open, closed, both, or neither? What TYPE?", "An open/closed classification problem."),
        ("Which MOVE?", "A set is closed iff it equals its closure; open iff it equals its interior; clopen if both."),
        ("Execute: compare the set to its closure/interior.", "Classify accordingly."),
    ]),
    ("open-closed-sets", [
        ("Problem: which set operations preserve openness? What TYPE?", "A topology-axioms problem."),
        ("Which MOVE / axioms?", "Arbitrary unions and finite intersections of open sets are open; the dual holds for closed sets."),
        ("Execute: apply to an infinite intersection.", "An infinite intersection of opens need not be open, e.g. intersection of (-1/n, 1/n) is {0}."),
    ]),
    # ---- examples / counterexamples ---------------------------------------
    ("examples", [
        ("Problem: is every connected space path-connected? What TYPE?", "A counterexample-arsenal problem."),
        ("Which MOVE / example?", "The topologist's sine curve: connected but not path-connected."),
        ("Execute: state why it works.", "Its closure is connected; no path joins the two pieces."),
    ]),
    ("examples", [
        ("Problem: extreme topologies on any set X. What TYPE?", "A canonical-examples problem."),
        ("Which MOVE / examples?", "Discrete (every subset open) and indiscrete (only empty and X)."),
        ("Execute: note continuity behavior.", "Every map out of a discrete space is continuous; every map into an indiscrete space is continuous."),
    ]),
    ("examples", [
        ("Problem: a topology where the closed sets are the finite sets plus X. What TYPE?", "A cofinite-topology problem."),
        ("Which MOVE / example?", "The cofinite topology; it is compact and T1 but not Hausdorff on an infinite set."),
        ("Execute: check T1 vs Hausdorff.", "Points are closed (T1), but any two nonempty opens intersect, so it is not Hausdorff."),
    ]),
    ("examples", [
        ("Problem: R with basis of half-open intervals [a,b). What TYPE?", "A Sorgenfrey-line problem."),
        ("Which MOVE / example?", "The lower-limit topology (Sorgenfrey line): finer than the standard topology."),
        ("Execute: note a key property.", "It is separable and first-countable but not second-countable, and [a,b) is clopen."),
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


def _remove_deck_if_present(col: Collection, name: str) -> None:
    existing = col.decks.by_name(name)
    if existing:
        col.decks.remove([existing["id"]])


def main() -> None:
    col = Collection(COL_PATH)
    try:
        try:
            col.set_config_bool(Config.Bool.FSRS, True)
        except Exception as exc:
            print("FSRS enable note:", exc)
            col.set_config("fsrs", True)

        # Deterministic clean slate: drop prior demo decks and recorded attempts.
        for name in [DECK_NAME, *LEGACY_DECK_NAMES]:
            _remove_deck_if_present(col, name)
        try:
            col.remove_config(PERF_KEY)
        except Exception as exc:
            print("attempt reset note:", exc)

        did = col.decks.id(DECK_NAME)
        col.decks.set_current(did)
        try:
            conf = col.decks.config_dict_for_deck_id(did)
            conf["new"]["perDay"] = 999
            conf["rev"]["perDay"] = 999
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
            for _ in range(6):
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

        from anki import readiness

        triaged = readiness.reorder_new_by_triage(col, f'deck:"{DECK_NAME}"')
        print(
            f"seeded {total} cards in {len(CHAINS)} chains | reviewed {reviewed} | "
            f"attempts {attempts} | triaged {triaged}"
        )
    finally:
        col.close()


if __name__ == "__main__":
    main()
