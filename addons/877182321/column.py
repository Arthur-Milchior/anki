from aqt.deckbrowser import DeckBrowser
from .config import writeConfig, getUserOption
from anki.lang import _
from aqt.qt import *
from aqt.utils import askUser


lastHandler = DeckBrowser._linkHandler
def  _linkHandler(self,url):
    if ":" in url:
        (cmd, arg) = url.split(":")
        if cmd=="dragColumn":
            return columnHandler(self, arg)
        elif cmd=="optsColumn":
            return columnOptions(self,arg)
    return lastHandler(self,url)


def columnHandler(self, arg):
    draggedDeckId, ontoDeckId = arg.split(",")
    draggedDeckId = int(draggedDeckId)
    ontoDeckId = int(ontoDeckId)
    columns = getUserOption("columns")
    columns.insert(draggedDeckId, columns.pop(ontoDeckId))
    writeConfig()
    self.show()

def columnOptions(self, colpos):
    m = QMenu(self.mw)
    a = m.addAction(_("Delete"))
    a.triggered.connect(lambda: deleteColumn(self, colpos))
    m.exec_(QCursor.pos())

def deleteColumn(self, colpos):
    if not askUser(_("""Are you sure you wish to delete this column ?""")):
        return
    colpos = int(colpos)
    print("They are sure.")
    columns = getUserOption("columns")
    column = columns[colpos]
    column["present"] = False
    writeConfig()
    self.show()
