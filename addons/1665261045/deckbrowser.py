from anki.hooks import addHook
from anki.lang import _
from aqt import mw
from aqt.utils import getText

from .sched import sortDid


def addActionToGear(fun, text):
    """fun -- takes an argument, the did
    text -- what's written in the gear."""
    def aux(m, did):
        a = m.addAction(text)
        a.triggered.connect(lambda b, did=did: fun(did))
    addHook("showDeckOptions", aux)

def _sort(did):
    deck = mw.col.decks.get(did)
    params = deck.get("special sort", "")
    (params, ret) = getText("How to sort those cards", default=params)
    if not ret:
        return
    deck["special sort"] = params
    mw.col.decks.save(deck)
    sortDid(did, f"[{params}]")

addActionToGear(_sort, _("Sort"))
