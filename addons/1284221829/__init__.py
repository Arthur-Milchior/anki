from anki.langs import _
from aqt.addcards import AddCards
from aqt.editor import Editor
from aqt.utils import askUser

old_init = AddCards.__init__
def __init__(self, *args, **kwargs):
    self.previousNote = None
    old_init(self, *args, **kwargs)

AddCards.__init__ = __init__

oldAddNote = AddCards.addNote
def addNote(self, *args, **kwargs):
    note = oldAddNote(self, *args, **kwargs)
    if note:
        self.previousNote = note
    return note
AddCards.addNote = addNote

def ifCanClose(self, onOk):
        def afterSave():
            ok = (self.editor.fieldsAreBlank(self.previousNote) or
                    askUser(_("Close and lose current input?"), defaultno=True))
            if ok:
                onOk()

        self.editor.saveNow(afterSave)
    
AddCards.ifCanClose = ifCanClose

def fieldsAreBlank(self, previousNote=None):
        if not self.note:
            return True
        for c, f in enumerate(self.note.fields):
            notChangedvalues = {"", "<br>"}
            if previousNote and self.model['flds'][c]['sticky']:
                notChangedvalues.add(previousNote.fields[c])
            if f not in notChangedvalues:
                return False
        return True
Editor.fieldsAreBlank = fieldsAreBlank
