from anki.hooks import addHook
from anki.lang import _
from aqt import mw


def _overviewDeck(did):
    mw.col.decks.select(did)
    mw.realOverview ()

def add(m, did):
    a = m.addAction(_("Overview"))
    a.triggered.connect(lambda b, did=did: _overviewDeck(did))

addHook("showDeckOptions", add)
