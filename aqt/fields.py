# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

import aqt
from anki.consts import *
from anki.lang import _, ngettext
from aqt.qt import *
from aqt.utils import askUser, getOnlyText, openHelp, showWarning


class FieldDialog(QDialog):

    def __init__(self, mw, note, ord=0, parent=None):
        QDialog.__init__(self, parent or mw) #, Qt.Window)
        self.mw = aqt.mw
        self.parent = parent or mw
        self.note = note
        self.col = self.mw.col
        self.mm = self.mw.col.models
        self.model = note.model()
        self.mw.checkpoint(_("Fields"))
        self.form = aqt.forms.fields.Ui_Dialog()
        self.form.setupUi(self)
        self.setWindowTitle(_("Fields for %s") % self.model.getName())
        self.form.buttonBox.button(QDialogButtonBox.Help).setAutoDefault(False)
        self.form.buttonBox.button(QDialogButtonBox.Close).setAutoDefault(False)
        self.currentIdx = None
        self.oldSortField = self.model['sortf']
        self.fillFields()
        self.setupSignals()
        self.form.fieldList.setCurrentRow(0)
        self.exec_()

    ##########################################################################

    def fillFields(self):
        """Write "ord:name" in each line"""
        self.currentIdx = None
        self.form.fieldList.clear()
        for index, fldType in enumerate(self.model['flds']):
            self.form.fieldList.addItem("{}: {}".format(index+1, fldType.getName()))

    def setupSignals(self):
        self.form.fieldList.currentRowChanged.connect(self.onRowChange)
        self.form.fieldAdd.clicked.connect(self.onAdd)
        self.form.fieldDelete.clicked.connect(self.onDelete)
        self.form.fieldRename.clicked.connect(self.onRename)
        self.form.fieldPosition.clicked.connect(self.onPosition)
        self.form.sortField.clicked.connect(self.onSortField)
        self.form.buttonBox.helpRequested.connect(self.onHelp)

    def onRowChange(self, idx):
        if idx == -1:
            return
        self.saveField()
        self.loadField(idx)

    def _uniqueName(self, prompt, ignoreOrd=None, old=""):
        """Ask for a new name using prompt, and default value old. Return it.

        Unless this name is already used elsewhere, in this case, return None and show a warning. """
        txt = getOnlyText(prompt, default=old)
        if not txt:
            return
        for fldType in self.model['flds']:
            if ignoreOrd is not None and fldType['ord'] == ignoreOrd:
                continue
            if fldType.getName() == txt:
                showWarning(_("That field name is already used."))
                return
        return txt

    def onRename(self):
        """Ask for a new name. If required, save in in the model, and reload the content.

        Templates are edited to use the new name. requirements are also recomputed.
        """
        idx = self.currentIdx
        fldType = self.model['flds'][idx]
        name = self._uniqueName(_("New name:"), self.currentIdx, fldType.getName())
        if not name:
            return
        self.mm.renameField(self.model, fldType, name)
        self.saveField()
        self.fillFields()
        self.form.fieldList.setCurrentRow(idx)

    def onAdd(self):
        name = self._uniqueName(_("Field name:"))
        if not name:
            return
        self.saveField()
        self.mw.progress.start()
        fldType = self.mm.newField(self.model, name)
        self.mm.addField(self.model, fldType)
        self.mw.progress.finish()
        self.fillFields()
        self.form.fieldList.setCurrentRow(len(self.model['flds'])-1)

    def onDelete(self):
        if len(self.model['flds']) < 2:
            return showWarning(_("Notes require at least one field."))
        count = self.model.useCount()
        count = ngettext("%d note", "%d notes", count) % count
        if not askUser(_("Delete field from %s?") % count):
            return
        fldType = self.model['flds'][self.form.fieldList.currentRow()]
        self.mw.progress.start()
        self.mm.remField(self.model, fldType)
        self.mw.progress.finish()
        self.fillFields()
        self.form.fieldList.setCurrentRow(0)

    def onPosition(self, delta=-1):
        idx = self.currentIdx
        nbFields = len(self.model['flds'])
        txt = getOnlyText(_("New position (1...%d):") % nbFields, default=str(idx+1))
        if not txt:
            return
        try:
            pos = int(txt)
        except ValueError:
            return
        if not 0 < pos <= nbFields:
            return
        self.saveField()
        fldType = self.model['flds'][self.currentIdx]
        self.mw.progress.start()
        self.mm.moveField(self.model, fldType, pos-1)
        self.mw.progress.finish()
        self.fillFields()
        self.form.fieldList.setCurrentRow(pos-1)

    def onSortField(self):
        # don't allow user to disable; it makes no sense
        self.form.sortField.setChecked(True)
        self.model['sortf'] = self.form.fieldList.currentRow()

    def loadField(self, idx):
        self.currentIdx = idx
        fldType = self.model['flds'][idx]
        self.form.fontFamily.setCurrentFont(QFont(fldType['font']))
        self.form.fontSize.setValue(fldType['size'])
        self.form.sticky.setChecked(fldType['sticky'])
        self.form.sortField.setChecked(self.model['sortf'] == fldType['ord'])
        self.form.rtl.setChecked(fldType['rtl'])

    def saveField(self):
        """Save all options in current field"""
        # not initialized yet?
        if self.currentIdx is None:
            return
        idx = self.currentIdx
        fldType = self.model['flds'][idx]
        fldType['font'] = self.form.fontFamily.currentFont().family()
        fldType['size'] = self.form.fontSize.value()
        fldType['sticky'] = self.form.sticky.isChecked()
        fldType['rtl'] = self.form.rtl.isChecked()

    def reject(self):
        """Close the window. If there were some change, recompute with updateFieldCache(todo)"""
        self.saveField()
        if self.oldSortField != self.model['sortf']:
            self.mw.progress.start()
            self.mw.col.updateFieldCache(self.model.nids())
            self.mw.progress.finish()
        self.model.save()
        self.mw.reset()
        QDialog.reject(self)

    def accept(self):
        self.reject()

    def onHelp(self):
        openHelp("fields")
