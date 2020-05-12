# Copyright: Ankitects Pty Ltd and contributors
# -*- coding: utf-8 -*-
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
"""
The window obtained, from main window "Tools>Study deck"
"""

import aqt
from anki.lang import _
from aqt import gui_hooks
from aqt.qt import *
from aqt.utils import getOnlyText, openHelp, restoreGeom, saveGeom, shortcut, showInfo


class StudyDeck(QDialog):
    """
    nameFunc -- names, a function or none. Called to compute the new name on reset. Currently, it's always the list of all decks or None.
    origNames -- the names ? Either computed from nameFunc, or the list of all name of decks.
    filt -- the text written in the window, to filter the decks shown
    names -- set of decks to be shown. Subset of origname
    name -- the selected deck, only after accepting
    """

    def __init__(
        self,
        mw,
        names=None,
        accept=None,
        title=None,
        help="studydeck",
        current=None,
        cancel=True,
        parent=None,
        dyn=False,
        buttons=None,
        geomKey="default",
    ) -> None:
        QDialog.__init__(self, parent or mw)
        if buttons is None:
            buttons = []
        self.mw = mw
        self.form = aqt.forms.studydeck.Ui_Dialog()
        self.form.setupUi(self)
        self.form.filter.installEventFilter(self)
        self.cancel = cancel
        gui_hooks.state_did_reset.append(self.onReset)
        self.geomKey = "studyDeck-" + geomKey
        restoreGeom(self, self.geomKey)
        if not cancel:
            self.form.buttonBox.removeButton(
                self.form.buttonBox.button(QDialogButtonBox.Cancel)
            )
        if buttons:
            for button in buttons:
                self.form.buttonBox.addButton(button, QDialogButtonBox.ActionRole)
        else:
            button = QPushButton(_("Add"))
            button.setShortcut(QKeySequence("Ctrl+N"))
            button.setToolTip(shortcut(_("Add New Deck (Ctrl+N)")))
            self.form.buttonBox.addButton(button, QDialogButtonBox.ActionRole)
            qconnect(button.clicked, self.onAddDeck)
        if title:
            self.setWindowTitle(title)
        if not names:
            names = [
                d.name
                for d in self.mw.col.decks.all_names_and_ids(
                    include_filtered=dyn, skip_empty_default=True
                )
            ]
            self.nameFunc = None
            self.origNames = names
        else:
            self.nameFunc = names
            self.origNames = names()
        self.name = None
        self.ok = self.form.buttonBox.addButton(
            accept or _("Study"), QDialogButtonBox.AcceptRole
        )
        self.setWindowModality(Qt.WindowModal)
        qconnect(self.form.buttonBox.helpRequested, lambda: openHelp(help))
        qconnect(self.form.filter.textEdited, self.redraw)
        qconnect(self.form.list.itemDoubleClicked, self.accept)
        self.show()
        # redraw after show so position at center correct
        self.redraw("", current)
        self.exec_()

    def eventFilter(self, obj: QObject, evt: QEvent) -> bool:
        if evt.type() == QEvent.KeyPress:
            if evt.key() == Qt.Key_Up:
                count = self.form.list.count()
                row = self.form.list.currentRow() - 1
                if row < 0:
                    row = count - 1
                self.form.list.setCurrentRow(row)
                return True
            elif evt.key() == Qt.Key_Down:
                count = self.form.list.count()
                row = self.form.list.currentRow() + 1
                if row == count:
                    row = 0
                self.form.list.setCurrentRow(row)
                return True
        return False

    def redraw(self, filt, focus=None):
        """filt -- text already entered
        focus -- the name on which to focus if its in the list of deck names
        """
        self.filt = filt
        self.focus = focus
        self.names = [name for name in self.origNames if self._matches(name, filt)]
        listDeckNames = self.form.list
        listDeckNames.clear()
        listDeckNames.addItems(self.names)
        if focus in self.names:
            idx = self.names.index(focus)
        else:
            idx = 0
        listDeckNames.setCurrentRow(idx)
        listDeckNames.scrollToItem(
            listDeckNames.item(idx), QAbstractItemView.PositionAtCenter
        )

    def _matches(self, name, filt):
        """whether all words of filt, separated by spaces, appear in
        name. This is how filter works."""
        name = name.lower()
        filt = filt.lower()
        if not filt:
            return True
        for word in filt.split(" "):
            if word not in name:
                return False
        return True

    def onReset(self):
        """Recompute the set of decks, show the new deck with same
        filter, same focus, but new name"""
        # model updated?
        if self.nameFunc:
            self.origNames = self.nameFunc()
        self.redraw(self.filt, self.focus)

    def accept(self) -> None:
        saveGeom(self, self.geomKey)
        gui_hooks.state_did_reset.remove(self.onReset)
        row = self.form.list.currentRow()
        if row < 0:
            showInfo(_("Please select something."))
            return
        self.name = self.names[self.form.list.currentRow()]
        QDialog.accept(self)

    def reject(self) -> None:
        saveGeom(self, self.geomKey)
        gui_hooks.state_did_reset.remove(self.onReset)
        QDialog.reject(self)

    def onAddDeck(self) -> None:
        row = self.form.list.currentRow()
        if row < 0:
            default = self.form.filter.text()
        else:
            default = self.names[self.form.list.currentRow()]
        name = getOnlyText(_("New deck name:"), default=default)
        if name:
            self.mw.col.decks.id(name)
            self.name = name
            # make sure we clean up reset hook when manually exiting
            gui_hooks.state_did_reset.remove(self.onReset)
            if self.mw.state == "deckBrowser":
                self.mw.deckBrowser.refresh()
            gui_hooks.sidebar_should_refresh_decks()
            QDialog.accept(self)
