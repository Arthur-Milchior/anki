from aqt.sync import *
from anki.lang import _

def _checkFailed(self, event):
    #difference is that this method takes as parameter the event
        showWarning(_(f"""\
Your collection is in an inconsistent state. Please run Tools>\
Check Database, then sync again.
This is due to event {event} during sync."""))
SyncManager._checkFailed = _checkFailed

def onEvent(self, evt, *args):
    # only difference is that _checkfailed is given the name of the event
        pu = self.mw.progress.update
        if evt == "badAuth":
            tooltip(
                _("AnkiWeb ID or password was incorrect; please try again."),
                parent=self.mw)
            # blank the key so we prompt user again
            self.pm.profile['syncKey'] = None
            self.pm.save()
        elif evt == "corrupt":
            pass
        elif evt == "newKey":
            self.pm.profile['syncKey'] = args[0]
            self.pm.save()
        elif evt == "offline":
            tooltip(_("Syncing failed; internet offline."))
        elif evt == "upbad":
            self._didFullUp = False
            self._checkFailed("upbad")
        elif evt == "sync":
            m = None; t = args[0]
            if t == "login":
                m = _("Syncing...")
            elif t == "upload":
                self._didFullUp = True
                m = _("Uploading to AnkiWeb...")
            elif t == "download":
                m = _("Downloading from AnkiWeb...")
            elif t == "sanity":
                m = _("Checking...")
            elif t == "findMedia":
                m = _("Checking media...")
            elif t == "upgradeRequired":
                showText(_("""\
Please visit AnkiWeb, upgrade your deck, then try again."""))
            if m:
                self.label = m
                self._updateLabel()
        elif evt == "syncMsg":
            self.label = args[0]
            self._updateLabel()
        elif evt == "error":
            self._didError = True
            showText(_("Syncing failed:\n%s")%
                     self._rewriteError(args[0]))
        elif evt == "clockOff":
            self._clockOff()
        elif evt == "checkFailed":
            self._checkFailed("checkFailed")
        elif evt == "mediaSanity":
            showWarning(_("""\
A problem occurred while syncing media. Please use Tools>Check Media, then \
sync again to correct the issue."""))
        elif evt == "noChanges":
            pass
        elif evt == "fullSync":
            self._confirmFullSync()
        elif evt == "downloadClobber":
            showInfo(_("Your AnkiWeb collection does not contain any cards. Please sync again and choose 'Upload' instead."))
        elif evt == "send":
            # posted events not guaranteed to arrive in order
            self.sentBytes = max(self.sentBytes, int(args[0]))
            self._updateLabel()
        elif evt == "recv":
            self.recvBytes = max(self.recvBytes, int(args[0]))
            self._updateLabel()
SyncManager.onEvent = onEvent
