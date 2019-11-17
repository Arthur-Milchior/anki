import aqt
from aqt import mw
from aqt.main import AnkiQt
from aqt.qt import *
from aqt.qt import sip

from .config import getUserOption


def onBrowse(self):
    print("onBrowse")
    search = None
    if self.state == "review":
        print("from review")
        whatToShow = getUserOption("open")
        if whatToShow == "card":
            search = f"cid:{self.reviewer.card.id}"
        elif whatToShow == "note":
            search = f"nid:{self.reviewer.card.note().id}"
        elif whatToShow == "deck":
            search = f"deck:{self.col.decks.get(self.reviewer.card.did)['name']}"
    elif self.state == "overview":
        search = f"deck:{self.col.decks.get(self.col.conf['curDeck'])['name']}"
    browser = aqt.dialogs.open("Browser", self)
    if search:
        print(f"search is {search}")
        browser.form.searchEdit.lineEdit().setText(search)
        print("Text is set")
        browser.onSearchActivated()
        print("Text and activated")
AnkiQt.onBrowse = onBrowse

# old_shortcutKeys = Reviewer._shortcutKeys
# def _shortcutKeys(self):
#     old_shortcutKeys(self)+[("b", self.)]

def setupKeys(self):
    print("new setupkey")
    globalShortcuts = [
        ("Ctrl+:", self.onDebug),
        ("d", lambda: self.moveToState("deckBrowser")),
        ("s", self.onStudyKey),
        ("a", self.onAddCard),
        #("b", lambda: onBrowse(self)),
        ("t", self.onStats),
        ("y", self.onSync)
    ]
    self.applyShortcuts(globalShortcuts)

    self.stateShortcuts = []

AnkiQt.setupKeys = setupKeys

# #AnkiQt.setupKeys()
# # oldSetupKeys = AnkiQt.setupKeys
# # def setupKeys(self):
# #     oldSetupKeys(self)
# #     self.applyShortcuts([("b", self.onBrowse)])
# # AnkiQt.setupKeys = setupKeys
action = QAction(aqt.mw)
action.setText("Browser...")
action.setShortcut(QKeySequence("b"))
mw.form.menuTools.addAction(action)
action.triggered.connect(lambda: onBrowser(mw))
