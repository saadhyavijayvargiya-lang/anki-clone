# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

from __future__ import annotations

import html
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

import aqt
import aqt.operations
from anki.collection import Collection, OpChanges
from anki.decks import DeckCollapseScope, DeckId, DeckTreeNode
from aqt import AnkiQt, gui_hooks
from aqt.deckoptions import display_options_for_deck_id
from aqt.operations import QueryOp
from aqt.operations.deck import (
    add_deck_dialog,
    remove_decks,
    rename_deck,
    reparent_decks,
    set_current_deck,
    set_deck_collapsed,
)
from aqt.qt import *
from aqt.sound import av_player
from aqt.toolbar import BottomBar
from aqt.utils import getOnlyText, openLink, shortcut, showInfo, tr


CRUX_OUTLINE = [
    "open-closed-sets",
    "interior-closure-boundary",
    "bases-subbases",
    "continuity",
    "homeomorphism",
    "compactness",
    "connectedness",
    "separation",
    "examples",
]

CRUX_TYPE_LABELS = {
    "open-closed-sets": "Open / closed",
    "interior-closure-boundary": "Interior / closure",
    "bases-subbases": "Bases / subbases",
    "continuity": "Continuity",
    "homeomorphism": "Homeomorphism",
    "compactness": "Compactness",
    "connectedness": "Connectedness",
    "separation": "Separation",
    "examples": "Examples",
}


class DeckBrowserBottomBar:
    def __init__(self, deck_browser: DeckBrowser) -> None:
        self.deck_browser = deck_browser


@dataclass
class RenderData:
    """Data from collection that is required to show the page."""

    tree: DeckTreeNode
    current_deck_id: DeckId
    studied_today: str
    sched_upgrade_required: bool
    readiness: Any = None
    type_map: list = field(default_factory=list)


@dataclass
class DeckBrowserContent:
    """Stores sections of HTML content that the deck browser will be
    populated with.

    Attributes:
        tree {str} -- HTML of the deck tree section
        stats {str} -- HTML of the stats section
    """

    tree: str
    stats: str


@dataclass
class RenderDeckNodeContext:
    current_deck_id: DeckId


class DeckBrowser:
    _render_data: RenderData

    def __init__(self, mw: AnkiQt) -> None:
        self.mw = mw
        self.web = mw.web
        self.bottom = BottomBar(mw, mw.bottomWeb)
        self.scrollPos = QPoint(0, 0)
        self._refresh_needed = False

    def show(self) -> None:
        av_player.stop_and_clear_queue()
        self.web.set_bridge_command(self._linkHandler, self)
        # redraw top bar for theme change
        self.mw.toolbar.redraw()
        self.refresh()

    def refresh(self) -> None:
        self._renderPage()
        self._refresh_needed = False

    def refresh_if_needed(self) -> None:
        if self._refresh_needed:
            self.refresh()

    def op_executed(
        self, changes: OpChanges, handler: object | None, focused: bool
    ) -> bool:
        if changes.study_queues and handler is not self:
            self._refresh_needed = True

        if focused:
            self.refresh_if_needed()

        return self._refresh_needed

    # Event handlers
    ##########################################################################

    def _linkHandler(self, url: str) -> Any:
        if ":" in url:
            (cmd, arg) = url.split(":", 1)
        else:
            cmd = url
            arg = ""
        if cmd == "open":
            self.set_current_deck(DeckId(int(arg)))
        elif cmd == "opts":
            self._showOptions(arg)
        elif cmd == "shared":
            self._onShared()
        elif cmd == "import":
            self.mw.onImport()
        elif cmd == "create":
            self._on_create()
        elif cmd == "drag":
            source, target = arg.split(",")
            self._handle_drag_and_drop(DeckId(int(source)), DeckId(int(target or 0)))
        elif cmd == "collapse":
            self._collapse(DeckId(int(arg)))
        elif cmd == "v2upgrade":
            self._confirm_upgrade()
        elif cmd == "v2upgradeinfo":
            if self.mw.col.sched_ver() == 1:
                openLink("https://faqs.ankiweb.net/the-anki-2.1-scheduler.html")
            else:
                openLink("https://faqs.ankiweb.net/the-2021-scheduler.html")
        elif cmd == "select":
            set_current_deck(
                parent=self.mw, deck_id=DeckId(int(arg))
            ).run_in_background()
        elif cmd == "crux":
            self._crux_action(arg)
        return False

    def _crux_action(self, which: str) -> None:
        if which == "cram":
            self.mw.onCramSession()
        elif which == "triage":
            self.mw.onReorderTriage()
        elif which == "readiness":
            self.mw.onReadiness()
        elif which == "router":
            self.mw.onRouterDrill()
        elif which.startswith("drilltype:"):
            move_type = which.split(":", 1)[1]
            try:
                self.mw.col.set_config("cruxRouterFocus", move_type)
            except Exception:
                pass
            self.mw.onRouterDrill()

    def set_current_deck(self, deck_id: DeckId) -> None:
        set_current_deck(parent=self.mw, deck_id=deck_id).success(
            lambda _: self.mw.onOverview()
        ).run_in_background(initiator=self)

    # HTML generation
    ##########################################################################

    _body = """
<center>
<table cellspacing=0 cellpadding=3>
%(tree)s
</table>

<br>
%(stats)s
</center>
"""

    def _compute_type_map(self, col: Collection) -> list[dict]:
        danger: dict[str, float] = {}
        try:
            resp = col._backend.most_dangerous_cards(search="", limit=400)
            for c in resp.cards:
                if c.move_type:
                    danger[c.move_type] = danger.get(c.move_type, 0.0) + c.points_at_stake
        except Exception:
            pass
        max_d = max(danger.values()) if danger else 1.0
        out: list[dict] = []
        for t in CRUX_OUTLINE:
            try:
                cards = len(col.find_cards(f"tag:move::{t}"))
            except Exception:
                cards = 0
            d = danger.get(t, 0.0)
            out.append(
                {
                    "type": t,
                    "cards": cards,
                    "danger_rel": (d / max_d) if max_d else 0.0,
                }
            )
        return out

    def _render_type_map(self, type_map: list[dict]) -> str:
        if not type_map:
            return ""
        tiles = ""
        for cell in type_map:
            label = html.escape(CRUX_TYPE_LABELS.get(cell["type"], cell["type"]))
            cards = cell["cards"]
            plural = "" if cards == 1 else "s"
            if cards == 0:
                tiles += (
                    "<div class='hm-tile empty' style='--a:0'>"
                    f"<span class='hm-name'>{label}</span>"
                    f"<span class='hm-meta'>{cards} cards</span>"
                    "</div>"
                )
            else:
                hot = " hot" if cell["danger_rel"] > 0.55 else ""
                tiles += (
                    f"<button class='hm-tile{hot}' style='--a:{cell['danger_rel']:.3f}' "
                    f"title='Drill {label}' "
                    f"onclick='pycmd(\"crux:drilltype:{cell['type']}\")'>"
                    f"<span class='hm-name'>{label}</span>"
                    f"<span class='hm-meta'>{cards} card{plural} &middot; drill</span>"
                    "</button>"
                )
        return (
            "<section class='deck-panel heatmap-panel'>"
            "<div class='panel-title'>Coverage and danger by type</div>"
            f"<div class='heatmap'>{tiles}</div>"
            "</section>"
        )

    def _score_chip(self, label: str, sub: str, score: Any) -> str:
        if score is not None and getattr(score, "available", False):
            pctval = round(score.value * 100)
            width = max(0, min(100, pctval))
            value_html = f"{pctval}<span class='chip-unit'>%</span>"
            bar = (
                f"<div class='chip-bar'><div class='chip-fill' "
                f"style='width:{width}%'></div></div>"
            )
            na = ""
        else:
            value_html = "<span class='chip-na'>n/a</span>"
            bar = "<div class='chip-bar empty'></div>"
            na = " na"
        return (
            f"<div class='score-chip{na}'>"
            f"<div class='chip-label'>{label}</div>"
            f"<div class='chip-value'>{value_html}</div>"
            f"{bar}"
            f"<div class='chip-sub'>{sub}</div>"
            f"</div>"
        )

    def _crux_status_line(self, r: Any) -> str:
        if r is None:
            return "Study a few cards and log exam attempts to start an estimate."
        if getattr(r.readiness, "available", False):
            pctval = round(r.readiness.value * 100)
            return (
                f"Projected {pctval}% on the point-set topology cluster. "
                "Topology only, not a full GRE score."
            )
        if getattr(r.memory, "available", False) or getattr(
            r.performance, "available", False
        ):
            return "Building your estimate. Keep logging exam attempts to unlock readiness."
        return "No readiness estimate yet. Study a few cards and log exam attempts to begin."

    def _render_crux_home(self, data: RenderData, content: DeckBrowserContent) -> str:
        r = data.readiness
        status = html.escape(self._crux_status_line(r))
        best_next = ""
        if r is not None and getattr(r, "best_next", ""):
            best_next = (
                "<div class='best-next'>"
                "<span class='bn-key'>Best next</span>"
                f"<span class='bn-val'>{html.escape(r.best_next)}</span>"
                "</div>"
            )

        chips = (
            self._score_chip("Memory", "recall a taught fact", r.memory if r else None)
            + self._score_chip(
                "Performance", "answer a new question", r.performance if r else None
            )
            + self._score_chip(
                "Readiness", "topology-cluster projection", r.readiness if r else None
            )
        )

        coverage = round(r.coverage * 100) if r else 0
        reviews = r.graded_reviews if r else 0
        attempts = r.exam_attempts if r else 0
        meta = (
            f"<span><b>{coverage}%</b> outline coverage</span>"
            f"<span><b>{reviews}</b> graded reviews</span>"
            f"<span><b>{attempts}</b> exam attempts</span>"
        )

        actions = (
            "<div class='crux-actions'>"
            "<button class='crux-btn primary' onclick='pycmd(\"crux:cram\")'>"
            "<span class='ci'>&#9650;</span>Cram most dangerous</button>"
            "<button class='crux-btn' onclick='pycmd(\"crux:router\")'>"
            "Router drill</button>"
            "<button class='crux-btn' onclick='pycmd(\"crux:triage\")'>"
            "Reorder triage</button>"
            "<button class='crux-btn' onclick='pycmd(\"crux:readiness\")'>"
            "Open readiness</button>"
            "</div>"
        )

        return f"""
<div class="crux-home">
  <div class="crux-bg" aria-hidden="true"><span class="blob b1"></span><span class="blob b2"></span></div>
  <header class="crux-hero">
    <div class="brand"><span class="mark">Crux</span><span class="brand-tag">topology readiness</span></div>
    <p class="crux-status">{status}</p>
    {actions}
  </header>
  <section class="score-strip">{chips}</section>
  {best_next}
  <div class="crux-meta">{meta}</div>
  {self._render_type_map(data.type_map)}
  <section class="deck-panel">
    <table cellspacing=0 cellpadding=3>
      {content.tree}
    </table>
  </section>
  <div class="crux-today">{content.stats}</div>
</div>
"""

    def _renderPage(self, reuse: bool = False) -> None:
        if not reuse:

            def get_data(col: Collection) -> RenderData:
                try:
                    readiness = col._backend.get_readiness(search="")
                except Exception:
                    readiness = None
                return RenderData(
                    tree=col.sched.deck_due_tree(),
                    current_deck_id=col.decks.get_current_id(),
                    studied_today=col.studied_today(),
                    sched_upgrade_required=not col.v3_scheduler(),
                    readiness=readiness,
                    type_map=self._compute_type_map(col),
                )

            def success(output: RenderData) -> None:
                self._render_data = output
                self.__renderPage(None)

            QueryOp(
                parent=self.mw,
                op=get_data,
                success=success,
            ).run_in_background()
        else:
            self.web.evalWithCallback("window.pageYOffset", self.__renderPage)

    def __renderPage(self, offset: int | None) -> None:
        data = self._render_data
        content = DeckBrowserContent(
            tree=self._renderDeckTree(data.tree),
            stats=self._renderStats(),
        )
        gui_hooks.deck_browser_will_render_content(self, content)
        self.web.stdHtml(
            self._v1_upgrade_message(data.sched_upgrade_required)
            + self._render_crux_home(data, content),
            css=["css/deckbrowser.css"],
            js=[
                "js/vendor/jquery.min.js",
                "js/vendor/jquery-ui.min.js",
                "js/deckbrowser.js",
            ],
            context=self,
        )
        self._drawButtons()
        if offset is not None:
            self._scrollToOffset(offset)
        gui_hooks.deck_browser_did_render(self)

    def _scrollToOffset(self, offset: int) -> None:
        self.web.eval("window.scrollTo(0, %d, 'instant');" % offset)

    def _renderStats(self) -> str:
        return '<div id="studiedToday"><span>{}</span></div>'.format(
            self._render_data.studied_today
        )

    def _renderDeckTree(self, top: DeckTreeNode) -> str:
        buf = """
<tr><th colspan=5 align=start>{}</th>
<th class=count>{}</th>
<th class=count>{}</th>
<th class=count>{}</th>
<th class=optscol></th></tr>""".format(
            tr.decks_deck(),
            tr.actions_new(),
            tr.decks_learn_header(),
            tr.decks_review_header(),
        )
        buf += self._topLevelDragRow()

        ctx = RenderDeckNodeContext(current_deck_id=self._render_data.current_deck_id)

        for child in top.children:
            buf += self._render_deck_node(child, ctx)

        return buf

    def _render_deck_node(self, node: DeckTreeNode, ctx: RenderDeckNodeContext) -> str:
        if node.collapsed:
            prefix = "+"
        else:
            prefix = "−"

        def indent() -> str:
            return "&nbsp;" * 6 * (node.level - 1)

        if node.deck_id == ctx.current_deck_id:
            klass = "deck current"
        else:
            klass = "deck"

        buf = (
            "<tr class='%s' id='%d' onclick='if(event.shiftKey) return pycmd(\"select:%d\")'>"
            % (
                klass,
                node.deck_id,
                node.deck_id,
            )
        )
        # deck link
        if node.children:
            collapse = (
                "<a class=collapse href=# onclick='return pycmd(\"collapse:%d\")'>%s</a>"
                % (node.deck_id, prefix)
            )
        else:
            collapse = "<span class=collapse></span>"
        if node.filtered:
            extraclass = "filtered"
        else:
            extraclass = ""
        buf += """

        <td class=decktd colspan=5>%s%s<a class="deck %s"
        href=# onclick="return pycmd('open:%d')">%s</a></td>""" % (
            indent(),
            collapse,
            extraclass,
            node.deck_id,
            html.escape(node.name),
        )

        # due counts
        def nonzeroColour(cnt: int, klass: str) -> str:
            if not cnt:
                klass = "zero-count"
            return f'<span class="{klass}">{cnt}</span>'

        review = nonzeroColour(node.review_count, "review-count")
        learn = nonzeroColour(node.learn_count, "learn-count")

        buf += ("<td align=end>%s</td>" * 3) % (
            nonzeroColour(node.new_count, "new-count"),
            learn,
            review,
        )
        # options
        buf += (
            "<td align=center class=opts><a onclick='return pycmd(\"opts:%d\");'>"
            "<img src='/_anki/imgs/gears.svg' class=gears></a></td></tr>" % node.deck_id
        )
        # children
        if not node.collapsed:
            for child in node.children:
                buf += self._render_deck_node(child, ctx)
        return buf

    def _topLevelDragRow(self) -> str:
        return "<tr class='top-level-drag-row'><td colspan='6'>&nbsp;</td></tr>"

    # Options
    ##########################################################################

    def _showOptions(self, did: str) -> None:
        m = QMenu(self.mw)
        a = m.addAction(tr.actions_rename())
        assert a is not None
        qconnect(a.triggered, lambda b, did=did: self._rename(DeckId(int(did))))
        a = m.addAction(tr.actions_options())
        assert a is not None
        qconnect(a.triggered, lambda b, did=did: self._options(DeckId(int(did))))
        a = m.addAction(tr.actions_export())
        assert a is not None
        qconnect(a.triggered, lambda b, did=did: self._export(DeckId(int(did))))
        a = m.addAction(tr.actions_delete())
        assert a is not None
        qconnect(a.triggered, lambda b, did=did: self._delete(DeckId(int(did))))
        gui_hooks.deck_browser_will_show_options_menu(m, int(did))
        m.popup(QCursor.pos())

    def _export(self, did: DeckId) -> None:
        self.mw.onExport(did=did)

    def _rename(self, did: DeckId) -> None:
        def prompt(name: str) -> None:
            new_name = getOnlyText(
                tr.decks_new_deck_name(), default=name, title=tr.actions_rename()
            )
            if not new_name or new_name == name:
                return
            else:
                rename_deck(
                    parent=self.mw, deck_id=did, new_name=new_name
                ).run_in_background()

        QueryOp(
            parent=self.mw, op=lambda col: col.decks.name(did), success=prompt
        ).run_in_background()

    def _options(self, did: DeckId) -> None:
        display_options_for_deck_id(did)

    def _collapse(self, did: DeckId) -> None:
        node = self.mw.col.decks.find_deck_in_tree(self._render_data.tree, did)
        if node:
            node.collapsed = not node.collapsed
            set_deck_collapsed(
                parent=self.mw,
                deck_id=did,
                collapsed=node.collapsed,
                scope=DeckCollapseScope.REVIEWER,
            ).run_in_background()
            self._renderPage(reuse=True)

    def _handle_drag_and_drop(self, source: DeckId, target: DeckId) -> None:
        reparent_decks(
            parent=self.mw, deck_ids=[source], new_parent=target
        ).run_in_background()

    def _delete(self, did: DeckId) -> None:
        deck = self.mw.col.decks.find_deck_in_tree(self._render_data.tree, did)
        assert deck is not None
        deck_name = deck.name
        remove_decks(
            parent=self.mw, deck_ids=[did], deck_name=deck_name
        ).run_in_background()

    # Top buttons
    ######################################################################

    drawLinks = [
        ["", "shared", tr.decks_get_shared()],
        ["", "create", tr.decks_create_deck()],
        ["Ctrl+Shift+I", "import", tr.decks_import_file()],
    ]

    def _drawButtons(self) -> None:
        buf = ""
        drawLinks = deepcopy(self.drawLinks)
        for b in drawLinks:
            if b[0]:
                b[0] = tr.actions_shortcut_key(val=shortcut(b[0]))
            buf += """
<button title='%s' onclick='pycmd(\"%s\");'>%s</button>""" % tuple(b)
        self.bottom.draw(
            buf=buf,
            link_handler=self._linkHandler,
            web_context=DeckBrowserBottomBar(self),
        )

    def _onShared(self) -> None:
        openLink(f"{aqt.appShared}decks/")

    def _on_create(self) -> None:
        if op := add_deck_dialog(
            parent=self.mw, default_text=self.mw.col.decks.current()["name"]
        ):
            op.run_in_background()

    ######################################################################

    def _v1_upgrade_message(self, required: bool) -> str:
        if not required:
            return ""

        update_required = tr.scheduling_update_required().replace("V2", "v3")

        return f"""
<center>
<div class=callout>
    <div>
      {update_required}
    </div>
    <div>
      <button onclick='pycmd("v2upgrade")'>
        {tr.scheduling_update_button()}
      </button>
      <button onclick='pycmd("v2upgradeinfo")'>
        {tr.scheduling_update_more_info_button()}
      </button>
    </div>
</div>
</center>
"""

    def _confirm_upgrade(self) -> None:
        if self.mw.col.sched_ver() == 1:
            self.mw.col.mod_schema(check=True)
            self.mw.col.upgrade_to_v2_scheduler()
        self.mw.col.set_v3_scheduler(True)

        showInfo(tr.scheduling_update_done())
        self.refresh()
