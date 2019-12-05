# -*- coding: utf-8 -*-
# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

import datetime
import time

import anki.lang
import aqt
from anki.consts import *
from anki.lang import _
from anki.utils import identity, negation
from aqt.qt import *
from aqt.utils import askUser, openHelp, showInfo


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
        self.setupBackup()
        self.setupCollection()
        self.setupNetwork()
        self.dealWithSettings(self.setupOneSetting)
        self.setupColor()
        self.show()

    def accept(self):
        # avoid exception if main window is already closed
        if not self.mw.col:
            return
        self.updateCollection()
        self.updateNetwork()
        self.dealWithSettings(self.updateOneSetting)
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
        f = self.form
        qc = self.mw.col.conf
        self._setupDayCutoff()
        if isMac:
            f.hwAccel.setVisible(False)
        else:
            f.hwAccel.setChecked(self.mw.pm.glMode() != "software")
        f.newSpread.addItems(list(newCardSchedulingLabels().values()))
        if self.mw.col.schedVer() != 2:
            f.dayLearnFirst.setVisible(False)
        else:
            f.newSched.setChecked(True)
    def setupCollection(self):
        from anki.consts import newCardSchedulingLabels
        qc = self.mw.col.conf
        self._setupDayCutoff()
        if isMac:
            self.form.hwAccel.setVisible(False)
        else:
            self.form.hwAccel.setChecked(self.mw.pm.glMode() != "software")
        self.form.newSpread.addItems(list(newCardSchedulingLabels().values()))
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
        self.form.rollover.setValue(self.startDate.hour)

    def _setupDayCutoffV2(self):
        self.setupOneSetting("rollover", 4, "numeric")

    def _updateDayCutoff(self):
        if self.mw.col.schedVer() == 2:
            self._updateDayCutoffV2()
        else:
            self._updateDayCutoffV1()

    def _updateDayCutoffV1(self):
        hrs = self.form.rollover.value()
        old = self.startDate
        date = datetime.datetime(
            old.year, old.month, old.day, hrs)
        self.mw.col.crt = int(time.mktime(date.timetuple()))

    def _updateDayCutoffV2(self):
        self.updateOneSetting("rollover", 4, "numeric")


    # Network
    ######################################################################

    def setupNetwork(self):
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
        if self.form.fullSync.isChecked():
            self.mw.col.modSchema(check=False)
            self.mw.col.setMod()
    # Color
    ########################
    def setupColor(self):
        if "colors" not in self.mw.col.conf:
            self.mw.col.conf["colors"] = defaultColors
        for colorName in defaultColors:
            defaultColor = defaultColors.get(colorName, "black")
            colors = self.mw.col.conf["colors"]
            color = colors.get(colorName, defaultColor) # useful if another color is added by an add-on.
            button = getattr(self.form, f"{colorName}Button")
            button.clicked.connect(lambda: self.onColor(colorName))
            button.setStyleSheet(f"background-color: {color}")


    def onColor(self, name):
        print(f"on color {name}")
        new = QColorDialog.getColor(QColor(self.mw.col.conf["colors"][name]), self, f"Choose the color for {name}")
        if new.isValid():
            colors = self.mw.col.conf["colors"]
            newColor = new.name()
            colors[name] = newColor

    # Basic & Advanced Options
    ######################################################################

    def setupBackup(self):
        self.form.openBackupFolder.linkActivated.connect(self.onOpenBackup)

    def onOpenBackup(self):
        openFolder(self.mw.pm.backupFolder())

    # General settings
    ########################

    allSettings = [
        # Collection
        {"name":"collapseTime", "fromCol": lambda x:x/60.0, "toCol": lambda x: x*60.0, "kind":"numeric"},
        {"name":"timeLim", "fromCol": lambda x:x/60.0, "toCol": lambda x: x*60.0, "kind":"numeric"},
        "estTimes",
        "dueCounts",
        "nightMode",
        {"name": "newSpread", "kind":"combo"},
        {"name": "addToCur", "kind":"combo", "fromCol": lambda x: int (not x), "toCol": negation},
        "dayLearnFirst",
        #{"name":"rollover", "default": "4"} Different between v1 and v2 , so can't use easily
        # Network
        {"name":"autoSync", "sync":False},
        {"name":"syncMedia", "sync":False},
        # Backup
        {"name":"numBackups", "kind":"numeric", "sync":False},
        # advanced option
        "exportSiblings",
        {"name":"pastePNG", "sync":False},
        "allowDuplicateFirstField",
        "allowEmptyFirstField",
        "compileLaTeX",
        "deckOverview",
        "minutesInBrowser",
        "newLineInBatchEdit",
        ("browserOnMissingMedia", True),
        ("copyLog", True),
        ("keepEmptyNote", True),
        ("keepSeenCard", True),
        ("preserveCreation", True),
        ("preserveReviewInfo", True),
        *[(f"{window}MultipleTime", True) for window in ["AddCards", "EditCurrent", "Browser", "OtherWindows"]],#those are the windows name, thus with caps
        {"name": "factorAddDay", "kind":"numeric"},
        {"name": "factorRemoveDay", "kind": "numeric"},
        {"name":"browserFromReviewer", "default":"note", "fromCol": (lambda x: {"cid":0,"nid":1,"did":2}.get(x, 1)), "toCol": (lambda x: {0:"cid",1:"nid",2:"did"}[x]), "kind": "combo"},
        {"name":"filesToKeep", "kind":"text", "default":"user_files .git .gitignore .svn .github"},
        {"name":"longTermBackUp", "default":True, "sync":False},
        {"name":"syncAddons", "sync":False},
    ]

    def setupOneSetting(self, name, default=False, kind="check", sync=True, fromCol=identity, toCol=identity):
        """Ensure that the preference manager default values for widget
        `name` is set correctly.

        name -- name of the widget; it's also the name used in the configuration
        default -- The value to take if the value is not in the profile/configuration
        kind -- either check, numberic or combo. Their default value are the falsy ones.
        sync -- whether the value should be synchronized. In this case
        it is in configuration of collection. Otherwise it is in
        profile's preference.
        fromCol -- function to apply to elements taken in the collection before sending them to the interface
        toCol -- function to apply to values from interface before saving them in collection
        """
        storeValue = self.mw.col.conf if sync else self.prof
        widget = getattr(self.form, name)
        if kind == "numeric" and default is False:
            default = 0
        value = storeValue.get(name, default)
        function = {
            "check": "setChecked",
            "numeric": "setValue",
            "combo": "setCurrentIndex",
            "text": "setText"
        }.get(kind)
        getattr(widget, function)(fromCol(value))
            

    def updateOneSetting(self, name, default=False, kind="check", sync=True, fromCol=identity, toCol=identity):
        """Save the value from the preference manager' widget
        `name`.

        Same argument as in setupOneSetting"""
        storeValue = self.mw.col.conf if sync else self.prof
        widget = getattr(self.form, name)
        function = {
            "check": "isChecked",
            "numeric": "value",
            "combo": "currentIndex",
            "text": "text",
        }.get(kind)
        value = getattr(widget, function)()
        storeValue[name] = toCol(value)

    def dealWithSettings(self, method):
        """Apply method methods with argumets from extraOptions, depending on
        the type of argument."""
        try:
            for args in self.allSettings:
                if isinstance(args, tuple):
                    method(*args)
                elif isinstance(args, dict):
                    method(**args)
                elif isinstance(args, str):
                    method(args)
        except:
            print(f"problem with {args}")
            raise

    # Basic & Advanced Options
    ######################################################################

    def setupColor(self):
        if "colors" not in self.mw.col.conf:
            self.mw.col.conf["colors"] = defaultColors
        for colorName in defaultColors:
            defaultColor = defaultColors.get(colorName, "black")
            colors = self.mw.col.conf["colors"]
            color = colors.get(colorName, defaultColor) # useful if another color is added by an add-on.
            button = getattr(self.form, f"{colorName}Button")
            button.clicked.connect(lambda: self.onColor(colorName))
            button.setStyleSheet(f"background-color: {color}")


    def onColor(self, name):
        print(f"on color {name}")
        new = QColorDialog.getColor(QColor(self.mw.col.conf["colors"][name]), self, f"Choose the color for {name}")
        if new.isValid():
            colors = self.mw.col.conf["colors"]
            newColor = new.name()
            colors[name] = newColor
            button.setStyleSheet(f"background-color: {newColor}")
