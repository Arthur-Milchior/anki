import aqt
from anki.hooks import addHook, remHook
from aqt import mw

from .internal_fields import iff

singleList = False
userOption = None
def getUserOption():
    global userOption
    if userOption is None:
        userOption = aqt.mw.addonManager.getConfig(__name__)
    return userOption

def getEachFieldInSingleList():
    return getUserOption().get("Use a single list for fields", False)

def getUseInternalFields():
    return getUserOption().get("Show internal fields", False)

def update(_):
    global userOption
    userOption = None
    processInternal()


def processInternal():
    fn = addHook if getUseInternalFields() else remHook
    fn("advBrowserLoaded", iff.onAdvBrowserLoad)
    fn("advBrowserBuildContext", iff.onBuildContextMenu)
processInternal()

mw.addonManager.setConfigUpdatedAction(__name__,update)
