from anki.decks import DeckManager
from anki.errors import DeckRenameError
from anki.utils import intTime


def rename(self, g, newName):
    """Rename the deck object g to newName. Updates
    descendants. Creates parents of newName if required.

    If newName already exists, the content of g is merged in
    it. If newName is a descendant of a filtered deck, the
    operation is aborted.
    """
    oldName = g['name']
    # ensure we have parents
    newName = self._ensureParents(newName)
    # make sure we're not nesting under a filtered deck
    for p in self.parentsByName(newName):
        if p['dyn']:
            raise DeckRenameError(_("A filtered deck cannot have subdecks."))
    children = self.children(g['id']) + [g['id']]
    childrenDecks = map(self.get, children)
    for grp in childrenDecks:
        newChildName = grp['name'].replace(oldName, newChildName, 1)
        newGrp = self.byName(newChildName)
        grpId = grp["id"]
        if newGrp: #deck with same name already existed. We move cards.
            self.col.db.execute("update cards set did=?, mod=?, usn=? where did=?", newGrp["id"], intTime(), self.col.usn(), grpId)
            self.rem(grpId, childrenToo=False)
        else: #no deck with same name. Deck renamed.
            grp['name'] = newChildName
            self.save(grp)
    # ensure we have parents again, as we may have renamed parent->Descendant
    self._ensureParents(newName)
    # renaming may have altered active did order
    self.maybeAddToActive()

DeckManager.rename = rename

def renameForDragAndDrop(self, draggedDeckDid, ontoDeckDid):
    """Rename the deck whose id is draggedDeckDid as a children of
    the deck whose id is ontoDeckDid."""
    newName = self.newNameForDragAndDrop(draggedDeckDid, ontoDeckDid)
    if newName is not None:
        draggedDeck = self.get(draggedDeckDid)
        self.rename(draggedDeck, newName)
DeckManager.renameForDragAndDrop = renameForDragAndDrop

def newNameForDragAndDrop(self, draggedDeckDid, ontoDeckDid):
    """name that would result from this drag and drop. None if it's impossible"""
    draggedDeck = self.get(draggedDeckDid)
    draggedDeckName = draggedDeck['name']
    ontoDeckName = self.get(ontoDeckDid)['name']

    if ontoDeckDid is None or ontoDeckDid == '':
        #if the deck is dragged to toplevel
        if len(self._path(draggedDeckName)) > 1:
            #And is not already at top level
            return self._basename(draggedDeckName)
    elif self._canDragAndDrop(draggedDeckName, ontoDeckName):
        assert ontoDeckName.strip()
        return ontoDeckName + "::" + self._basename(draggedDeckName)
DeckManager.newNameForDragAndDrop = newNameForDragAndDrop

def cards(self, did, children=False):
    """Return the list of cards whose deck's id is did.

    If Children is set to true, returns also the list of the cards
    of the descendant."""
    return [self.col.getCard(cid) for cid in self.cids(did, children)]
DeckManager.cards = cards
