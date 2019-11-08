from anki.hooks import addHook
from aqt.qt import *
from aqt.utils import getText

from .sched import sortCids


def addToBrowser(fun, text, shortcut=None):
    """fun -- function taking as argument: the browser
    text -- what to enter in the menu
    shortcut
    """
    def aux(browser):
        action = browser.form.menuEdit.addAction(text)
        action.triggered.connect(lambda: fun(browser))
        if shortcut:
            action.setShortcut(QKeySequence(shortcut))
    addHook("browser.setupMenus", aux)

def sort(self):
    cids = self.selectedCards()
    params = self.col.conf.get("special sort", "")
    (params, ret) = getText("How to sort those cards", self, default=params)
    if not ret:
        return
    self.col.conf["special sort"] = params
    sortCids(cids, f"[{params}]")
addToBrowser(sort, "Sort", "Alt+S")
