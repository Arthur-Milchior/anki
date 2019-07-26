from ..debug import debug
from anki.consts import *
from anki.decks import *

def rem(self, did, cardsToo=False, childrenToo=True):
        #difference:simplifying a little bit the code
        # adding a reason to remCards
        """Remove the deck whose id is did.

        Does not delete the default deck, but rename it.

        Log the removal, even if the deck does not exists, assuming it
        is not default.

        Keyword arguments:
        cardsToo -- if set to true, delete its card.
        ChildrenToo -- if set to false,
        """
        deck = self.get(did, default = False)#new
        dname = deck.get('name')# new
        if str(did) == '1':
            # we won't allow the default deck to be deleted, but if it's a
            # child of an existing deck then it needs to be renamed
            if '::' in dname:#changed: used dname instead of deck['name']
                base = dname.split("::")[-1]#changed: used dname instead of deck['name']
                suffix = ""
                while True:
                    # find an unused name
                    name = base + suffix
                    if not self.byName(name):
                        deck['name'] = name
                        self.save(deck)
                        break
                    suffix += "1"
            return
        # log the removal regardless of whether we have the deck or not
        self.col._logRem([did], REM_DECK)
        # do nothing else if doesn't exist
        if deck is None:# simplifying the condition since deck was already found
            return
        if deck['dyn']:
            # deleting a cramming deck returns cards to their previous deck
            # rather than deleting the cards
            self.col.sched.emptyDyn(did)
            if childrenToo:
                for name, id in self.children(did):
                    self.rem(id, cardsToo)
        else:
            # delete children first
            if childrenToo:
                # we don't want to delete children when syncing
                for name, id in self.children(did):
                    self.rem(id, cardsToo)
            # delete cards too?
            if cardsToo:
                # don't use cids(), as we want cards in cram decks too
                cids = self.col.db.list(
                    "select id from cards where did=? or odid=?", did, did)
                self.col.remCards(cids,reason=f"The last card of this note was in deck {did}:{dname}, which got deleted.") # adding reason
        # delete the deck and add a grave (it seems no grave is added)
        del self.decks[str(did)]
        # ensure we have an active deck.
        if did in self.active():
            self.select(int(list(self.decks.keys())[0]))
        self.save()
DeckManager.rem=rem
