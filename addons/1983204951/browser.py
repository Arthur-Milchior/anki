from PyQt5.QtWidgets import QAction

from anki.hooks import addHook
from aqt.exporting import ExportDialog
from aqt.qt import QKeySequence


def setupMenu(browser):
    a = QAction("Export selection", browser)
    a.setShortcut(QKeySequence("Ctrl+Shift+E"))
    a.triggered.connect(lambda : ExportDialog(mw,cids=browser.selectedCards()))
    browser.form.menuEdit.addAction(a)

addHook("browser.setupMenus", setupMenu)
