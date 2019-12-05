# -*- coding: utf-8 -*-
# Copyright: Arthur Milchior arthur@milchior.fr
# License: GNU GPL, version 3 or later; http://www.gnu.org/copyleft/gpl.html
# Select any number of cards in the card browser and create exact copies of each card in the deck
# Feel free to contribute to this code on https://github.com/Arthur-Milchior/anki-copy-note
# Anki's add-on number: 1566928056

#This add-ons is heavily based on Kealan Hobelmann's addon 396494452

"""To use:

1) Open the card browser
2) Select the desired notes (at least one card by note)
3) Go to "Edit > Copy Notes in place" or "Edit > Full note copy"

Both option consider the note you did select, and create a new note with the same content. (Fields and tags)
Both option add the card of the copied note to the deck in which the original card is (this is the main difference with addon 396494452)

"Copy notes in place" create  cards which are new. Empty card's are not copied.
"Full note copy" also copy the reviews paramater (number of reviews,  of leeches, easiness, due date...). Empty card's are copied. 

Recall that an «empty cards» is a card that should be deleted by
«check empty card».
"""

from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *

import anki.notes
from anki.hooks import addHook
from anki.utils import intTime
from aqt import mw
from aqt.utils import showWarning, tooltip

from .config import getUserOption

#import profile

def copyNotes(nids,copy_review):
    """
    
    nids -- id of notes to copy
    copy_review -- whether to copy easiness, 
    """
    mw.checkpoint("Copy Notes")
    mw.progress.start()
    for nid in nids:
        copyNote(nid, copy_review)
    # Reset collection and main window
    mw.progress.finish()
    mw.col.reset()
    mw.reset()
        
    tooltip(_("""Cards copied."""))

def copyNote(nid, copy_review):
    note = mw.col.getNote(nid)
    cards= note.cards()
    note.id = timestampID(note.col.db, "notes", note.id if getUserOption().get("Preserve creation time", True) else None)
    for card in cards:
        card.id = timestampID(note.col.db, "cards", card.id if getUserOption().get("Preserve creation time", True) else None)
        if not copy_review:
            card.type = 0
            card.ivl = 0
            card.factor = 0
            card.reps = 0
            card.lapses = 0
            card.left = 0
            card.odue = 0
        card.nid = note.id
        card.flush()
    note.flush()
    
def setupMenu(browser):
    a = QAction("Note Copy", browser)
    a.setShortcut(QKeySequence("Ctrl+C")) # Shortcut for convenience. Added by Didi
    a.triggered.connect(lambda : copyNotes(browser.selectedNotes(), copy_review = False))
    browser.form.menuEdit.addSeparator()
    browser.form.menuEdit.addAction(a)
    a = QAction("Full Notes Copy", browser)
    a.setShortcut(QKeySequence("Ctrl+Alt+C")) # Shortcut for convenience. Added by Didi
    a.triggered.connect(lambda : copyNotes(browser.selectedNotes(), copy_review = True))
    browser.form.menuEdit.addAction(a)

addHook("browser.setupMenus", setupMenu)

def timestampID(db, table, t=None):
    "Return a non-conflicting timestamp for table."
    # be careful not to create multiple objects without flushing them, or they
    # may share an ID.
    t = t or intTime(1000)
    while db.scalar("select id from %s where id = ?" % table, t):
        t += 1
    return t
