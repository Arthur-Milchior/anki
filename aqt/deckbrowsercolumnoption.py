# Copyright: Ankitects Pty Ltd and contributors
# -*- coding: utf-8 -*-
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
from operator import itemgetter

from anki.consts import *
from aqt.qt import *
import aqt
from aqt.deckcolumns import columns
from aqt.utils import showInfo, showWarning, openHelp, getOnlyText, askUser, \
    tooltip, saveGeom, restoreGeom
from anki.lang import _, ngettext

class DeckBrowserColumnOption(QDialog):
    def __init__(self, deckbrowser, column):
        QDialog.__init__(self, deckbrowser.mw)
        self.mw = deckbrowser.mw
        self.deckbrowser = deckbrowser
        self.column = column
        self.form = aqt.forms.deckbrowsercolumnoption.Ui_Dialog()
        self.form.setupUi(self)
        self.mw.checkpoint(_("Column options"))
        self.color = self.deckbrowser.getColor(self.column)
        self.setupColumns()
        self.setWindowModality(Qt.WindowModal)
        if column:
            title = _("New column in deck browser")
        else:
            title = _("Edit column %s") % column['name']
        self.setWindowTitle(title)
        # qt doesn't size properly with altered fonts otherwise
        restoreGeom(self, "deckbrowsercolumnoption", adjustSize=True)
        self.show()
        self.exec_()
        saveGeom(self, "deckbrowsercolumnoption")

    # Column list
    ######################################################################

    def setupColumns(self):
        self.possibleColumns = self.deckbrowser._allPossibleColumns()
        startOn = 0
        self.ignoreColumnChange = True
        self.form.column.clear()
        for idx, name in enumerate(self.possibleColumns):
            self.form.column.addItem(self.deckbrowser.getHeader(columns[name]))
            if name == self.column['name']:
                startOn = idx
        self.ignoreColumnChange = False
        self.form.column.setCurrentIndex(startOn)
        self.form.percent.setChecked(self.column.get("percent", False))
        self.form.withSubdecks.setChecked(self.column.get("withSubdecks", True))
        self.form.defaultColor.setChecked(self.column.get("defaultColor", True))
        self.form.header.setText(self.column.get("header", ""))
        self.form.defaultColor.clicked.connect(self.changeColor)
        self.changeColor()
        self.setupDescription()
        self.form.column.currentIndexChanged.connect(self.setupDescription)

    def setupDescription(self):
        description = columns[self.getSelectedName()]["description"]
        self.form.description.setText(description)


    def changeColor(self):
        hide = self.form.defaultColor.isChecked()
        print(f"Change color called, hide is {hide}")
        self.form.colorLabel.setHidden(hide)
        self.form.colorButton.setHidden(hide)
        button = self.form.colorButton
        button.clicked.connect(self._onColor)
        button.setStyleSheet(f"background-color: {self.color}")

    def _onColor(self):
        new = QColorDialog.getColor(QColor(self.color), self, f"Choose the color for {self.getSelectedName()}")
        if new.isValid():
            newColor = new.name()
            self.color = newColor
            self.form.colorButton.setStyleSheet(f"background-color: {newColor}")

    def updateColumn(self):
        self.column["withSubdecks"] = self.form.withSubdecks.isChecked()
        self.column["defaultColor"] = self.form.defaultColor.isChecked()
        self.column["color"] = self.color
        self.column["percent"] = self.form.percent.isChecked()
        self.column["header"] = self.form.header.text()
        if not self.column["header"]:
            del self.column["header"]
        self.column["name"] = self.getSelectedName()

    def getSelectedName(self):
        return self.possibleColumns[self.form.column.currentIndex()]

    def reject(self):
        self.accept()
        # self.column.clear()
        # super().reject()

    def accept(self):
        self.updateColumn()
        super().accept()
