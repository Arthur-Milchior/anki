# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

from operator import itemgetter
from typing import List, Optional

import aqt.clayout
from anki import stdmodels
from anki.lang import _, ngettext
from anki.models import NoteType
from anki.notes import Note
from anki.rsbackend import pb
from aqt import AnkiQt, gui_hooks
from aqt.qt import *
from aqt.utils import (
    askUser,
    getText,
    maybeHideClose,
    openHelp,
    restoreGeom,
    saveGeom,
    showInfo,
)


class Models(QDialog):
    """The window used to select a model. Either directly from note type manager in main. Or through a model chooser window.

    An object of class Models contains:
    mw -- The main window (?)
    parent -- the window which opened the current window. By default
    the main window
    fromMain -- whether the window is opened from the main window. It
    is used to check whether Fields... and Cards... buttons should be
    added.
    col -- the collection
    mm -- the set of models of the colection
    form -- TODO
    models -- all models of the collection
    model -- the selected model
    """

    def __init__(self, mw: AnkiQt, parent=None, fromMain=False):
        self.mw = mw
        parent = parent or mw
        self.fromMain = fromMain
        QDialog.__init__(self, parent, Qt.Window)
        self.col = mw.col.weakref()
        assert self.col
        self.mm = self.col.models
        self.mw.checkpoint(_("Note Types"))
        self.form = aqt.forms.models.Ui_Dialog()
        self.form.setupUi(self)
        qconnect(self.form.buttonBox.helpRequested, lambda: openHelp("notetypes"))
        self.models: List[pb.NoteTypeNameIDUseCount] = []
        self.setupModels()
        restoreGeom(self, "models")
        self.exec_()

    # Models
    ##########################################################################

    def setupModels(self):
        self.model = None
        box = self.form.buttonBox
        t = QDialogButtonBox.ActionRole
        addButton = box.addButton(_("Add"), t)
        qconnect(addButton.clicked, self.onAdd)
        renameButton = box.addButton(_("Rename"), t)
        qconnect(renameButton.clicked, self.onRename)
        deleteButton = box.addButton(_("Delete"), t)
        qconnect(deleteButton.clicked, self.onDelete)
        if self.fromMain:
            button = box.addButton(_("Fields..."), t)
            qconnect(button.clicked, self.onFields)
            button = box.addButton(_("Cards..."), t)
            qconnect(button.clicked, self.onCards)
        button = box.addButton(_("Options..."), t)
        qconnect(button.clicked, self.onAdvanced)
        qconnect(self.form.modelsList.itemDoubleClicked, self.onRename)

        def on_done(fut):
            self.updateModelsList(fut.result())

        self.mw.taskman.with_progress(self.col.models.all_use_counts, on_done, self)
        self.form.modelsList.setCurrentRow(0)
        maybeHideClose(box)

    def onRename(self):
        """Ask the user for a new name for the model. Save it"""
        nt = self.current_notetype()
        txt = getText(_("New name:"), default=nt["name"])
        if txt[1] and txt[0]:
            nt["name"] = txt[0]
            self.saveAndRefresh(nt)

    def saveAndRefresh(self, nt: NoteType) -> None:
        def save():
            self.mm.save(nt)
            return self.col.models.all_use_counts()

        def on_done(fut):
            self.updateModelsList(fut.result())

        self.mw.taskman.with_progress(save, on_done, self)

    def updateModelsList(self, notetypes):
        row = self.form.modelsList.currentRow()
        if row == -1:
            row = 0
        self.form.modelsList.clear()

        self.models = notetypes
        for model in self.models:
            mUse = model.use_count
            mUse = ngettext("%d note", "%d notes", mUse) % mUse
            item = QListWidgetItem("%s [%s]" % (model.name, mUse))
            self.form.modelsList.addItem(item)
        self.form.modelsList.setCurrentRow(row)

    def current_notetype(self) -> NoteType:
        row = self.form.modelsList.currentRow()
        return self.mm.get(self.models[row].id)

    def onAdd(self):
        model = AddModel(self.mw, self).get()
        if model:
            txt = getText(_("Name:"), default=model["name"])[0]
            if txt:
                model["name"] = txt
            self.saveAndRefresh(model)

    def onDelete(self):
        if len(self.models) < 2:
            showInfo(_("Please add another note type first."), parent=self)
            return
        idx = self.form.modelsList.currentRow()
        if self.models[idx].use_count:
            msg = _("Delete this note type and all its cards?")
        else:
            msg = _("Delete this unused note type?")
        if not askUser(msg, parent=self):
            return

        self.col.modSchema(check=True)

        nt = self.current_notetype()

        def save():
            self.mm.rem(nt)
            return self.col.models.all_use_counts()

        def on_done(fut):
            self.updateModelsList(fut.result())

        self.mw.taskman.with_progress(save, on_done, self)

    def onAdvanced(self):
        nt = self.current_notetype()
        dialog = QDialog(self)
        frm = aqt.forms.modelopts.Ui_Dialog()
        frm.setupUi(dialog)
        frm.latexsvg.setChecked(nt.get("latexsvg", False))
        frm.latexHeader.setText(nt["latexPre"])
        frm.latexFooter.setText(nt["latexPost"])
        dialog.setWindowTitle(_("Options for %s") % nt["name"])
        qconnect(frm.buttonBox.helpRequested, lambda: openHelp("latex"))
        restoreGeom(dialog, "modelopts")
        gui_hooks.models_advanced_will_show(dialog)
        dialog.exec_()
        saveGeom(dialog, "modelopts")
        nt["latexsvg"] = frm.latexsvg.isChecked()
        nt["latexPre"] = str(frm.latexHeader.toPlainText())
        nt["latexPost"] = str(frm.latexFooter.toPlainText())
        self.saveAndRefresh(nt)

    def _tmpNote(self):
        nt = self.current_notetype()
        return Note(self.col, nt)

    def onFields(self):
        from aqt.fields import FieldDialog

        FieldDialog(self.mw, self.current_notetype(), parent=self)

    def onCards(self):
        """Open the card preview(layout) window."""
        from aqt.clayout import CardLayout

        note = self._tmpNote()
        CardLayout(self.mw, note, ord=0, parent=self, fill_empty=True)

    # Cleanup
    ##########################################################################

    # need to flush model on change or reject

    def reject(self):
        self.mw.reset()
        saveGeom(self, "models")
        QDialog.reject(self)


class AddModel(QDialog):
    def __init__(self, mw: AnkiQt, parent: Optional[QWidget] = None):
        self.parent_ = parent or mw
        self.mw = mw
        self.col = mw.col
        QDialog.__init__(self, self.parent_, Qt.Window)
        self.model = None
        self.dialog = aqt.forms.addmodel.Ui_Dialog()
        self.dialog.setupUi(self)
        # standard models
        self.models = []
        for (name, func) in stdmodels.get_stock_notetypes(self.col):
            item = QListWidgetItem(_("Add: %s") % name)
            self.dialog.models.addItem(item)
            self.models.append((True, func))
        # add copies
        for model in sorted(self.col.models.all(), key=itemgetter("name")):
            item = QListWidgetItem(_("Clone: %s") % model["name"])
            self.dialog.models.addItem(item)
            self.models.append((False, model))  # type: ignore
        self.dialog.models.setCurrentRow(0)
        # the list widget will swallow the enter key
        shortcut = QShortcut(QKeySequence("Return"), self)
        qconnect(shortcut.activated, self.accept)
        # help
        qconnect(self.dialog.buttonBox.helpRequested, self.onHelp)

    def get(self):
        self.exec_()
        return self.model

    def reject(self):
        QDialog.reject(self)

    def accept(self):
        (isStd, model) = self.models[self.dialog.models.currentRow()]
        if isStd:
            # create
            self.model = model(self.col)
        else:
            # add copy to deck
            self.model = self.mw.col.models.copy(model)
            self.mw.col.models.setCurrent(self.model)
        QDialog.accept(self)

    def onHelp(self):
        openHelp("notetypes")
