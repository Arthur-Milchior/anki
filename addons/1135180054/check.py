from anki.collection import _Collection
from anki.consts import *
from anki.utils import ids2str
import sys

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
