import random

from anki.sched import Scheduler
from anki.schedv2 import Scheduler as SchedV2
from anki.utils import ids2str, intTime

CARD_NEW = 0

def randomizeCards(self, did):
    # Difference: return only cids of new cards
    """Change the due value of new cards of deck `did`. The new due value
        is the same for every card of a note (as long as they are in the same
        deck.) This number is random."""
    cids = self.col.db.list(f"select id from cards where did = ? and type = {CARD_NEW}", did)#Restrict to type= card new
    self.sortCards(cids, shuffle=True)

def orderCards(self, did):
    # Difference: return only cids of new card
    """Change the due value of new cards of deck `did`. The new due value
        is the same for every card of a note (as long as they are in
        the same deck.)

    The note are now ordered according to the smallest id of their
    cards. It generally means they are ordered according to date
    creation.

    """
    cids = self.col.db.list(f"select id from cards where did = ? and type = {CARD_NEW} order by id", did) # difference: type = {CARD_NEW}
    self.sortCards(cids)

def sortCards(self, cids, start=1, step=1, shuffle=False, shift=False):
    # Only difference: if not shuffle, then sort by note creation order first. (And thus save nid as int and not string)
        """Change the due of new cards in `cids`.

        Each card of the same note have the same due. The order of the
        due is random if shuffle. Otherwise the order of the note `n` is
        similar to the order of the first occurrence of a card of `n` in cids.

        Keyword arguments:
        cids -- list of card ids to reorder (i.e. change due). Not new cards are ignored
        start -- the first due to use
        step -- the difference between to successive due of notes
        shuffle -- whether to shuffle the note. By default, the order is similar to the created order
        shift -- whether to change the due of all new cards whose due is greater than start (to ensure that the new due of cards in cids is not already used)

        """
        scids = ids2str(cids)
        now = intTime()
        nids = []
        nidsSet = set()
        for id in cids:
            nid = int(self.col.db.scalar("select nid from cards where id = ?", id))#Adding int, so that sorting can be done in numerical and not alphabetical order
            if nid not in nidsSet:
                nids.append(nid)
                nidsSet.add(nid)
        if not nids:
            # no new cards
            return
        # determine nid ordering
        due = {}
        if shuffle:
            random.shuffle(nids)
        else:#This is new. It ensures that due is sorted according to
             #note creation and not card creation.
            nids.sort()
        for c, nid in enumerate(nids):
            due[nid] = start+c*step
        # pylint: disable=undefined-loop-variable
        high = start+c*step #Highest due which will be used
        # shift?
        if shift:
            low = self.col.db.scalar(
                f"select min(due) from cards where due >= ? and type = {CARD_NEW} "
                "and id not in %s" % (scids),
                start)
            if low is not None:
                shiftby = high - low + 1
                self.col.db.execute(f"""
update cards set mod=?, usn=?, due=due+? where id not in %s
and due >= ? and queue = {QUEUE_NEW_CRAM}""" % (scids), now, self.col.usn(), shiftby, low)
        # reorder cards
        d = []
        for id, nid in self.col.db.execute(
            (f"select id, nid from cards where type = {CARD_NEW} and id in ")+scids):
            d.append(dict(now=now, due=due[nid], usn=self.col.usn(), cid=id))
        self.col.db.executemany(
            "update cards set due=:due,mod=:now,usn=:usn where id = :cid", d)


Scheduler.randomizeCards = randomizeCards
Scheduler.orderCards = orderCards
Scheduler.sortCards = sortCards
SchedV2.randomizeCards = randomizeCards
SchedV2.orderCards = orderCards
SchedV2.sortCards = sortCards
