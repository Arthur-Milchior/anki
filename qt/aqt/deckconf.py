# Copyright: Ankitects Pty Ltd and contributors
# -*- coding: utf-8 -*-
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

from operator import itemgetter
from typing import Dict, Union

import aqt
from anki.consts import NEW_CARDS_RANDOM
from anki.lang import _, ngettext
from aqt import gui_hooks
from aqt.qt import *
from aqt.utils import (
    askUser,
    getOnlyText,
    openHelp,
    restoreGeom,
    saveGeom,
    showInfo,
    showWarning,
    tooltip,
)


class DeckConf(QDialog):
    def __init__(self, mw: aqt.AnkiQt, deck: Dict):
        QDialog.__init__(self, mw)
        self.mw = mw
        self.deck = deck
        self.childDids = [d[1] for d in self.mw.col.decks.children(self.deck["id"])]
        self._origNewOrder = None
        self.form = aqt.forms.dconf.Ui_Dialog()
        self.form.setupUi(self)
        gui_hooks.deck_conf_did_setup_ui_form(self)
        self.mw.checkpoint(_("Options"))
        self.setupCombos()
        self.setupConfs()
        self.setWindowModality(Qt.WindowModal)
        qconnect(self.form.buttonBox.helpRequested, lambda: openHelp("deckoptions"))
        qconnect(self.form.confOpts.clicked, self.confOpts)
        qconnect(
            self.form.buttonBox.button(QDialogButtonBox.RestoreDefaults).clicked,
            self.onRestore,
        )
        self.setWindowTitle(_("Options for %s") % self.deck["name"])
        # qt doesn't size properly with altered fonts otherwise
        restoreGeom(self, "deckconf", adjustSize=True)
        gui_hooks.deck_conf_will_show(self)
        self.show()
        self.exec_()
        saveGeom(self, "deckconf")

    def setupCombos(self):
        import anki.consts as cs

        f = self.form
        f.newOrder.addItems(list(cs.newCardOrderLabels().values()))
        qconnect(f.newOrder.currentIndexChanged, self.onNewOrderChanged)

    # Conf list
    ######################################################################

    def setupConfs(self):
        qconnect(self.form.dconf.currentIndexChanged, self.onConfChange)
        self.conf = None
        self.loadConfs()

    def loadConfs(self):
        current = self.deck["conf"]
        self.confList = self.mw.col.decks.allConf()
        self.confList.sort(key=itemgetter("name"))
        startOn = 0
        self.ignoreConfChange = True
        self.form.dconf.clear()
        for idx, conf in enumerate(self.confList):
            self.form.dconf.addItem(conf["name"])
            if str(conf["id"]) == str(current):
                startOn = idx
        self.ignoreConfChange = False
        self.form.dconf.setCurrentIndex(startOn)
        if self._origNewOrder is None:
            self._origNewOrder = self.confList[startOn]["new"]["order"]
        self.onConfChange(startOn)

    def confOpts(self):
        menu = QMenu(self.mw)
        a = menu.addAction(_("Add"))
        qconnect(a.triggered, self.addGroup)
        a = menu.addAction(_("Delete"))
        qconnect(a.triggered, self.remGroup)
        a = menu.addAction(_("Rename"))
        qconnect(a.triggered, self.renameGroup)
        a = menu.addAction(_("Set for all subdecks"))
        qconnect(a.triggered, self.setChildren)
        if not self.childDids:
            a.setEnabled(False)
        menu.exec_(QCursor.pos())

    def onConfChange(self, idx):
        if self.ignoreConfChange:
            return
        if self.conf:
            self.saveConf()
        conf = self.confList[idx]
        self.deck["conf"] = conf["id"]
        self.mw.col.decks.save(self.deck)
        self.loadConf()
        cnt = len(self.mw.col.decks.didsForConf(conf))
        if cnt > 1:
            txt = _(
                "Your changes will affect multiple decks. If you wish to "
                "change only the current deck, please add a new options group first."
            )
        else:
            txt = ""
        self.form.count.setText(txt)

    def addGroup(self) -> None:
        name = getOnlyText(_("New options group name:"))
        if not name:
            return

        # first, save currently entered data to current conf
        self.saveConf()
        # then clone the conf
        id = self.mw.col.decks.add_config_returning_id(name, clone_from=self.conf)
        gui_hooks.deck_conf_did_add_config(self, self.deck, self.conf, name, id)
        # set the deck to the new conf
        self.deck["conf"] = id
        # then reload the conf list
        self.loadConfs()

    def remGroup(self) -> None:
        if int(self.conf["id"]) == 1:
            showInfo(_("The default configuration can't be removed."), self)
        else:
            gui_hooks.deck_conf_will_remove_config(self, self.deck, self.conf)
            self.mw.col.modSchema(check=True)
            self.mw.col.decks.remove_config(self.conf["id"])
            self.conf = None
            self.deck["conf"] = 1
            self.loadConfs()

    def renameGroup(self) -> None:
        old = self.conf["name"]
        name = getOnlyText(_("New name:"), default=old)
        if not name or name == old:
            return

        gui_hooks.deck_conf_will_rename_config(self, self.deck, self.conf, name)
        self.conf["name"] = name
        self.saveConf()
        self.loadConfs()

    def setChildren(self):
        if not askUser(
            _("Set all decks below %s to this option group?") % self.deck["name"]
        ):
            return
        for did in self.childDids:
            deck = self.mw.col.decks.get(did)
            if deck["dyn"]:
                continue
            deck["conf"] = self.deck["conf"]
            self.mw.col.decks.save(deck)
        tooltip(
            ngettext("%d deck updated.", "%d decks updated.", len(self.childDids))
            % len(self.childDids)
        )

    # Loading
    ##################################################

    def listToUser(self, l):
        def num_to_user(n: Union[int, float]):
            if n == round(n):
                return str(int(n))
            else:
                return str(n)

        return " ".join(map(num_to_user, l))

    def parentLimText(self, type="new"):
        # top level?
        if "::" not in self.deck["name"]:
            return ""
        lim = -1
        for d in self.mw.col.decks.parents(self.deck["id"]):
            conf = self.mw.col.decks.confForDid(d["id"])
            x = conf[type]["perDay"]
            if lim == -1:
                lim = x
            else:
                lim = min(x, lim)
        return _("(parent limit: %d)") % lim

    def loadConf(self):
        self.conf = self.mw.col.decks.confForDid(self.deck["id"])
        # new
        conf = self.conf["new"]
        f = self.form
        f.lrnSteps.setText(self.listToUser(conf["delays"]))
        f.lrnGradInt.setValue(conf["ints"][0])
        f.lrnEasyInt.setValue(conf["ints"][1])
        f.lrnFactor.setValue(conf["initialFactor"] / 10.0)
        f.newOrder.setCurrentIndex(conf["order"])
        f.newPerDay.setValue(conf["perDay"])
        f.bury.setChecked(conf.get("bury", True))
        f.newplim.setText(self.parentLimText("new"))
        # rev
        conf = self.conf["rev"]
        f.revPerDay.setValue(conf["perDay"])
        f.easyBonus.setValue(conf["ease4"] * 100)
        f.fi1.setValue(conf["ivlFct"] * 100)
        f.maxIvl.setValue(conf["maxIvl"])
        f.revplim.setText(self.parentLimText("rev"))
        f.buryRev.setChecked(conf.get("bury", True))
        f.hardFactor.setValue(int(conf.get("hardFactor", 1.2) * 100))
        if self.mw.col.schedVer() == 1:
            f.hardFactor.setVisible(False)
            f.hardFactorLabel.setVisible(False)
        # lapse
        conf = self.conf["lapse"]
        f.lapSteps.setText(self.listToUser(conf["delays"]))
        f.lapMult.setValue(conf["mult"] * 100)
        f.lapMinInt.setValue(conf["minInt"])
        f.leechThreshold.setValue(conf["leechFails"])
        f.leechAction.setCurrentIndex(conf["leechAction"])
        # general
        conf = self.conf
        f.maxTaken.setValue(conf["maxTaken"])
        f.showTimer.setChecked(conf.get("timer", 0))
        f.autoplaySounds.setChecked(conf["autoplay"])
        f.replayQuestion.setChecked(conf.get("replayq", True))
        # description
        f.desc.setPlainText(self.deck["desc"])
        gui_hooks.deck_conf_did_load_config(self, self.deck, self.conf)

    def onRestore(self):
        self.mw.progress.start()
        self.mw.col.decks.restoreToDefault(self.conf)
        self.mw.progress.finish()
        self.loadConf()

    # New order
    ##################################################

    def onNewOrderChanged(self, new):
        old = self.conf["new"]["order"]
        if old == new:
            return
        self.conf["new"]["order"] = new
        self.mw.progress.start()
        self.mw.col.sched.resortConf(self.conf)
        self.mw.progress.finish()

    # Saving
    ##################################################

    def updateList(self, conf, key, w, minSize=1):
        items = str(w.text()).split(" ")
        ret = []
        for i in items:
            if not i:
                continue
            try:
                i = float(i)
                assert i > 0
                if i == int(i):
                    i = int(i)
                ret.append(i)
            except:
                # invalid, don't update
                showWarning(_("Steps must be numbers."))
                return
        if len(ret) < minSize:
            showWarning(_("At least one step is required."))
            return
        conf[key] = ret

    def saveConf(self):
        # new
        conf = self.conf["new"]
        f = self.form
        self.updateList(conf, "delays", f.lrnSteps)
        conf["ints"][0] = f.lrnGradInt.value()
        conf["ints"][1] = f.lrnEasyInt.value()
        conf["initialFactor"] = f.lrnFactor.value() * 10
        conf["order"] = f.newOrder.currentIndex()
        conf["perDay"] = f.newPerDay.value()
        conf["bury"] = f.bury.isChecked()
        if self._origNewOrder != conf["order"]:
            # order of current deck has changed, so have to resort
            if conf["order"] == NEW_CARDS_RANDOM:
                self.mw.col.sched.randomizeCards(self.deck["id"])
            else:
                self.mw.col.sched.orderCards(self.deck["id"])
        # rev
        conf = self.conf["rev"]
        conf["perDay"] = f.revPerDay.value()
        conf["ease4"] = f.easyBonus.value() / 100.0
        conf["ivlFct"] = f.fi1.value() / 100.0
        conf["maxIvl"] = f.maxIvl.value()
        conf["bury"] = f.buryRev.isChecked()
        conf["hardFactor"] = f.hardFactor.value() / 100.0
        # lapse
        conf = self.conf["lapse"]
        self.updateList(conf, "delays", f.lapSteps, minSize=0)
        conf["mult"] = f.lapMult.value() / 100.0
        conf["minInt"] = f.lapMinInt.value()
        conf["leechFails"] = f.leechThreshold.value()
        conf["leechAction"] = f.leechAction.currentIndex()
        # general
        conf = self.conf
        conf["maxTaken"] = f.maxTaken.value()
        conf["timer"] = f.showTimer.isChecked() and 1 or 0
        conf["autoplay"] = f.autoplaySounds.isChecked()
        conf["replayq"] = f.replayQuestion.isChecked()
        # description
        self.deck["desc"] = f.desc.toPlainText()
        gui_hooks.deck_conf_will_save_config(self, self.deck, self.conf)
        self.mw.col.decks.save(self.deck)
        self.mw.col.decks.save(self.conf)

    def reject(self):
        self.accept()

    def accept(self):
        self.saveConf()
        self.mw.reset()
        QDialog.accept(self)
