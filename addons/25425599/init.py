from anki.collection import _Collection
from anki.consts import *
from anki.lang import _
from anki.utils import ids2str
from aqt import mw


def emptyCardReport(self, cids):
    col = mw.col
    models = col.models
    rep = ""
    for ords, mid, flds in self.db.all("""
    select group_concat(ord), mid, flds from cards c, notes n
    where c.nid = n.id and c.id in %s group by nid order by mid""" % ids2str(cids)):
        model = models.get(mid)
        modelName  = model["name"]
        templates = model["tmpls"]
        isCloze = model["type"] == MODEL_CLOZE
        rep += _("Empty cards")+" ("+modelName+"): "
        if isCloze:
             rep+=ords
        else:
            for ord in ords.split(","):
                ord  = int(ord)
                templateName = templates[ord]["name"]
                rep += templateName+", "
        rep +="\nFields: %(f)s\n\n" % dict(f=flds.replace("\x1f", " / "))
    return rep


_Collection.emptyCardReport = emptyCardReport
