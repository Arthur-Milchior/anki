import aqt
from anki.lang import _
from aqt import mw
from aqt.browser import Browser
from aqt.qt import *
from aqt.qt import sip

from .config import getUserOption


def setupSearch(self):
    query = onBrowse()
    self.form.searchButton.clicked.connect(self.onSearchActivated)
    self.form.searchEdit.lineEdit().returnPressed.connect(self.onSearchActivated)
    self.form.searchEdit.setCompleter(None)
    self._searchPrompt =  _("<type here to search; hit enter to show current deck>")
    self.form.searchEdit.addItems([query or self._searchPrompt] + self.mw.pm.profile['searchHistory'])
    self._lastSearchTxt = query or onBrowse()
    self.search()
    # then replace text for easily showing the deck
    self.form.searchEdit.lineEdit().setText(query or self._searchPrompt)
    self.form.searchEdit.lineEdit().selectAll()
    self.form.searchEdit.setFocus()
# def search(self):
#     if "is:current" in self._lastSearchTxt:
#         # show current card if there is one
#         self._lastSearchTxt = onBrowse()
#     self.model.search(self._lastSearchTxt)

#     if not self.model.cards:
#         # no row change will fire
#         self._onRowChanged(None, None)
Browser.setupSearch = setupSearch

def onBrowse():
    if mw.state == "review":
        whatToShow = getUserOption("open")
        if whatToShow == "card":
            return f"cid:{mw.reviewer.card.id}"
        elif whatToShow == "note":
            return f"nid:{mw.reviewer.card.note().id}"
        elif whatToShow == "deck":
            return f"deck:{mw.col.decks.get(mw.reviewer.card.did)['name']}"
    elif mw.state == "overview":
        return f"deck:{mw.col.decks.get(mw.col.conf['curDeck'])['name']}"
    else:
        return ""
