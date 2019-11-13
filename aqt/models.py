# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

import collections
from operator import itemgetter

import aqt.clayout
from anki import stdmodels
from anki.lang import _, ngettext
from aqt.qt import *
from aqt.utils import (askUser, getText, maybeHideClose, openHelp, restoreGeom,
                       saveGeom, showInfo)


class Models(QDialog):
    def __init__(self, mw, parent=None, fromMain=False):
        self.mw = mw
        self.parent = parent or mw
        self.fromMain = fromMain
        QDialog.__init__(self, self.parent, Qt.Window)
        self.col = mw.col
        self.mm = self.col.models
        self.mw.checkpoint(_("Note Types"))
        self.form = aqt.forms.models.Ui_Dialog()
        self.form.setupUi(self)
        self.form.buttonBox.helpRequested.connect(lambda: openHelp("notetypes"))
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
        addButton.clicked.connect(self.onAdd)
        renameButton = box.addButton(_("Rename"), t)
        renameButton.clicked.connect(self.onRename)
        deleteButton = box.addButton(_("Delete"), t)
        deleteButton.clicked.connect(self.onDelete)
        if self.fromMain:
            fieldButton = box.addButton(_("Fields..."), t)
            fieldButton.clicked.connect(self.onFields)
            cardButton = box.addButton(_("Cards..."), t)
            cardButton.clicked.connect(self.onCards)
        optionButton = box.addButton(_("Options..."), t)
        optionButton.clicked.connect(self.onAdvanced)
        self.form.modelsList.currentRowChanged.connect(self.modelChanged)
        self.form.modelsList.itemDoubleClicked.connect(self.onRename)
        self.updateModelsList()
        self.form.modelsList.setCurrentRow(0)
        maybeHideClose(box)

    def onRename(self):
        txt = getText(_("New name:"), default=self.model['name'])
        if txt[1] and txt[0]:
            self.model['name'] = txt[0]
            self.mm.save(self.model)
        self.updateModelsList()

    def updateModelsList(self):
        row = self.form.modelsList.currentRow()
        if row == -1:
            row = 0
        self.models = self.col.models.all()
        self.models.sort(key=itemgetter("name"))
        self.form.modelsList.clear()
        for model in self.models:
            mUse = self.mm.useCount(model)
            mUse = ngettext("%d note", "%d notes", mUse) % mUse
            item = QListWidgetItem("%s [%s]" % (model['name'], mUse))
            self.form.modelsList.addItem(item)
        self.form.modelsList.setCurrentRow(row)

    def modelChanged(self):
        if self.model:
            self.saveModel()
        idx = self.form.modelsList.currentRow()
        self.model = self.models[idx]

    def onAdd(self):
        model = AddModel(self.mw, self).get()
        if model:
            txt = getText(_("Name:"), default=model['name'])[0]
            if txt:
                model['name'] = txt
            self.mm.ensureNameUnique(model)
            self.mm.save(model)
            self.updateModelsList()

    def onDelete(self):
        if len(self.models) < 2:
            showInfo(_("Please add another note type first."),
                     parent=self)
            return
        if self.mm.useCount(self.model):
            msg = _("Delete this note type and all its cards?")
        else:
            msg = _("Delete this unused note type?")
        if not askUser(msg, parent=self):
            return
        self.mm.rem(self.model)
        self.model = None
        self.updateModelsList()

    def onAdvanced(self):
        dialog = QDialog(self)
        frm = aqt.forms.modelopts.Ui_Dialog()
        frm.setupUi(dialog)
        frm.latexsvg.setChecked(self.model.get("latexsvg", False))
        frm.latexHeader.setText(self.model['latexPre'])
        frm.latexFooter.setText(self.model['latexPost'])
        dialog.setWindowTitle(_("Options for %s") % self.model['name'])
        frm.buttonBox.helpRequested.connect(lambda: openHelp("latex"))
        restoreGeom(dialog, "modelopts")
        dialog.exec_()
        saveGeom(dialog, "modelopts")
        self.model['latexsvg'] = frm.latexsvg.isChecked()
        self.model['latexPre'] = str(frm.latexHeader.toPlainText())
        self.model['latexPost'] = str(frm.latexFooter.toPlainText())

    def saveModel(self):
        self.mm.save(self.model)

    def _tmpNote(self):
        self.mm.setCurrent(self.model)
        note = self.col.newNote(forDeck=False)
        for name in list(note.keys()):
            note[name] = "("+name+")"
        try:
            if "{{cloze:Text}}" in self.model['tmpls'][0]['qfmt']:
                note['Text'] = _("This is a {{c1::sample}} cloze deletion.")
        except:
            # invalid cloze
            pass
        return note

    def onFields(self):
        from aqt.fields import FieldDialog
        note = self._tmpNote()
        FieldDialog(self.mw, note, parent=self)

    def onCards(self):
        from aqt.clayout import CardLayout
        note = self._tmpNote()
        CardLayout(self.mw, note, ord=0, parent=self, addMode=True)

    # Cleanup
    ##########################################################################

    # need to flush model on change or reject

    def reject(self):
        self.saveModel()
        self.mw.reset()
        saveGeom(self, "models")
        QDialog.reject(self)

class AddModel(QDialog):

    def __init__(self, mw, parent=None):
        self.parent = parent or mw
        self.mw = mw
        self.col = mw.col
        QDialog.__init__(self, self.parent, Qt.Window)
        self.model = None
        self.dialog = aqt.forms.addmodel.Ui_Dialog()
        self.dialog.setupUi(self)
        # standard models
        self.models = []
        for (name, func) in stdmodels.models:
            if isinstance(name, collections.Callable):
                name = name()
            item = QListWidgetItem(_("Add: %s") % name)
            self.dialog.models.addItem(item)
            self.models.append((True, func))
        # add copies
        for model in sorted(self.col.models.all(), key=itemgetter("name")):
            item = QListWidgetItem(_("Clone: %s") % model['name'])
            self.dialog.models.addItem(item)
            self.models.append((False, model))
        self.dialog.models.setCurrentRow(0)
        # the list widget will swallow the enter key
        s = QShortcut(QKeySequence("Return"), self)
        s.activated.connect(self.accept)
        # help
        self.dialog.buttonBox.helpRequested.connect(self.onHelp)

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
