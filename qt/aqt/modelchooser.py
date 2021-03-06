# -*- coding: utf-8 -*-
# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

from anki.lang import _
from aqt import gui_hooks
from aqt.qt import *
from aqt.utils import shortcut


class ModelChooser(QHBoxLayout):
    """The window allowing to choose a model. Either for a card to add,
    to import notes, or to change the model of a card.

    label -- Whether this object corresponds to a button
    (i.e. note importer/addcards, but not browser.
    widget -- the button used to open this window. It contains the
    name of the current model.

    """

    def __init__(self, mw, widget, label=True) -> None:
        QHBoxLayout.__init__(self)
        self.widget = widget  # type: ignore
        self.mw = mw
        self.deck = mw.col
        self.label = label
        self.setContentsMargins(0, 0, 0, 0)
        self.setSpacing(8)
        self.setupModels()
        gui_hooks.state_did_reset.append(self.onReset)
        self.widget.setLayout(self)  # type: ignore

    def setupModels(self):
        if self.label:
            self.modelLabel = QLabel(_("Type"))
            self.addWidget(self.modelLabel)
        # models box
        self.models = QPushButton()
        # self.models.setStyleSheet("* { text-align: left; }")
        self.models.setToolTip(shortcut(_("Change Note Type (Ctrl+N)")))
        QShortcut(QKeySequence("Ctrl+N"), self.widget, activated=self.onModelChange)
        self.models.setAutoDefault(False)
        self.addWidget(self.models)
        qconnect(self.models.clicked, self.onModelChange)
        # layout
        sizePolicy = QSizePolicy(QSizePolicy.Policy(7), QSizePolicy.Policy(0))
        self.models.setSizePolicy(sizePolicy)
        self.updateModels()

    def cleanup(self) -> None:
        gui_hooks.state_did_reset.remove(self.onReset)

    def onReset(self):
        """Change the button's text so that it has the name of the current
        model."""
        self.updateModels()

    def show(self):
        self.widget.show()

    def hide(self):
        self.widget.hide()

    def onEdit(self):
        import aqt.models

        aqt.models.Models(self.mw, self.widget)

    def onModelChange(self) -> None:
        """Open Choose Note Type window"""
        # Method called when we want to change the current model
        from aqt.studydeck import StudyDeck

        current = self.deck.models.current()["name"]
        # edit button
        edit = QPushButton(_("Manage"), clicked=self.onEdit)  # type: ignore

        def nameFunc():
            return sorted(self.deck.models.allNames())

        ret = StudyDeck(
            self.mw,
            names=nameFunc,
            accept=_("Choose"),
            title=_("Choose Note Type"),
            help="_notes",
            current=current,
            parent=self.widget,
            buttons=[edit],
            cancel=True,
            geomKey="selectModel",
        )
        if not ret.name:
            return
        model = self.deck.models.byName(ret.name)
        self.deck.conf["curModel"] = model["id"]
        cdeck = self.deck.decks.current()
        cdeck["mid"] = model["id"]
        self.deck.decks.save(cdeck)
        gui_hooks.current_note_type_did_change(current)
        self.mw.reset()

    def updateModels(self):
        """Change the button's text so that it has the name of the current
        model."""
        self.models.setText(self.deck.models.current()["name"])
