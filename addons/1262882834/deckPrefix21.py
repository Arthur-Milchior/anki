# -*- coding: utf-8 -*-

"""Copyright: Arthur Milchior arthur@milchior.fr
License: GNU GPL, version 3 or later; http://www.gnu.org/copyleft/gpl.html
Select any number of cards in the card browser and add a prefix to
their deck name, or remove the left-most prefix

To use:

1) Open the card browser
2) Select the desired cards
3) Go to "Edit > Add prefix "/"Remove prefix" or press ctrl+alt+p/ctrl+alt+shift+p

My main goal was: exporting some cards selected in the browser. Adding
a common prefix to all of them allows to use the usual export
procedure. Once inported, I only need to remove the prefix in order
for the card to go back to their deck. It leaves an empty deck
"prefix" which can quickly and easily be removed.
"""

from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *

import anki.notes
from anki.hooks import addHook
from aqt import mw
from aqt.utils import getOnlyText, tooltip

from .config import getConfig


def addPrefix(cids):
    mw.checkpoint("Add prefix")
    mw.progress.start()

    prefix=getOnlyText(_("Prefix to add:"), default="prefix")
    # Copy notes
    for cid in cids:
        #print ("Found card: %s" % (cid))
        card = mw.col.getCard(cid)
        did = card.odid or card.did
        deckName = mw.col.decks.name(did)
        deck = mw.col.decks.get(did, default=False)
        assert deck
        newDeckName = "%s::%s"% (prefix,deckName)
        newDid = mw.col.decks.id(newDeckName,type=deck)
        card.did=newDid
        card.flush()

    # Reset collection and main window
    mw.col.decks.flush()
    mw.progress.finish()
    mw.col.reset()
    mw.reset()
    tooltip(_("""Prefix added."""))

def removePrefix(cids):
    mw.checkpoint("Remove prefix")
    mw.progress.start()

    # Copy notes
    for cid in cids:
        #print( "Found card: %s" % (cid))
        card = mw.col.getCard(cid)
        did = card.odid or card.did
        deckName = mw.col.decks.name(did)
        deck = mw.col.decks.get(did, default=False)
        assert deck
        newDeckName = '::'.join(mw.col.decks._path(deckName)[1:])
        newDid = mw.col.decks.id(newDeckName,type=deck)
        card.did=newDid
        card.flush()

    # Reset collection and main window
    mw.col.decks.flush()
    mw.col.reset()
    mw.reset()
    mw.progress.finish()
    tooltip(_("""Prefix removed."""))


def setupMenu(browser):
    a = QAction("Add prefix", browser)
    shortcut = getConfig("Shortcut: Add prefix","Ctrl+Alt+P")
    if shortcut:
        a.setShortcut(QKeySequence(shortcut))
    a.triggered.connect(lambda : onAddPrefix(browser))
    browser.form.menuEdit.addAction(a)
    shortcut = getConfig("Shortcut: Remove prefix","Ctrl+Shift+Alt+P")
    if shortcut:
        a.setShortcut(QKeySequence(shortcut))
    a = QAction("Remove prefix", browser)
    a.setShortcut(QKeySequence("Ctrl+Shift+Alt+P"))
    a.triggered.connect(lambda : onRemovePrefix(browser))
    browser.form.menuEdit.addAction(a)

def onAddPrefix(browser):
    addPrefix(browser.selectedCards())

def onRemovePrefix(browser):
    removePrefix(browser.selectedCards())

addHook("browser.setupMenus", setupMenu)
