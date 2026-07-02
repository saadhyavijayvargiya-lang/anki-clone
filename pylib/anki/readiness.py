# Copyright: Ankitects Pty Ltd and contributors
# Copyright: TopGRE contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""TopGRE readiness helpers on top of the Rust ReadinessService.

The engine exposes the points-at-stake triage order; here we use it to actually
reorder the *new* card queue so the desktop reviewer studies the highest-value
(exam-leverage x weakness / time) cards first."""

from __future__ import annotations

import anki.collection
from anki.cards import CardId
from anki.consts import QUEUE_TYPE_NEW
from anki.decks import DeckId


def triage_new_card_ids(col: anki.collection.Collection, search: str = "") -> list[CardId]:
    """New card ids for `search`, in points-at-stake (triage) order."""
    resp = col._backend.points_at_stake_queue(search=search, limit=0)
    cards = getattr(resp, "cards", resp)
    ordered: list[CardId] = []
    for entry in cards:
        cid = CardId(entry.card_id)
        if col.get_card(cid).queue == QUEUE_TYPE_NEW:
            ordered.append(cid)
    return ordered


def reorder_new_by_triage(col: anki.collection.Collection, search: str = "") -> int:
    """Reposition new cards into triage order. Returns the count repositioned.

    Uses the scheduler's reposition op (undoable), so the change is safe and
    reversible - it only rewrites new-card positions, never review history."""
    ids = triage_new_card_ids(col, search)
    if ids:
        col.sched.reposition_new_cards(
            ids,
            starting_from=1,
            step_size=1,
            randomize=False,
            shift_existing=False,
        )
    return len(ids)


def most_dangerous_card_ids(
    col: anki.collection.Collection, search: str = "", limit: int = 20
) -> list[CardId]:
    """Card ids ranked most-dangerous first (leverage x weakness x exam miss-rate)."""
    resp = col._backend.most_dangerous_cards(search=search, limit=limit)
    cards = getattr(resp, "cards", resp)
    return [CardId(c.card_id) for c in cards]


def _expand_with_chain_mates(
    col: anki.collection.Collection, cids: list[CardId], search: str = ""
) -> list[CardId]:
    """Add the adjacent steps of each card's decision chain (problem -> type ->
    move), identified by a shared `chain::<id>` tag, so cram covers the whole
    routing context rather than isolated cards."""
    chain_tags: set[str] = set()
    for cid in cids:
        for tag in col.get_card(cid).note().tags:
            if tag.startswith("chain::"):
                chain_tags.add(tag)

    ordered: list[CardId] = list(cids)
    seen = {int(c) for c in ordered}
    for chain_tag in chain_tags:
        query = f"tag:{chain_tag}"
        if search.strip():
            query = f"({search}) {query}"
        for cid in col.find_cards(query):
            if int(cid) not in seen:
                seen.add(int(cid))
                ordered.append(cid)
    return ordered


def start_cram_session(
    col: anki.collection.Collection,
    search: str = "",
    limit: int = 20,
    deck_name: str = "TopGRE Cram",
) -> tuple[DeckId | None, int]:
    """Build (or refresh) a filtered "cram" deck containing only the most
    dangerous cards, so you can drill exactly those. Returns (deck_id, count).

    Filtered decks let you study cards regardless of due state, and reschedule
    the reviews normally - so cramming the dangerous set still updates memory."""
    ids = most_dangerous_card_ids(col, search, limit)
    if not ids:
        return None, 0
    # Pull in each dangerous card's chain-mates (adjacent decision steps).
    ids = _expand_with_chain_mates(col, ids, search)

    existing = col.decks.by_name(deck_name)
    deck_id = DeckId(int(existing["id"])) if existing else DeckId(0)
    deck = col.sched.get_or_create_filtered_deck(deck_id)
    deck.name = deck_name

    config = deck.config
    del config.search_terms[:]
    term = config.search_terms.add()
    term.search = "cid:" + ",".join(str(int(cid)) for cid in ids)
    term.limit = len(ids)
    term.order = 0  # order within the (already dangerous) set
    config.reschedule = True

    out = col.sched.add_or_update_filtered_deck(deck)
    did = DeckId(out.id)
    col.sched.rebuild_filtered_deck(did)
    return did, len(ids)
