# -*- coding: utf-8 -*-
# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html


import datetime
import itertools
import random
import time
from heapq import *
from operator import itemgetter

from anki.bothSched import BothScheduler
from anki.consts import *
from anki.hooks import runHook
from anki.lang import _
from anki.utils import fmtTimeSpan, ids2str, intTime

# card types: 0=new, 1=lrn, 2=rev, 3=relrn
# queue types: 0=new, 1=(re)lrn, 2=rev, 3=day (re)lrn,
#   4=preview, -1=suspended, -2=sibling buried, -3=manually buried
# revlog types: 0=lrn, 1=rev, 2=relrn, 3=early review
# positive revlog intervals are in days (rev), negative in seconds (lrn)
# odue/odid store original due/did when cards moved to filtered deck

class Scheduler(BothScheduler):
    name = "std2"

    def __init__(self, col):
        self.dynReportLimit = 99999
        self._lrnCutoff = 0
        super().__init__(col)

    def answerCard(self, card, ease):
        self.col.log()
        assert 1 <= ease <= 4
        assert 0 <= card.queue <= 4
        self.col.markReview(card)
        if self._burySiblingsOnAnswer:
            self._burySiblings(card)

        self._answerCard(card, ease)

        self._updateStats(card, 'time', card.timeTaken())
        card.mod = intTime()
        card.usn = self.col.usn()
        card.flushSched()

    def _answerCard(self, card, ease):
        if self._previewingCard(card):
            self._answerCardPreview(card, ease)
            return

        card.reps += 1

        if card.queue == QUEUE_NEW:
            # came from the new queue, move to learning
            card.queue = QUEUE_LRN
            card.type = CARD_LRN
            # init reps to graduation
            card.left = self._startingLeft(card)
            # update daily limit
            self._updateStats(card, 'new')

        if card.queue in (QUEUE_LRN, QUEUE_DAY_LRN):
            self._answerLrnCard(card, ease)
        elif card.queue == QUEUE_REV:
            self._answerRevCard(card, ease)
            # update daily limit
            self._updateStats(card, 'rev')
        else:
            assert 0

        # once a card has been answered once, the original due date
        # no longer applies
        if card.odue:
            card.odue = 0

    def _answerCardPreview(self, card, ease):
        assert 1 <= ease <= 2

        if ease == BUTTON_ONE:
            # repeat after delay
            card.queue = QUEUE_PREVIEW
            card.due = intTime() + self._previewDelay(card)
            self.lrnCount += 1
        else: #BUTTON_TWO
            # restore original card state and remove from filtered deck
            self._restorePreviewCard(card)
            self._removeFromFiltered(card)

    def counts(self, card=None):
        counts = [self.newCount, self.lrnCount, self.revCount]
        if card:
            idx = self.countIdx(card)
            counts[idx] += 1
        return tuple(counts)

    def dueForecast(self, days=7):
        "Return counts over next DAYS. Includes today."
        daysd = dict(self.col.db.all(f"""
select due, count() from cards
where did in %s and queue = {QUEUE_REV}
and due between ? and ?
group by due
order by due""" % (self._deckLimit()),
                            self.today,
                            self.today+days-1))
        for day in range(days):
            day = self.today+day
            if day not in daysd:
                daysd[day] = 0
        # return in sorted order
        ret = [count for (due, count) in sorted(daysd.items())]
        return ret

    def countIdx(self, card):
        if card.queue in (QUEUE_DAY_LRN,QUEUE_PREVIEW):
            return QUEUE_LRN
        return card.queue

    def answerButtons(self, card):
        """Number of buttons to show for this card"""
        conf = self._cardConf(card)
        if card.odid and not conf['resched']:
            return 2
        return 4

    # Deck list
    ##########################################################################

    def deckDueList(self):
        "Returns [deckname, did, rev, lrn, new]"
        self._checkDay()
        self.col.decks.checkIntegrity()
        decks = self.col.decks.all()
        decks.sort(key=itemgetter('name'))
        lims = {}
        data = []
        def parent(name):
            parts = name.split("::")
            if len(parts) < 2:
                return None
            parts = parts[:-1]
            return "::".join(parts)
        childMap = self.col.decks.childMap()
        for deck in decks:
            parentName = parent(deck['name'])
            # new
            nlim = self._deckNewLimitSingle(deck)
            if parentName:
                nlim = min(nlim, lims[parentName][0])
            new = self._newForDeck(deck['id'], nlim)
            # learning
            lrn = self._lrnForDeck(deck['id'])
            # reviews
            if parentName:
                plim = lims[parentName][1]
            else:
                plim = None
            rlim = self._deckRevLimitSingle(deck, parentLimit=plim)
            rev = self._revForDeck(deck['id'], rlim, childMap)
            # save to list
            data.append([deck['name'], deck['id'], rev, lrn, new])
            # add deck as a parent
            lims[deck['name']] = [nlim, rlim]
        return data

    def deckDueTree(self):
        return self._groupChildren(self.deckDueList())

    def _groupChildrenMain(self, decks):
        tree = []
        # group and recurse
        def key(deck):
            return deck[0][0]
        for (head, tail) in itertools.groupby(decks, key=key):
            tail = list(tail)
            did = None
            rev = 0
            new = 0
            lrn = 0
            children = []
            for node in tail:
                if len(node[0]) == 1:
                    # current node
                    did = node[1]
                    rev += node[2]
                    lrn += node[3]
                    new += node[4]
                else:
                    # set new string to tail
                    node[0] = node[0][1:]
                    children.append(node)
            children = self._groupChildrenMain(children)
            # tally up children counts
            for ch in children:
                lrn += ch[3]
                new += ch[4]
            # limit the counts to the deck's limits
            conf = self.col.decks.confForDid(did)
            deck = self.col.decks.get(did)
            if not conf['dyn']:
                new = max(0, min(new, conf['new']['perDay']-deck['newToday'][1]))
            tree.append((head, did, rev, lrn, new, children))
        return tuple(tree)

    # Getting the next card
    ##########################################################################

    def _getCard(self):
        "Return the next due card id, or None."
        # learning card due?
        card = self._getLrnCard()
        if card:
            return card

        # new first, or time for one?
        if self._timeForNewCard():
            card = self._getNewCard()
            if card:
                return card

        # day learning first and card due?
        dayLearnFirst = self.col.conf.get("dayLearnFirst", False)
        if dayLearnFirst:
            card = self._getLrnDayCard()
            if card:
                return card

        # card due for review?
        card = self._getRevCard()
        if card:
            return card

        # day learning card due?
        if not dayLearnFirst:
            card = self._getLrnDayCard()
            if card:
                return card

        # new cards left?
        card = self._getNewCard()
        if card:
            return card

        # collapse or finish
        return self._getLrnCard(collapse=True)

    # Learning queues
    ##########################################################################

    # scan for any newly due learning cards every minute
    def _updateLrnCutoff(self, force):
        nextCutoff = intTime() + self.col.conf['collapseTime']
        if nextCutoff - self._lrnCutoff > 60 or force:
            self._lrnCutoff = nextCutoff
            return True
        return False

    def _maybeResetLrn(self, force):
        if self._updateLrnCutoff(force):
            self._resetLrn()

    def _resetLrnCount(self):
        # sub-day
        self.lrnCount = self.col.db.scalar(f"""
select count() from cards where did in %s and queue = {QUEUE_LRN}
and due < ?""" %
            self._deckLimit(),
            self._lrnCutoff) or 0
        # day
        self.lrnCount += self.col.db.scalar(f"""
select count() from cards where did in %s and queue = {QUEUE_DAY_LRN}
and due <= ?""" % self._deckLimit(),
                                            self.today)
        # previews
        self.lrnCount += self.col.db.scalar(f"""
select count() from cards where did in %s and queue = {QUEUE_PREVIEW}
""" % self._deckLimit())

    def _resetLrn(self):
        self._updateLrnCutoff(force=True)
        super()._resetLrn()

    # sub-day learning
    def _fillLrn(self):
        cutoff = intTime() + self.col.conf['collapseTime']
        return super()._fillLrn(cutoff, f"queue in ({QUEUE_LRN},{QUEUE_PREVIEW})")

    def _getLrnCard(self, collapse=False):
        self._maybeResetLrn(force=collapse and self.lrnCount == 0)
        if self._fillLrn():
            cutoff = time.time()
            if collapse:
                cutoff += self.col.conf['collapseTime']
            if self._lrnQueue[0][0] < cutoff:
                id = heappop(self._lrnQueue)[1]
                card = self.col.getCard(id)
                self.lrnCount -= 1
                return card

    def _answerLrnCard(self, card, ease):
        conf = self._lrnConf(card)
        if card.type in (CARD_DUE,CARD_RELRN):
            type = REVLOG_RELRN
        else:
            type = REVLOG_LRN
        # lrnCount was decremented once when card was fetched
        lastLeft = card.left

        leaving = False

        # immediate graduate?
        if ease == BUTTON_FOUR:
            self._rescheduleAsRev(card, conf, True)
            leaving = True
        # next step?
        elif ease == BUTTON_THREE:
            # graduation time?
            if (card.left%1000)-1 <= 0:
                self._rescheduleAsRev(card, conf, False)
                leaving = True
            else:
                self._moveToNextStep(card, conf)
        elif ease == BUTTON_TWO:
            self._repeatStep(card, conf)
        else:
            # back to first step
            self._moveToFirstStep(card, conf)

        self._logLrn(card, ease, conf, leaving, type, lastLeft)

    def _updateRevIvlOnFail(self, card, conf):
        card.lastIvl = card.ivl
        card.ivl = self._lapseIvl(card, conf)

    def _moveToFirstStep(self, card, conf):
        card.left = self._startingLeft(card)

        # relearning card?
        if card.type == CARD_RELRN:
            self._updateRevIvlOnFail(card, conf)

        return self._rescheduleLrnCard(card, conf)

    def _moveToNextStep(self, card, conf):
        # decrement real left count and recalculate left today
        left = (card.left % 1000) - 1
        card.left = self._leftToday(conf['delays'], left)*1000 + left

        self._rescheduleLrnCard(card, conf)

    def _repeatStep(self, card, conf):
        delay = self._delayForRepeatingGrade(conf, card.left)
        self._rescheduleLrnCard(card, conf, delay=delay)

    def _rescheduleLrnCard(self, card, conf, delay=None):
        # normal delay for the current step?
        if delay is None:
            delay = self._delayForGrade(conf, card.left)

        card.due = int(time.time() + delay)
        # due today?
        if card.due < self.dayCutoff:
            # add some randomness, up to 5 minutes or 25%
            maxExtra = min(300, int(delay*0.25))
            fuzz = random.randrange(0, maxExtra)
            card.due = min(self.dayCutoff-1, card.due + fuzz)
            card.queue = QUEUE_LRN
            if card.due < (intTime() + self.col.conf['collapseTime']):
                self.lrnCount += 1
                # if the queue is not empty and there's nothing else to do, make
                # sure we don't put it at the head of the queue and end up showing
                # it twice in a row
                if self._lrnQueue and not self.revCount and not self.newCount:
                    smallestDue = self._lrnQueue[0][0]
                    card.due = max(card.due, smallestDue+1)
                heappush(self._lrnQueue, (card.due, card.id))
        else:
            # the card is due in one or more days, so we need to use the
            # day learn queue
            ahead = ((card.due - self.dayCutoff) // 86400) + 1
            card.due = self.today + ahead
            card.queue = QUEUE_DAY_LRN
        return delay

    def _delayForRepeatingGrade(self, conf, left):
        # halfway between last and next
        delay1 = self._delayForGrade(conf, left)
        if len(conf['delays']) > 1:
            delay2 = self._delayForGrade(conf, left-1)
        else:
            delay2 = delay1 * 2
        avg = (delay1+max(delay1, delay2))//2
        return avg

    def _lrnConf(self, card):
        if card.type in (CARD_DUE, CARD_RELRN):
            return self._lapseConf(card)
        else:
            return self._newConf(card)

    def _rescheduleAsRev(self, card, conf, early):
        lapse = card.type in (CARD_DUE, CARD_RELRN)

        if lapse:
            self._rescheduleGraduatingLapse(card, early)
        else:
            self._rescheduleNew(card, conf, early)

        # if we were dynamic, graduating means moving back to the old deck
        if card.odid:
            self._removeFromFiltered(card)

    def _rescheduleGraduatingLapse(self, card, early=False):
        if early:
            card.ivl += 1
        card.due = self.today+card.ivl
        card.queue = QUEUE_REV
        card.type = CARD_DUE

    def _startingLeft(self, card):
        if card.type == CARD_RELRN:
            conf = self._lapseConf(card)
        else:
            conf = self._lrnConf(card)
        tot = len(conf['delays'])
        tod = self._leftToday(conf['delays'], tot)
        return tot + tod*1000

    def _graduatingIvl(self, card, conf, early, fuzz=True):
        if card.type in (CARD_DUE, CARD_RELRN):
            bonus = early and 1 or 0
            return card.ivl + bonus
        if not early:
            # graduate
            ideal =  conf['ints'][0]
        else:
            # early remove
            ideal = conf['ints'][1]
        if fuzz:
            ideal = self._fuzzedIvl(ideal)
        return ideal

    def _rescheduleNew(self, card, conf, early):
        "Reschedule a new card that's graduated for the first time."
        super()._rescheduleNew(card, conf, early)
        card.type = CARD_DUE
        card.queue = QUEUE_REV

    def _lrnForDeck(self, did):
        cnt = self.col.db.scalar(
            f"""
select count() from
(select null from cards where did = ? and queue = {QUEUE_LRN} and due < ? limit ?)""",
            did, intTime() + self.col.conf['collapseTime'], self.reportLimit) or 0
        return cnt + self.col.db.scalar(
            f"""
select count() from
(select null from cards where did = ? and queue = {QUEUE_DAY_LRN}
and due <= ? limit ?)""",
            did, self.today, self.reportLimit)

    # Reviews
    ##########################################################################

    def _currentRevLimit(self):
        deck = self.col.decks.get(self.col.decks.selected(), default=False)
        return self._deckRevLimitSingle(deck)

    def _deckRevLimitSingle(self, deck, parentLimit=None):
        # invalid deck selected?
        if not deck:
            return 0

        lim = super()._deckRevLimitSingle(deck)

        if parentLimit is not None:
            return min(parentLimit, lim)
        elif '::' not in deck['name']:
            return lim
        else:
            for ancestor in self.col.decks.parents(deck['id']):
                # pass in dummy parentLimit so we don't do parent lookup again
                lim = min(lim, self._deckRevLimitSingle(ancestor, parentLimit=lim))
            return lim

    def _revForDeck(self, did, lim, childMap):
        dids = [did] + self.col.decks.childDids(did, childMap)
        lim = min(lim, self.reportLimit)
        return self.col.db.scalar(
            f"""
select count() from
(select 1 from cards where did in %s and queue = {QUEUE_REV}
and due <= ? limit ?)""" % ids2str(dids),
            self.today, lim)

    def _resetRevCount(self):
        lim = self._currentRevLimit()
        self.revCount = self.col.db.scalar(f"""
select count() from (select id from cards where
did in %s and queue = {QUEUE_REV} and due <= ? limit {lim})""" %
                                           ids2str(self.col.decks.active()),
                                           self.today)

    def _fillRev(self):
        if self._revQueue:
            return True
        if not self.revCount:
            return False

        lim = min(self.queueLimit, self._currentRevLimit())
        if lim:
            self._revQueue = self.col.db.list(f"""
select id from cards where
did in %s and queue = {QUEUE_REV} and due <= ?
order by due, random()
limit ?""" % ids2str(self.col.decks.active()),
                    self.today, lim)

            if self._revQueue:
                # preserve order
                self._revQueue.reverse()
                return True

        if self.revCount:
            # if we didn't get a card but the count is non-zero,
            # we need to check again for any cards that were
            # removed from the queue but not buried
            self._resetRev()
            return self._fillRev()

    # Answering a review card
    ##########################################################################

    def _answerRevCard(self, card, ease):
        delay = 0
        early = card.odid and (card.odue > self.today)
        type = early and REVLOG_CRAM or REVLOG_REV

        if ease == BUTTON_ONE:
            delay = self._rescheduleLapse(card)
        else:
            self._rescheduleRev(card, ease, early)

        self._logRev(card, ease, delay, type)

    def _rescheduleLapse(self, card):
        conf = self._lapseConf(card)

        card.lapses += 1
        card.factor = max(1300, card.factor-200)

        suspended = self._checkLeech(card, conf) and card.queue == QUEUE_SUSPENDED

        if conf['delays'] and not suspended:
            card.type = CARD_RELRN
            delay = self._moveToFirstStep(card, conf)
        else:
            # no relearning steps
            self._updateRevIvlOnFail(card, conf)
            self._rescheduleAsRev(card, conf, early=False)
            # need to reset the queue after rescheduling
            if suspended:
                card.queue = QUEUE_SUSPENDED
            delay = 0

        return delay

    def _lapseIvl(self, card, conf):
        ivl = max(1, conf['minInt'], int(card.ivl*conf['mult']))
        return ivl

    def _rescheduleRev(self, card, ease, early):
        # update interval
        card.lastIvl = card.ivl
        if early:
            self._updateEarlyRevIvl(card, ease)
        else:
            self._updateRevIvl(card, ease)

        # then the rest
        card.factor = max(1300, card.factor+[-150, 0, 150][ease-2])
        card.due = self.today + card.ivl

        # card leaves filtered deck
        self._removeFromFiltered(card)

    def _logRev(self, card, ease, delay, type):
        def log():
            self.col.db.execute(
                "insert into revlog values (?,?,?,?,?,?,?,?,?)",
                int(time.time()*1000), card.id, self.col.usn(), ease,
                -delay or card.ivl, card.lastIvl, card.factor, card.timeTaken(),
                type)
        try:
            log()
        except:
            # duplicate pk; retry in 10ms
            time.sleep(0.01)
            log()

    # Interval management
    ##########################################################################

    def _nextRevIvl(self, card, ease, fuzz):
        "Next review interval for CARD, given EASE."
        delay = self._daysLate(card)
        conf = self._revConf(card)
        fct = card.factor / 1000
        hardFactor = conf.get("hardFactor", 1.2)
        if hardFactor > 1:
            hardMin = card.ivl
        else:
            hardMin = 0
        ivl2 = self._constrainedIvl(card.ivl * hardFactor, conf, hardMin, fuzz)
        if ease == BUTTON_TWO:
            return ivl2

        ivl3 = self._constrainedIvl((card.ivl + delay // 2) * fct, conf, ivl2, fuzz)
        if ease == BUTTON_THREE:
            return ivl3

        ivl4 = self._constrainedIvl(
            (card.ivl + delay) * fct * conf['ease4'], conf, ivl3, fuzz)
        return ivl4

    def _constrainedIvl(self, ivl, conf, prev, fuzz):
        ivl = int(ivl * conf.get('ivlFct', 1))
        if fuzz:
            ivl = self._fuzzedIvl(ivl)
        ivl = max(ivl, prev+1, 1)
        ivl = min(ivl, conf['maxIvl'])
        return int(ivl)

    def _updateRevIvl(self, card, ease):
        card.ivl = self._nextRevIvl(card, ease, fuzz=True)

    def _updateEarlyRevIvl(self, card, ease):
        card.ivl = self._earlyReviewIvl(card, ease)

    # next interval for card when answered early+correctly
    def _earlyReviewIvl(self, card, ease):
        assert card.odid and card.type == CARD_DUE
        assert card.factor
        assert ease > 1

        elapsed = card.ivl - (card.odue - self.today)

        conf = self._revConf(card)

        easyBonus = 1
        # early 3/4 reviews shouldn't decrease previous interval
        minNewIvl = 1

        if ease == BUTTON_TWO:
            factor = conf.get("hardFactor", 1.2)
            # hard cards shouldn't have their interval decreased by more than 50%
            # of the normal factor
            minNewIvl = factor / 2
        elif ease == BUTTON_THREE:
            factor = card.factor / 1000
        else: # ease == BUTTON_FOUR:
            factor = card.factor / 1000
            ease4 = conf['ease4']
            # 1.3 -> 1.15
            easyBonus = ease4 - (ease4-1)/2

        ivl = max(elapsed * factor, 1)

        # cap interval decreases
        ivl = max(card.ivl*minNewIvl, ivl) * easyBonus

        ivl = self._constrainedIvl(ivl, conf, prev=0, fuzz=False)

        return ivl

    # Dynamic deck handling
    ##########################################################################

    def rebuildDyn(self, did=None):
        "Rebuild a dynamic deck."
        did = did or self.col.decks.selected()
        deck = self.col.decks.get(did)
        assert deck['dyn']
        # move any existing cards back first, then fill
        self.emptyDyn(did)
        cnt = self._fillDyn(deck)
        if not cnt:
            return
        # and change to our new deck
        self.col.decks.select(did)
        return cnt

    def _fillDyn(self, deck):
        start = -100000
        total = 0
        for search, limit, order in deck['terms']:
            orderlimit = self._dynOrder(order, limit)
            if search.strip():
                search = "(%s)" % search
            search = "%s -is:suspended -is:buried -deck:filtered" % search
            try:
                ids = self.col.findCards(search, order=orderlimit)
            except:
                return total
            # move the cards over
            self.col.log(deck['id'], ids)
            self._moveToDyn(deck['id'], ids, start=start+total)
            total += len(ids)
        return total

    def emptyDyn(self, did, lim=None):
        if not lim:
            lim = "did = %s" % did
        self.col.log(self.col.db.list("select id from cards where %s" % lim))

        self.col.db.execute("""
update cards set did = odid, %s,
due = (case when odue>0 then odue else due end), odue = 0, odid = 0, usn = ? where %s""" % (
            self._restoreQueueSnippet, lim),
                            self.col.usn())

    def remFromDyn(self, cids):
        self.emptyDyn(None, "id in %s and odid" % ids2str(cids))

    def _dynOrder(self, order, limit):
        if order == DYN_OLDEST:
            sort = "(select max(id) from revlog where cid=card.id)"
        elif order == DYN_RANDOM:
            sort = "random()"
        elif order == DYN_SMALLINT:
            sort = "ivl"
        elif order == DYN_BIGINT:
            sort = "ivl desc"
        elif order == DYN_LAPSES:
            sort = "lapses desc"
        elif order == DYN_ADDED:
            sort = "note.id"
        elif order == DYN_REVADDED:
            sort = "note.id desc"
        elif sort == DYN_DUEPRIORITY:
            sort = f"(case when queue={QUEUE_REV} and due <= %d then (ivl / cast(%d-due+0.001 as real)) else 100000+due end)" % (
                    self.today, self.today)
        else:# DYN_DUE or unknown
            sort = "card.due, card.ord"
        return sort + " limit %d" % limit

    def _moveToDyn(self, did, ids, start=-100000):
        deck = self.col.decks.get(did)
        data = []
        usn = self.col.usn()
        due = start
        for id in ids:
            data.append((did, due, usn, id))
            due += 1

        queue = ""
        if not deck['resched']:
            queue = f",queue={QUEUE_REV}"
        query = """
update cards set
odid = did, odue = due,
did = ?,
due = (case when due <= 0 then due else ? end),
usn = ?
%s
where id = ?
""" % queue
        self.col.db.executemany(query, data)

    def _removeFromFiltered(self, card):
        if card.odid:
            card.did = card.odid
            card.odue = 0
            card.odid = 0

    def _restorePreviewCard(self, card):
        assert card.odid

        card.due = card.odue

        # learning and relearning cards may be seconds-based or day-based;
        # other types map directly to queues
        if card.type in (CARD_LRN, CARD_RELRN):
            if card.odue > 1000000000:
                card.queue = QUEUE_LRN
            else:
                card.queue = QUEUE_DAY_LRN
        else:
            card.queue = card.type

    # Leeches
    ##########################################################################

    def _checkLeech(self, card, conf):
        "Leech handler. True if card was a leech."
        lf = conf['leechFails']
        if not lf:
            return
        # if over threshold or every half threshold reps after that
        if (card.lapses >= lf and
            (card.lapses-lf) % (max(lf // 2, 1)) == 0):
            # add a leech tag
            note = card.note()
            note.addTag("leech")
            note.flush()
            # handle
            leechAction = conf['leechAction']
            if leechAction == LEECH_SUSPEND:
                card.queue = QUEUE_SUSPENDED
            # notify UI
            runHook("leech", card)
            return True

    # Tools
    ##########################################################################

    def _cardConf(self, card):
        return self.col.decks.confForDid(card.did)

    def _newConf(self, card):
        conf = self._cardConf(card)
        # normal deck
        if not card.odid:
            return conf['new']
        # dynamic deck; override some attributes, use original deck for others
        oconf = self.col.decks.confForDid(card.odid)
        return dict(
            # original deck
            ints=oconf['new']['ints'],
            initialFactor=oconf['new']['initialFactor'],
            bury=oconf['new'].get("bury", True),
            delays=oconf['new']['delays'],
            # overrides
            separate=conf['separate'],
            order=NEW_CARDS_DUE,
            perDay=self.reportLimit
        )

    def _lapseConf(self, card):
        conf = self._cardConf(card)
        # normal deck
        if not card.odid:
            return conf['lapse']
        # dynamic deck; override some attributes, use original deck for others
        oconf = self.col.decks.confForDid(card.odid)
        return dict(
            # original deck
            minInt=oconf['lapse']['minInt'],
            leechFails=oconf['lapse']['leechFails'],
            leechAction=oconf['lapse']['leechAction'],
            mult=oconf['lapse']['mult'],
            delays=oconf['lapse']['delays'],
            # overrides
            resched=conf['resched'],
        )

    def _revConf(self, card):
        conf = self._cardConf(card)
        # normal deck
        if not card.odid:
            return conf['rev']
        # dynamic deck
        return self.col.decks.confForDid(card.odid)['rev']

    def _deckLimit(self):
        return ids2str(self.col.decks.active())

    def _previewingCard(self, card):
        conf = self._cardConf(card)
        return conf['dyn'] and not conf['resched']

    def _previewDelay(self, card):
        return self._cardConf(card).get("previewDelay", 10)*60

    # Daily cutoff
    ##########################################################################

    def _updateCutoff(self):
        oldToday = self.today
        # days since col created
        self.today = self._daysSinceCreation()
        # end of day cutoff
        self.dayCutoff = self._dayCutoff()
        if oldToday != self.today:
            self.col.log(self.today, self.dayCutoff)
        # update all daily counts, but don't save decks to prevent needless
        # conflicts. we'll save on card answer instead
        def update(deck):
            for type in "new", "rev", "lrn", "time":
                key = type+"Today"
                if deck[key][0] != self.today:
                    deck[key] = [self.today, 0]
        for deck in self.col.decks.all():
            update(deck)
        # unbury if the day has rolled over
        unburied = self.col.conf.get("lastUnburied", 0)
        if unburied < self.today:
            self.unburyCards()
            self.col.conf['lastUnburied'] = self.today

    def _checkDay(self):
        # check if the day has rolled over
        if time.time() > self.dayCutoff:
            self.reset()

    def _dayCutoff(self):
        rolloverTime = self.col.conf.get("rollover", 4)
        if rolloverTime < 0:
            rolloverTime = 24+rolloverTime
        date = datetime.datetime.today()
        date = date.replace(hour=rolloverTime, minute=0, second=0, microsecond=0)
        if date < datetime.datetime.today():
            date = date + datetime.timedelta(days=1)

        stamp = int(time.mktime(date.timetuple()))
        return stamp

    def _daysSinceCreation(self):
        startDate = datetime.datetime.fromtimestamp(self.col.crt)
        startDate = startDate.replace(hour=self.col.conf.get("rollover", 4),
                                      minute=0, second=0, microsecond=0)
        return int((time.time() - time.mktime(startDate.timetuple())) // 86400)

    # Deck finished state
    ##########################################################################

    def finishedMsg(self):
        return ("<b>"+_(
            "Congratulations! You have finished this deck for now.")+
            "</b><br><br>" + self._nextDueMsg())

    def _nextDueMsg(self):
        line = []
        # the new line replacements are so we don't break translations
        # in a point release
        if self.revDue():
            line.append(_("""\
Today's review limit has been reached, but there are still cards
waiting to be reviewed. For optimum memory, consider increasing
the daily limit in the options.""").replace("\n", " "))
        if self.newDue():
            line.append(_("""\
There are more new cards available, but the daily limit has been
reached. You can increase the limit in the options, but please
bear in mind that the more new cards you introduce, the higher
your short-term review workload will become.""").replace("\n", " "))
        if self.haveBuried():
            if self.haveCustomStudy:
                now = " " +  _("To see them now, click the Unbury button below.")
            else:
                now = ""
            line.append(_("""\
Some related or buried cards were delayed until a later session.""")+now)
        if self.haveCustomStudy and not self.col.decks.current()['dyn']:
            line.append(_("""\
To study outside of the normal schedule, click the Custom Study button below."""))
        return "<p>".join(line)

    def revDue(self):
        "True if there are any rev cards due."
        return self.col.db.scalar(
            (f"select 1 from cards where did in %s and queue = {QUEUE_REV} "
             "and due <= ? limit 1") % self._deckLimit(),
            self.today)

    def newDue(self):
        "True if there are any new cards due."
        return self.col.db.scalar(
            (f"select 1 from cards where did in %s and queue = {QUEUE_NEW} "
             "limit 1") % self._deckLimit())

    def haveBuriedSiblings(self):
        sdids = ids2str(self.col.decks.active())
        cnt = self.col.db.scalar(
            f"select 1 from cards where queue = {QUEUE_SCHED_BURIED} and did in %s limit 1" % sdids)
        return not not cnt

    def haveManuallyBuried(self):
        sdids = ids2str(self.col.decks.active())
        cnt = self.col.db.scalar(
            f"select 1 from cards where queue = {QUEUE_USER_BURIED} and did in %s limit 1" % sdids)
        return not not cnt

    def haveBuried(self):
        return self.haveManuallyBuried() or self.haveBuriedSiblings()

    # Next time reports
    ##########################################################################

    def nextIvlStr(self, card, ease, short=False):
        "Return the next interval for CARD as a string."
        ivl = self.nextIvl(card, ease)
        if not ivl:
            return _("(end)")
        ivlStr = fmtTimeSpan(ivl, short=short)
        if ivl < self.col.conf['collapseTime']:
            ivlStr = "<"+ivlStr
        return ivlStr

    def nextIvl(self, card, ease):
        "Return the next interval for CARD, in seconds."
        # preview mode?
        if self._previewingCard(card):
            if ease == BUTTON_ONE:
                return self._previewDelay(card)
            return 0

        # (re)learning?
        if card.queue in (QUEUE_NEW, QUEUE_LRN, QUEUE_DAY_LRN):
            return self._nextLrnIvl(card, ease)
        elif ease == BUTTON_ONE:
            # lapse
            conf = self._lapseConf(card)
            if conf['delays']:
                return conf['delays'][0]*60
            return self._lapseIvl(card, conf)*86400
        else:
            # review
            early = card.odid and (card.odue > self.today)
            if early:
                return self._earlyReviewIvl(card, ease)*86400
            else:
                return self._nextRevIvl(card, ease, fuzz=False)*86400

    # this isn't easily extracted from the learn code
    def _nextLrnIvl(self, card, ease):
        if card.queue == QUEUE_NEW:
            card.left = self._startingLeft(card)
        conf = self._lrnConf(card)
        if ease == BUTTON_ONE:
            # fail
            return self._delayForGrade(conf, len(conf['delays']))
        elif ease == BUTTON_TWO:
            return self._delayForRepeatingGrade(conf, card.left)
        elif ease == BUTTON_FOUR:
            return self._graduatingIvl(card, conf, True, fuzz=False) * 86400
        else: # ease == BUTTON_THREE
            left = card.left%1000 - 1
            if left <= 0:
                # graduate
                return self._graduatingIvl(card, conf, False, fuzz=False) * 86400
            else:
                return self._delayForGrade(conf, left)

    # Suspending & burying
    ##########################################################################

    # learning and relearning cards may be seconds-based or day-based;
    # other types map directly to queues
    _restoreQueueSnippet = f"""
queue = (case when type in ({CARD_LRN},{CARD_RELRN}) then
  (case when (case when odue then odue else due end) > 1000000000 then {QUEUE_LRN} else {QUEUE_DAY_LRN} end)
else
  type
end)
"""
    def suspendCards(self, ids):
        "Suspend cards."
        self.col.log(ids)
        self.col.db.execute(
            ("update cards set queue=%d,mod=?,usn=? where id in "%QUEUE_SUSPENDED)+
            ids2str(ids), intTime(), self.col.usn())

    def unsuspendCards(self, ids):
        "Unsuspend cards."
        self.col.log(ids)
        self.col.db.execute(
            ("update cards set %s,mod=?,usn=? "
            f"where queue = {QUEUE_SUSPENDED} and id in %s") % (self._restoreQueueSnippet, ids2str(ids)),
            intTime(), self.col.usn())

    def buryCards(self, cids, manual=True):
        queue = manual and QUEUE_USER_BURIED or QUEUE_SCHED_BURIED
        self.col.log(cids)
        self.col.db.execute("""
update cards set queue=?,mod=?,usn=? where id in """+ids2str(cids),
                            queue, intTime(), self.col.usn())

    def buryNote(self, nid):
        "Bury all cards for note until next session."
        cids = self.col.db.list(
            "select id from cards where nid = ? and queue >= 0", nid)
        self.buryCards(cids)

    def unburyCards(self):
        "Unbury all buried cards in all decks."
        self.col.log(
            self.col.db.list(f"select id from cards where queue in ({QUEUE_SCHED_BURIED}, {QUEUE_USER_BURIED})"))
        self.col.db.execute(
            f"update cards set %s where queue in ({QUEUE_SCHED_BURIED}, {QUEUE_USER_BURIED})" % self._restoreQueueSnippet)

    def unburyCardsForDeck(self, type="all"):
        if type == "all":
            queue = f"queue in ({QUEUE_SCHED_BURIED}, {QUEUE_USER_BURIED})"
        elif type == "manual":
            queue = f"queue = {QUEUE_USER_BURIED}"
        elif type == "siblings":
            queue = f"queue = {QUEUE_SCHED_BURIED}"
        else:
            raise Exception("unknown type")

        sids = ids2str(self.col.decks.active())
        self.col.log(
            self.col.db.list("select id from cards where %s and did in %s"
                             % (queue, sids)))
        self.col.db.execute(
            "update cards set mod=?,usn=?,%s where %s and did in %s"
            % (self._restoreQueueSnippet, queue, sids), intTime(), self.col.usn())

    # Sibling spacing
    ##########################################################################

    def _burySiblings(self, card):
        toBury = []
        nconf = self._newConf(card)
        buryNew = nconf.get("bury", True)
        rconf = self._revConf(card)
        buryRev = rconf.get("bury", True)
        # loop through and remove from queues
        for cid,queue in self.col.db.execute(f"""
select id, queue from cards where nid=? and id!=?
and (queue={QUEUE_NEW} or (queue={QUEUE_REV} and due<=?))""",
                card.nid, card.id, self.today):
            if queue == QUEUE_REV:
                if buryRev:
                    toBury.append(cid)
                # if bury disabled, we still discard to give same-day spacing
                try:
                    self._revQueue.remove(cid)
                except ValueError:
                    pass
            else:
                # if bury disabled, we still discard to give same-day spacing
                if buryNew:
                    toBury.append(cid)
                try:
                    self._newQueue.remove(cid)
                except ValueError:
                    pass
        # then bury
        if toBury:
            self.buryCards(toBury, manual=False)

    # Resetting
    ##########################################################################

    def forgetCards(self, ids):
        "Put cards at the end of the new queue."
        self.remFromDyn(ids)
        self.col.db.execute(
            (f"update cards set type={CARD_NEW},queue={QUEUE_NEW},ivl=0,due=0,odue=0,factor=?"
             " where id in ")+ids2str(ids), STARTING_FACTOR)
        pmax = self.col.db.scalar(
            f"select max(due) from cards where type={CARD_NEW}") or 0
        # takes care of mod + usn
        self.sortCards(ids, start=pmax+1)
        self.col.log(ids)

    def reschedCards(self, ids, imin, imax):
        "Put cards in review queue with a new interval in days (min, max)."
        cardData = []
        today = self.today
        mod = intTime()
        for id in ids:
            randValue = random.randint(imin, imax)
            cardData.append(dict(id=id, due=randValue+today, ivl=max(1, randValue), mod=mod,
                          usn=self.col.usn(), fact=STARTING_FACTOR))
        self.remFromDyn(ids)
        self.col.db.executemany(f"""
update cards set type={CARD_DUE},queue={QUEUE_REV},ivl=:ivl,due=:due,odue=0,
usn=:usn,mod=:mod,factor=:fact where id=:id""",
                                cardData)
        self.col.log(ids)

    def resetCards(self, ids):
        "Completely reset cards for export."
        sids = ids2str(ids)
        # we want to avoid resetting due number of existing new cards on export
        nonNew = self.col.db.list(
            f"select id from cards where id in %s and (queue != {QUEUE_NEW} or type != {CARD_NEW})"
            % sids)
        # reset all cards
        self.col.db.execute(
            f"update cards set reps=0,lapses=0,odid=0,odue=0,queue={QUEUE_NEW}"
            " where id in %s" % sids
        )
        # and forget any non-new cards, changing their due numbers
        self.forgetCards(nonNew)
        self.col.log(ids)

    # Repositioning new cards
    ##########################################################################

    def sortCards(self, cids, start=1, step=1, shuffle=False, shift=False):
        scids = ids2str(cids)
        now = intTime()
        nids = []
        nidsSet = set()
        for id in cids:
            nid = self.col.db.scalar("select nid from cards where id = ?", id)
            if nid not in nidsSet:
                nids.append(nid)
                nidsSet.add(nid)
        if not nids:
            # no new cards
            return
        # determine nid ordering
        due = {}
        if shuffle:
            random.shuffle(nids)
        for index, nid in enumerate(nids):
            due[nid] = start+index*step
        # pylint: disable=undefined-loop-variable
        high = start+index*step
        # shift?
        if shift:
            low = self.col.db.scalar(
                f"select min(due) from cards where due >= ? and type = {CARD_NEW} "
                "and id not in %s" % scids,
                start)
            if low is not None:
                shiftby = high - low + 1
                self.col.db.execute(f"""
update cards set mod=?, usn=?, due=due+? where id not in %s
and due >= ? and queue = {QUEUE_NEW}""" % scids, now, self.col.usn(), shiftby, low)
        # reorder cards
        cardData = []
        for id, nid in self.col.db.execute(
            (f"select id, nid from cards where type = {CARD_NEW} and id in ")+scids):
            cardData.append(dict(now=now, due=due[nid], usn=self.col.usn(), cid=id))
        self.col.db.executemany(
            "update cards set due=:due,mod=:now,usn=:usn where id = :cid", cardData)

    def randomizeCards(self, did):
        cids = self.col.db.list("select id from cards where did = ?", did)
        self.sortCards(cids, shuffle=True)

    def orderCards(self, did):
        cids = self.col.db.list("select id from cards where did = ? order by id", did)
        self.sortCards(cids)

    def resortConf(self, conf):
        for did in self.col.decks.didsForConf(conf):
            if conf['new']['order'] == NEW_CARDS_RANDOM:
                self.randomizeCards(did)
            else:
                self.orderCards(did)

    # for post-import
    def maybeRandomizeDeck(self, did=None):
        if not did:
            did = self.col.decks.selected()
        conf = self.col.decks.confForDid(did)
        # in order due?
        if conf['new']['order'] == NEW_CARDS_RANDOM:
            self.randomizeCards(did)

    # Changing scheduler versions
    ##########################################################################

    def _emptyAllFiltered(self):
        self.col.db.execute(f"""
update cards set did = odid, queue = (case
when type = {CARD_LRN} then {QUEUE_NEW}
when type = {CARD_RELRN} then {QUEUE_REV}
else type end), type = (case
        when type = {CARD_LRN} then {CARD_NEW}
        when type = {CARD_RELRN} then {CARD_DUE}
else type end),
        due = odue, odue = 0, odid = 0, usn = ? where odid != 0""",
                            self.col.usn())

    def _removeAllFromLearning(self, schedVer=2):
        # remove review cards from relearning
        if schedVer == 1:
            self.col.db.execute(f"""
    update cards set
    due = odue, queue = {QUEUE_REV}, type = {CARD_DUE}, mod = %d, usn = %d, odue = 0
    where queue in ({QUEUE_LRN},{QUEUE_DAY_LRN}) and type in ({CARD_DUE}, {CARD_RELRN})
    """ % (intTime(), self.col.usn()))
        else:
            self.col.db.execute(f"""
    update cards set
    due = %d+ivl, queue = {QUEUE_REV}, type = {CARD_DUE}, mod = %d, usn = %d, odue = 0
    where queue in ({QUEUE_LRN},{QUEUE_DAY_LRN}) and type in ({CARD_DUE}, {CARD_RELRN})
    """ % (self.today, intTime(), self.col.usn()))
        # remove new cards from learning
        self.forgetCards(self.col.db.list(
            f"select id from cards where queue in ({QUEUE_LRN}, {QUEUE_DAY_LRN})"))

    # v1 doesn't support buried/suspended (re)learning cards
    def _resetSuspendedLearning(self):
        self.col.db.execute(f"""
update cards set type = (case
when type = {CARD_LRN} then {CARD_NEW}
when type in ({CARD_DUE}, {CARD_RELRN}) then {CARD_DUE}
else type end),
due = (case when odue then odue else due end),
odue = 0,
mod = %d, usn = %d
where queue < 0""" % (intTime(), self.col.usn()))

    # no 'manually buried' queue in v1
    def _moveManuallyBuried(self):
        self.col.db.execute(f"update cards set queue={QUEUE_SCHED_BURIED},mod=%d where queue={QUEUE_USER_BURIED}" % intTime())

    # adding 'hard' in v2 scheduler means old ease entries need shifting
    # up or down
    def _remapLearningAnswers(self, sql):
        self.col.db.execute("update revlog set %s and type in (0,2)" % sql)

    def moveToV1(self):
        self._emptyAllFiltered()
        self._removeAllFromLearning()

        self._moveManuallyBuried()
        self._resetSuspendedLearning()
        self._remapLearningAnswers("ease=ease-1 where ease in (3,4)")

    def moveToV2(self):
        self._emptyAllFiltered()
        self._removeAllFromLearning(schedVer=1)
        self._remapLearningAnswers("ease=ease+1 where ease in (2,3)")
