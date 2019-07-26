from anki.collection import  *
from anki.collection import  _Collection
from anki.utils import ids2str, maxID, intTime
from ..debug import debugFun
import os
from .fixIntegrity import fixIntegrity
import stat
from anki.consts import *
from ..consts import *
from anki.lang import _
from aqt import mw
@debugFun
def genCards(self, nids, changedOrNewReq = None):
    #new parameter: changedOrNewReq
    # The only differences are:
    # changedOrNewReq is passed to models.availOrds
    # if changedOrNewReq is not None, then only cards in positions belonging to changedOrNewReq may be returned
    """Ids of cards needed to be removed.
     Generate missing cards of a note with id in nids and with ord in changedOrNewReq.
    """
    # build map of (nid,ord) so we don't create dupes
    snids = ids2str(nids)
    have = {}#Associated to each nid a dictionnary from card's order to card id.
    dids = {}#Associate to each nid the only deck id containing its cards. Or None if there are multiple decks
    dues = {}#Associate to each nid the due value of the last card seen.
    for id, nid, ord, did, due, odue, odid in self.db.execute(
        "select id, nid, ord, did, due, odue, odid from cards where nid in "+snids):
        # existing cards
        if nid not in have:
            have[nid] = {}
        have[nid][ord] = id
        # if in a filtered deck, add new cards to original deck
        if odid != 0:
            did = odid
        # and their dids
        if nid in dids:
            if dids[nid] and dids[nid] != did:
                # cards are in two or more different decks; revert to
                # model default
                dids[nid] = None
        else:
            # first card or multiple cards in same deck
            dids[nid] = did
        # save due
        if odid != 0:
            due = odue
        if nid not in dues:
            dues[nid] = due
    # build cards for each note
    data = []#Tuples for cards to create. Each tuple is newCid, nid, did, ord, now, usn, due
    ts = maxID(self.db)
    now = intTime()
    rem = []#cards to remove
    usn = self.usn()
    for nid, mid, flds in self.db.execute(
        "select id, mid, flds from notes where id in "+snids):
        model = self.models.get(mid)
        avail = self.models.availOrds(model, flds, changedOrNewReq)# modified: adding last parameter.
        did = dids.get(nid) or model['did']
        due = dues.get(nid)
        # add any missing cards
        for t in self._tmplsFromOrds(model, avail):
            doHave = nid in have and t['ord'] in have[nid]
            if not doHave:
                # check deck is not a cram deck
                did = t['did'] or did
                if self.decks.isDyn(did):
                    did = 1
                # if the deck doesn't exist, use default instead
                did = self.decks.get(did)['id']
                # use sibling due# if there is one, else use a new id
                if due is None:
                    due = self.nextID("pos")
                data.append((ts, nid, did, t['ord'],
                             now, usn, due))
                ts += 1
        # note any cards that need removing
        if nid in have:
            for ord, id in list(have[nid].items()):
                if ((changedOrNewReq is None or ord in changedOrNewReq) and #Adding this line to the condition
                    ord not in avail):
                    rem.append(id)
    # bulk update
    self.db.executemany("""
insert into cards values (?,?,?,?,?,?,0,0,?,0,0,0,0,0,0,0,0,"")""",
                        data)
    return rem

_Collection.genCards = genCards


_Collection.fixIntegrity = fixIntegrity

def remCards(self, ids, notes=True, reason=None):
        """Bulk delete cards by ID.

        keyword arguments:
        notes -- whether note without cards should be deleted."""
        #only difference: argument ```reason```. It is given to _remNotes to be logged. If not given when the function is called, a generic reason is given.
        if not ids:
            return
        sids = ids2str(ids)
        nids = self.db.list("select nid from cards where id in "+sids)
        # remove cards
        self._logRem(ids, REM_CARD)
        self.db.execute("delete from cards where id in "+sids)
        # then notes
        if not notes:
            return
        nids = self.db.list("""
select id from notes where id in %s and id not in (select nid from cards)""" %
                     ids2str(nids))
        self._remNotes(nids, reason or f"No cards remained for this note.")# only difference
_Collection.remCards=remCards

def _remNotes(self, ids, reason=""):
    """Bulk delete notes by ID. Don't call this directly.

    keyword arguments:
    self -- collection"""
    #only difference: adding a reason for deletion, calling onRemNotes
    if not ids:
        return
    strids = ids2str(ids)
    # we need to log these independently of cards, as one side may have
    # more card templates
    mw.onRemNotes(self,ids,reason=reason)# new
    self._logRem(ids, REM_NOTE)
    self.db.execute("delete from notes where id in %s" % strids)

_Collection._remNotes=_remNotes

def remNotes(self, ids, reason=None):
    #only diff: adding a reason for deletion
        """Removes all cards associated to the notes whose id is in ids"""
        self.remCards(self.db.list("select id from cards where nid in "+
                                   ids2str(ids)), reason=reason or f"Removing notes  {ids}")
_Collection.remNotes=remNotes


# Differences:
# code factorized, thanks to checks
# Long explanation of each error
def basicCheck(self):
    """True if basic integrity is meet.

    Used before and after sync, or before a full upload.

    Tests:
    * whether each card belong to a note
    * each note has a model
    * each note has a card
    * each card's ord is valid according to the note model.
    * each card has distinct pair (ord, nid)

    """
    checks = [
        ("select id, nid from cards where nid not in (select id from notes)",
         "Card {} belongs to note {} which does not exists"),
        ("select id, flds, tags, mid from notes where id not in (select distinct nid from cards)",
         """Note {} has no cards. Fields: «{}», tags:«{}», mid:«{}»"""),
        ("""select id, flds, tags, mid from notes where mid not in %s""" % ids2str(self.models.ids()),
         """Note {} has an unexisting note type. Fields: «{}», tags:«{}», mid:{}"""),
        ("""select nid, ord, count(*), GROUP_CONCAT(id) from cards group by ord, nid having count(*)>1""",
         """Note {} has card at ord {} repeated {} times. Card ids are {}"""
        )
    ]
    for m in self.models.all():
        # ignore clozes
        mid = m['id']
        if m['type'] != MODEL_STD:
            continue
        checks.append((f"""select id, ord, nid from cards where ord <0 or ord>{len(m['tmpls'])} and nid in (select id from notes where mid = {mid})""",
                       "Card {}'s ord {} of note {} does not exists in model {mid}"))

    error = False
    for query,msg in checks:
        l = self.db.all(query)
        for tup in l:
            #print(f"Message is «{msg}», tup = «{tup}»", file = sys.stderr)
            formatted = msg.format(*tup)
            print(formatted, file = sys.stderr)
            error = True

    if error:
        return
    return True

_Collection.basicCheck = basicCheck
