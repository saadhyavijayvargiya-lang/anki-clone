# Copyright: Crux contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
"""Challenge 7f runner: generate cards from ONE named source through the working
AI proxy, enforce source-quote traceability, then run them through the checker
against the 50-pair gold set and report the three counts.

Uses qt/aqt/crux_ai.py (the verified proxy path) for generation, so it works
with the same env the desktop app uses (OPENAI_BASE_URL / OPENAI_API_KEY, or
CRUX_AI_PROXY_URL / CRUX_AI_PROXY_TOKEN). If AI is unavailable, it falls back to
a bundled candidate set so the checker still runs and reports counts.

Usage:
  out\\pyenv\\Scripts\\python topgre_eval\\ai_cardcheck.py
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parent

_spec = importlib.util.spec_from_file_location(
    "crux_ai", str(ROOT / "qt" / "aqt" / "crux_ai.py")
)
crux_ai = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(crux_ai)

sys.path.insert(0, str(HERE))
import ai_cardgen  # noqa: E402


def generate_via_proxy(source: str, source_name: str, n: int = 50) -> list[dict]:
    if not crux_ai.ai_available():
        return []
    system = (
        "You generate GRE Mathematics Subject Test topology practice cards from "
        "ONE source. Teach the proof MOVE a problem routes to, not just facts. "
        f"Allowed move_type values: {ai_cardgen.MOVE_TYPES}. "
        "Keep each 'back' a short flashcard answer (a few words naming the move or "
        "fact, not a paragraph). "
        "Reply with ONLY a JSON object of the form "
        '{"cards":[{"front":"","back":"","move_type":"","source_quote":""}]} '
        "and nothing else. Every source_quote MUST be copied verbatim from the "
        "source (for traceability), and use only facts present in the source."
    )
    user = (
        f"Source name: {source_name}\nSource:\n{source}\n\n"
        f"Generate {n} cards, one per distinct fact in the source, concise answers."
    )
    text = crux_ai.chat(system, user, timeout=60, max_tokens=3000)
    if not text:
        return []
    t = text.strip()
    if t.startswith("```"):
        t = t.strip("`")
        if t.lower().startswith("json"):
            t = t[4:]
    lo, hi = t.find("{"), t.rfind("}")
    if lo == -1 or hi == -1:
        return []
    try:
        cards = json.loads(t[lo : hi + 1]).get("cards", [])
    except Exception:
        return []
    # Enforce traceability: drop any card whose source_quote isn't in the source.
    verified = [
        c for c in cards if c.get("source_quote") and c["source_quote"] in source
    ]
    for c in verified:
        c["source_name"] = source_name
    return verified


def main() -> None:
    source = (HERE / "sample_data" / "source_topology.txt").read_text(encoding="utf-8")
    gold = [
        json.loads(x)
        for x in (HERE / "sample_data" / "gold.jsonl")
        .read_text(encoding="utf-8-sig")
        .splitlines()
        if x.strip()
    ]

    # The model returns a modest batch per call; accumulate unique cards over a
    # few calls (temperature gives variety) to build a fuller set.
    seen: set[str] = set()
    cards: list[dict] = []
    for _ in range(6):
        for c in generate_via_proxy(source, "Point-Set Topology: Selected Results"):
            key = ai_cardgen._norm(c.get("front", ""))
            if key and key not in seen:
                seen.add(key)
                cards.append(c)
    origin = "AI via proxy"
    if not cards:
        fallback = HERE / "sample_data" / "candidate_cards.json"
        if fallback.exists():
            cards = json.loads(fallback.read_text(encoding="utf-8-sig"))
            origin = "bundled candidate set (AI unavailable)"
        else:
            print("AI unavailable and no fallback candidate set present.")
            return

    print(f"source: Point-Set Topology: Selected Results")
    print(f"cards from: {origin}   generated/loaded: {len(cards)}   gold pairs: {len(gold)}\n")

    result = ai_cardgen.check_cards(cards, gold)
    for k in ("total", "correct_useful", "wrong", "correct_but_bad", "pass_rate", "cutoff", "passed", "blocked_count"):
        print(f"  {k}: {result[k]}")
    print("\n" + ("PASS: enough correct-useful cards" if result["passed"]
                  else "FAIL: below cutoff, failing cards are blocked"))


if __name__ == "__main__":
    main()
