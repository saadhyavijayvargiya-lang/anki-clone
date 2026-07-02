# Copyright: TopGRE contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
"""Challenge 7e - the leakage check.

Scans training data for any test item, or a near-copy of one, that slipped in.
Leaked data makes a model look smarter than it is, so this must come back clean.

Detection:
  - exact match after normalization (lowercase, strip punctuation, collapse ws)
  - near-duplicate via token Jaccard similarity >= THRESHOLD

Usage:
  out\\pyenv\\Scripts\\python topgre_eval\\leakage_check.py
Exit code is non-zero if leakage is found (so it can gate CI).
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

THRESHOLD = 0.8
HERE = Path(__file__).parent


def normalize(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def tokens(text: str) -> set[str]:
    return set(normalize(text).split())


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def load(path: Path) -> list[str]:
    items = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        obj = json.loads(line)
        items.append(f"{obj.get('q', '')} {obj.get('a', '')}".strip())
    return items


def main() -> int:
    train = load(HERE / "sample_data" / "train.jsonl")
    test = load(HERE / "sample_data" / "test.jsonl")
    train_norm = {normalize(t) for t in train}
    train_tok = [tokens(t) for t in train]

    leaks = []
    for t in test:
        if normalize(t) in train_norm:
            leaks.append((t, "exact/normalized match", 1.0))
            continue
        tt = tokens(t)
        best = max((jaccard(tt, tr) for tr in train_tok), default=0.0)
        if best >= THRESHOLD:
            leaks.append((t, "near-duplicate", best))

    print(f"train items: {len(train)}   test items: {len(test)}")
    print(f"similarity threshold: {THRESHOLD}")
    if leaks:
        print(f"\nLEAKAGE FOUND ({len(leaks)}):")
        for text, why, score in leaks:
            print(f"  [{why} {score:.2f}] {text[:80]}")
        print("\nRESULT: DIRTY - remove leaked items before training.")
        return 1
    print("\nRESULT: CLEAN - no test item or near-copy found in training data.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
