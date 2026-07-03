# Copyright: Crux contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Crux router drill: a decision-routing trainer. It shows a problem stem and
asks which problem type (move family) it calls for, then reveals the move that
solves it. This teaches the problem -> type -> method path rather than isolated
facts. Data comes from the decision-chain notes in the collection; the outcome
of each routing choice feeds the Performance model via RecordExamAttempt."""

from __future__ import annotations

import aqt
import aqt.main
from aqt.qt import *
from aqt.utils import disable_help_button, restoreGeom, saveGeom
from aqt.webview import AnkiWebView, AnkiWebViewKind


class RouterDrillDialog(QDialog):
    def __init__(self, mw: aqt.main.AnkiQt) -> None:
        QDialog.__init__(self, mw, Qt.WindowType.Window)
        mw.garbage_collect_on_dialog_finish(self)
        self.mw = mw
        self.name = "routerdrill"
        self.setWindowTitle("Crux: Router drill")
        self.setMinimumSize(720, 600)
        disable_help_button(self)
        restoreGeom(self, self.name, default_size=(820, 720))

        self.web = AnkiWebView(kind=AnkiWebViewKind.ROUTER)
        self.web.setParent(self)
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.web)
        self.setLayout(layout)

        self.web.set_bridge_command(self._on_bridge_cmd, self)
        self.web.load_sveltekit_page("router")
        self.show()
        self.activateWindow()

    def _on_bridge_cmd(self, cmd: str) -> bool:
        return False

    def reject(self) -> None:
        saveGeom(self, self.name)
        if self.web:
            self.web.cleanup()
            self.web = None
        QDialog.reject(self)
