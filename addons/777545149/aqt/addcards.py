from aqt.addcards import *

def removeTempNote(self, note):
    #Only difference: adding a reason for deletion (normally it should not be logged anyway)
    if not note or not note.id:
        return
    # we don't have to worry about cards; just the note
    self.mw.col._remNotes([note.id],reason="Temporary note")
AddCards.removeTempNote=removeTempNote
