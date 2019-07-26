from aqt import mw
userOption = None
def getUserOption(key = None, default = None):
    global userOption
    if userOption is None:
        userOption = mw.addonManager.getConfig(__name__)
    if key is not None:
        return userOption.get(key, default)
    return userOption

def update(_):
    global userOption
    userOption = None

mw.addonManager.setConfigUpdatedAction(__name__,update)
