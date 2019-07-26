from anki.collection import _Collection
from anki.utils import ids2str, maxID, intTime
from .debug import debugFun
import os
import stat
from anki.consts import *
from anki.lang import _

@debugFun
def genCards(self, nids, changedOrNewReq = None):
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
        avail = self.models.availOrds(model, flds, changedOrNewReq)
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
                if ((changedOrNewReq is None or ord in changedOrNewReq) and
                    ord not in avail):
                    rem.append(id)
    # bulk update
    self.db.executemany("""
insert into cards values (?,?,?,?,?,?,0,0,?,0,0,0,0,0,0,0,0,"")""",
                        data)
    return rem

_Collection.genCards = genCards
print("gen cards is changed")


## This one is changed only to ask not to recompute models.save
def fixIntegrity(self):
        "Fix possible problems and rebuild caches."
        problems = []
        self.save()
        oldSize = os.stat(self.path)[stat.ST_SIZE]
        if self.db.scalar("pragma integrity_check") != "ok":
            return (_("Collection is corrupt. Please see the manual."), False)
        # note types with a missing model
        ids = self.db.list("""
select id from notes where mid not in """ + ids2str(self.models.ids()))
        if ids:
            problems.append(
                ngettext("Deleted %d note with missing note type.",
                         "Deleted %d notes with missing note type.", len(ids))
                         % len(ids))
            self.remNotes(ids)
        # for each model
        for m in self.models.all():
            for t in m['tmpls']:
                if t['did'] == "None":
                    t['did'] = None
                    problems.append(_("Fixed AnkiDroid deck override bug."))
                    self.models.save(m, recomputeReq=False)
            if m['type'] == MODEL_STD:
                # model with missing req specification
                if 'req' not in m:
                    self.models._updateRequired(m)
                    problems.append(_("Fixed note type: %s") % m['name'])
                # cards with invalid ordinal
                ids = self.db.list("""
select id from cards where ord not in %s and nid in (
select id from notes where mid = ?)""" %
                                   ids2str([t['ord'] for t in m['tmpls']]),
                                   m['id'])
                if ids:
                    problems.append(
                        ngettext("Deleted %d card with missing template.",
                                 "Deleted %d cards with missing template.",
                                 len(ids)) % len(ids))
                    self.remCards(ids)
            # notes with invalid field count
            ids = []
            for id, flds in self.db.execute(
                    "select id, flds from notes where mid = ?", m['id']):
                if (flds.count("\x1f") + 1) != len(m['flds']):
                    ids.append(id)
            if ids:
                problems.append(
                    ngettext("Deleted %d note with wrong field count.",
                             "Deleted %d notes with wrong field count.",
                             len(ids)) % len(ids))
                self.remNotes(ids)
        # delete any notes with missing cards
        ids = self.db.list("""
select id from notes where id not in (select distinct nid from cards)""")
        if ids:
            cnt = len(ids)
            problems.append(
                ngettext("Deleted %d note with no cards.",
                         "Deleted %d notes with no cards.", cnt) % cnt)
            self._remNotes(ids)
        # cards with missing notes
        ids = self.db.list("""
select id from cards where nid not in (select id from notes)""")
        if ids:
            cnt = len(ids)
            problems.append(
                ngettext("Deleted %d card with missing note.",
                         "Deleted %d cards with missing note.", cnt) % cnt)
            self.remCards(ids)
        # cards with odue set when it shouldn't be
        ids = self.db.list("""
select id from cards where odue > 0 and (type=1 or queue=2) and not odid""")
        if ids:
            cnt = len(ids)
            problems.append(
                ngettext("Fixed %d card with invalid properties.",
                         "Fixed %d cards with invalid properties.", cnt) % cnt)
            self.db.execute("update cards set odue=0 where id in "+
                ids2str(ids))
        # cards with odid set when not in a dyn deck
        dids = [id for id in self.decks.allIds() if not self.decks.isDyn(id)]
        ids = self.db.list("""
select id from cards where odid > 0 and did in %s""" % ids2str(dids))
        if ids:
            cnt = len(ids)
            problems.append(
                ngettext("Fixed %d card with invalid properties.",
                         "Fixed %d cards with invalid properties.", cnt) % cnt)
            self.db.execute("update cards set odid=0, odue=0 where id in "+
                ids2str(ids))
        # tags
        self.tags.registerNotes()
        # field cache
        for m in self.models.all():
            self.updateFieldCache(self.models.nids(m))
        # new cards can't have a due position > 32 bits
        self.db.execute("""
update cards set due = 1000000, mod = ?, usn = ? where due > 1000000
and type = 0""", intTime(), self.usn())
        # new card position
        self.conf['nextPos'] = self.db.scalar(
            "select max(due)+1 from cards where type = 0") or 0
        # reviews should have a reasonable due #
        ids = self.db.list(
            "select id from cards where queue = 2 and due > 100000")
        if ids:
            problems.append("Reviews had incorrect due date.")
            self.db.execute(
                "update cards set due = ?, ivl = 1, mod = ?, usn = ? where id in %s"
                % ids2str(ids), self.sched.today, intTime(), self.usn())
        # v2 sched had a bug that could create decimal intervals
        curs = self.db.cursor()

        curs.execute("update cards set ivl=round(ivl),due=round(due) where ivl!=round(ivl) or due!=round(due)")
        if curs.rowcount:
            problems.append("Fixed %d cards with v2 scheduler bug." % curs.rowcount)

        curs.execute("update revlog set ivl=round(ivl),lastIvl=round(lastIvl) where ivl!=round(ivl) or lastIvl!=round(lastIvl)")
        if curs.rowcount:
            problems.append("Fixed %d review history entries with v2 scheduler bug." % curs.rowcount)
        # and finally, optimize
        self.optimize()
        newSize = os.stat(self.path)[stat.ST_SIZE]
        txt = _("Database rebuilt and optimized.")
        ok = not problems
        problems.append(txt)
        # if any problems were found, force a full sync
        if not ok:
            self.modSchema(check=False)
        self.save()
        return ("\n".join(problems), ok)

_Collection.fixIntegrity = fixIntegrity
