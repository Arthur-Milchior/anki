# -*- coding: utf-8 -*-
#Copyright: Arthur Milchior arthur@milchior.fr
#License: GNU GPL, version 3 or later; http://www.gnu.org/copyleft/gpl.html
#Feel free to contribute to this code on https://github.com/Arthur-Milchior/anki-change-note-type
#Anki add-on number: 719871418

"""
"Change card's type" does not require a new upload of the database.
The only downside being that the identifier of the note change. 
I.e. you lose the content provided by the «info» button (i.e. the list of dates at which you clicked on again, hard, good, easy).
Note however that the number of leech, the easyness, the date of next review, etc... are all preserved.

Update 2018-01-10: The creation date of note is preserved as much as possible (the date is incremented of a few miliseconds). The creation date of card is not preserved.
"""
from PyQt4.QtCore import *
from PyQt4.QtGui import *
from anki.hooks import addHook
from aqt import mw
from aqt.utils import tooltip
from anki.utils import timestampID
import anki.notes
from anki.models import ModelManager



def oldChange(self, m, nids, newModel, fmap, cmap):
        """Change the model of the nodes in nids to newModel

        currently, fmap and cmap are null only for tests.

        keyword arguments
        m -- the previous model of the notes
        nids -- a list of id of notes whose model is m
        newModel -- the model to which the cards must be converted
        fmap -- the dictionnary sending to each fields'ord of the old model a field'ord of the new model or to None. 
        cmap -- the dictionnary sending to each card type's ord of the old model a card type's ord of the new model
        """
        assert newModel['id'] == m['id'] or (fmap and cmap)
        if fmap:
            self._changeNotes(nids, newModel, fmap)
        if cmap:
            self._changeCards(nids, m, newModel, cmap)
        self.col.genCards(nids)

def newChange(self,m,nids,newModel,fmap,cmap):
        """As change. As side effect, change nids of cards. Return new nids """
        new_nids=map(copyCards,nids)
        oldChange(self,m,new_nids,newModel,fmap,cmap)
        self.col.remNotes(nids)
        self.col._remNotes(nids)
        return new_nids

ModelManager.change =newChange

###Taken from Copy.py
def timestampID(db, table, t=None):
    "Return a non-conflicting timestamp for table."
    # be careful not to create multiple objects without flushing them, or they
    # may share an ID.
    t = t or intTime(1000)
    while db.scalar("select id from %s where id = ?" % table, t):
        t += 1
    return t
def copyCards(nids):
    mw.checkpoint("Copy Notes")
    mw.progress.start()
    
    
    # Copy notes
    for nid in nids:
        print "Found note: %s" % (nid)
        note = mw.col.getNote(nid)
        model = note._model
        
        # Create new note
        note_copy = anki.notes.Note(mw.col,model=model)
        # Copy tags and fields (all model fields) from original note
        note_copy.tags = note.tags
        note_copy.fields = note.fields
        note_copy.id = timestampID(note.col.db, "notes", note.id)
        # Refresh note and add to database
        note_copy.flush()
        mw.col.addNote(note_copy)
        nid_copy = note_copy.id
        
        cards_copy= note_copy.cards()
        cards= note.cards()
        ord_to_card = {card.ord:card for card in cards}
        ord_to_card_copy = {card.ord:card for card in cards_copy}
        for card in cards:
            ord = card.ord
            card_copy = ord_to_card_copy.get(ord)
            if card_copy:
                card.id=card_copy.id
                card.nid = nid_copy
            else:
                tooltip("We copy a card which should not exists.")
                card.id=timestampID(mw.col.db,"cards")
                card.nid=nid_copy
            card.flush()

    # Reset collection and main window
    mw.col.reset()
    mw.reset()
        
    tooltip(_("""Cards copied."""))
