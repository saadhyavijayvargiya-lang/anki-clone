# Copyright: TopGRE contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
"""TopGRE AI card generation + safety checker (challenge 7f).

Pipeline (all AI output is traceable + gated):
  1. generate_cards(source) -> candidate cards, each citing an exact source quote
     from ONE named source (traceability requirement).
  2. check_cards(cards, gold) -> classifies each as correct-useful / wrong /
     correct-but-bad against a gold set, with a cutoff set BEFORE looking at
     results; cards that fail are blocked.
  3. Runs with AI OFF: if no API key is set, generation is disabled and the app
     still functions (scores come from the non-AI engine).

WHERE TO PUT YOUR API KEY: see topgre_eval/AI_SETUP.md. In short, set the
environment variable OPENAI_API_KEY (do NOT hardcode/commit it).

Usage:
  out\\pyenv\\Scripts\\python topgre_eval\\ai_cardgen.py --source path\\to\\chapter.txt
  out\\pyenv\\Scripts\\python topgre_eval\\ai_cardgen.py --check-only cards.json
"""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path

HERE = Path(__file__).parent

# ---- Configuration -------------------------------------------------------
# The API key is read from this environment variable. See AI_SETUP.md.
API_KEY_ENV = "OPENAI_API_KEY"
# Model + provider are overridable via env so no code edit is needed.
MODEL = os.environ.get("TOPGRE_AI_MODEL", "gpt-4o-mini")
# Pass cutoff is fixed BEFORE looking at results (7f requirement).
PASS_CUTOFF = 0.80

MOVE_TYPES = [
    "open-closed-sets", "interior-closure-boundary", "bases-subbases",
    "continuity", "homeomorphism", "compactness", "connectedness",
    "separation", "examples",
]


def ai_enabled() -> bool:
    """True only if an API key is configured. Everything else runs AI-off."""
    return bool(os.environ.get(API_KEY_ENV))


# ---- 1. Generation (requires the key) ------------------------------------
def generate_cards(source_text: str, source_name: str, n: int = 50) -> list[dict]:
    if not ai_enabled():
        raise RuntimeError(
            f"AI is OFF: environment variable {API_KEY_ENV} is not set. "
            "See topgre_eval/AI_SETUP.md."
        )
    try:
        from openai import OpenAI  # lazy import so AI-off needs no dependency
    except ImportError as e:
        raise RuntimeError(
            "The 'openai' package is not installed. Run: "
            "out\\pyenv\\Scripts\\python -m pip install openai"
        ) from e

    client = OpenAI()  # reads OPENAI_API_KEY from the environment
    prompt = (
        "You generate GRE Mathematics Subject Test topology practice cards from "
        "ONE source. Teach the proof MOVE a problem routes to, not just facts.\n"
        f"Allowed move_type values: {MOVE_TYPES}.\n"
        f"Source name: {source_name}\nSource text:\n\"\"\"\n{source_text}\n\"\"\"\n"
        f"Return JSON: {{\"cards\": [{{\"front\", \"back\", \"move_type\", "
        f"\"source_quote\"}}]}} with up to {n} cards. Every card MUST include an "
        "exact source_quote copied verbatim from the source (traceability), and "
        "use only facts present in the source."
    )
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
    )
    data = json.loads(resp.choices[0].message.content)
    cards = data.get("cards", [])
    # Enforce traceability: drop any card whose source_quote isn't in the source.
    verified = [c for c in cards if c.get("source_quote", "") and c["source_quote"] in source_text]
    for c in verified:
        c["source_name"] = source_name
    return verified


# ---- 2. Checker (runs offline on any cards) ------------------------------
def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s]", " ", s.lower())).strip()


def _tokens(s: str) -> set[str]:
    return set(_norm(s).split())


def _overlap(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def check_cards(cards: list[dict], gold: list[dict]) -> dict:
    """Classify each card vs a gold Q/A set. Returns counts + pass/fail.

    - correct_useful: answer matches a gold answer for a similar question, has a
      source_quote (traceable), and isn't trivial/duplicate.
    - wrong: no gold answer matches (potential wrong fact - worse than no card).
    - correct_but_bad: matches gold but is vague/trivial/duplicate.
    """
    seen: set[str] = set()
    correct_useful = wrong = correct_but_bad = 0
    blocked: list[dict] = []
    for card in cards:
        front = card.get("front", "")
        back = card.get("back", "")
        traceable = bool(card.get("source_quote"))
        # best-matching gold item by question similarity
        best = max(gold, key=lambda g: _overlap(front, g["q"]), default=None)
        answer_ok = best is not None and _overlap(back, best["a"]) >= 0.5
        key = _norm(front)
        duplicate = key in seen
        seen.add(key)
        trivial = len(_tokens(back)) < 2

        if not answer_ok:
            wrong += 1
            blocked.append(card)
        elif duplicate or trivial or not traceable:
            correct_but_bad += 1
            blocked.append(card)
        else:
            correct_useful += 1

    total = max(len(cards), 1)
    pass_rate = correct_useful / total
    return {
        "total": len(cards),
        "correct_useful": correct_useful,
        "wrong": wrong,
        "correct_but_bad": correct_but_bad,
        "pass_rate": pass_rate,
        "cutoff": PASS_CUTOFF,
        "passed": pass_rate >= PASS_CUTOFF,
        "blocked_count": len(blocked),
        "accepted_cards": [c for c in cards if c not in blocked],
    }


# ---- 3. Baseline to beat (keyword move-type classifier) ------------------
def keyword_baseline_move_type(text: str) -> str:
    """Simple keyword baseline the AI must beat on held-out labelled problems."""
    keywords = {
        "compactness": ["compact", "cover", "finite subcover", "sequential"],
        "connectedness": ["connected", "path", "component"],
        "separation": ["hausdorff", "t2", "separation", "normal", "regular"],
        "continuity": ["continuous", "preimage", "open set"],
        "homeomorphism": ["homeomorph", "invariant"],
        "examples": ["counterexample", "discrete", "cofinite", "sine curve"],
    }
    t = _norm(text)
    best, score = "examples", 0
    for mt, words in keywords.items():
        hits = sum(1 for w in words if w in t)
        if hits > score:
            best, score = mt, hits
    return best


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", help="path to ONE source text file")
    ap.add_argument("--name", default="source", help="named source label")
    ap.add_argument("--n", type=int, default=50)
    ap.add_argument("--check-only", help="path to a cards.json to check without generating")
    args = ap.parse_args()

    gold_path = HERE / "sample_data" / "gold.jsonl"
    gold = [json.loads(x) for x in gold_path.read_text(encoding="utf-8-sig").splitlines() if x.strip()]

    if args.check_only:
        cards = json.loads(Path(args.check_only).read_text(encoding="utf-8-sig"))
    elif args.source:
        if not ai_enabled():
            print(f"AI is OFF ({API_KEY_ENV} not set). See AI_SETUP.md. Nothing generated.")
            return
        text = Path(args.source).read_text(encoding="utf-8")
        cards = generate_cards(text, args.name, args.n)
        (HERE / "generated_cards.json").write_text(json.dumps(cards, indent=2), encoding="utf-8")
        print(f"generated {len(cards)} traceable cards -> generated_cards.json")
    else:
        print("Provide --source <file> to generate, or --check-only <cards.json>.")
        return

    result = check_cards(cards, gold)
    print(json.dumps({k: v for k, v in result.items() if k != "accepted_cards"}, indent=2))
    print("PASS" if result["passed"] else "FAIL (cards below cutoff are blocked)")


if __name__ == "__main__":
    main()
