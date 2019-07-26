from anki.collection import _Collection
from anki.consts import *
from ..consts import *
from anki.lang import _, ngettext
from anki.utils import ids2str, intTime
from aqt import mw
from anki.cards import Card
from ..config import getUserOption
import os
import stat

def integrity(self):
    # whether sqlite find a problem in its database
    if self.db.scalar("pragma integrity_check") != "ok":
        return (_("The database containing the collection is corrupt (i.e. pragma integrity_check fails). Please see the manual."), False)

def template(query, problem, singular, plural, deletion = None, reason = None):
    def f(self,problems):
        l = self.db.all(query)
        for tup in l:
            problems.append(problem.format(*tup))
        if l:
             problems.append(ngettext(singular,
                                       plural, len(l))
                              % len(l))
             if deletion:
                 deletion(l)
    return f

def noteWithMissingModel(self, problems):
    (template(
        """select id, flds, tags, mid from notes where mid not in """ + ids2str(self.models.ids()),
        "Deleted note {}, with fields «{}», tags «{}» whose model id is {}, which does not exists.",
        "Deleted %d note with missing note type.",
        "Deleted %d notes with missing note type.",
        lambda lines: self.remNotes([line[0]for line in lines],reason=f"Its note type is missing"
        )
    ))(self, problems)

def fixOverride(self, problems):
    for m in self.models.all():
        for t in m['tmpls']:
            if t['did'] == "None":
                t['did'] = None
                problems.append(_("Fixed AnkiDroid deck override bug. (I.e. some template has did = to 'None', it is now None.)"))
                self.models.save(m, recomputeReq=False)# modified: adding last parameter

def fixReq(self, problems):
    for m in self.models.all():
        if m['type'] == MODEL_STD:
            # model with missing req specification
            if 'req' not in m:
                self.models._updateRequired(m)
                problems.append(_("Fixed note type: %s") % m['name'])

def fixInvalidCardOrdinal(self, problems):
    funs = [
        template(
            f"""select id, nid, ord from cards where (ord <0 or ord >= {len(m['tmpls'])}) and nid in (select id from notes where mid = {m['id']})""",
            "Deleted card {} of note {} because its ord {} does not belong to its model",
            "Deleted %d card with missing template.",
            "Deleted %d cards with missing template.",
            lambda lines: self.remCards([line[0]for line in lines], reason=f"Cards removed because of missing templates."
            )
        )
        for m in self.models.all() if m['type'] == MODEL_STD]
    for fun in funs:
        fun(self,problems)

def fixWrongNumberOfField(self, problems):
    for m in self.models.all():
        # notes with invalid field count
        l = self.db.all(
            "select id, flds from notes where mid = ?", m['id'])
        ids = []
        for (id, flds) in l:
            nbFieldNote = flds.count("\x1f") + 1
            nbFieldModel = len(m['flds'])
            if nbFieldNote != nbFieldModel:
                ids.append(id)
                problems.append(f"""Note {id} with fields «{flds}» has {nbFieldNote} fields while its model {m['name']} has {nbFieldModel} fields""")
        if ids:
            self.remNotes([line[0]for line in lines],reason=f"It hads a wrong number of fields")


def fixNoteWithoutCard(self, problems):
    if getUserOption("Create empty card for empty note while checking database"):
        l = self.db.all("""select id, flds, tags, mid from notes where id not in (select distinct nid from cards)""")
        for nid, flds, tags, mid in l:
            note = mw.col.getNote(nid)
            note.addTag("NoteWithNoCard")
            note.flush()
            model = note.model()
            template0 = model["tmpls"][0]
            mw.col._newCard(note,template0,mw.col.nextID("pos"))
            problems.append("No cards in note {} with fields «{}» and tags «{}» of model {}. Adding card 1 and tag «NoteWithNoCard».".format(nid, fld, tags, mid))
        if l:
            problems.append("Created %d cards for notes without card"% (len(l)))
    else:
     (template(
         """select id, flds, tags, mid from notes where id not in (select distinct nid from cards)""",
         "Deleting note {} with fields «{}» and tags «{}» of model {} because it has no card.",
         "Deleted %d note with no cards.",
         "Deleted %d notes with no cards.",
         lambda lines: self.remNotes([line[0]for line in lines],reason=f"It has no cards")
     ))(self, problems)

def fixCardWithoutNote(self, problems):
    (template(
        "select id, nid from cards where nid not in (select id from notes)",
        "Deleted card {} of note {} because this note does not exists.",
        "Deleted %d card with missing note.",
        "Deleted %d cards with missing note.",
        lambda lines: self.remCards([line[0]for line in lines],reason=f"Card's note is missing")
    ))(self, problems)

def fixOdueType1(self, problems):
     # cards with odue set when it shouldn't be
     (template(
         f"select id,nid from cards where odue > 0 and type={CARD_LRN} and not odid",
         "set odue of card {} of note {} to 0, because it was positive while type was 1 (i.e. card in learning)",
         "Fixed %d card with invalid properties.",
         "Fixed %d cards with invalid properties.",
         lambda lines:(self.db.execute("update cards set odue=0 where id in "+ids2str([line[0] for line in lines])))

     ))(self, problems)

def fixOdueQueue2(self, problems):
    (template(
        f"select id, nid from cards where odue > 0 and queue={CARD_DUE} and not odid",
        "set odue of card {} of note {} to 0, because it was positive while queue was 2 (i.e. in the review queue).",
        "Fixed %d card with invalid properties.",
        "Fixed %d cards with invalid properties.",
         lambda lines:(self.db.execute("update cards set odue=0 where id in "+ids2str([line[0] for line in lines]))))
    )(self, problems)



def fixOdidOdue(self, problems):
    (template(
        """select id, odid, did from cards where odid > 0 and did in %s""" % ids2str([id for id in self.decks.allIds() if not self.decks.isDyn(id)]),# cards with odid set when not in a dyn deck
        "Card {}: Set odid and odue to 0 because odid was {} while its did was {} which is not filtered(a.k.a. not dymanic).",
        "Fixed %d card with invalid properties.",
        "Fixed %d cards with invalid properties.",
        lambda lists: self.db.execute("update cards set odid=0, odue=0 where id in "+
                                      ids2str([list[0] for list in lists]))
    )
    )(self, problems)

def intermediate(self, problems):
    # tags
    self.tags.registerNotes()
    # field cache
    for m in self.models.all():
        self.updateFieldCache(self.models.nids(m))

def atMost1000000Due(self, problems):
    # new cards can't have a due position > 32 bits
        curs = self.db.cursor()
        curs.execute("""
update cards set due = 1000000, mod = ?, usn = ? where due > 1000000
        and type = {CARD_NEW}""", intTime(), self.usn())
        if curs.rowcount:
            problems.append("Fixed %d cards with due greater than 1000000 due." % curs.rowcount)
    # (template (f"""select cards, due where due > 1000000 and type = {CARD_NEW}""",
    #            "Card {}: set due to 1000000 because it was {}, which is far too big for a due card.",
    #            "Fixed %d due card with due too big.",
    #            "Fixed %d due cards with due too big."
    # ))(self, problems)


def setNextPos(self):
    # new card position
    self.conf['nextPos'] = self.db.scalar(
        "select max(due)+1 from cards where type = 0") or 0

def reasonableRevueDue(self, problems):
    (template(# reviews should have a reasonable due #
        "select id, due from cards where queue = 2 and due > 100000",
        "Changue  of card {}, because its due is {} which is excessive",
        "Reviews had incorrect due date.",
        "Reviews had incorrect due date.",
        lambda lists: self.db.execute(
            "update cards set due = ?, ivl = 1, mod = ?, usn = ? where id in %s"
            % ids2str([list[0] for list in lists]), self.sched.today, intTime(), self.usn())
    )
    )(self, problems)

# v2 sched had a bug that could create decimal intervals
def fixFloatIvlInCard(self, problems):
    curs = self.db.cursor()
    curs.execute("update cards set ivl=round(ivl),due=round(due) where ivl!=round(ivl) or due!=round(due)")
    if curs.rowcount:
        problems.append("Fixed %d cards with v2 scheduler bug." % curs.rowcount)
    # (template(
    #     "select id, ivl from cards where ivl != round(ivl)",
    #     "Round the ivl of card {} because it was {} (this is a known bug of schedule v2.",
    #     "Fixed %d cards with v2 scheduler bug.",
    #     "Fixed %d cards with v2 scheduler bug."
    # )
    # )(self, problems)

def fixFloatIvlInRevLog(self, problems):
    curs = self.db.cursor()
    curs.execute("update revlog set ivl=round(ivl),lastIvl=round(lastIvl) where ivl!=round(ivl) or lastIvl!=round(lastIvl)")
    if curs.rowcount:
        problems.append("Fixed %d review history entires with v2 scheduler bug." % curs.rowcount)

def fixFloatDue(self, problems):
    (template(
    "select id, due from cards where due != round(due)",
    "Round the due of card {} because it was {} (this is a known bug of schedule v2.",
    "Fixed %d cards with v2 scheduler bug.",
    "Fixed %d cards with v2 scheduler bug."))(self, problems)

def doubleCard(self, problems):
    l = self.db.all("""select nid, ord, count(*), GROUP_CONCAT(id) from cards group by ord, nid having count(*)>1""")
    toRemove = []
    for nid, ord, count, ids in l:
        ids = ids.split(",")
        ids = [int(id) for id in ids]
        cards = [Card(self,id) for id in ids]
        bestCard = max(cards, key = (lambda card: (card.ivl, card.factor, card.due)))
        bestId = bestCard.id
        problems.append(f"There are {count} card for note {nid} at ord {ord}. They are {ids}. We only keep {bestId}")
        toRemove += [id for id in ids  if id!= bestId]
    if toRemove:
        self.remCards(toRemove)


def fixIntegrity(self):
    print("fix integrity")
    """Find the problems which will be found. Then call last fixing."""
    #differences: not recomputing models' req. Giving reason to deletion
    problems = []
    self.save()
    ret = integrity(self)#If the database itself is broken, there is nothing else to do.
    if ret:
        return ret

    for fun in [noteWithMissingModel,
                fixOverride,
                fixReq,
                fixInvalidCardOrdinal,
                fixWrongNumberOfField,
                fixNoteWithoutCard,
                fixCardWithoutNote,
                fixOdueType1,
                fixOdueQueue2,
                fixOdidOdue,
                intermediate,
                reasonableRevueDue,
                fixFloatIvlInCard,
                fixFloatIvlInRevLog,
                fixFloatDue,
                doubleCard,
    ]:
        fun(self,problems)


    # and finally, optimize
    self.optimize()
    newSize = os.stat(self.path)[stat.ST_SIZE]
    txt = _("Database rebuilt and optimized.")
    ok = not problems
    print("Adding in fixIntegrity.py")
    problems.append(txt)
    # if any problems were found, force a full sync
    if not ok:
        self.modSchema(check=False)
    self.save()
    return ("\n".join(problems), ok)
