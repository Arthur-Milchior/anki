from anki.find import Finder
from anki.hooks import addHook
from aqt import mw
from aqt.qt import QAction
from aqt.utils import getText, showWarning, tooltip

from .config import getIntervalCoefficient, getIntervalForNegativeCoefficient


#From https://stackoverflow.com/questions/1265665/how-can-i-check-if-a-string-represents-an-int-without-using-try-except
def RepresentsInt(s):
    try: 
        return int(s)
    except ValueError:
        return None

def getDelay():
    return getDelayWithResponse()[0]

def getDelayWithResponse():
    (s, r) = getText("How many day to add to cards ? (negative number to substract days)")
    if r:
        return (RepresentsInt(s), r)
    return (None, r)

def getReviewCards():
    finder = Finder(mw.col)
    cids = finder.findCards("is:review")
    return cids

def addDelay(cids):
    (delay, delayResp) = getDelayWithResponse()
    if delay is None:
        if delayResp:
            showWarning("Please enter an integral number of days")
        return

    mw.checkpoint("Adding delay")
    mw.progress.start()

    ivlDelay = max(0, round(delay * (getIntervalCoefficient() if delay >0 else getIntervalForNegativeCoefficient())))
    for cid in cids:
        card = mw.col.getCard(cid)
        if card.type !=2:
            continue
        card.ivl += ivlDelay
        if card.odid: # Also update cards in filtered decks
            card.odue += delay
        else:
            card.due += delay
        card.flush()

    mw.progress.finish()
    mw.col.reset()
    mw.reset()

    tooltip(_("""Delay added."""))

def runMain():
    addDelay(getReviewCards())
    
def runBrowser(browser):
    cids=browser.selectedCards()
    addDelay(cids)

text = "Postpone cards"
def setupBrowserMenu(browser):
    a = QAction(text, browser)
    a.triggered.connect(lambda : runBrowser(browser))
    browser.form.menuEdit.addAction(a)
    
addHook("browser.setupMenus", setupBrowserMenu)
action = QAction(mw)
action.setText(text)
mw.form.menuTools.addAction(action)
action.triggered.connect(runMain)
