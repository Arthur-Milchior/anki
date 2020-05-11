# -*- coding: utf-8 -*-
# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

import anki.lang
import aqt
from anki.lang import _
from aqt import AnkiQt
from aqt.qt import *
from aqt.utils import TR, askUser, openHelp, showInfo, showWarning, tr


class Preferences(QDialog):
    def __init__(self, mw: AnkiQt):
        QDialog.__init__(self, mw, Qt.Window)
        self.mw = mw
        self.prof = self.mw.pm.profile
        self.form = aqt.forms.preferences.Ui_Preferences()
        self.form.setupUi(self)
        self.form.buttonBox.button(QDialogButtonBox.Help).setAutoDefault(False)
        self.form.buttonBox.button(QDialogButtonBox.Close).setAutoDefault(False)
        qconnect(self.form.buttonBox.helpRequested, lambda: openHelp("profileprefs"))
        self.silentlyClose = True
        self.prefs = self.mw.col.backend.get_preferences()
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
        qconnect(self.form.lang.currentIndexChanged, self.onLangIdxChanged)

    def langIdx(self):
        codes = [x[1] for x in anki.lang.langs]
        lang = anki.lang.currentLang
        if lang in anki.lang.compatMap:
            lang = anki.lang.compatMap[lang]
        else:
            lang = lang.replace("-", "_")
        try:
            return codes.index(lang)
        except:
            return codes.index("en_US")

    def onLangIdxChanged(self, idx):
        code = anki.lang.langs[idx][1]
        self.mw.pm.setLang(code)
        showInfo(_("Please restart Anki to complete language change."), parent=self)

    # Collection options
    ######################################################################

    def setupCollection(self):
        import anki.consts as c

        qc = self.mw.col.conf

        if isMac:
            self.form.hwAccel.setVisible(False)
        else:
            self.form.hwAccel.setChecked(self.mw.pm.glMode() != "software")

        self.form.newSpread.addItems(list(c.newCardSchedulingLabels().values()))

        self.form.useCurrent.setCurrentIndex(int(not qc.get("addToCur", True)))

        s = self.prefs
        self.form.lrnCutoff.setValue(s.learn_ahead_secs / 60.0)
        self.form.timeLimit.setValue(s.time_limit_secs / 60.0)
        self.form.showEstimates.setChecked(s.show_intervals_on_buttons)
        self.form.showProgress.setChecked(s.show_remaining_due_counts)
        self.form.newSpread.setCurrentIndex(s.new_review_mix)
        self.form.dayLearnFirst.setChecked(s.day_learn_first)
        self.form.dayOffset.setValue(s.rollover)

        if s.scheduler_version < 2:
            self.form.dayLearnFirst.setVisible(False)
            self.form.new_timezone.setVisible(False)
        else:
            self.form.newSched.setChecked(True)
            self.form.new_timezone.setChecked(s.new_timezone)

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
        qc["addToCur"] = not self.form.useCurrent.currentIndex()

        s = self.prefs
        s.show_remaining_due_counts = self.form.showProgress.isChecked()
        s.show_intervals_on_buttons = self.form.showEstimates.isChecked()
        s.new_review_mix = self.form.newSpread.currentIndex()
        s.time_limit_secs = self.form.timeLimit.value() * 60
        s.learn_ahead_secs = self.form.lrnCutoff.value() * 60
        s.day_learn_first = self.form.dayLearnFirst.isChecked()
        s.rollover = self.form.dayOffset.value()
        s.new_timezone = self.form.new_timezone.isChecked()

        # if moving this, make sure scheduler change is moved to Rust or
        # happens afterwards
        self.mw.col.backend.set_preferences(self.prefs)

        self._updateSchedVer(self.form.newSched.isChecked())
        self.mw.col.setMod()

    # Scheduler version
    ######################################################################

    def _updateSchedVer(self, wantNew):
        haveNew = self.mw.col.schedVer() == 2

        # nothing to do?
        if haveNew == wantNew:
            return

        if not askUser(
            _(
                "This will reset any cards in learning, clear filtered decks, and change the scheduler version. Proceed?"
            )
        ):
            return

        if wantNew:
            self.mw.col.changeSchedulerVer(2)
        else:
            self.mw.col.changeSchedulerVer(1)

    # Network
    ######################################################################

    def setupNetwork(self):
        self.form.media_log.setText(tr(TR.SYNC_MEDIA_LOG_BUTTON))
        qconnect(self.form.media_log.clicked, self.on_media_log)
        self.form.syncOnProgramOpen.setChecked(self.prof["autoSync"])
        self.form.syncMedia.setChecked(self.prof["syncMedia"])
        self.form.autoSyncMedia.setChecked(self.mw.pm.auto_sync_media_minutes() != 0)
        if not self.prof["syncKey"]:
            self._hideAuth()
        else:
            self.form.syncUser.setText(self.prof.get("syncUser", ""))
            qconnect(self.form.syncDeauth.clicked, self.onSyncDeauth)

    def on_media_log(self):
        self.mw.media_syncer.show_sync_log()

    def _hideAuth(self):
        self.form.syncDeauth.setVisible(False)
        self.form.syncUser.setText("")
        self.form.syncLabel.setText(
            _(
                """\
<b>Synchronization</b><br>
Not currently enabled; click the sync button in the main window to enable."""
            )
        )

    def onSyncDeauth(self) -> None:
        if self.mw.media_syncer.is_syncing():
            showWarning("Can't log out while sync in progress.")
            return
        self.prof["syncKey"] = None
        self.mw.col.media.force_resync()
        self._hideAuth()

    def updateNetwork(self):
        self.prof["autoSync"] = self.form.syncOnProgramOpen.isChecked()
        self.prof["syncMedia"] = self.form.syncMedia.isChecked()
        self.mw.pm.set_auto_sync_media_minutes(
            self.form.autoSyncMedia.isChecked() and 15 or 0
        )
        if self.form.fullSync.isChecked():
            self.mw.col.modSchema(check=False)
            self.mw.col.setMod()

    # Backup
    ######################################################################

    def setupBackup(self):
        self.form.numBackups.setValue(self.prof["numBackups"])

    def updateBackup(self):
        self.prof["numBackups"] = self.form.numBackups.value()

    # Basic & Advanced Options
    ######################################################################

    def setupOptions(self):
        self.form.pastePNG.setChecked(self.prof.get("pastePNG", False))
        self.form.uiScale.setValue(self.mw.pm.uiScale() * 100)
        self.form.pasteInvert.setChecked(self.prof.get("pasteInvert", False))
        self.form.showPlayButtons.setChecked(self.prof.get("showPlayButtons", True))
        self.form.nightMode.setChecked(self.mw.pm.night_mode())
        self.form.nightMode.setChecked(self.mw.pm.night_mode())
        self.form.interrupt_audio.setChecked(self.mw.pm.interrupt_audio())

    def updateOptions(self):
        restart_required = False

        self.prof["pastePNG"] = self.form.pastePNG.isChecked()
        self.prof["pasteInvert"] = self.form.pasteInvert.isChecked()
        newScale = self.form.uiScale.value() / 100
        if newScale != self.mw.pm.uiScale():
            self.mw.pm.setUiScale(newScale)
            restart_required = True
        self.prof["showPlayButtons"] = self.form.showPlayButtons.isChecked()

        if self.mw.pm.night_mode() != self.form.nightMode.isChecked():
            self.mw.pm.set_night_mode(not self.mw.pm.night_mode())
            restart_required = True

        self.mw.pm.set_interrupt_audio(self.form.interrupt_audio.isChecked())

        if restart_required:
            showInfo(_("Changes will take effect when you restart Anki."))
