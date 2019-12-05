from aqt import mw

userOption = None
def getUserOption():
    global userOption
    if userOption is None:
        userOption = mw.addonManager.getConfig(__name__)
    return userOption

def update(_):
    global userOption
    userOption = None

mw.addonManager.setConfigUpdatedAction(__name__,update)

def getIntervalCoefficient():
    return getUserOption().get("interval coefficient", 0.33)

def getIntervalForNegativeCoefficient():
    neg =  getUserOption().get("coefficient for negative",False)
    if neg is True:
        return getIntervalCoefficient()
    if neg is False:
        return 0
    if isinstance(neg,(int,float)):
        return neg
    assert False
