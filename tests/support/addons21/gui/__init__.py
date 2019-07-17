import time

from anki.hooks import addHook
from aqt import mw
from aqt.qt import *


def ensureStudy():
    mw.onStudyKey()
    mw.overview._linkHandler("study")

def doAndUndoInStudy(method, txt = ""):
    ensureStudy()
    method()
    mw.onUndo()
    time.sleep(1)
    if txt:
        print(f"{txt} done")

def test():
    doAndUndoInStudy(lambda: [mw.reviewer._linkHandler("ans"),  mw.reviewer._linkHandler("ease2")], "ease2")
    doAndUndoInStudy(mw.reviewer.onBuryNote, "bury note")
    doAndUndoInStudy(mw.reviewer.onBuryCard, "bury card")
    doAndUndoInStudy(mw.reviewer.onSuspend, "suspend note")
    doAndUndoInStudy(mw.reviewer.onSuspendCard, "suspend card")
    doAndUndoInStudy(mw.reviewer.onDelete, "delete")
    doAndUndoInStudy(lambda: mw.reviewer.setFlag(1), "flag1")

    ensureStudy()
    edit = mw.onEditCurrent()

    browser = mw.onBrowse()
    browser.close()
    addCard = mw.onAddCard()
    addCard.close()
    stats = mw.onStats()
    stats.close()
    debug= mw.onDebug()
    #debug.close()
    prefs = mw.onPrefs()
    # can't test options, because it blocks the script
    time.sleep(3)
    # debug= mw.onDebug()
    # debug.close()
    prefs.accept()
    mw.close()

addHook("profileLoaded", test)
