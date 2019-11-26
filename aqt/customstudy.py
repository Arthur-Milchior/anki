# Copyright: Ankitects Pty Ltd and contributors
# -*- coding: utf-8 -*-
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

import aqt
from anki.consts import *
from anki.lang import _
from aqt.qt import *
from aqt.utils import showInfo, showWarning

RADIO_NEW = 1
RADIO_REV = 2
RADIO_FORGOT = 3
RADIO_AHEAD = 4
RADIO_PREVIEW = 5
RADIO_CRAM = 6

TYPE_NEW = 0
TYPE_DUE = 1
TYPE_REVIEW = 2
TYPE_ALL = 3

class CustomStudy(QDialog):
    def __init__(self, mw):
        QDialog.__init__(self, mw)
        self.mw = mw
        self.deck = self.mw.col.decks.current()
        self.conf = self.deck.getConf()
        self.form = aqt.forms.customstudy.Ui_Dialog()
        self.form.setupUi(self)
        self.setWindowModality(Qt.WindowModal)
        self.setupSignals()
        self.form.radioNew.click()
        self.exec_()

    def setupSignals(self):
        self.form.radioNew.clicked.connect(lambda: self.onRadioChange(RADIO_NEW))
        self.form.radioRev.clicked.connect(lambda: self.onRadioChange(RADIO_REV))
        self.form.radioForgot.clicked.connect(lambda: self.onRadioChange(RADIO_FORGOT))
        self.form.radioAhead.clicked.connect(lambda: self.onRadioChange(RADIO_AHEAD))
        self.form.radioPreview.clicked.connect(lambda: self.onRadioChange(RADIO_PREVIEW))
        self.form.radioCram.clicked.connect(lambda: self.onRadioChange(RADIO_CRAM))

    def onRadioChange(self, idx):
        sp = self.form.spin
        smin = 1; smax = DYN_MAX_SIZE; sval = 1
        post = _("cards")
        tit = ""
        spShow = True
        typeShow = False
        ok = _("OK")
        def plus(num):
            if num == 1000:
                num = "1000+"
            return "<b>"+str(num)+"</b>"
        if idx == RADIO_NEW:
            new = self.mw.col.sched.totalNewForCurrentDeck()
            # get the number of new cards in deck that exceed the new cards limit
            newUnderLearning = min(new, self.conf['new']['perDay'] - self.deck['newToday'][1])
            newExceeding = min(new, new - newUnderLearning)
            tit = _("New cards in deck over today limit: %s") % plus(newExceeding)
            pre = _("Increase today's new card limit by")
            sval = min(new, self.deck.get('extendNew', 10))
            smin = -DYN_MAX_SIZE
            smax = newExceeding
        elif idx == RADIO_REV:
            rev = self.mw.col.sched.totalRevForCurrentDeck()
            # get the number of review due in deck that exceed the review due limit
            revUnderLearning = min(rev, self.conf['rev']['perDay'] - self.deck['revToday'][1])
            revExceeding = min(rev, rev - revUnderLearning)
            tit = _("Reviews due in deck over today limit: %s") % plus(revExceeding)
            pre = _("Increase today's review limit by")
            sval = min(rev, self.deck.get('extendRev', 10))
            smin = -DYN_MAX_SIZE
            smax = revExceeding
        elif idx == RADIO_FORGOT:
            pre = _("Review cards forgotten in last")
            post = _("days")
            smax = 30
        elif idx == RADIO_AHEAD:
            pre = _("Review ahead by")
            post = _("days")
        elif idx == RADIO_PREVIEW:
            pre = _("Preview new cards added in the last")
            post = _("days")
            sval = 1
        elif idx == RADIO_CRAM:
            pre = _("Select")
            post = _("cards from the deck")
            #tit = _("After pressing OK, you can choose which tags to include.")
            ok = _("Choose Tags")
            sval = 100
            typeShow = True
        sp.setVisible(spShow)
        self.form.cardType.setVisible(typeShow)
        self.form.title.setText(tit)
        self.form.title.setVisible(not not tit)
        self.form.spin.setMinimum(smin)
        self.form.spin.setMaximum(smax)
        self.form.spin.setValue(sval)
        self.form.preSpin.setText(pre)
        self.form.postSpin.setText(post)
        self.form.buttonBox.button(QDialogButtonBox.Ok).setText(ok)
        self.radioIdx = idx

    def accept(self):
        spin = self.form.spin.value()
        if self.radioIdx == RADIO_NEW:
            self.deck['extendNew'] = spin
            self.deck.save()
            self.mw.col.sched.extendLimits(spin, 0)
            self.mw.reset()
            return QDialog.accept(self)
        elif self.radioIdx == RADIO_REV:
            self.deck['extendRev'] = spin
            self.deck.save()
            self.mw.col.sched.extendLimits(0, spin)
            self.mw.reset()
            return QDialog.accept(self)
        elif self.radioIdx == RADIO_CRAM:
            tags = self._getTags()
        # the rest create a filtered deck
        cur = self.mw.col.decks.byName(_("Custom Study Session"))
        if cur:
            if cur.isStd():
                showInfo("Please rename the existing Custom Study deck first.")
                return QDialog.accept(self)
            else:
                # safe to empty
                self.mw.col.sched.emptyDyn(cur.getId())
                # reuse; don't delete as it may have children
                dyn = cur
                cur.select()
        else:
            did = self.mw.col.decks.newDyn(_("Custom Study Session"))
            dyn = self.mw.col.decks.get(did)
        # and then set various options
        if self.radioIdx == RADIO_FORGOT:
            dyn['terms'][0] = ['rated:%d:1' % spin, DYN_MAX_SIZE, DYN_RANDOM]
            dyn['resched'] = False
        elif self.radioIdx == RADIO_AHEAD:
            dyn['terms'][0] = ['prop:due<=%d' % spin, DYN_MAX_SIZE, DYN_DUE]
            dyn['resched'] = True
        elif self.radioIdx == RADIO_PREVIEW:
            dyn['terms'][0] = ['is:new added:%s'%spin, DYN_MAX_SIZE, DYN_OLDEST]
            dyn['resched'] = False
        elif self.radioIdx == RADIO_CRAM:
            type = self.form.cardType.currentRow()
            if type == TYPE_NEW:
                terms = "is:new "
                ord = DYN_ADDED
                dyn['resched'] = True
            elif type == TYPE_DUE:
                terms = "is:due "
                ord = DYN_DUE
                dyn['resched'] = True
            elif type == TYPE_REVIEW:
                terms = "-is:new "
                ord = DYN_RANDOM
                dyn['resched'] = True
            else:
                terms = ""
                ord = DYN_RANDOM
                dyn['resched'] = False
            dyn['terms'][0] = [(terms+tags).strip(), spin, ord]
        # add deck limit
        dyn['terms'][0][0] = "deck:\"%s\" %s " % (self.deck.getName(), dyn['terms'][0][0])
        # generate cards
        if not self.mw.col.sched.rebuildDyn():
            return showWarning(_("No cards matched the criteria you provided."))
        self.mw.moveToState("overview")
        QDialog.accept(self)

    def _getTags(self):
        from aqt.taglimit import TagLimit
        tl = TagLimit(self.mw, self)
        return tl.tags
