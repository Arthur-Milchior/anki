# Copyright: Ankitects Pty Ltd and contributors
# -*- coding: utf-8 -*-
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

import aqt
from anki.lang import _
from aqt.qt import *
from aqt.utils import askUser, openHelp, restoreGeom, saveGeom, showWarning


class DeckConf(QDialog):
    def __init__(self, mw, first=False, search="", deck=None):
        QDialog.__init__(self, mw)
        self.mw = mw
        self.deck = deck or self.mw.col.decks.current()
        self.search = search
        self.form = aqt.forms.dyndconf.Ui_Dialog()
        self.form.setupUi(self)
        if first:
            label = _("Build")
        else:
            label = _("Rebuild")
        self.ok = self.form.buttonBox.addButton(
            label, QDialogButtonBox.AcceptRole)
        self.mw.checkpoint(_("Options"))
        self.setWindowModality(Qt.WindowModal)
        self.form.buttonBox.helpRequested.connect(lambda: openHelp("filtered"))
        self.setWindowTitle(_("Options for %s") % self.deck['name'])
        restoreGeom(self, "dyndeckconf")
        self.initialSetup()
        self.loadConf()
        if search:
            self.form.search.setText(search + " is:due")
            self.form.search_2.setText(search + " is:new")
        self.form.search.selectAll()

        if self.mw.col.schedVer() == 1:
            self.form.secondFilter.setVisible(False)

        self.show()
        self.exec_()
        saveGeom(self, "dyndeckconf")

    def initialSetup(self):
        import anki.consts as cs
        self.form.order.addItems(list(cs.dynOrderLabels().values()))
        self.form.order_2.addItems(list(cs.dynOrderLabels().values()))

        self.form.resched.stateChanged.connect(self._onReschedToggled)

    def _onReschedToggled(self, _state):
        self.form.previewDelayWidget.setVisible(not self.form.resched.isChecked()
                                                and self.mw.col.schedVer() > 1)

    def loadConf(self):
        self.form.resched.setChecked(self.deck['resched'])
        self._onReschedToggled(0)

        search, limit, order = self.deck['terms'][0]
        self.form.search.setText(search)

        if self.mw.col.schedVer() == 1:
            if self.deck['delays']:
                self.form.steps.setText(self.listToUser(self.deck['delays']))
                self.form.stepsOn.setChecked(True)
        else:
            self.form.steps.setVisible(False)
            self.form.stepsOn.setVisible(False)

        self.form.order.setCurrentIndex(order)
        self.form.limit.setValue(limit)
        self.form.previewDelay.setValue(self.deck.get("previewDelay", 10))

        if len(self.deck['terms']) > 1:
            search, limit, order = self.deck['terms'][1]
            self.form.search_2.setText(search)
            self.form.order_2.setCurrentIndex(order)
            self.form.limit_2.setValue(limit)
            self.form.secondFilter.setChecked(True)
            self.form.filter2group.setVisible(True)
        else:
            self.form.order_2.setCurrentIndex(5)
            self.form.limit_2.setValue(20)
            self.form.secondFilter.setChecked(False)
            self.form.filter2group.setVisible(False)

    def saveConf(self):
        self.deck['resched'] = self.form.resched.isChecked()
        self.deck['delays'] = None

        if self.mw.col.schedVer() == 1 and self.form.stepsOn.isChecked():
            steps = self.userToList(self.form.steps)
            if steps:
                self.deck['delays'] = steps
            else:
                self.deck['delays'] = None

        terms = [[
            self.form.search.text(),
            self.form.limit.value(),
            self.form.order.currentIndex()]]

        if self.form.secondFilter.isChecked():
            terms.append([
                self.form.search_2.text(),
                self.form.limit_2.value(),
                self.form.order_2.currentIndex()])

        self.deck['terms'] = terms
        self.deck['previewDelay'] = self.form.previewDelay.value()

        self.mw.col.decks.save(self.deck)
        return True

    def reject(self):
        self.ok = False
        QDialog.reject(self)

    def accept(self):
        if not self.saveConf():
            return
        if not self.mw.col.sched.rebuildDyn():
            if askUser(_("""\
The provided search did not match any cards. Would you like to revise \
it?""")):
                return
        self.mw.reset()
        QDialog.accept(self)

    # Step load/save - fixme: share with std options screen
    ########################################################

    def listToUser(self, delays):
        return " ".join([str(x) for x in delays])

    def userToList(self, w, minSize=1):
        items = str(w.text()).split(" ")
        ret = []
        for item in items:
            if not item:
                continue
            try:
                item = float(item)
                assert item > 0
                if item == int(item):
                    item = int(item)
                ret.append(item)
            except:
                # invalid, don't update
                showWarning(_("Steps must be numbers."))
                return
        if len(ret) < minSize:
            showWarning(_("At least one step is required."))
            return
        return ret
