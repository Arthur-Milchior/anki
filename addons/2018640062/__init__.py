from aqt import mw
from aqt.main import AnkiQt

from .init import onEmptyCards

AnkiQt.onEmptyCards = onEmptyCards
mw.form.actionEmptyCards.triggered.disconnect()
mw.form.actionEmptyCards.triggered.connect(mw.onEmptyCards)
