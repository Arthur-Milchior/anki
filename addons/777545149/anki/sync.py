from anki.sync import *


def remove(self, graves):
    #only dif: log the reason of removal.
        # pretend to be the server so we don't set usn = -1
        self.col.server = True

        # notes first, so we don't end up with duplicate graves
        self.col._remNotes(graves['notes'],reason=f"Remove notes {graves['notes']} from grave after sync")
        # then cards
        self.col.remCards(graves['cards'], notes=False, reason=f"Remove cards {graves['cards']} from grave, after sync.")
        # and decks
        for oid in graves['decks']:
            self.col.decks.rem(oid, childrenToo=False)

        self.col.server = False
Syncer.remove = remove
