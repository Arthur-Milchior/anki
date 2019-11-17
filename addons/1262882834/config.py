from aqt import mw

configs = None
def readIfRequired():
    global configs
    if configs is None:
        configs = mw.addonManager.getConfig(__name__) or dict()

def newConf(config):
    global configs
    configs = None

def getConfig(s = None, default = None):
    """Get the dictionnary of configs. If a name is given, return the
    object with this name if it exists.

    reads if required."""

    readIfRequired()
    if s is None:
        return configs
    else:
        return configs.get(s, default)

mw.addonManager.setConfigUpdatedAction(__name__,newConf)
