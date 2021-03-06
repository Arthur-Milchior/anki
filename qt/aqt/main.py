# Copyright: Ankitects Pty Ltd and contributors
# -*- coding: utf-8 -*-
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

from __future__ import annotations

import faulthandler
import gc
import os
import re
import signal
import time
import weakref
import zipfile
from argparse import Namespace
from threading import Thread
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import anki
import aqt
import aqt.mediasrv
import aqt.mpv
import aqt.progress
import aqt.sound
import aqt.stats
import aqt.toolbar
import aqt.webview
from anki import hooks
from anki.collection import Collection
from anki.hooks import runHook
from anki.lang import _, ngettext
from anki.rsbackend import RustBackend
from anki.sound import AVTag, SoundOrVideoTag
from anki.utils import devMode, ids2str, intTime, isMac, isWin, splitFields
from aqt import gui_hooks
from aqt.addons import DownloadLogEntry, check_and_prompt_for_updates, show_log_to_user
from aqt.dbcheck import check_db
from aqt.emptycards import show_empty_cards
from aqt.legacy import install_pylib_legacy
from aqt.mediacheck import check_media_db
from aqt.mediasync import MediaSyncer
from aqt.profiles import ProfileManager as ProfileManagerType
from aqt.qt import *
from aqt.qt import sip
from aqt.sync import sync_collection, sync_login
from aqt.taskman import TaskManager
from aqt.theme import theme_manager
from aqt.utils import (
    TR,
    askUser,
    checkInvalidFilename,
    getFile,
    getOnlyText,
    openHelp,
    openLink,
    restoreGeom,
    restoreSplitter,
    restoreState,
    saveGeom,
    saveSplitter,
    showInfo,
    showWarning,
    tooltip,
    tr,
)

install_pylib_legacy()


class ResetRequired:
    def __init__(self, mw: AnkiQt):
        self.mw = mw


class AnkiQt(QMainWindow):
    """
    stateShortcuts -- the list of QShortcut elements due to the actual state of the main window (i.e. reviewer or overwiew).

    col -- The collection
    state -- It's states which kind of content main shows. Either:
      -- startup
      -- resetRequired: during review, when edit or browser is opened, the window show "waiting for editing to finish. Resume now
      -- sync
      -- overview
      -- review
      -- profileManager
      -- deckBrowser
    stateShortcuts -- shortcuts related to the kind of window currently in main.
    bottomWeb -- a ankiwebview, with the bottom of the main window. Shown unless for reset required.
    app -- an object of class AnkiApp.
    """

    col: Collection
    pm: ProfileManagerType
    web: aqt.webview.AnkiWebView
    bottomWeb: aqt.webview.AnkiWebView

    def __init__(
        self,
        app: QApplication,
        profileManager: ProfileManagerType,
        backend: RustBackend,
        opts: Namespace,
        args: List[Any],
    ) -> None:
        QMainWindow.__init__(self)
        self.backend = backend
        self.state = "startup"
        self.opts = opts
        self.col: Optional[Collection] = None
        self.taskman = TaskManager(self)
        self.media_syncer = MediaSyncer(self)
        aqt.mw = self
        self.app = app
        self.pm = profileManager
        # init rest of app
        self.safeMode = self.app.queryKeyboardModifiers() & Qt.ShiftModifier
        try:
            self.setupUI()
            self.setupAddons(args)
        except:
            showInfo(_("Error during startup:\n%s") % traceback.format_exc())
            sys.exit(1)
        # must call this after ui set up
        if self.safeMode:
            tooltip(
                _(
                    "Shift key was held down. Skipping automatic "
                    "syncing and add-on loading."
                )
            )
        # were we given a file to import?
        if args and args[0] and not self._isAddon(args[0]):
            self.onAppMsg(args[0])
        # Load profile in a timer so we can let the window finish init and not
        # close on profile load error.
        if isWin:
            fn = self.setupProfileAfterWebviewsLoaded
        else:
            fn = self.setupProfile

        def on_window_init():
            fn()
            gui_hooks.main_window_did_init()

        self.progress.timer(10, on_window_init, False, requiresCollection=False)

    def setupUI(self) -> None:
        self.col = None
        self.setupCrashLog()
        self.disableGC()
        self.setupAppMsg()
        self.setupKeys()
        self.setupThreads()
        self.setupMediaServer()
        self.setupSound()
        self.setupSpellCheck()
        self.setupStyle()
        self.setupMainWindow()
        self.setupSystemSpecific()
        self.setupMenus()
        self.setupProgress()
        self.setupErrorHandler()
        self.setupSignals()
        self.setupAutoUpdate()
        self.setupHooks()
        self.setup_timers()
        self.updateTitleBar()
        # screens
        self.setupDeckBrowser()
        self.setupOverview()
        self.setupReviewer()

    def setupProfileAfterWebviewsLoaded(self):
        for webWidget in (self.web, self.bottomWeb):
            if not webWidget._domDone:
                self.progress.timer(
                    10,
                    self.setupProfileAfterWebviewsLoaded,
                    False,
                    requiresCollection=False,
                )
                return
            else:
                webWidget.requiresCol = True

        self.setupProfile()

    def weakref(self) -> AnkiQt:
        "Shortcut to create a weak reference that doesn't break code completion."
        return weakref.proxy(self)  # type: ignore

    # Profiles
    ##########################################################################

    class ProfileManager(QMainWindow):
        onClose = pyqtSignal()
        closeFires = True

        def closeEvent(self, evt):
            if self.closeFires:
                self.onClose.emit()
            evt.accept()

        def closeWithoutQuitting(self):
            self.closeFires = False
            self.close()
            self.closeFires = True

    def setupProfile(self) -> None:
        if self.pm.meta["firstRun"]:
            # load the new deck user profile
            self.pm.load(self.pm.profiles()[0])
            self.pm.meta["firstRun"] = False
            self.pm.save()

        self.pendingImport: Optional[str] = None
        self.restoringBackup = False
        # profile not provided on command line?
        if not self.pm.name:
            # if there's a single profile, load it automatically
            profs = self.pm.profiles()
            if len(profs) == 1:
                self.pm.load(profs[0])
        if not self.pm.name:
            self.showProfileManager()
        else:
            self.loadProfile()

    def showProfileManager(self) -> None:
        self.pm.profile = None
        self.state = "profileManager"
        d = self.profileDiag = self.ProfileManager()
        self.profileForm = aqt.forms.profiles.Ui_MainWindow()
        self.profileForm.setupUi(d)
        qconnect(self.profileForm.login.clicked, self.onOpenProfile)
        qconnect(self.profileForm.profiles.itemDoubleClicked, self.onOpenProfile)
        qconnect(self.profileForm.openBackup.clicked, self.onOpenBackup)
        qconnect(self.profileForm.quit.clicked, d.close)
        qconnect(d.onClose, self.cleanupAndExit)
        qconnect(self.profileForm.add.clicked, self.onAddProfile)
        qconnect(self.profileForm.rename.clicked, self.onRenameProfile)
        qconnect(self.profileForm.delete_2.clicked, self.onRemProfile)
        qconnect(self.profileForm.profiles.currentRowChanged, self.onProfileRowChange)
        self.profileForm.statusbar.setVisible(False)
        qconnect(self.profileForm.downgrade_button.clicked, self._on_downgrade)
        # enter key opens profile
        QShortcut(QKeySequence("Return"), self.profilDiag, activated=self.onOpenProfile)  # type: ignore
        self.refreshProfilesList()
        # raise first, for osx testing
        self.profileDiag.show()
        self.profileDiag.activateWindow()
        self.profileDiag.raise_()

    def refreshProfilesList(self):
        self.profileForm.profiles.clear()
        profs = self.pm.profiles()
        self.profileForm.profiles.addItems(profs)
        try:
            idx = profs.index(self.pm.name)
        except:
            idx = 0
        self.profileForm.profiles.setCurrentRow(idx)

    def onProfileRowChange(self, profileIndex: int) -> None:
        if profileIndex < 0:
            # called on .clear()
            return
        name = self.pm.profiles()[profileIndex]
        self.pm.load(name)

    def openProfile(self):
        name = self.pm.profiles()[self.profileForm.profiles.currentRow()]
        return self.pm.load(name)

    def onOpenProfile(self) -> None:
        self.profileDiag.hide()
        # code flow is confusing here - if load fails, profile dialog
        # will be shown again
        self.loadProfile(self.profileDiag.closeWithoutQuitting)

    def profileNameOk(self, name: str) -> bool:
        return not checkInvalidFilename(name) and name != "addons21"

    def onAddProfile(self):
        name = getOnlyText(_("Name:")).strip()
        if name:
            if name in self.pm.profiles():
                return showWarning(_("Name exists."))
            if not self.profileNameOk(name):
                return
            self.pm.create(name)
            self.pm.name = name
            self.refreshProfilesList()

    def onRenameProfile(self):
        name = getOnlyText(_("New name:"), default=self.pm.name).strip()
        if not name:
            return
        if name == self.pm.name:
            return
        if name in self.pm.profiles():
            return showWarning(_("Name exists."))
        if not self.profileNameOk(name):
            return
        self.pm.rename(name)
        self.refreshProfilesList()

    def onRemProfile(self):
        profs = self.pm.profiles()
        if len(profs) < 2:
            return showWarning(_("There must be at least one profile."))
        # sure?
        if not askUser(
            _(
                """\
All cards, notes, and media for this profile will be deleted. \
Are you sure?"""
            ),
            msgfunc=QMessageBox.warning,
            defaultno=True,
        ):
            return
        self.pm.remove(self.pm.name)
        self.refreshProfilesList()

    def onOpenBackup(self):
        if not askUser(
            _(
                """\
Replace your collection with an earlier backup?"""
            ),
            msgfunc=QMessageBox.warning,
            defaultno=True,
        ):
            return

        def doOpen(path):
            self._openBackup(path)

        getFile(
            self.profileDiag,
            _("Revert to backup"),
            cb=doOpen,
            filter="*.colpkg",
            dir=self.pm.backupFolder(),
        )

    def _openBackup(self, path):
        try:
            # move the existing collection to the trash, as it may not open
            self.pm.trashCollection()
        except:
            showWarning(
                _(
                    "Unable to move existing file to trash - please try restarting your computer."
                )
            )
            return

        self.pendingImport = path
        self.restoringBackup = True

        showInfo(
            _(
                """\
Automatic syncing and backups have been disabled while restoring. To enable them again, \
close the profile or restart Anki."""
            )
        )

        self.onOpenProfile()

    def _on_downgrade(self):
        self.progress.start()
        profiles = self.pm.profiles()

        def downgrade():
            return self.pm.downgrade(profiles)

        def on_done(future):
            self.progress.finish()
            problems = future.result()
            if not problems:
                showInfo("Profiles can now be opened with an older version of Anki.")
            else:
                showWarning(
                    "The following profiles could not be downgraded: {}".format(
                        ", ".join(problems)
                    )
                )
                return
            self.profileDiag.close()

        self.taskman.run_in_background(downgrade, on_done)

    def loadProfile(self, onsuccess: Optional[Callable] = None) -> None:
        if not self.loadCollection():
            return

        self.pm.apply_profile_options()

        # show main window
        if self.pm.profile["mainWindowState"]:
            restoreGeom(self, "mainWindow")
            restoreState(self, "mainWindow")
        # titlebar
        self.setWindowTitle(self.pm.name + " - Anki")
        # show and raise window for osx
        self.show()
        self.activateWindow()
        self.raise_()

        # import pending?
        if self.pendingImport:
            if self._isAddon(self.pendingImport):
                self.installAddon(self.pendingImport)
            else:
                self.handleImport(self.pendingImport)
            self.pendingImport = None
        gui_hooks.profile_did_open()

        if onsuccess is None:
            onsuccess = lambda: None
        self.maybe_auto_sync_on_open_close(onsuccess)

    def unloadProfile(self, onsuccess: Callable) -> None:
        def callback():
            self._unloadProfile()
            onsuccess()

        gui_hooks.profile_will_close()
        self.unloadCollection(callback)

    def _unloadProfile(self) -> None:
        self.pm.profile["mainWindowGeom"] = self.saveGeometry()
        self.pm.profile["mainWindowState"] = self.saveState()
        self.pm.save()
        self.hide()

        self.restoringBackup = False

        # at this point there should be no windows left
        self._checkForUnclosedWidgets()

    def _checkForUnclosedWidgets(self) -> None:
        for topLevelWidget in self.app.topLevelWidgets():
            if topLevelWidget.isVisible():
                # windows with this property are safe to close immediately
                if getattr(topLevelWidget, "silentlyClose", None):
                    topLevelWidget.close()
                else:
                    print("Window should have been closed: {}".format(topLevelWidget))

    def unloadProfileAndExit(self) -> None:
        self.unloadProfile(self.cleanupAndExit)

    def unloadProfileAndShowProfileManager(self):
        self.unloadProfile(self.showProfileManager)

    def cleanupAndExit(self) -> None:
        self.errorHandler.unload()
        self.mediaServer.shutdown()
        self.app.exit(0)

    # Sound/video
    ##########################################################################

    def setupSound(self) -> None:
        aqt.sound.setup_audio(self.taskman, self.pm.base)

    def _add_play_buttons(self, text: str) -> str:
        "Return card text with play buttons added, or stripped."
        if self.pm.profile.get("showPlayButtons", True):
            return aqt.sound.av_refs_to_play_icons(text)
        else:
            return anki.sound.strip_av_refs(text)

    def prepare_card_text_for_display(self, text: str) -> str:
        text = self.col.media.escapeImages(text)
        text = self._add_play_buttons(text)
        return text

    # Collection load/unload
    ##########################################################################

    def loadCollection(self) -> bool:
        try:
            self._loadCollection()
        except Exception as e:
            if "FileTooNew" in str(e):
                showWarning(
                    "This profile requires a newer version of Anki to open. Did you forget to use the Downgrade button prior to switching Anki versions?"
                )
            else:
                showWarning(
                    tr(TR.ERRORS_UNABLE_OPEN_COLLECTION) + "\n" + traceback.format_exc()
                )
            # clean up open collection if possible
            try:
                self.backend.close_collection(False)
            except Exception as e:
                print("unable to close collection:", e)
            self.col = None
            # return to profile manager
            self.hide()
            self.showProfileManager()
            return False

        # make sure we don't get into an inconsistent state if an add-on
        # has broken the deck browser or the did_load hook
        try:
            self.maybeEnableUndo()
            gui_hooks.collection_did_load(self.col)
            self.moveToState("deckBrowser")
        except Exception as e:
            # dump error to stderr so it gets picked up by errors.py
            traceback.print_exc()

        return True

    def _loadCollection(self):
        cpath = self.pm.collectionPath()
        self.col = Collection(cpath, backend=self.backend, log=True)
        self.setEnabled(True)

    def reopen(self):
        self.col.reopen()

    def unloadCollection(self, onsuccess: Callable) -> None:
        def after_media_sync():
            self._unloadCollection()
            onsuccess()

        def after_sync():
            self.media_syncer.show_diag_until_finished(after_media_sync)

        def before_sync():
            self.setEnabled(False)
            self.maybe_auto_sync_on_open_close(after_sync)

        self.closeAllWindows(before_sync)

    def _unloadCollection(self) -> None:
        if not self.col:
            return
        if self.restoringBackup:
            label = _("Closing...")
        else:
            label = _("Backing Up...")
        self.progress.start(label=label)
        corrupt = False
        try:
            self.maybeOptimize()
            if not devMode:
                corrupt = self.col.db.scalar("pragma quick_check") != "ok"
        except:
            corrupt = True
        try:
            self.col.close(downgrade=False)
        except Exception as e:
            print(e)
            corrupt = True
        finally:
            self.col = None
            self.progress.finish()
        if corrupt:
            showWarning(
                _(
                    "Your collection file appears to be corrupt. \
This can happen when the file is copied or moved while Anki is open, or \
when the collection is stored on a network or cloud drive. If problems \
persist after restarting your computer, please open an automatic backup \
from the profile screen."
                )
            )
        if not corrupt and not self.restoringBackup:
            self.backup()

    # Backup and auto-optimize
    ##########################################################################

    class BackupThread(Thread):
        def __init__(self, path, data):
            Thread.__init__(self)
            self.path = path
            self.data = data
            # create the file in calling thread to ensure the same
            # file is not created twice
            with open(self.path, "wb") as file:
                pass

        def run(self):
            zip = zipfile.ZipFile(self.path, "w", zipfile.ZIP_DEFLATED)
            zip.writestr("collection.anki2", self.data)
            zip.writestr("media", "{}")
            zip.close()

    def backup(self) -> None:
        nbacks = self.pm.profile["numBackups"]
        if not nbacks or devMode:
            return
        dir = self.pm.backupFolder()
        path = self.pm.collectionPath()

        # do backup
        fname = time.strftime(
            "backup-%Y-%m-%d-%H.%M.%S.colpkg", time.localtime(time.time())
        )
        newpath = os.path.join(dir, fname)
        with open(path, "rb") as file_object:
            data = file_object.read()
        self.BackupThread(newpath, data).start()

        # find existing backups
        backups = []
        for file_name in os.listdir(dir):
            # only look for new-style format
            match = re.match(r"backup-\d{4}-\d{2}-.+.colpkg", file_name)
            if not match:
                continue
            backups.append(file_name)
        backups.sort()

        # remove old ones
        while len(backups) > nbacks:
            fname = backups.pop(0)
            path = os.path.join(dir, fname)
            os.unlink(path)
        gui_hooks.backup_did_complete()

    def maybeOptimize(self) -> None:
        # have two weeks passed?
        if (intTime() - self.pm.profile["lastOptimize"]) < 86400 * 14:
            return
        self.progress.start(label=_("Optimizing..."))
        self.col.optimize()
        self.pm.profile["lastOptimize"] = intTime()
        self.pm.save()
        self.progress.finish()

    # State machine
    ##########################################################################

    def moveToState(self, state: str, *args) -> None:
        """Call self._oldStateCleanup(state) if it exists for oldState. It seems it's the
        case only for review.
        remove shortcut related to this state
        run hooks beforeStateChange and afterStateChange. By default they are empty.
        show the bottom, unless its reset required.
        """
        # print("-> move from", self.state, "to", state)
        oldState = self.state or "dummy"
        cleanup = getattr(self, "_" + oldState + "Cleanup", None)
        if cleanup:
            # pylint: disable=not-callable
            cleanup(state)
        self.clearStateShortcuts()
        self.state = state
        gui_hooks.state_will_change(state, oldState)
        getattr(self, "_" + state + "State")(oldState, *args)
        if state != "resetRequired":
            self.bottomWeb.show()
        gui_hooks.state_did_change(state, oldState)

    def _deckBrowserState(self, oldState: str) -> None:
        self.maybe_check_for_addon_updates()
        self.deckBrowser.show()

    def _selectedDeck(self) -> Optional[Dict[str, Any]]:
        did = self.col.decks.selected()
        if not self.col.decks.nameOrNone(did):
            showInfo(_("Please select a deck."))
            return None
        return self.col.decks.get(did)

    def _overviewState(self, oldState: str) -> None:
        if not self._selectedDeck():
            return self.moveToState("deckBrowser")
        self.overview.show()

    def _reviewState(self, oldState):
        self.reviewer.show()

    def _reviewCleanup(self, newState):
        """Run hook "reviewCleanup". Unless new state is resetRequired or review."""
        if newState != "resetRequired" and newState != "review":
            self.reviewer.cleanup()

    # Resetting state
    ##########################################################################

    def reset(self, guiOnly: bool = False) -> None:
        """Called for non-trivial edits. Rebuilds queue and updates UI.

        set Edit>undo
        change state (show the bottom bar, remove shortcut from last state)
        run hooks beforeStateChange and afterStateChange. By default they are empty.
        call cleanup of last state.
        call the hook "reset". It contains at least the onReset method
        from the current window if it is browser, (and its
        changeModel), editCurrent, addCard, studyDeck,
        modelChooser. Reset reinitialize those window without closing
        them.

        unless guiOnly:
        Deal with the fact that it's potentially a new day.
        Reset number of learning, review, new cards according to current decks
        empty queues. Set haveQueues to true.
        """
        if self.col:
            if not guiOnly:
                self.col.reset()
            gui_hooks.state_did_reset()
            self.maybeEnableUndo()
            self.moveToState(self.state)

    def requireReset(self, modal=False):
        "Signal queue needs to be rebuilt when edits are finished or by user."
        self.autosave()
        self.resetModal = modal
        if self.interactiveState():
            self.moveToState("resetRequired")

    def interactiveState(self):
        "True if not in profile manager, syncing, etc."
        return self.state in ("overview", "review", "deckBrowser")

    def maybeReset(self) -> None:
        self.autosave()
        if self.state == "resetRequired":
            self.state = self.returnState
            self.reset()

    def delayedMaybeReset(self):
        # if we redraw the page in a button click event it will often crash on
        # windows
        self.progress.timer(100, self.maybeReset, False)

    def _resetRequiredState(self, oldState: str) -> None:
        if oldState != "resetRequired":
            self.returnState = oldState
        if self.resetModal:
            # we don't have to change the webview, as we have a covering window
            return
        web_context = ResetRequired(self)
        self.web.set_bridge_command(lambda url: self.delayedMaybeReset(), web_context)
        waitEditMessage = _("Waiting for editing to finish.")
        refreshButton = self.button("refresh", _("Resume Now"), id="resume")
        self.web.stdHtml(
            """
<center><div style="height: 100%%">
<div style="position:relative; vertical-align: middle;">
%s<br><br>
%s</div></div></center>
<script>$('#resume').focus()</script>
"""
            % (waitEditMessage, refreshButton),
            context=web_context,
        )
        self.bottomWeb.hide()
        self.web.setFocus()

    # HTML helpers
    ##########################################################################

    def button(
        self,
        link: str,
        name: str,
        key: Optional[str] = None,
        class_: str = "",
        id: str = "",
        extra: str = "",
    ) -> str:
        class_ = "but " + class_
        if key:
            key = _("Shortcut key: %s") % key
        else:
            key = ""
        return """
<button id="%s" class="%s" onclick="pycmd('%s');return false;"
title="%s" %s>%s</button>""" % (
            id,
            class_,
            link,
            key,
            extra,
            name,
        )

    # Main window setup
    ##########################################################################

    def setupMainWindow(self) -> None:
        # main window
        self.form = aqt.forms.main.Ui_MainWindow()
        self.form.setupUi(self)
        # toolbar
        tweb = self.toolbarWeb = aqt.webview.AnkiWebView(title="top toolbar")
        tweb.setFocusPolicy(Qt.WheelFocus)
        self.toolbar = aqt.toolbar.Toolbar(self, tweb)
        self.toolbar.draw()
        # main area
        self.web = aqt.webview.AnkiWebView(title="main webview")
        self.web.setFocusPolicy(Qt.WheelFocus)
        self.web.setMinimumWidth(400)
        # bottom area
        sweb = self.bottomWeb = aqt.webview.AnkiWebView(title="bottom toolbar")
        sweb.setFocusPolicy(Qt.WheelFocus)
        # add in a layout
        self.mainLayout = QVBoxLayout()
        self.mainLayout.setContentsMargins(0, 0, 0, 0)
        self.mainLayout.setSpacing(0)
        self.mainLayout.addWidget(tweb)
        self.mainLayout.addWidget(self.web)
        self.mainLayout.addWidget(sweb)
        self.form.centralwidget.setLayout(self.mainLayout)

        # force webengine processes to load before cwd is changed
        if isWin:
            for webWidget in self.web, self.bottomWeb:
                webWidget.requiresCol = False
                webWidget._domReady = False
                webWidget._page.setContent(bytes("", "ascii"))

    def closeAllWindows(self, onsuccess: Callable) -> None:
        aqt.dialogs.closeAll(onsuccess)

    # Components
    ##########################################################################

    def setupSignals(self) -> None:
        signal.signal(signal.SIGINT, self.onSigInt)

    def onSigInt(self, signum, frame):
        # schedule a rollback & quit
        def quit():
            self.col.db.rollback()
            self.close()

        self.progress.timer(100, quit, False)

    def setupProgress(self) -> None:
        self.progress = aqt.progress.ProgressManager(self)

    def setupErrorHandler(self) -> None:
        import aqt.errors

        self.errorHandler = aqt.errors.ErrorHandler(self)

    def setupAddons(self, args: Optional[List]) -> None:
        import aqt.addons

        self.addonManager = aqt.addons.AddonManager(self)

        if args and args[0] and self._isAddon(args[0]):
            self.installAddon(args[0], startup=True)

        if not self.safeMode:
            self.addonManager.loadAddons()
            self.maybe_check_for_addon_updates()

    def maybe_check_for_addon_updates(self):
        last_check = self.pm.last_addon_update_check()
        elap = intTime() - last_check

        if elap > 86_400:
            check_and_prompt_for_updates(
                self, self.addonManager, self.on_updates_installed
            )
            self.pm.set_last_addon_update_check(intTime())

    def on_updates_installed(self, log: List[DownloadLogEntry]) -> None:
        if log:
            show_log_to_user(self, log)

    def setupSpellCheck(self) -> None:
        os.environ["QTWEBENGINE_DICTIONARIES_PATH"] = os.path.join(
            self.pm.base, "dictionaries"
        )

    def setupThreads(self) -> None:
        self._mainThread = QThread.currentThread()

    def inMainThread(self) -> bool:
        return self._mainThread == QThread.currentThread()

    def setupDeckBrowser(self) -> None:
        from aqt.deckbrowser import DeckBrowser

        self.deckBrowser = DeckBrowser(self)

    def setupOverview(self) -> None:
        from aqt.overview import Overview

        self.overview = Overview(self)

    def setupReviewer(self) -> None:
        from aqt.reviewer import Reviewer

        self.reviewer = Reviewer(self)

    # Syncing
    ##########################################################################

    def on_sync_button_clicked(self):
        if self.media_syncer.is_syncing():
            self.media_syncer.show_sync_log()
        else:
            auth = self.pm.sync_auth()
            if not auth:
                sync_login(self, lambda: self._sync_collection_and_media(lambda: None))
            else:
                self._sync_collection_and_media(lambda: None)

    def _sync_collection_and_media(self, after_sync: Callable[[], None]):
        "Caller should ensure auth available."
        # start media sync if not already running
        if not self.media_syncer.is_syncing():
            self.media_syncer.start()

        def on_collection_sync_finished():
            self.reset()
            after_sync()

        sync_collection(self, on_done=on_collection_sync_finished)

    def maybe_auto_sync_on_open_close(self, after_sync: Callable[[], None]) -> None:
        "If disabled, after_sync() is called immediately."
        if self.can_auto_sync():
            self._sync_collection_and_media(after_sync)
        else:
            after_sync()

    def maybe_auto_sync_media(self) -> None:
        if self.can_auto_sync():
            return
        # media_syncer takes care of media syncing preference check
        self.media_syncer.start()

    def can_auto_sync(self) -> bool:
        return (
            self.pm.auto_syncing_enabled()
            and bool(self.pm.sync_auth())
            and not self.safeMode
            and not self.restoringBackup
        )

    # legacy
    def _sync(self):
        pass

    onSync = on_sync_button_clicked

    # Tools
    ##########################################################################

    def raiseMain(self):
        if not self.app.activeWindow():
            # make sure window is shown
            self.setWindowState(self.windowState() & ~Qt.WindowMinimized)
        return True

    def setupStyle(self) -> None:
        theme_manager.night_mode = self.pm.night_mode()
        theme_manager.apply_style(self.app)

    # Key handling
    ##########################################################################

    def setupKeys(self) -> None:
        globalShortcuts = [
            ("Ctrl+:", self.onDebug),
            ("d", lambda: self.moveToState("deckBrowser")),
            ("s", self.onStudyKey),
            ("a", self.onAddCard),
            ("b", self.onBrowse),
            ("t", self.onStats),
            ("y", self.on_sync_button_clicked),
        ]
        self.applyShortcuts(globalShortcuts)

        self.stateShortcuts: Sequence[Tuple[str, Callable]] = []

    def applyShortcuts(
        self, shortcuts: Sequence[Tuple[str, Callable]]
    ) -> List[QShortcut]:
        """A list of shortcuts.

        Keyword arguments:
        shortcuts -- a list of pair (shortcut key, function called by the shortcut)
        """
        qshortcuts = []
        for key, fn in shortcuts:
            scut = QShortcut(QKeySequence(key), self, activated=fn)  # type: ignore
            scut.setAutoRepeat(False)
            qshortcuts.append(scut)
        return qshortcuts

    def setStateShortcuts(self, shortcuts: List[Tuple[str, Callable]]) -> None:
        """set stateShortcuts to QShortcut from shortcuts

        run hook CURRENTSTATEStateShorcuts
        """
        gui_hooks.state_shortcuts_will_change(self.state, shortcuts)
        # legacy hook
        runHook(self.state + "StateShortcuts", shortcuts)
        self.stateShortcuts = self.applyShortcuts(shortcuts)

    def clearStateShortcuts(self) -> None:
        """Delete the shortcut of current state, empty stateShortcuts"""
        for qs in self.stateShortcuts:
            sip.delete(qs)
        self.stateShortcuts = []

    def onStudyKey(self) -> None:
        if self.state == "overview":
            self.col.startTimebox()
            self.moveToState("review")
        else:
            self.moveToState("overview")

    # App exit
    ##########################################################################

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.state == "profileManager":
            # if profile manager active, this event may fire via OS X menu bar's
            # quit option
            self.profileDiag.close()
            event.accept()
        else:
            # ignore the event for now, as we need time to clean up
            event.ignore()
            self.unloadProfileAndExit()

    # Undo & autosave
    ##########################################################################

    def onUndo(self) -> None:
        name = self.col.undoName()
        if not name:
            return
        cid = self.col.undo()
        if cid and self.state == "review":
            card = self.col.getCard(cid)
            self.col.sched.reset()
            self.reviewer.cardQueue.append(card)
            self.reviewer.nextCard()
            gui_hooks.review_did_undo(cid)
        else:
            self.reset()
            tooltip(_("Reverted to state prior to '%s'.") % name.lower())
            gui_hooks.state_did_revert(name)
        self.maybeEnableUndo()

    def maybeEnableUndo(self) -> None:
        """Enable undo in the GUI if something can be undone. Call the
        hook undoState(somethingCanBeUndone)."""
        # Whether something can be undone
        if self.col and self.col.undoName():
            self.form.actionUndo.setText(_("Undo %s") % self.col.undoName())
            self.form.actionUndo.setEnabled(True)
            gui_hooks.undo_state_did_change(True)
        else:
            self.form.actionUndo.setText(_("Undo"))
            self.form.actionUndo.setEnabled(False)
            gui_hooks.undo_state_did_change(False)

    def checkpoint(self, name):
        self.col.save(name)
        self.maybeEnableUndo()

    def autosave(self) -> None:
        saved = self.col.autosave()
        self.maybeEnableUndo()
        if saved:
            self.doGC()

    # Other menu operations
    ##########################################################################

    def onAddCard(self) -> None:
        """Open the addCards window."""
        aqt.dialogs.open("AddCards", self)

    def onBrowse(self) -> None:
        """Open the browser window."""
        aqt.dialogs.open("Browser", self)

    def onEditCurrent(self):
        """Open the editing window."""
        aqt.dialogs.open("EditCurrent", self)

    def onDeckConf(self, deck=None):
        """Open the deck editor.

        According to whether the deck is dynamic or not, open distinct window
        keyword arguments:
        deck -- The deck to edit. If not give, current Deck"""
        if not deck:
            deck = self.col.decks.current()
        if deck["dyn"]:
            import aqt.dyndeckconf

            aqt.dyndeckconf.DeckConf(self, deck=deck)
        else:
            import aqt.deckconf

            aqt.deckconf.DeckConf(self, deck)

    def onOverview(self):
        self.col.reset()
        self.moveToState("overview")

    def onStats(self):
        """Open stats for selected decks

        If there are no selected deck, don't do anything."""
        deck = self._selectedDeck()
        if not deck:
            return
        aqt.dialogs.open("DeckStats", self)

    def onPrefs(self):
        """Open preference window"""
        aqt.dialogs.open("Preferences", self)

    def onNoteTypes(self):
        import aqt.models

        aqt.models.Models(self, self, fromMain=True)

    def onAbout(self):
        """Open the about window"""
        aqt.dialogs.open("About", self)

    def onDonate(self):
        """Ask the OS to open the donate web page"""
        openLink(aqt.appDonate)

    def onDocumentation(self):
        """Ask the OS to open the documentation web page"""
        openHelp("")

    # Importing & exporting
    ##########################################################################

    def handleImport(self, path: str) -> None:
        import aqt.importing

        if not os.path.exists(path):
            showInfo(_("Please use File>Import to import this file."))
            return None

        aqt.importing.importFile(self, path)
        return None

    def onImport(self):
        import aqt.importing

        aqt.importing.onImport(self)

    def onExport(self, did=None):
        """Open exporting window, with did as in its argument."""
        import aqt.exporting

        aqt.exporting.ExportDialog(self, did=did)

    # Installing add-ons from CLI / mimetype handler
    ##########################################################################

    def installAddon(self, path: str, startup: bool = False):
        from aqt.addons import installAddonPackages

        installAddonPackages(
            self.addonManager,
            [path],
            warn=True,
            advise_restart=not startup,
            strictly_modal=startup,
            parent=None if startup else self,
        )

    # Cramming
    ##########################################################################

    def onCram(self, search=""):
        import aqt.dyndeckconf

        index = 1
        deck = self.col.decks.current()
        if not search:
            if not deck["dyn"]:
                search = 'deck:"%s" ' % deck["name"]
        while self.col.decks.id_for_name(_("Filtered Deck %d") % index):
            index += 1
        name = _("Filtered Deck %d") % index
        did = self.col.decks.newDyn(name)
        diag = aqt.dyndeckconf.DeckConf(self, first=True, search=search)
        if not diag.ok:
            # user cancelled first config
            self.col.decks.rem(did)
            self.col.decks.select(deck["id"])

    # Menu, title bar & status
    ##########################################################################

    def setupMenus(self) -> None:
        qconnect(
            self.form.actionSwitchProfile.triggered,
            self.unloadProfileAndShowProfileManager,
        )
        qconnect(self.form.actionImport.triggered, self.onImport)
        qconnect(self.form.actionExport.triggered, self.onExport)
        qconnect(self.form.actionExit.triggered, self.close)
        qconnect(self.form.actionPreferences.triggered, self.onPrefs)
        qconnect(self.form.actionAbout.triggered, self.onAbout)
        qconnect(self.form.actionUndo.triggered, self.onUndo)
        if qtminor < 11:
            self.form.actionUndo.setShortcut(QKeySequence("Ctrl+Alt+Z"))
        qconnect(self.form.actionFullDatabaseCheck.triggered, self.onCheckDB)
        qconnect(self.form.actionCheckMediaDatabase.triggered, self.on_check_media_db)
        qconnect(self.form.actionDocumentation.triggered, self.onDocumentation)
        qconnect(self.form.actionDonate.triggered, self.onDonate)
        qconnect(self.form.actionStudyDeck.triggered, self.onStudyDeck)
        qconnect(self.form.actionCreateFiltered.triggered, self.onCram)
        qconnect(self.form.actionEmptyCards.triggered, self.onEmptyCards)
        qconnect(self.form.actionNoteTypes.triggered, self.onNoteTypes)

    def updateTitleBar(self) -> None:
        self.setWindowTitle("Anki")

    # Auto update
    ##########################################################################

    def setupAutoUpdate(self) -> None:
        import aqt.update

        self.autoUpdate = aqt.update.LatestVersionFinder(self)
        qconnect(self.autoUpdate.newVerAvail, self.newVerAvail)
        qconnect(self.autoUpdate.newMsg, self.newMsg)
        qconnect(self.autoUpdate.clockIsOff, self.clockIsOff)
        self.autoUpdate.start()

    def newVerAvail(self, ver):
        if self.pm.meta.get("suppressUpdate", None) != ver:
            aqt.update.askAndUpdate(self, ver)

    def newMsg(self, data):
        aqt.update.showMessages(self, data)

    def clockIsOff(self, diff):
        diffText = ngettext("%s second", "%s seconds", diff) % diff
        warn = (
            _(
                """\
In order to ensure your collection works correctly when moved between \
devices, Anki requires your computer's internal clock to be set correctly. \
The internal clock can be wrong even if your system is showing the correct \
local time.

Please go to the time settings on your computer and check the following:

- AM/PM
- Clock drift
- Day, month and year
- Timezone
- Daylight savings

Difference to correct time: %s."""
            )
            % diffText
        )
        showWarning(warn)
        self.app.closeAllWindows()

    # Timers
    ##########################################################################

    def setup_timers(self) -> None:
        # refresh decks every 10 minutes
        self.progress.timer(10 * 60 * 1000, self.onRefreshTimer, True)
        # check media sync every 5 minutes
        self.progress.timer(5 * 60 * 1000, self.on_autosync_timer, True)

    def onRefreshTimer(self):
        if self.state == "deckBrowser":
            self.deckBrowser.refresh()
        elif self.state == "overview":
            self.overview.refresh()

    def on_autosync_timer(self):
        elap = self.media_syncer.seconds_since_last_sync()
        # autosync if 15 minutes have elapsed since last sync
        if elap > 15 * 60:
            self.maybe_auto_sync_media()

    # Permanent libanki hooks
    ##########################################################################

    def setupHooks(self) -> None:
        """Adds onSchemadMod, onRemNotes and onOdueInvalid to their hooks"""
        hooks.schema_will_change.append(self.onSchemaMod)
        hooks.notes_will_be_deleted.append(self.onRemNotes)
        hooks.card_odue_was_invalid.append(self.onOdueInvalid)

        gui_hooks.av_player_will_play.append(self.on_av_player_will_play)
        gui_hooks.av_player_did_end_playing.append(self.on_av_player_did_end_playing)

        self._activeWindowOnPlay: Optional[QWidget] = None

    def onOdueInvalid(self):
        showWarning(
            _(
                """\
Invalid property found on card. Please use Tools>Check Database, \
and if the problem comes up again, please ask on the support site."""
            )
        )

    def _isVideo(self, tag: AVTag) -> bool:
        if isinstance(tag, SoundOrVideoTag):
            head, ext = os.path.splitext(tag.filename.lower())
            return ext in (".mp4", ".mov", ".mpg", ".mpeg", ".mkv", ".avi")

        return False

    def on_av_player_will_play(self, tag: AVTag) -> None:
        "Record active window to restore after video playing."
        if not self._isVideo(tag):
            return

        self._activeWindowOnPlay = self.app.activeWindow() or self._activeWindowOnPlay

    def on_av_player_did_end_playing(self, player: Any) -> None:
        "Restore window focus after a video was played."
        if (
            not self.app.activeWindow()
            and self._activeWindowOnPlay
            and not sip.isdeleted(self._activeWindowOnPlay)
            and self._activeWindowOnPlay.isVisible()
        ):
            self._activeWindowOnPlay.activateWindow()
            self._activeWindowOnPlay.raise_()
        self._activeWindowOnPlay = None

    # Log note deletion
    ##########################################################################

    def onRemNotes(self, col: Collection, nids: Sequence[int]) -> None:
        """Append (id, model id and fields) to the end of deleted.txt

        This is done for each id of nids.
        This method is added to the hook remNotes; and executed on note deletion.
        """
        path = os.path.join(self.pm.profileFolder(), "deleted.txt")
        existed = os.path.exists(path)
        with open(path, "ab") as file_object:
            if not existed:
                file_object.write(b"nid\tmid\tfields\n")
            for id, mid, flds in col.db.execute(
                "select id, mid, flds from notes where id in %s" % ids2str(nids)
            ):
                fields = splitFields(flds)
                file_object.write(
                    ("\t".join([str(id), str(mid)] + fields)).encode("utf8")
                )
                file_object.write(b"\n")

    # Schema modifications
    ##########################################################################

    # this will gradually be phased out
    def onSchemaMod(self, arg):
        """Ask the user whether they accept to do an action which will request a full reupload of
                the db"""
        assert self.inMainThread()
        progress_shown = self.progress.busy()
        if progress_shown:
            self.progress.finish()
        ret = askUser(
            _(
                """\
The requested change will require a full upload of the database when \
you next synchronize your collection. If you have reviews or other changes \
waiting on another device that haven't been synchronized here yet, they \
will be lost. Continue?"""
            )
        )
        if progress_shown:
            self.progress.start()
        return ret

    # in favour of this
    def confirm_schema_modification(self) -> bool:
        """If schema unmodified, ask user to confirm change.
        True if confirmed or already modified."""
        if self.col.schemaChanged():
            return True
        return askUser(
            _(
                """\
The requested change will require a full upload of the database when \
you next synchronize your collection. If you have reviews or other changes \
waiting on another device that haven't been synchronized here yet, they \
will be lost. Continue?"""
            )
        )

    # Advanced features
    ##########################################################################

    def onCheckDB(self):
        check_db(self)

    def on_check_media_db(self) -> None:
        check_media_db(self)

    def onStudyDeck(self):
        from aqt.studydeck import StudyDeck

        ret = StudyDeck(self, dyn=True, current=self.col.decks.current()["name"])
        if ret.name:
            self.col.decks.select(self.col.decks.id(ret.name))
            self.moveToState("overview")

    def onEmptyCards(self) -> None:
        """Method called by Tools>Empty Cards..."""
        show_empty_cards(self)

    # Debugging
    ######################################################################

    def onDebug(self):
        frm = self.debug_diag_form = aqt.forms.debug.Ui_Dialog()

        class DebugDialog(QDialog):
            def reject(self):
                super().reject()
                saveSplitter(frm.splitter, "DebugConsoleWindow")
                saveGeom(self, "DebugConsoleWindow")

        self.debugDiag = DebugDialog()
        self.debugDiag.silentlyClose = True
        frm.setupUi(self.debugDiag)
        restoreGeom(self.debugDiag, "DebugConsoleWindow")
        restoreSplitter(frm.splitter, "DebugConsoleWindow")
        font = QFontDatabase.systemFont(QFontDatabase.FixedFont)
        font.setPointSize(frm.text.font().pointSize() + 1)
        frm.text.setFont(font)
        frm.log.setFont(font)
        self.debugDiagShort = QShortcut(QKeySequence("ctrl+return"), self.debugDiag)
        qconnect(self.debugDiagShort.activated, lambda: self.onDebugRet(frm))
        self.debugDiagShort = QShortcut(
            QKeySequence("ctrl+shift+return"), self.debugDiag
        )
        qconnect(self.debugDiagShort.activated, lambda: self.onDebugPrint(frm))
        self.debugDiagShort = QShortcut(QKeySequence("ctrl+l"), self.debugDiag)
        qconnect(self.debugDiagShort.activated, frm.log.clear)
        self.debugDiagShort = QShortcut(QKeySequence("ctrl+shift+l"), self.debugDiag)
        qconnect(self.debugDiagShort.activated, frm.text.clear)

        def addContextMenu(ev: QCloseEvent, name: str) -> None:
            ev.accept()
            menu = frm.log.createStandardContextMenu(QCursor.pos())
            menu.addSeparator()
            if name == "log":
                a = menu.addAction("Clear Log")
                a.setShortcuts(QKeySequence("ctrl+l"))
                qconnect(a.triggered, frm.log.clear)
            elif name == "text":
                a = menu.addAction("Clear Code")
                a.setShortcuts(QKeySequence("ctrl+shift+l"))
                qconnect(a.triggered, frm.text.clear)
            menu.exec(QCursor.pos())

        frm.log.contextMenuEvent = lambda ev: addContextMenu(ev, "log")
        frm.text.contextMenuEvent = lambda ev: addContextMenu(ev, "text")
        gui_hooks.debug_console_will_show(self.debugDiag)
        self.debugDiag.show()

    def _captureOutput(self, on):
        mw = self

        class Stream:
            def write(self, data):
                mw._output += data

        if on:
            self._output = ""
            self._oldStderr = sys.stderr
            self._oldStdout = sys.stdout
            stream = Stream()
            sys.stderr = stream
            sys.stdout = stream
        else:
            sys.stderr = self._oldStderr
            sys.stdout = self._oldStdout

    def _card_repr(self, card: anki.cards.Card) -> None:
        import pprint, copy

        if not card:
            print("no card")
            return

        print("Front:", card.question())
        print("\n")
        print("Back:", card.answer())

        print("\nNote:")
        note = copy.copy(card.note())
        for k, v in note.items():
            print(f"- {k}:", v)

        print("\n")
        del note.fields
        del note._fmap
        pprint.pprint(note.__dict__)

        print("\nCard:")
        c = copy.copy(card)
        c._render_output = None
        pprint.pprint(c.__dict__)

    def _debugCard(self) -> Optional[anki.cards.Card]:
        card = self.reviewer.card
        self._card_repr(card)
        return card

    def _debugBrowserCard(self) -> Optional[anki.cards.Card]:
        card = aqt.dialogs._dialogs["Browser"][1].card
        self._card_repr(card)
        return card

    def onDebugPrint(self, frm):
        cursor = frm.text.textCursor()
        position = cursor.position()
        cursor.select(QTextCursor.LineUnderCursor)
        line = cursor.selectedText()
        pfx, sfx = "pp(", ")"
        if not line.startswith(pfx):
            line = "{}{}{}".format(pfx, line, sfx)
            cursor.insertText(line)
            cursor.setPosition(position + len(pfx))
            frm.text.setTextCursor(cursor)
        self.onDebugRet(frm)

    def onDebugRet(self, frm):
        import pprint, traceback

        text = frm.text.toPlainText()
        card = self._debugCard
        bcard = self._debugBrowserCard
        mw = self
        pp = pprint.pprint
        self._captureOutput(True)
        try:
            # pylint: disable=exec-used
            exec(text)
        except:
            self._output += traceback.format_exc()
        self._captureOutput(False)
        buf = ""
        for index, line in enumerate(text.strip().split("\n")):
            if index == 0:
                buf += ">>> %s\n" % line
            else:
                buf += "... %s\n" % line
        try:
            to_append = buf + (self._output or "<no output>")
            to_append = gui_hooks.debug_console_did_evaluate_python(
                to_append, text, frm
            )
            frm.log.appendPlainText(to_append)
        except UnicodeDecodeError:
            to_append = _("<non-unicode text>")
            to_append = gui_hooks.debug_console_did_evaluate_python(
                to_append, text, frm
            )
            frm.log.appendPlainText(to_append)
        frm.log.ensureCursorVisible()

    # System specific code
    ##########################################################################

    def setupSystemSpecific(self) -> None:
        self.hideMenuAccels = False
        if isMac:
            # mac users expect a minimize option
            self.minimizeShortcut = QShortcut("Ctrl+M", self)
            qconnect(self.minimizeShortcut.activated, self.onMacMinimize)
            self.hideMenuAccels = True
            self.maybeHideAccelerators()
            self.hideStatusTips()
        elif isWin:
            # make sure ctypes is bundled
            from ctypes import windll, wintypes  # type: ignore

            _dummy1 = windll
            _dummy2 = wintypes

    def maybeHideAccelerators(self, tgt: Optional[Any] = None) -> None:
        if not self.hideMenuAccels:
            return
        tgt = tgt or self
        for action in tgt.findChildren(QAction):
            txt = str(action.text())
            match = re.match(r"^(.+)\(&.+\)(.+)?", txt)
            if match:
                action.setText(match.group(1) + (match.group(2) or ""))

    def hideStatusTips(self) -> None:
        for action in self.findChildren(QAction):
            action.setStatusTip("")

    def onMacMinimize(self):
        self.setWindowState(self.windowState() | Qt.WindowMinimized)

    # Single instance support
    ##########################################################################

    def setupAppMsg(self) -> None:
        qconnect(self.app.appMsg, self.onAppMsg)

    def onAppMsg(self, buf: str) -> Optional[QTimer]:
        is_addon = self._isAddon(buf)

        if self.state == "startup":
            # try again in a second
            return self.progress.timer(
                1000, lambda: self.onAppMsg(buf), False, requiresCollection=False
            )
        elif self.state == "profileManager":
            # can't raise window while in profile manager
            if buf == "raise":
                return None
            self.pendingImport = buf
            if is_addon:
                msg = _("Add-on will be installed when a profile is opened.")
            else:
                msg = _("Deck will be imported when a profile is opened.")
            return tooltip(msg)
        if not self.interactiveState() or self.progress.busy():
            # we can't raise the main window while in profile dialog, syncing, etc
            if buf != "raise":
                showInfo(
                    _(
                        """\
Please ensure a profile is open and Anki is not busy, then try again."""
                    ),
                    parent=None,
                )
            return None
        # raise window
        if isWin:
            # on windows we can raise the window by minimizing and restoring
            self.showMinimized()
            self.setWindowState(Qt.WindowActive)
            self.showNormal()
        else:
            # on osx we can raise the window. on unity the icon in the tray will just flash.
            self.activateWindow()
            self.raise_()
        if buf == "raise":
            return None

        # import / add-on installation
        if is_addon:
            self.installAddon(buf)
        else:
            self.handleImport(buf)

        return None

    def _isAddon(self, buf: str) -> bool:
        return buf.endswith(self.addonManager.ext)

    # GC
    ##########################################################################
    # ensure gc runs in main thread

    def setupDialogGC(self, obj: Any) -> None:
        qconnect(obj.finished, lambda: self.gcWindow(obj))

    def gcWindow(self, obj: Any) -> None:
        obj.deleteLater()
        self.progress.timer(1000, self.doGC, False, requiresCollection=False)

    def disableGC(self) -> None:
        gc.collect()
        gc.disable()

    def doGC(self) -> None:
        gc.collect()

    # Crash log
    ##########################################################################

    def setupCrashLog(self) -> None:
        crashPath = os.path.join(self.pm.base, "crash.log")
        self._crashLog = open(crashPath, "ab", 0)
        faulthandler.enable(self._crashLog)

    # Media server
    ##########################################################################

    def setupMediaServer(self) -> None:
        self.mediaServer = aqt.mediasrv.MediaServer(self)
        self.mediaServer.start()

    def baseHTML(self) -> str:
        return '<base href="%s">' % self.serverURL()

    def serverURL(self) -> str:
        return "http://127.0.0.1:%d/" % self.mediaServer.getPort()
