# Copyright: Ankitects Pty Ltd and contributors
# -*- coding: utf-8 -*-
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

import os
import time

import aqt
from anki.lang import _
from aqt.qt import *
from aqt.utils import (addCloseShortcut, getSaveFile, maybeHideClose,
                       restoreGeom, saveGeom, tooltip)

# Deck Stats
######################################################################

class DeckStats(QDialog):

    def __init__(self, mw):
        QDialog.__init__(self, mw, Qt.Window)
        mw.setupDialogGC(self)
        self.mw = mw
        self.name = "deckStats"
        self.period = 0
        self.form = aqt.forms.stats.Ui_Dialog()
        self.oldPos = None
        self.wholeCollection = False
        self.setMinimumWidth(700)
        self.form.setupUi(self)
        restoreGeom(self, self.name)
        saveButton = self.form.buttonBox.addButton(_("Save PDF"),
                                          QDialogButtonBox.ActionRole)
        saveButton.clicked.connect(self.saveImage)
        saveButton.setAutoDefault(False)
        self.form.groups.clicked.connect(lambda: self.changeScope("deck"))
        self.form.groups.setShortcut("g")
        self.form.all.clicked.connect(lambda: self.changeScope("collection"))
        self.form.month.clicked.connect(lambda: self.changePeriod(0))
        self.form.year.clicked.connect(lambda: self.changePeriod(1))
        self.form.life.clicked.connect(lambda: self.changePeriod(2))
        maybeHideClose(self.form.buttonBox)
        addCloseShortcut(self)
        self.show()
        self.refresh()
        self.activateWindow()

    def reject(self):
        self.form.web = None
        saveGeom(self, self.name)
        aqt.dialogs.markClosed("DeckStats")
        QDialog.reject(self)

    def closeWithCallback(self, callback):
        self.reject()
        callback()

    def _imagePath(self):
        name = time.strftime("-%Y-%m-%d@%H-%M-%S.pdf",
                             time.localtime(time.time()))
        name = "anki-"+_("stats")+name
        file = getSaveFile(self, title=_("Save PDF"),
                           dir_description="stats",
                           key="stats",
                           ext=".pdf",
                           fname=name)
        return file

    def saveImage(self):
        path = self._imagePath()
        if not path:
            return
        self.form.web.page().printToPdf(path)
        tooltip(_("Saved."))

    def changePeriod(self, period):
        self.period = period
        self.refresh()

    def changeScope(self, type):
        self.wholeCollection = type == "collection"
        self.refresh()

    def refresh(self):
        self.mw.progress.start(immediate=True, parent=self)
        stats = self.mw.col.stats()
        stats.wholeCollection = self.wholeCollection
        self.report = stats.report(type=self.period)
        self.form.web.stdHtml("<html><body>"+self.report+"</body></html>",
                              js=["jquery.js", "plot.js"])
        self.mw.progress.finish()
