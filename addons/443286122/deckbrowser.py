from anki.errors import DeckRenameError
from anki.lang import _
from aqt.deckbrowser import DeckBrowser
from aqt.utils import askUser, getOnlyText, showWarning


def _rename(self, did, newName=None):
    self.mw.checkpoint(_("Rename Deck"))
    deck = self.mw.col.decks.get(did)
    oldName = deck['name']
    if newName is None:
        newName = getOnlyText(_("New deck name:"), default=oldName)
        newName = newName.replace('"', "")
    if not newName or newName == oldName:
        return
    try:
        if newName in self.mw.col.decks.allNames():
            merge = askUser(_("The deck %s already exists. Do you want to merge %s in it ?")%(newName, oldName))
            if merge:
                self.mw.col.decks.rename(deck, newName)
        else:
            self.mw.col.decks.rename(deck, newName)

    except DeckRenameError as e:
        return showWarning(e.description)
    self.show()
DeckBrowser._rename = _rename

def _dragDeckOnto(self, draggedDeckDid, ontoDeckDid):
    ontoDeckName = self.mw.col.decks.newNameForDragAndDrop(draggedDeckDid, ontoDeckDid)
    print (f"ontoDeckName is {ontoDeckDid}")
    if ontoDeckName is None:
        return
    self._rename(draggedDeckDid, newName = ontoDeckName)
    self.show()

    
DeckBrowser._dragDeckOnto = _dragDeckOnto
