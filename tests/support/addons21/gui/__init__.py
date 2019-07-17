from aqt.qt import *
from aqt import mw
from anki.hooks import addHook
import time
import sys

def ensureStudy():
    mw.onStudyKey()
    mw.overview._linkHandler("study")

def doAndUndoInStudy(method, txt = ""):
    ensureStudy()
    method()
    mw.onUndo()
    time.sleep(1)
    # if txt:
    #     print(f"{txt} done")

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
    # print("after edit")

    browser = mw.onBrowse()
    addCard = mw.onAddCard()
    stats = mw.onStats()
    prefs = mw.onPrefs()
    # can't test options, because it blocks the script
    time.sleep(1)
    # debug= mw.onDebug()
    # debug.close()
    mw.close()
    # print("end")

addHook("profileLoaded", test)

from threading import Thread

def myfunc():
    time.sleep(1)
    browser.close()
    addCard.reject()
    stats.reject()
    prefs.accept()
    mw.close()
    print ("finished sleeping and closing")
