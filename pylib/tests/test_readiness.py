# Copyright: Ankitects Pty Ltd and contributors
# Copyright: TopGRE contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

from __future__ import annotations

from tests.shared import getEmptyCol


def test_points_at_stake_queue():
    """The Rust triage queue is reachable from Python and orders by efficiency.

    New cards have no memory state (weakness = 1.0), so efficiency reduces to
    weight / minutes per move-type:
        examples    0.6 / 1.0 = 0.600
        continuity  0.7 / 1.5 = 0.467
        compactness 1.0 / 3.0 = 0.333
    """
    col = getEmptyCol()
    model = col.models.by_name("Basic")
    deck_id = col.decks.id("Default")
    for move in ["compactness", "examples", "continuity"]:
        note = col.new_note(model)
        note["Front"] = f"q-{move}"
        note["Back"] = "a"
        note.tags = [f"move::{move}"]
        col.add_note(note, deck_id)

    resp = col._backend.points_at_stake_queue(search="", limit=0)
    cards = getattr(resp, "cards", resp)

    order = [c.move_type for c in cards]
    assert order == ["examples", "continuity", "compactness"]

    # new cards -> maximal weakness
    assert all(abs(c.weakness - 1.0) < 1e-9 for c in cards)
    # efficiency is descending
    effs = [c.time_efficiency for c in cards]
    assert effs == sorted(effs, reverse=True)

    # limit is respected
    limited = col._backend.points_at_stake_queue(search="", limit=2)
    limited_cards = getattr(limited, "cards", limited)
    assert len(limited_cards) == 2
    assert limited_cards[0].move_type == "examples"


def test_reorder_new_by_triage():
    """The engine's triage order actually repositions the new-card queue."""
    from anki import readiness as tg

    col = getEmptyCol()
    model = col.models.by_name("Basic")
    deck_id = col.decks.id("Default")
    for move in ["compactness", "examples", "continuity"]:
        note = col.new_note(model)
        note["Front"] = f"q-{move}"
        note["Back"] = "a"
        note.tags = [f"move::{move}"]
        col.add_note(note, deck_id)

    count = tg.reorder_new_by_triage(col, "")
    assert count == 3

    # New cards study in ascending `due` (position); highest value/min first.
    cards = sorted((col.get_card(c) for c in col.find_cards("is:new")), key=lambda c: c.due)
    first_tags = cards[0].note().tags
    assert "move::examples" in first_tags  # examples has the best value-per-minute
