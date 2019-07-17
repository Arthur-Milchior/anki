# -*- coding: utf-8 -*-
# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

import datetime, time
from aqt.qt import *
import anki.lang
from aqt.utils import openFolder, openHelp, showInfo, askUser
import aqt
from anki.lang import _

class Preferences(QDialog):

    """
    startdate -- datetime where collection was created. Only in schedV1
    """

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
        self.setupExtra()
        self.show()

    def accept(self):
        # avoid exception if main window is already closed
        if not self.mw.col:
            return
        self.updateCollection()
        self.updateNetwork()
        self.updateBackup()
        self.updateOptions()
        self.updateExtra()
        self.mw.pm.save()
        self.mw.reset()
        self.done(0)
        aqt.dialogs.markClosed("Preferences")

    def reject(self):
        self.accept()

    # Language
    ######################################################################

    def setupLang(self):
        f = self.form
        f.lang.addItems([x[0] for x in anki.lang.langs])
        f.lang.setCurrentIndex(self.langIdx())
        f.lang.currentIndexChanged.connect(self.onLangIdxChanged)

    def langIdx(self):
        codes = [x[1] for x in anki.lang.langs]
        try:
            return codes.index(anki.lang.getLang())
        except:
            return codes.index("en")

    def onLangIdxChanged(self, idx):
        code = anki.lang.langs[idx][1]
        self.mw.pm.setLang(code)
        showInfo(_("Please restart Anki to complete language change."), parent=self)

    # Collection options
    ######################################################################

    def setupCollection(self):
        import anki.consts as c
        f = self.form
        qc = self.mw.col.conf
        self._setupDayCutoff()
        if isMac:
            f.hwAccel.setVisible(False)
        else:
            f.hwAccel.setChecked(self.mw.pm.glMode() != "software")
        f.lrnCutoff.setValue(qc['collapseTime']/60.0)
        f.timeLimit.setValue(qc['timeLim']/60.0)
        f.showEstimates.setChecked(qc['estTimes'])
        f.showProgress.setChecked(qc['dueCounts'])
        f.nightMode.setChecked(qc.get("nightMode", False))
        f.newSpread.addItems(list(c.newCardSchedulingLabels().values()))
        f.newSpread.setCurrentIndex(qc['newSpread'])
        f.useCurrent.setCurrentIndex(int(not qc.get("addToCur", True)))
        f.dayLearnFirst.setChecked(qc.get("dayLearnFirst", False))
        if self.mw.col.schedVer() != 2:
            f.dayLearnFirst.setVisible(False)
        else:
            f.newSched.setChecked(True)

    def updateCollection(self):
        f = self.form
        d = self.mw.col

        if not isMac:
            wasAccel = self.mw.pm.glMode() != "software"
            wantAccel = f.hwAccel.isChecked()
            if wasAccel != wantAccel:
                if wantAccel:
                    self.mw.pm.setGlMode("auto")
                else:
                    self.mw.pm.setGlMode("software")
                showInfo(_("Changes will take effect when you restart Anki."))

        qc = d.conf
        qc['dueCounts'] = f.showProgress.isChecked()
        qc['estTimes'] = f.showEstimates.isChecked()
        qc['newSpread'] = f.newSpread.currentIndex()
        qc['nightMode'] = f.nightMode.isChecked()
        qc['timeLim'] = f.timeLimit.value()*60
        qc['collapseTime'] = f.lrnCutoff.value()*60
        qc['addToCur'] = not f.useCurrent.currentIndex()
        qc['dayLearnFirst'] = f.dayLearnFirst.isChecked()
        self._updateDayCutoff()
        self._updateSchedVer(f.newSched.isChecked())
        d.setMod()

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
        self.setupOneOption('syncMedia')
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
        self.updateOneOption('syncMedia')
        if self.form.fullSync.isChecked():
            self.mw.col.modSchema(check=False)
            self.mw.col.setMod()

    # Backup
    ######################################################################

    def setupBackup(self):
        self.setupOneOption("numBackups", 50, False)
        self.form.openBackupFolder.linkActivated.connect(self.onOpenBackup)

    def onOpenBackup(self):
        openFolder(self.mw.pm.backupFolder())

    def updateBackup(self):
        self.updateOneOption("numBackups", 50, False)

    # Basic & Advanced Options
    ######################################################################

    def setupOptions(self):
        self.setupOneOption("pastePNG")

    def updateOptions(self):
        self.updateOneOption("pastePNG")

    def setupOneOption(self, name, default=False, check=True, sync=True):
        """Ensure that the preference manager default values for widget
        `name` is set correctly.

        name -- name of the widget; it's also the name used in the configuration
        default -- The value to take if the value is not in the profile/configuration
        check -- whether it's a checkbox (otherwise, default value is 0)
        sync -- whether the value should be synchronized. In this case
        it is in configuration of collection. Otherwise it is in
        profile's preference.

        """
        storeValue = self.mw.col.conf if sync else self.prof
        widget = getattr(self.form, name)
        if not check and default is False:
            default = 0
        value = storeValue.get(name, default)
        function = "setChecked" if check else "setValue"
        getattr(widget, function)(value)

    def updateOneOption(self, name, default=False, check=True, sync=True):
        """Save the value from the preference manager' widget
        `name`.

        name -- name of the widget; it's also the name used in the
        configuration
        default -- not used here, only for having same parameters as setupOneOption
        default -- The value to take if the value is not in the profile/configuration
        check -- whether it's a checkbox (otherwise, default value is 0)
        sync -- whether the value should be synchronized. In this case
        it is in configuration of collection. Otherwise it is in
        profile's preference.

        """
        storeValue = self.mw.col.conf if sync else self.prof
        widget = getattr(self.form, name)
        function = "isChecked" if check else "value"
        value = getattr(widget, function)()
        storeValue[name] = value

    extraOptions = [
        ("noteWithoutCard", True),
    ]

    def setupExtra(self):
        """Set in the GUI the preferences related to add-ons
        forked."""
        for args in self.extraOptions:
            self.setupOneOption(*args)

    def updateExtra(self):
        """Check the preferences related to add-ons forked."""
        for args in self.extraOptions:
            self.updateOneOption(*args)
