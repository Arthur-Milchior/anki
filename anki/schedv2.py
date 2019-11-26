# -*- coding: utf-8 -*-
# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

import datetime
import itertools
import random
import time
from heapq import *
from operator import itemgetter

from anki.bothSched import *
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
        super().__init__(col)
        self.dynReportLimit = 99999
        self._lrnCutoff = 0

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

    def countIdx(self, card):
        if card.queue in (QUEUE_DAY_LRN,QUEUE_PREVIEW):
            return QUEUE_LRN
        return card.queue

    def answerButtons(self, card):
        """The number of buttons to show in the reviewer for `card`"""
        conf = self._cardConf(card)
        if card.isFiltered() and not conf['resched']:
            return 2
        return 4

    # Deck list
    ##########################################################################

    def deckDueList(self):
        "Returns [deckname, did, rev, lrn, new]"
        self._checkDay()
        self.col.decks.checkIntegrity()
        decks = self.col.decks.all(sort=True)
        lims = {}
        data = []
        for deck in decks:
            parentName = deck.getParentName()
            # new
            nlim = self._deckNewLimitSingle(deck)
            if parentName:
                nlim = min(nlim, lims[parentName][0])
            new = self._newForDeck(deck.getId(), nlim)
            # learning
            lrn = self._lrnForDeck(deck.getId())
            # reviews
            if parentName:
                plim = lims[parentName][1]
            else:
                plim = None
            rlim = self._deckRevLimitSingle(deck, parentLimit=plim)
            rev = self._revForDeck(deck.getId(), rlim)
            # save to list
            data.append([deck.getName(), deck.getId(), rev, lrn, new])
            # add deck as a parent
            lims[deck.getName()] = [nlim, rlim]
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
            conf = self.col.decks.get(did).getConf()
            deck = self.col.decks.get(did)
            if conf.isStd():
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
        card = dayLearnFirst and self._getLrnDayCard()
        if card:
            return card

        # card due for review?
        card = self._getRevCard()
        if card:
            return card

        # day learning card due?
        card = not dayLearnFirst and self._getLrnDayCard()
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
        return super()._resetLrn()

    # sub-day learning
    def _fillLrn(self):
        return super()._fillLrn(intTime() + self.col.conf['collapseTime'], f"({QUEUE_LRN},{QUEUE_PREVIEW})")

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
        if card.type in (CARD_DUE,CARD_FILTERED):
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
        if card.type == CARD_FILTERED:
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
        if card.type in (CARD_DUE, CARD_FILTERED):
            return self._lapseConf(card)
        else:
            return self._newConf(card)

    def _rescheduleAsRev(self, card, conf, early):
        lapse = card.type in (CARD_DUE, CARD_FILTERED)

        if lapse:
            self._rescheduleGraduatingLapse(card)
        else:
            self._rescheduleNew(card, conf, early)

        # if we were dynamic, graduating means moving back to the old deck
        if card.isFiltered():
            self._removeFromFiltered(card)

    def _rescheduleGraduatingLapse(self, card):
        card.due = self.today+card.ivl
        card.queue = QUEUE_REV
        card.type = CARD_DUE

    def _startingLeft(self, card):
        if card.type == CARD_FILTERED:
            conf = self._lapseConf(card)
        else:
            conf = self._lrnConf(card)
        tot = len(conf['delays'])
        tod = self._leftToday(conf['delays'], tot)
        return tot + tod*1000

    def _graduatingIvl(self, card, conf, early, fuzz=True):
        if card.type in (CARD_DUE, CARD_FILTERED):
            return card.ivl
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
        elif '::' not in deck.getName():
            return lim
        else:
            for parent in deck.getAncestors():
                # pass in dummy parentLimit so we don't do parent lookup again
                lim = min(lim, self._deckRevLimitSingle(parent, parentLimit=lim))
            return lim

    def _revForDeck(self, did, lim, sort=True):
        dids = self.col.decks.childDids(did, includeSelf=True)
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
        early = card.isFiltered() and (card.odue > self.today)
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
            card.type = CARD_FILTERED
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
        assert card.isFiltered() and card.type == CARD_DUE
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
            self.col.log(deck.getId(), ids)
            self._moveToDyn(deck.getId(), ids, start=start+total)
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
        if card.isFiltered():
            card.did = card.odid
            card.odue = 0
            card.odid = 0

    def _restorePreviewCard(self, card):
        assert card.isFiltered()

        card.due = card.odue

        # learning and relearning cards may be seconds-based or day-based;
        # other types map directly to queues
        if card.type in (CARD_LRN, CARD_FILTERED):
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

    def _delays(self, conf, oconf, type):
        return oconf[type]['delays']

    def _previewingCard(self, card):
        conf = self._cardConf(card)
        return conf.isDyn() and not conf['resched']

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

    def haveManuallyBuried(self):
        sdids = ids2str(self.col.decks.active())
        cnt = self.col.db.scalar(
            f"select 1 from cards where queue = {QUEUE_USER_BURIED} and did in %s limit 1" % sdids)
        return not not cnt

    def haveBuried(self):
        return self.haveManuallyBuried() or self.haveBuriedSiblings()

    # Next time reports
    ##########################################################################

    def nextIvl(self, card, ease):
        "Return the next interval for CARD, in seconds."
        # preview mode?
        if self._previewingCard(card):
            if ease == BUTTON_ONE:
                return self._previewDelay(card)
            return 0
        # (re)learning?
        if card.queue in (QUEUE_NEW, QUEUE_LRN, QUEUE_DAY_LRN):
            r =  self._nextLrnIvl(card, ease)
            return r
        elif ease == BUTTON_ONE:
            # lapse
            conf = self._lapseConf(card)
            if conf['delays']:
                return conf['delays'][0]*60
            r = self._lapseIvl(card, conf)*86400
            return r
        else:
            # review
            early = card.isFiltered() and (card.odue > self.today)
            if early:
                r = self._earlyReviewIvl(card, ease)*86400
                return r
            else:
                r = self._nextRevIvl(card, ease, fuzz=False)*86400
                return r

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
queue = (case when type in ({CARD_LRN},{CARD_FILTERED}) then
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
        toBury = super()._burySiblings(card)
        # then bury
        if toBury:
            self.buryCards(toBury, manual=False)

    # Changing scheduler versions
    ##########################################################################

    def _emptyAllFiltered(self):
        self.col.db.execute(f"""
update cards set did = odid, queue = (case
when type = {CARD_LRN} then {QUEUE_NEW}
when type = {CARD_FILTERED} then {QUEUE_REV}
else type end), type = (case
        when type = {CARD_LRN} then {CARD_NEW}
        when type = {CARD_FILTERED} then {CARD_DUE}
else type end),
        due = odue, odue = 0, odid = 0, usn = ? where odid != 0""",
                            self.col.usn())

    def _removeAllFromLearning(self, schedVer=2):
        # remove review cards from relearning
        if schedVer == 1:
            self.col.db.execute(f"""
    update cards set
    due = odue, queue = {QUEUE_REV}, type = {CARD_DUE}, mod = %d, usn = %d, odue = 0
    where queue in ({QUEUE_LRN},{QUEUE_DAY_LRN}) and type in ({CARD_DUE}, {CARD_FILTERED})
    """ % (intTime(), self.col.usn()))
        else:
            self.col.db.execute(f"""
    update cards set
    due = %d+ivl, queue = {QUEUE_REV}, type = {CARD_DUE}, mod = %d, usn = %d, odue = 0
    where queue in ({QUEUE_LRN},{QUEUE_DAY_LRN}) and type in ({CARD_DUE}, {CARD_FILTERED})
    """ % (self.today, intTime(), self.col.usn()))
        # remove new cards from learning
        self.forgetCards(self.col.db.list(
            f"select id from cards where queue in ({QUEUE_LRN}, {QUEUE_DAY_LRN})"))

    # v1 doesn't support buried/suspended (re)learning cards
    def _resetSuspendedLearning(self):
        self.col.db.execute(f"""
update cards set type = (case
when type = {CARD_LRN} then {CARD_NEW}
when type in ({CARD_DUE}, {CARD_FILTERED}) then {CARD_DUE}
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
