from anki.hooks import addHook
from anki.lang import _
from aqt import mw
from aqt.addons import AddonManager
from aqt.utils import askUser, showInfo, showWarning, tooltip


def checkForUpdate():
    mgr = AddonManager(mw)
    try:
        updated = mgr.checkForUpdates()
    except Exception as e:
        showWarning(_("Addons not updated because of lack of internet.") + "\n\n" + str(e),
                    textFormat="plain")
        return
    if not updated:
        return
    names = [mgr.addonName(d) for d in updated]
    if askUser(_("Update the following add-ons?") +
                       "\n" + "\n".join(names)):
        log, errs = mgr.downloadIds(updated)
        if log:
            log_html = "<br>".join(log)
            if len(log) == 1:
                tooltip(log_html, parent=mw)
            else:
                showInfo(log_html, parent=mw, textFormat="rich")
        if errs:
            showWarning("\n\n".join(errs), parent=mw, textFormat="plain")


addHook("profileLoaded", checkForUpdate)
