# -*- coding: utf-8 -*-
# Copyright: Arthur Milchior <arthur@milchior.fr>
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
# feel free to contribute on https://github.com/Arthur-Milchior/anki-empty-new-cards
# Anki add-on number: 1402327111

import aqt
from anki.collection import _Collection
from anki.utils import ids2str
from aqt import mw
from aqt.qt import *


def check():
    oldGenCards= _Collection.genCards
    def genCards(*args,**kwargs):
        """Ids of cards which needs to be removed.

        Generate missing cards of a note with id in nids.
        """
        col = mw.col
        cids = oldGenCards(*args,**kwargs)
        cids = ids2str(cids)
        toDeleteCids=col.db.list("select id from cards where (type=0 and (id in "+cids+"))")
        #l =[]
        #for id in toDeleteCids:
        #print ("genCards: %s" %str(toDeleteCids))
        return toDeleteCids
    _Collection.genCards=genCards
    mw.onEmptyCards()
    _Collection.genCards=oldGenCards

action = QAction(aqt.mw)
action.setText("Empty new cards")
mw.form.menuTools.addAction(action)
action.triggered.connect(check)
