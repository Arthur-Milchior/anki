# -*- coding: utf-8 -*-
# Copyright: Arthur Milchior arthur@milchior.fr
# encoding: utf8
# License: GNU GPL, version 3 or later; http://www.gnu.org/copyleft/gpl.html
# Feel free to contribute to this code on https://github.com/Arthur-Milchior/anki-export-from-browser
# Add-on number 1983204951 https://ankiweb.net/shared/info/1983204951

import os
import re
import time

from PyQt5.QtWidgets import QAction

from anki import Collection
from anki.exporting import AnkiExporter, Exporter, exporters
from anki.hooks import addHook, remHook
from anki.lang import _, ngettext
from anki.utils import ids2str
from aqt import mw
from aqt.exporting import ExportDialog
from aqt.qt import QDialog, QDialogButtonBox, QKeySequence, QPushButton
from aqt.utils import (checkInvalidFilename, getSaveFile, showInfo,
                       showWarning, tooltip)


def debug(t):
    print(t)
    pass

def needSiblings(self):
    userOption = mw.addonManager.getConfig(__name__)
    siblings = userOption["siblings"]
    r=siblings.get(self.key)
    if r is None:
        r= siblings.get("default")
    if r is None:
        r = True
    debug(f"Calling needSiblings() with key {self.key}, returning {r}")
    return r
Exporter.needSiblings = needSiblings

def siblings(cids):
    siblings = mw.col.db.list(f"select id from cards where nid in (select nid from cards where id in {ids2str(cids)})")
    debug(f"Calling siblings({cids}), returning {siblings}")
    return siblings

oldCardIds= Exporter.cardIds
def cardIds(self):
    debug(f"Calling cardIds()")
    if self.cids is not None:
        debug(f"cids: {self.cids}, returning it")
        cids= self.cids
        self.count = len(cids)
    else:
        cids=oldCardIds(self)
        debug(f"cids: {self.did}, returning {cids}")
    if self.needSiblings():
        cids = siblings(cids)
    return cids
Exporter.cardIds = cardIds
