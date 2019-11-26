# Copyright: Ankitects Pty Ltd and contributors
# -*- coding: utf-8 -*-
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
from operator import itemgetter

import aqt
from anki.consts import NEW_CARDS_RANDOM
from anki.lang import _, ngettext
from aqt.qt import *
from aqt.utils import (askUser, getOnlyText, openHelp, restoreGeom, saveGeom,
                       showInfo, showWarning, tooltip)


class DeckConf(QDialog):
    def __init__(self, mw, deck):
        QDialog.__init__(self, mw)
        self.mw = mw
        self.deck = deck
        self.childDids = self.deck.getDescendantsIds()
        self._origNewOrder = None
        self.form = aqt.forms.dconf.Ui_Dialog()
        self.form.setupUi(self)
        self.mw.checkpoint(_("Options"))
        self.setupCombos()
        self.setupConfs()
        self.setWindowModality(Qt.WindowModal)
        self.form.buttonBox.helpRequested.connect(lambda: openHelp("deckoptions"))
        self.form.confOpts.clicked.connect(self.confOpts)
        self.form.buttonBox.button(QDialogButtonBox.RestoreDefaults).clicked.connect(self.onRestore)
        self.setWindowTitle(_("Options for %s") % self.deck.getName())
        # qt doesn't size properly with altered fonts otherwise
        restoreGeom(self, "deckconf", adjustSize=True)
        self.show()
        self.exec_()
        saveGeom(self, "deckconf")

    def setupCombos(self):
        import anki.consts as cs
        self.form.newOrder.addItems(list(cs.newCardOrderLabels().values()))
        self.form.newOrder.currentIndexChanged.connect(self.onNewOrderChanged)

    # Conf list
    ######################################################################

    def setupConfs(self):
        self.form.dconf.currentIndexChanged.connect(self.onConfChange)
        self.conf = None
        self.loadConfs()

    def loadConfs(self):
        current = self.deck.getConfId()
        self.confList = self.mw.col.decks.allConf()
        self.confList.sort(key=itemgetter('name'))
        startOn = 0
        self.ignoreConfChange = True
        self.form.dconf.clear()
        for idx, conf in enumerate(self.confList):
            self.form.dconf.addItem(conf.getName())
            if str(conf.getId()) == str(current):
                startOn = idx
        self.ignoreConfChange = False
        self.form.dconf.setCurrentIndex(startOn)
        if self._origNewOrder is None:
            self._origNewOrder =  self.confList[startOn]['new']['order']
        self.onConfChange(startOn)

    def confOpts(self):
        menu = QMenu(self.mw)
        action = menu.addAction(_("Add"))
        action.triggered.connect(self.addGroup)
        action = menu.addAction(_("Delete"))
        action.triggered.connect(self.remGroup)
        action = menu.addAction(_("Rename"))
        action.triggered.connect(self.renameGroup)
        action = menu.addAction(_("Set for all subdecks"))
        action.triggered.connect(self.setChildren)
        if not self.childDids:
            action.setEnabled(False)
        menu.exec_(QCursor.pos())

    def onConfChange(self, idx):
        if self.ignoreConfChange:
            return
        if self.conf:
            self.saveConf()
        conf = self.confList[idx]
        self.deck.setConf(conf.getId())
        self.loadConf()
        cnt = 0
        for deck in self.mw.col.decks.all():
            if deck.isDyn():
                continue
            if deck.getConfId() == conf.getId():
                cnt += 1
        if cnt > 1:
            txt = _("Your changes will affect multiple decks. If you wish to "
            "change only the current deck, please add a new options group first.")
        else:
            txt = ""
        self.form.count.setText(txt)

    def addGroup(self):
        name = getOnlyText(_("New options group name:"))
        if not name:
            return
        # first, save currently entered data to current conf
        self.saveConf()
        # then clone the conf
        id = self.mw.col.decks.confId(name, cloneFrom=self.conf)
        # set the deck to the new conf
        self.deck.setConf(id)
        # then reload the conf list
        self.loadConfs()

    def remGroup(self):
        if self.conf.isDefault():
            showInfo(_("The default configuration can't be removed."), self)
        else:
            self.mw.col.decks.remConf(self.conf.getId())
            self.deck.setDefaultConf()
            self.loadConfs()

    def renameGroup(self):
        old = self.conf.getName()
        name = getOnlyText(_("New name:"), default=old)
        if not name or name == old:
            return
        self.conf.setName(name)
        self.loadConfs()

    def setChildren(self):
        if not askUser(
            _("Set all decks below %s to this option group?") %
            self.deck.getName()):
            return
        for did in self.childDids:
            deck = self.mw.col.decks.get(did)
            if deck.isDyn():
                continue
            deck.setConf(self.deck['conf'])
            self.mw.col.decks.save(deck)
        tooltip(ngettext("%d deck updated.", "%d decks updated.", \
                        len(self.childDids)) % len(self.childDids))

    # Loading
    ##################################################

    def listToUser(self, delays):
        return " ".join([str(delay) for delay in delays])

    def parentLimText(self, type="new"):
        # top level?
        if self.deck.isTopLevel():
            return ""
        lim = -1
        for ancestor in self.deck.getAncestors():
            conf = ancestor.getConf()
            perDay = conf[type]['perDay']
            if lim == -1:
                lim = perDay
            else:
                lim = min(perDay, lim)
        return _("(parent limit: %d)") % lim

    def loadConf(self):
        self.conf = self.deck.getConf()
        # new
        conf = self.conf['new']
        self.form.lrnSteps.setText(self.listToUser(conf['delays']))
        self.form.lrnGradInt.setValue(conf['ints'][0])
        self.form.lrnEasyInt.setValue(conf['ints'][1])
        self.form.lrnEasyInt.setValue(conf['ints'][1])
        self.form.lrnFactor.setValue(conf['initialFactor']/10.0)
        self.form.newOrder.setCurrentIndex(conf['order'])
        self.form.newPerDay.setValue(conf['perDay'])
        self.form.bury.setChecked(conf.get("bury", True))
        self.form.newplim.setText(self.parentLimText('new'))
        # rev
        conf = self.conf['rev']
        self.form.revPerDay.setValue(conf['perDay'])
        self.form.easyBonus.setValue(conf['ease4']*100)
        self.form.fi1.setValue(conf['ivlFct']*100)
        self.form.maxIvl.setValue(conf['maxIvl'])
        self.form.revplim.setText(self.parentLimText('rev'))
        self.form.buryRev.setChecked(conf.get("bury", True))
        self.form.hardFactor.setValue(int(conf.get("hardFactor", 1.2)*100))
        if self.mw.col.schedVer() == 1:
            self.form.hardFactor.setVisible(False)
            self.form.hardFactorLabel.setVisible(False)
        # lapse
        conf = self.conf['lapse']
        self.form.lapSteps.setText(self.listToUser(conf['delays']))
        self.form.lapMult.setValue(conf['mult']*100)
        self.form.lapMinInt.setValue(conf['minInt'])
        self.form.leechThreshold.setValue(conf['leechFails'])
        self.form.leechAction.setCurrentIndex(conf['leechAction'])
        # general
        conf = self.conf
        self.form.maxTaken.setValue(conf['maxTaken'])
        self.form.showTimer.setChecked(conf.get('timer', 0))
        self.form.autoplaySounds.setChecked(conf['autoplay'])
        self.form.replayQuestion.setChecked(conf.get('replayq', True))
        # description
        self.form.desc.setPlainText(self.deck['desc'])

    def onRestore(self):
        self.mw.progress.start()
        self.mw.col.decks.restoreToDefault(self.conf)
        self.mw.progress.finish()
        self.loadConf()

    # New order
    ##################################################

    def onNewOrderChanged(self, new):
        old = self.conf['new']['order']
        if old == new:
            return
        self.conf['new']['order'] = new
        self.mw.progress.start()
        self.mw.col.sched.resortConf(self.conf)
        self.mw.progress.finish()

    # Saving
    ##################################################

    def updateList(self, conf, key, steps, minSize=1):
        items = str(steps.text()).split(" ")
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
        conf[key] = ret

    def saveConf(self):
        # new
        conf = self.conf['new']
        self.updateList(conf, 'delays', self.form.lrnSteps)
        conf['ints'][0] = self.form.lrnGradInt.value()
        conf['ints'][1] = self.form.lrnEasyInt.value()
        conf['initialFactor'] = self.form.lrnFactor.value()*10
        conf['order'] = self.form.newOrder.currentIndex()
        conf['perDay'] = self.form.newPerDay.value()
        conf['bury'] = self.form.bury.isChecked()
        if self._origNewOrder != conf['order']:
            # order of current deck has changed, so have to resort
            if conf['order'] == NEW_CARDS_RANDOM:
                self.mw.col.sched.randomizeCards(self.deck.getId())
            else:
                self.mw.col.sched.orderCards(self.deck.getId())
        # rev
        conf = self.conf['rev']
        conf['perDay'] = self.form.revPerDay.value()
        conf['ease4'] = self.form.easyBonus.value()/100.0
        conf['ivlFct'] = self.form.fi1.value()/100.0
        conf['maxIvl'] = self.form.maxIvl.value()
        conf['bury'] = self.form.buryRev.isChecked()
        conf['hardFactor'] = self.form.hardFactor.value()/100.0
        # lapse
        conf = self.conf['lapse']
        self.updateList(conf, 'delays', self.form.lapSteps, minSize=0)
        conf['mult'] = self.form.lapMult.value()/100.0
        conf['minInt'] = self.form.lapMinInt.value()
        conf['leechFails'] = self.form.leechThreshold.value()
        conf['leechAction'] = self.form.leechAction.currentIndex()
        # general
        conf = self.conf
        conf['maxTaken'] = self.form.maxTaken.value()
        conf['timer'] = self.form.showTimer.isChecked() and 1 or 0
        conf['autoplay'] = self.form.autoplaySounds.isChecked()
        conf['replayq'] = self.form.replayQuestion.isChecked()
        # description
        self.deck['desc'] = self.form.desc.toPlainText()
        self.mw.col.decks.save(self.deck)
        self.mw.col.decks.save(self.conf)

    def reject(self):
        self.accept()

    def accept(self):
        self.saveConf()
        self.mw.reset()
        QDialog.accept(self)
