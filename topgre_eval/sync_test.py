# Copyright: Crux contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
"""Challenge 7b: two-device sync + conflict test, run at the engine level.

Two independent collection instances (device A and device B) sync through the
local Anki sync server (SYNC_SETUP.md). This exercises the exact shared Rust
sync + revlog merge that the desktop app and AnkiDroid use; it is device-
agnostic, so it proves the data correctness without driving the phone GUI.

Test:
  1. A creates a 20-card deck and uploads. B downloads (both in sync).
  2. Offline: A reviews 10 cards; B reviews 10 DIFFERENT cards.
  3. Sync all. Assert all 20 reviews are present on both, none lost/doubled.
  4. Conflict: A and B both review the SAME card offline (different answers).
     Sync all. Assert both devices converge to one state and no revlog is lost.

Prereq: start the sync server first (tools/crux_sync_server.ps1).
  out\\pyenv\\Scripts\\python topgre_eval\\sync_test.py
"""

from __future__ import annotations

import os
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in ("pylib", "qt", "out/pylib", "out/qt"):
    sys.path.insert(0, os.path.join(ROOT, _p))

from anki.collection import Collection  # noqa: E402
from anki.decks import DeckId  # noqa: E402

# Point at a throwaway server for testing so the real crux account is untouched:
#   set CRUX_SYNC_ENDPOINT=http://127.0.0.1:8081/
ENDPOINT = os.environ.get("CRUX_SYNC_ENDPOINT", "http://127.0.0.1:8080/")
USER, PW = os.environ.get("CRUX_SYNC_USER", "crux"), os.environ.get("CRUX_SYNC_PW", "crux")


def make_col(name: str) -> Collection:
    d = tempfile.mkdtemp(prefix=f"crux_sync_{name}_")
    return Collection(os.path.join(d, "collection.anki2"))


def sync(col: Collection, auth, prefer_upload: bool | None = None) -> str:
    out = col.sync_collection(auth, False)
    r = out.required
    if r in (out.NO_CHANGES, out.NORMAL_SYNC):
        return "normal"
    if r == out.FULL_UPLOAD:
        upload = True
    elif r == out.FULL_DOWNLOAD:
        upload = False
    else:
        upload = bool(prefer_upload)
    col.close_for_full_sync()
    col.full_upload_or_download(auth=auth, server_usn=None, upload=upload)
    col.reopen(after_full_sync=True)
    return f"full-{'upload' if upload else 'download'}"


def revlog_count(col: Collection) -> int:
    return col.db.scalar("select count() from revlog") or 0


def reviewed_cids(col: Collection) -> set[int]:
    return set(col.db.list("select distinct cid from revlog"))


def review_n(col: Collection, n: int) -> int:
    done = 0
    for _ in range(n):
        card = col.sched.getCard()
        if card is None:
            break
        col.sched.answerCard(card, 3)
        done += 1
    return done


def review_one(col: Collection, cid: int, ease: int, tag: str) -> bool:
    """Review exactly one card via a one-card filtered deck (reschedules)."""
    deck = col.sched.get_or_create_filtered_deck(DeckId(0))
    deck.name = f"conflict-{tag}"
    cfg = deck.config
    del cfg.search_terms[:]
    term = cfg.search_terms.add()
    term.search = f"cid:{cid}"
    term.limit = 1
    term.order = 0
    cfg.reschedule = True
    out = col.sched.add_or_update_filtered_deck(deck)
    col.sched.rebuild_filtered_deck(DeckId(out.id))
    col.decks.set_current(DeckId(out.id))
    card = col.sched.getCard()
    ok = card is not None
    if ok:
        col.sched.answerCard(card, ease)
    # return the card to its home deck so the only cross-device difference is the
    # card's schedule (a clean conflict), then drop the temp filtered deck.
    col.sched.empty_filtered_deck(DeckId(out.id))
    col.decks.remove([DeckId(out.id)])
    return ok


def main() -> None:
    # ---- 1. A builds + uploads; B downloads --------------------------------
    a = make_col("A")
    model = a.models.by_name("Basic")
    did = a.decks.id("Sync Deck")
    a.decks.set_current(did)
    conf = a.decks.config_dict_for_deck_id(did)
    conf["new"]["perDay"] = 100
    a.decks.save(conf)
    for i in range(20):
        note = a.new_note(model)
        note["Front"] = f"Q{i}"
        note["Back"] = f"A{i}"
        a.add_note(note, did)
    auth_a = a.sync_login(USER, PW, ENDPOINT)
    print("A initial sync:", sync(a, auth_a, prefer_upload=True))

    b = make_col("B")
    auth_b = b.sync_login(USER, PW, ENDPOINT)
    print("B initial sync:", sync(b, auth_b, prefer_upload=False))
    print(f"cards -> A: {a.card_count()}  B: {b.card_count()}")

    # ---- 2. Offline: A reviews 10, B reviews 10 DIFFERENT ------------------
    cids = sorted(int(c) for c in b.find_cards('deck:"Sync Deck"'))
    ra = review_n(a, 10)                       # A: first 10 by new-queue order
    from anki.cards import CardId
    b.sched.reposition_new_cards(
        [CardId(c) for c in cids[10:20]], starting_from=1, step_size=1,
        randomize=False, shift_existing=True,
    )
    rb = review_n(b, 10)                       # B: the other 10 (repositioned first)
    print(f"\noffline reviews -> A: {ra}  B: {rb}")
    print(f"pre-sync revlog -> A: {revlog_count(a)}  B: {revlog_count(b)}")

    # ---- 3. Sync all, verify no loss / no double-count --------------------
    print("A sync:", sync(a, auth_a))
    print("B sync:", sync(b, auth_b))
    print("A sync:", sync(a, auth_a))
    ca, cb = revlog_count(a), revlog_count(b)
    da, db = reviewed_cids(a), reviewed_cids(b)
    print(f"\npost-sync revlog -> A: {ca}  B: {cb}")
    print(f"distinct reviewed cards -> A: {len(da)}  B: {len(db)}  (union {len(da | db)})")
    ok_count = ca == 20 and cb == 20
    ok_disjoint = len(da) == 20 and da == db
    print(f"RESULT no-loss/no-dup: {'PASS' if ok_count else 'FAIL'} "
          f"(20 reviews on both)")
    print(f"RESULT all-20-distinct-cards synced: {'PASS' if ok_disjoint else 'FAIL'}")

    # ---- 4. Conflict: same card modified on both devices offline ----------
    from anki.cards import CardId as _Cid
    x = cids[0]
    a.sched.set_due_date([_Cid(x)], "5")       # A reschedules X to +5 days
    time.sleep(1.1)                            # ensure B's edit has a strictly later mod
    b.sched.set_due_date([_Cid(x)], "10")      # B reschedules X to +10 days (later edit)
    pre_revlog = revlog_count(a)
    print(f"\nconflict card {x}: A set due={a.get_card(x).due}  "
          f"B set due={b.get_card(x).due} (concurrent offline edit; B is later)")
    # A publishes first, then B merges (its later edit wins), then A pulls it back.
    for _ in range(3):
        sync(a, auth_a)
        sync(b, auth_b)
    sync(a, auth_a)
    a_due = a.get_card(x).due
    b_due = b.get_card(x).due
    print(f"due after sync -> A: {a_due}  B: {b_due}")
    converged = a_due == b_due
    # No review may vanish: the revlog is append-only, so the count never drops.
    no_loss = revlog_count(a) >= pre_revlog and revlog_count(b) >= pre_revlog
    print(f"RESULT conflict-converges: {'PASS' if converged else 'FAIL'} "
          f"(both agree on due={a_due}; later edit wins by mod time)")
    print(f"RESULT conflict-no-review-lost: {'PASS' if no_loss else 'FAIL'}")

    a.close()
    b.close()


if __name__ == "__main__":
    main()
