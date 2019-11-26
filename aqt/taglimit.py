# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/copyleft/agpl.html

import aqt
from aqt.qt import *
from aqt.utils import restoreGeom, saveGeom


class TagLimit(QDialog):

    def __init__(self, mw, parent):
        QDialog.__init__(self, parent, Qt.Window)
        self.mw = mw
        self.parent = parent
        self.deck = self.parent.deck
        self.dialog = aqt.forms.taglimit.Ui_Dialog()
        self.dialog.setupUi(self)
        shortcut = QShortcut(QKeySequence("ctrl+d"), self.dialog.activeList, context=Qt.WidgetShortcut)
        shortcut.activated.connect(self.dialog.activeList.clearSelection)
        shortcut = QShortcut(QKeySequence("ctrl+d"), self.dialog.inactiveList, context=Qt.WidgetShortcut)
        shortcut.activated.connect(self.dialog.inactiveList.clearSelection)
        self.rebuildTagList()
        restoreGeom(self, "tagLimit")
        self.exec_()

    def rebuildTagList(self):
        usertags = self.mw.col.tags.byDeck(self.deck.getId(), True)
        yes = self.deck.get("activeTags", [])
        noes = self.deck.get("inactiveTags", [])
        yesHash = {}
        noHash = {}
        for y in yes:
            yesHash[y] = True
        for no in noes:
            noHash[no] = True
        groupedTags = []
        usertags.sort()
        groupedTags.append(usertags)
        self.tags = []
        for tags in groupedTags:
            for tag in tags:
                self.tags.append(tag)
                item = QListWidgetItem(tag.replace("_", " "))
                self.dialog.activeList.addItem(item)
                if tag in yesHash:
                    mode = QItemSelectionModel.Select
                    self.dialog.activeCheck.setChecked(True)
                else:
                    mode = QItemSelectionModel.Deselect
                idx = self.dialog.activeList.indexFromItem(item)
                self.dialog.activeList.selectionModel().select(idx, mode)
                # inactive
                item = QListWidgetItem(tag.replace("_", " "))
                self.dialog.inactiveList.addItem(item)
                if tag in noHash:
                    mode = QItemSelectionModel.Select
                else:
                    mode = QItemSelectionModel.Deselect
                idx = self.dialog.inactiveList.indexFromItem(item)
                self.dialog.inactiveList.selectionModel().select(idx, mode)

    def reject(self):
        self.tags = ""
        QDialog.reject(self)

    def accept(self):
        self.hide()
        # gather yes/no tags
        yes = []
        noes = []
        for index in range(self.dialog.activeList.count()):
            # active
            if self.dialog.activeCheck.isChecked():
                item = self.dialog.activeList.item(index)
                idx = self.dialog.activeList.indexFromItem(item)
                if self.dialog.activeList.selectionModel().isSelected(idx):
                    yes.append(self.tags[index])
            # inactive
            item = self.dialog.inactiveList.item(index)
            idx = self.dialog.inactiveList.indexFromItem(item)
            if self.dialog.inactiveList.selectionModel().isSelected(idx):
                noes.append(self.tags[index])
        # save in the deck for future invocations
        self.deck['activeTags'] = yes
        self.deck['inactiveTags'] = noes
        self.deck.save()
        # build query string
        self.tags = ""
        if yes:
            arr = []
            for req in yes:
                arr.append("tag:'%s'" % req)
            self.tags += "(" + " or ".join(arr) + ")"
        if noes:
            arr = []
            for req in noes:
                arr.append("-tag:'%s'" % req)
            self.tags += " " + " ".join(arr)
        saveGeom(self, "tagLimit")
        QDialog.accept(self)
