# -*- coding: utf-8 -*-
# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

import datetime
import time

import anki.lang
import aqt
from anki.lang import _
from aqt.qt import *
from aqt.utils import askUser, openHelp, showInfo


class Preferences(QDialog):

    def __init__(self, mw):
        QDialog.__init__(self, mw, Qt.Window)
        self.mw = mw
        self.prof = self.mw.pm.profile
        self.form = aqt.forms.preferences.Ui_Preferences()
        self.form.setupUi(self)
        self.form.buttonBox.button(QDialogButtonBox.Help).setAutoDefault(False)
        self.form.buttonBox.button(QDialogButtonBox.Close).setAutoDefault(False)
        self.form.buttonBox.helpRequested.connect(lambda: openHelp("profileprefs"))
        self.silentlyClose = True
        self.setupLang()
        self.setupCollection()
        self.setupNetwork()
        self.setupBackup()
        self.setupOptions()
        self.show()

    def accept(self):
        # avoid exception if main window is already closed
        if not self.mw.col:
            return
        self.updateCollection()
        self.updateNetwork()
        self.updateBackup()
        self.updateOptions()
        self.mw.pm.save()
        self.mw.reset()
        self.done(0)
        aqt.dialogs.markClosed("Preferences")

    def reject(self):
        self.accept()

    # Language
    ######################################################################

    def setupLang(self):
        self.form.lang.addItems([lang for (lang, lang_shorcut) in anki.lang.langs])
        self.form.lang.setCurrentIndex(self.langIdx())
        self.form.lang.currentIndexChanged.connect(self.onLangIdxChanged)

    def langIdx(self):
        codes = [x[1] for x in anki.lang.langs]
        try:
            return codes.index(anki.lang.getLang())
        except:
            return codes.index("en_US")

    def onLangIdxChanged(self, idx):
        code = anki.lang.langs[idx][1]
        self.mw.pm.setLang(code)
        showInfo(_("Please restart Anki to complete language change."), parent=self)

    # Collection options
    ######################################################################

    def setupCollection(self):
        from anki.consts import newCardSchedulingLabels
        qc = self.mw.col.conf
        self._setupDayCutoff()
        if isMac:
            self.form.hwAccel.setVisible(False)
        else:
            self.form.hwAccel.setChecked(self.mw.pm.glMode() != "software")
        self.form.lrnCutoff.setValue(qc['collapseTime']/60.0)
        self.form.timeLimit.setValue(qc['timeLim']/60.0)
        self.form.showEstimates.setChecked(qc['estTimes'])
        self.form.showProgress.setChecked(qc['dueCounts'])
        self.form.nightMode.setChecked(qc.get("nightMode", False))
        self.form.newSpread.addItems(list(newCardSchedulingLabels().values()))
        self.form.newSpread.setCurrentIndex(qc['newSpread'])
        self.form.useCurrent.setCurrentIndex(int(not qc.get("addToCur", True)))
        self.form.dayLearnFirst.setChecked(qc.get("dayLearnFirst", False))
        if self.mw.col.schedVer() != 2:
            self.form.dayLearnFirst.setVisible(False)
        else:
            self.form.newSched.setChecked(True)

    def updateCollection(self):

        if not isMac:
            wasAccel = self.mw.pm.glMode() != "software"
            wantAccel = self.form.hwAccel.isChecked()
            if wasAccel != wantAccel:
                if wantAccel:
                    self.mw.pm.setGlMode("auto")
                else:
                    self.mw.pm.setGlMode("software")
                showInfo(_("Changes will take effect when you restart Anki."))

        qc = self.mw.col.conf
        qc['dueCounts'] = self.form.showProgress.isChecked()
        qc['estTimes'] = self.form.showEstimates.isChecked()
        qc['newSpread'] = self.form.newSpread.currentIndex()
        qc['nightMode'] = self.form.nightMode.isChecked()
        qc['timeLim'] = self.form.timeLimit.value()*60
        qc['collapseTime'] = self.form.lrnCutoff.value()*60
        qc['addToCur'] = not self.form.useCurrent.currentIndex()
        qc['dayLearnFirst'] = self.form.dayLearnFirst.isChecked()
        self._updateDayCutoff()
        self._updateSchedVer(self.form.newSched.isChecked())
        self.mw.col.setMod()

    # Scheduler version
    ######################################################################

    def _updateSchedVer(self, wantNew):
        haveNew = self.mw.col.schedVer() == 2

        # nothing to do?
        if haveNew == wantNew:
            return

        if haveNew and not wantNew:
            if not askUser(_("This will reset any cards in learning, clear filtered decks, and change the scheduler version. Proceed?")):
                return
            self.mw.col.changeSchedulerVer(1)
            return

        if not askUser(_("The experimental scheduler could cause incorrect scheduling. Please ensure you have read the documentation first. Proceed?")):
            return

        self.mw.col.changeSchedulerVer(2)

    # Day cutoff
    ######################################################################

    def _setupDayCutoff(self):
        if self.mw.col.schedVer() == 2:
            self._setupDayCutoffV2()
        else:
            self._setupDayCutoffV1()

    def _setupDayCutoffV1(self):
        self.startDate = datetime.datetime.fromtimestamp(self.mw.col.crt)
        self.form.dayOffset.setValue(self.startDate.hour)

    def _setupDayCutoffV2(self):
        self.form.dayOffset.setValue(self.mw.col.conf.get("rollover", 4))

    def _updateDayCutoff(self):
        if self.mw.col.schedVer() == 2:
            self._updateDayCutoffV2()
        else:
            self._updateDayCutoffV1()

    def _updateDayCutoffV1(self):
        hrs = self.form.dayOffset.value()
        old = self.startDate
        date = datetime.datetime(
            old.year, old.month, old.day, hrs)
        self.mw.col.crt = int(time.mktime(date.timetuple()))

    def _updateDayCutoffV2(self):
        self.mw.col.conf['rollover'] = self.form.dayOffset.value()

    # Network
    ######################################################################

    def setupNetwork(self):
        self.form.syncOnProgramOpen.setChecked(
            self.prof['autoSync'])
        self.form.syncMedia.setChecked(
            self.prof['syncMedia'])
        if not self.prof['syncKey']:
            self._hideAuth()
        else:
            self.form.syncUser.setText(self.prof.get('syncUser', ""))
            self.form.syncDeauth.clicked.connect(self.onSyncDeauth)

    def _hideAuth(self):
        self.form.syncDeauth.setVisible(False)
        self.form.syncUser.setText("")
        self.form.syncLabel.setText(_("""\
<b>Synchronization</b><br>
Not currently enabled; click the sync button in the main window to enable."""))

    def onSyncDeauth(self):
        self.prof['syncKey'] = None
        self.mw.col.media.forceResync()
        self._hideAuth()

    def updateNetwork(self):
        self.prof['autoSync'] = self.form.syncOnProgramOpen.isChecked()
        self.prof['syncMedia'] = self.form.syncMedia.isChecked()
        if self.form.fullSync.isChecked():
            self.mw.col.modSchema(check=False)
            self.mw.col.setMod()

    # Backup
    ######################################################################

    def setupBackup(self):
        self.form.numBackups.setValue(self.prof['numBackups'])

    def updateBackup(self):
        self.prof['numBackups'] = self.form.numBackups.value()

    # Basic & Advanced Options
    ######################################################################

    def setupOptions(self):
        self.form.pastePNG.setChecked(self.prof.get("pastePNG", False))

    def updateOptions(self):
        self.prof['pastePNG'] = self.form.pastePNG.isChecked()
