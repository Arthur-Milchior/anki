import aqt
from anki.hooks import addHook, remHook
from aqt import mw

singleList = False
userOption = None
def getUserOption():
    global userOption
    if userOption is None:
        userOption = aqt.mw.addonManager.getConfig(__name__)
    return userOption

def update(_):
    global userOption
    userOption = None

mw.addonManager.setConfigUpdatedAction(__name__,update)
