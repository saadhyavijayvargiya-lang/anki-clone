# Copyright: Ankitects Pty Ltd and contributors
# Copyright: TopGRE contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""TopGRE readiness dashboard: three honest scores (Memory / Performance /
Readiness) with ranges, coverage, evidence, and the give-up rule. The UI is the
SvelteKit `readiness` page; data comes from the Rust ReadinessService."""

from __future__ import annotations

import aqt
import aqt.main
from aqt.qt import *
from aqt.utils import disable_help_button, restoreGeom, saveGeom
from aqt.webview import AnkiWebView, AnkiWebViewKind


class ReadinessDialog(QDialog):
    def __init__(self, mw: aqt.main.AnkiQt) -> None:
        QDialog.__init__(self, mw, Qt.WindowType.Window)
        mw.garbage_collect_on_dialog_finish(self)
        self.mw = mw
        self.name = "readiness"
        self.setWindowTitle("Crux: Readiness")
        self.setMinimumSize(760, 620)
        disable_help_button(self)
        restoreGeom(self, self.name, default_size=(840, 760))

        self.web = AnkiWebView(kind=AnkiWebViewKind.READINESS)
        self.web.setParent(self)
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.web)
        self.setLayout(layout)

        self.web.set_bridge_command(self._on_bridge_cmd, self)
        self.web.load_sveltekit_page("readiness")
        self.show()
        self.activateWindow()

    def _on_bridge_cmd(self, cmd: str) -> bool:
        if cmd == "topgre:cram":
            # Build the cram deck, then close so the deck overview is visible.
            self.close()
            self.mw.onCramSession()
            return True
        if cmd == "topgre:triage":
            self.mw.onReorderTriage()
            return True
        if cmd.startswith("topgre:drilltype:"):
            move_type = cmd.split(":", 2)[2]
            try:
                self.mw.col.set_config("cruxRouterFocus", move_type)
            except Exception:
                pass
            # Opening a webview dialog from inside this webview's own bridge
            # callback re-enters QtWebEngine and crashes; close this dialog first,
            # then defer the router open to the next event-loop tick.
            self.close()
            QTimer.singleShot(0, self.mw.onRouterDrill)
            return True
        return False

    def reject(self) -> None:
        saveGeom(self, self.name)
        if self.web:
            self.web.cleanup()
            self.web = None
        aqt.dialogs.markClosed("Readiness")
        QDialog.reject(self)
