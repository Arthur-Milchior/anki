# -*- coding: utf-8 -*-
# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

import itertools
import random
import time
from heapq import *
from operator import itemgetter

from anki.bothSched import *
from anki.consts import *
from anki.hooks import runHook
from anki.lang import _
#from anki.cards import Card
from anki.utils import fmtTimeSpan, ids2str, intTime

# queue types: 0=new/cram, 1=lrn, 2=rev, 3=day lrn, -1=suspended, -2=buried
# revlog types: 0=lrn, 1=rev, 2=relrn, 3=cram
# positive revlog intervals are in days (rev), negative in seconds (lrn)

class Scheduler(BothScheduler):
    name = "std"
    _spreadRev = True

    def answerCard(self, card, ease):
        """Change the number of card to see in the decks and its
        ancestors. Change the due/interval/ease factor of this card,
        according to the button ease.

        """
        self.col.log()
        assert 1 <= ease <= 4
        self.col.markReview(card)
        if self._burySiblingsOnAnswer:
            self._burySiblings(card)
        card.reps += 1
        # former is for logging new cards, latter also covers filt. decks
        card.wasNew = card.type == CARD_NEW
        wasNewQ = card.queue == QUEUE_NEW
        if wasNewQ:
            # came from the new queue, move to learning
            card.queue = QUEUE_LRN
            # if it was a new card, it's now a learning card
            if card.type == CARD_NEW:
                card.type = CARD_LRN
            # init reps to graduation
            card.left = self._startingLeft(card)
            # dynamic?
            if card.isFiltered() and card.type == CARD_DUE:
                if self._resched(card):
                    # reviews get their ivl boosted on first sight
                    card.ivl = self._dynIvlBoost(card)
                    card.odue = self.today + card.ivl
            self._updateStats(card, 'new')
        if card.queue in (QUEUE_LRN, QUEUE_DAY_LRN):
            self._answerLrnCard(card, ease)
            if not wasNewQ:# if wasNewQ holds, updating already
                # happened above
                self._updateStats(card, 'lrn')
        elif card.queue == QUEUE_REV:
            self._answerRevCard(card, ease)
            self._updateStats(card, 'rev')
        else:
            raise Exception("Invalid queue")
        self._updateStats(card, 'time', card.timeTaken())
        card.mod = intTime()
        card.usn = self.col.usn()
        card.flushSched()

    def counts(self, card=None):
        """The three numbers to show in anki deck's list/footer.
        Number of new cards, learning repetition, review card.

        If cards, then the tuple takes into account the card.
        """
        counts = [self.newCount, self.lrnCount, self.revCount]
        if card:
            idx = self.countIdx(card)
            if idx == QUEUE_LRN:
                counts[1] += card.left // 1000
            else:
                counts[idx] += 1
        return tuple(counts)

    def countIdx(self, card):
        """In which column the card in the queue should be counted.
        day_lrn is sent to lrn, otherwise its the identity"""
        if card.queue == QUEUE_DAY_LRN:
            return QUEUE_LRN
        return card.queue

    def answerButtons(self, card):
        """The number of buttons to show in the reviewer for `card`"""
        if card.odue:
            # normal review in dyn deck?
            if card.isFiltered() and card.queue == QUEUE_REV:
                return 4
            conf = self._lrnConf(card)
            if card.type in (CARD_NEW,CARD_LRN) or len(conf['delays']) > 1:
                return 3
            return 2
        elif card.queue == QUEUE_REV:
            return 4
        else:
            return 3

    def unburyCards(self):
        "Unbury all cards of the collection."
        self.col.conf['lastUnburied'] = self.today
        self.col.log(
            self.col.db.list(f"select id from cards where queue = {QUEUE_SCHED_BURIED}"))
        self.col.db.execute(
            f"update cards set queue=type where queue = {QUEUE_SCHED_BURIED}")

    def unburyCardsForDeck(self):
        sids = ids2str(self.col.decks.active())
        self.col.log(
            self.col.db.list(f"select id from cards where queue = {QUEUE_SCHED_BURIED} and did in %s"
                             % (sids)))
        self.col.db.execute(
            f"update cards set mod=?,usn=?,queue=type where queue = {QUEUE_SCHED_BURIED} and did in %s"
            % (sids), intTime(), self.col.usn())

    # Deck list
    ##########################################################################

    def deckDueList(self):
        """
        Similar to nodes, without the recursive counting, with the full deck name

        [deckname (with ::),
        did, rev, lrn, new (not counting subdeck)]"""
        self._checkDay()
        self.col.decks.checkIntegrity()
        decks = self.col.decks.all()
        decks.sort(key=itemgetter('name'))
        #lims -- associating to each deck maximum number of new card and of review. Taking custom study into account
        lims = {}
        data = []
        for deck in decks:
            parentName = deck.getParentName()
            # new
            #nlim -- maximal number of new card, taking parent into account
            nlim = self._deckNewLimitSingle(deck)
            if parentName:
                nlim = min(nlim, lims[parentName][0])
            new = self._newForDeck(deck.getId(), nlim)
            # learning
            lrn = self._lrnForDeck(deck.getId())
            # reviews
            #rlim -- maximal number of review, taking parent into account
            rlim = self._deckRevLimitSingle(deck)
            if parentName:
                rlim = min(rlim, lims[parentName][1])
            rev = self._revForDeck(deck.getId(), rlim)
            # save to list
            data.append([deck.getName(), deck.getId(), rev, lrn, new])
            # add deck as a parent
            lims[deck.getName()] = [nlim, rlim]
        return data

    def deckDueTree(self):
        """Generate the node of the main deck. See deckbroser introduction to see what a node is
        """
        #something similar to nodes, but without the recursive part
        nodes_=self.deckDueList()
        #the actual nodes
        nodes=self._groupChildren(nodes_)
        return nodes

    def _groupChildrenMain(self, decks):
        """
        [subdeck name without parent parts,
        did, rev, lrn, new (counting subdecks)
        [recursively the same things for the children]]

        keyword arguments:
        grps -- [[subdeck], did, rev, lrn, new] sorted according to the list subdeck. Number for the subdeck precisely"""
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
                rev += ch[2]
                lrn += ch[3]
                new += ch[4]
            # limit the counts to the deck's limits
            conf = self.col.decks.get(did).getConf()
            deck = self.col.decks.get(did)
            if conf.isStd():
                rev = max(0, min(rev, conf['rev']['perDay']-deck['revToday'][1]))
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
        # card due for review?
        card = self._getRevCard()
        if card:
            return card
        # day learning card due?
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

    def _resetLrnCount(self):
        """Set lrnCount"""
        # Number of reps which are due today, last seen today caped by report limit, in the selected decks
        self.lrnCount = self.col.db.scalar(f"""
select sum(left/1000) from (select left from cards where
did in %s and queue = {QUEUE_LRN} and due < ? limit %d)""" % (
            self.col.decks._deckLimit(), self.reportLimit),
            self.dayCutoff) or 0
        # Number of cards in learning which are due today, last seen another day caped by report limit, in the selected decks
        self.lrnCount += self.col.db.scalar(f"""
select count() from cards where did in %s and queue = {QUEUE_DAY_LRN}
and due <= ? limit %d""" % (self.col.decks._deckLimit(),  self.reportLimit),
                                            self.today)

    # sub-day learning
    def _fillLrn(self):
        return super()._fillLrn(self.dayCutoff, f"({QUEUE_LRN})")

    def _getLrnCard(self, collapse=False):
        if self._fillLrn():
            cutoff = time.time()
            if collapse:
                cutoff += self.col.conf['collapseTime']
            if self._lrnQueue[0][0] < cutoff:
                id = heappop(self._lrnQueue)[1]
                card = self.col.getCard(id)
                self.lrnCount -= card.left // 1000
                return card

    def _answerLrnCard(self, card, ease):
        # ease 1=no, 2=yes, 3=remove
        conf = self._lrnConf(card)
        if card.isFiltered() and not card.wasNew:
            type = REVLOG_CRAM
        elif card.type == CARD_DUE:
            type = REVLOG_RELRN
        else:
            type = REVLOG_LRN
        leaving = False
        # lrnCount was decremented once when card was fetched
        lastLeft = card.left
        # immediate graduate?
        if ease == BUTTON_THREE:
            self._rescheduleAsRev(card, conf, True)
            leaving = True
        # graduation time?
        elif ease == BUTTON_TWO and (card.left%1000)-1 <= 0:
            self._rescheduleAsRev(card, conf, False)
            leaving = True
        else:
            # one step towards graduation
            if ease == BUTTON_TWO:
                # decrement real left count and recalculate left today
                left = (card.left % 1000) - 1
                card.left = self._leftToday(conf['delays'], left)*1000 + left
            # failed
            else:
                card.left = self._startingLeft(card)
                resched = self._resched(card)
                if 'mult' in conf and resched:
                    # review that's lapsed
                    card.ivl = max(1, conf['minInt'], card.ivl*conf['mult'])
                else:
                    # new card; no ivl adjustment
                    pass
                if resched and card.isFiltered():
                    card.odue = self.today + 1
            delay = self._delayForGrade(conf, card.left)
            if card.due < time.time():
                # not collapsed; add some randomness
                delay *= random.uniform(1, 1.25)
            card.due = int(time.time() + delay)
            # due today?
            if card.due < self.dayCutoff:
                self.lrnCount += card.left // 1000
                # if the queue is not empty and there's nothing else to do, make
                # sure we don't put it at the head of the queue and end up showing
                # it twice in a row
                card.queue = QUEUE_LRN
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
        self._logLrn(card, ease, conf, leaving, type, lastLeft)

    def _lrnConf(self, card):
        """ lapse configuration if the card was due(i.e. review card
        ?), otherwise new configuration.  I don't get the point"""
        if card.type == CARD_DUE:
            return self._lapseConf(card)
        else:
            return self._newConf(card)

    def _rescheduleAsRev(self, card, conf, early):
        """Change schedule for graduation.

        We assume that card is currently in learning. So it's easier
        new and did all its steps, or a lapse.

        If it's filtered without rescheduling, remove the card from
        filtered and do nothing else.

        If it's lapsed, set the due date to tomorrow. Do not change
        the interval.

        If it's a new card, change interval according to
        _rescheduleNew. I.e. conf['ints'][1 if early
        else 0]", change the due date accordingly. Change the easyness
        to initial one.

        """
        lapse = card.type == CARD_DUE
        if lapse:
            if self._resched(card):
                card.due = max(self.today+1, card.odue)
            else: #i.e. a filtered deck not rescheduling.
                card.due = card.odue
            card.odue = 0
        else:
            self._rescheduleNew(card, conf, early)
        # Interval is now set. We must deal with queue and moving deck
        # if dynamic.
        card.queue = QUEUE_REV
        card.type = CARD_DUE
        # if we were dynamic, graduating means moving back to the old deck
        resched = self._resched(card)
        if card.isFiltered():
            card.did = card.odid
            card.odue = 0
            card.odid = 0
            # if rescheduling is off, it needs to be set back to a new card
            if not resched and not lapse:
                card.queue = QUEUE_NEW
                card.type = CARD_NEW
                card.due = self.col.nextID("pos")

    def _startingLeft(self, card):
        """(number of review to see, number which can be seen today)
        But instead of a pair (a,b), returns a+1000*b.
        """
        if card.type == CARD_DUE:
            conf = self._lapseConf(card)
        else:
            conf = self._lrnConf(card)
        tot = len(conf['delays'])
        tod = self._leftToday(conf['delays'], tot)
        return tot + tod*1000

    def _graduatingIvl(self, card, conf, early, adj=True):
        """
        The interval before the next review.
        If its lapsed card in a filtered deck, then use _dynIvlBoost.
        Otherwise, if button was easy or not, use the 'ints' value
        according to conf parameter.
        Maybe apply some fuzzyness according to adj

        Card is supposed to be in learning.
        card -- a card object
        conf -- the configuration dictionnary for this kind of card
        early -- whether "easy" was pressed
        adj -- whether to add fuzziness
        """
        if card.type == CARD_DUE:
            # lapsed card being relearnt
            if card.isFiltered():
                if conf['resched']:
                    return self._dynIvlBoost(card)
            return card.ivl
        if not early:
            # graduate
            ideal =  conf['ints'][0]
        else:
            # early remove
            ideal = conf['ints'][1]
        if adj:
            return self._adjRevIvl(card, ideal)
        else:
            return ideal

    def removeLrn(self, ids=None):
        "Remove cards from the learning queues."
        if ids:
            extra = " and id in "+ids2str(ids)
        else:
            # benchmarks indicate it's about 10x faster to search all decks
            # with the index than scan the table
            extra = " and did in "+ids2str(self.col.decks.allIds())
        # review cards in relearning
        self.col.db.execute(f"""
update cards set
due = odue, queue = {QUEUE_REV}, mod = %d, usn = %d, odue = 0
where queue in ({QUEUE_LRN},{QUEUE_DAY_LRN}) and type = {CARD_DUE}
%s
""" % (intTime(), self.col.usn(), extra))
        # new cards in learning
        self.forgetCards(self.col.db.list(
            f"select id from cards where queue in ({QUEUE_LRN}, {QUEUE_DAY_LRN}) %s" % extra))

    def _lrnForDeck(self, did):
        """Number of review of cards in learing of deck did. """
        cnt = self.col.db.scalar(
            f"""
select sum(left/1000) from
(select left from cards where did = ? and queue = {QUEUE_LRN} and due < ? limit ?)""",
            did, intTime() + self.col.conf['collapseTime'], self.reportLimit) or 0
        return cnt + self.col.db.scalar(
            f"""
select count() from
(select 1 from cards where did = ? and queue = {QUEUE_DAY_LRN}
and due <= ? limit ?)""" ,
            did, self.today, self.reportLimit)

    # Reviews
    ##########################################################################

    def _deckRevLimit(self, did):
        return self._deckLimit(did, self._deckRevLimitSingle)

    def _revForDeck(self, did, lim):
        """number of cards to review today for deck did

        Minimum between this number, self report and limit. Not taking subdeck into account """
        lim = min(lim, self.reportLimit)
        return self.col.db.scalar(
            f"""
select count() from
(select 1 from cards where did = ? and queue = {QUEUE_REV}
and due <= ? limit ?)""",
            did, self.today, lim)

    def _resetRevCount(self):
        """Set revCount"""
        def cntFn(did, lim):
            """Number of review cards to see today for deck with id did. At most equal to lim."""
            return self.col.db.scalar(f"""
select count() from (select id from cards where
did = ? and queue = {QUEUE_REV} and due <= ? limit %d)""" % (lim),
                                      did, self.today)
        self.revCount = self._walkingCount(
            self._deckRevLimitSingle, cntFn)

    def _resetRev(self):
        super()._resetRev()
        self._revDids = self.col.decks.active()[:]

    def _fillRev(self):
        if self._revQueue:
            return True
        if not self.revCount:
            return False
        while self._revDids:
            did = self._revDids[0]
            lim = min(self.queueLimit, self._deckRevLimit(did))
            if lim:
                # fill the queue with the current did
                self._revQueue = self.col.db.list(f"""
select id from cards where
did = ? and queue = {QUEUE_REV} and due <= ? limit ?""",
                                                  did, self.today, lim)
                if self._revQueue:
                    # ordering
                    if self.col.decks.get(did).isDyn():
                        # dynamic decks need due order preserved
                        self._revQueue.reverse()
                    else:
                        # random order for regular reviews
                        rand = random.Random()
                        rand.seed(self.today)
                        rand.shuffle(self._revQueue)
                    # is the current did empty?
                    if len(self._revQueue) < lim:
                        self._revDids.pop(0)
                    return True
            # nothing left in the deck; move to next
            self._revDids.pop(0)
        if self.revCount:
            # if we didn't get a card but the count is non-zero,
            # we need to check again for any cards that were
            # removed from the queue but not buried
            self._resetRev()
            return self._fillRev()

    def _getRevCard(self):
        if self._fillRev():
            self.revCount -= 1
            return self.col.getCard(self._revQueue.pop())

    def totalRevForCurrentDeck(self):
        return self.col.db.scalar(
            """
select count() from cards where id in (
select id from cards where did in %s and queue = {QUEUE_REV} and due <= ? limit ?)"""
            % ids2str(self.col.decks.active()), self.today, self.reportLimit)

    # Answering a review card
    ##########################################################################

    def _answerRevCard(self, card, ease):
        """
        move the card out of filtered if required
        change the queue

        if not (filtered without rescheduling):
        change interval
        change due
        change factor
        change lapse if BUTTON_ONE

        log this review
        """
        delay = 0
        if ease == BUTTON_ONE:
            delay = self._rescheduleLapse(card)
        else:
            self._rescheduleRev(card, ease)
        self._logRev(card, ease, delay)

    def _rescheduleLapse(self, card):
        """
        The number of second for the delay until the next time the card can
        be reviewed. 0 if it should not be reviewed (because leech, or
        because conf['delays'] is empty)

        Called the first time we press "again" on a review card.


        Unless filtered without reschedule:
        lapse incread
        ivl changed
        factor decreased by 200
        due changed.

        if leech, suspend and return 0.

        card -- review card
        """

        conf = self._lapseConf(card)
        card.lastIvl = card.ivl
        if self._resched(card):
            card.lapses += 1
            card.ivl = self._nextLapseIvl(card, conf)
            card.factor = max(1300, card.factor-200)
            card.due = self.today + card.ivl
            # if it's a filtered deck, update odue as well
            if card.isFiltered():
                card.odue = card.due
        # if suspended as a leech, nothing to do
        delay = 0
        if self._checkLeech(card, conf) and card.queue == QUEUE_SUSPENDED:
            return delay#i.e. return 0
        # if no relearning steps, nothing to do
        if not conf['delays']:
            return delay#i.e. return 0
        # record rev due date for later
        if not card.odue:
            card.odue = card.due
        delay = self._delayForGrade(conf, 0)
        card.due = int(delay + time.time())
        #number of rev+1000*number of rev to do today
        card.left = self._startingLeft(card)
        # queue LRN
        if card.due < self.dayCutoff:
            self.lrnCount += card.left // 1000
            card.queue = QUEUE_LRN
            heappush(self._lrnQueue, (card.due, card.id))
        else:
            # day learn queue
            ahead = ((card.due - self.dayCutoff) // 86400) + 1
            card.due = self.today + ahead
            card.queue = QUEUE_DAY_LRN
        return delay

    def _nextLapseIvl(self, card, conf):
        return max(conf['minInt'], int(card.ivl*conf['mult']))

    def _rescheduleRev(self, card, ease):
        """Update the card according to review.

        If it's filtered, remove from filtered. If the filtered deck
        states not to update, nothing else is done.

        Change the interval. Change the due date. Change the factor.


        ease -- button pressed. Between 2 and 4
        card -- assumed to be in review mode

        """
        # update interval
        card.lastIvl = card.ivl
        if self._resched(card):
            self._updateRevIvl(card, ease)
            # then the rest
            card.factor = max(1300, card.factor+[-150, 0, 150][ease-2])
            card.due = self.today + card.ivl
        else:#Filtered without rescheduling
            card.due = card.odue
        if card.isFiltered():
            card.did = card.odid
            card.odid = 0
            card.odue = 0

    def _logRev(self, card, ease, delay):
        """Log this review. Retry once if failed.
        card -- a card object
        ease -- the button pressed
        delay -- if the answer is again, then the number of second until the next review
        """
        def log():
            self.col.db.execute(
                "insert into revlog values (?,?,?,?,?,?,?,?,?)",
                int(time.time()*1000), card.id, self.col.usn(), ease,
                -delay or card.ivl, card.lastIvl, card.factor, card.timeTaken(),
                1)
        try:
            log()
        except:
            # duplicate pk; retry in 10ms
            time.sleep(0.01)
            log()

    # Interval management
    ##########################################################################

    def _nextRevIvl(self, card, ease):
        """Ideal next interval for CARD, given EASE.

        Fuzzyness not applied.
        Cardds assumed to be a review card succesfully reviewed."""
        delay = self._daysLate(card)
        conf = self._revConf(card)
        fct = card.factor / 1000
        ivl2 = self._constrainedIvl((card.ivl + delay // 4) * 1.2, conf, card.ivl)
        ivl3 = self._constrainedIvl((card.ivl + delay // 2) * fct, conf, ivl2)
        ivl4 = self._constrainedIvl(
            (card.ivl + delay) * fct * conf['ease4'], conf, ivl3)
        if ease == BUTTON_TWO:
            interval = ivl2
        elif ease == BUTTON_THREE:
            interval = ivl3
        elif ease == BUTTON_FOUR:
            interval = ivl4
        # interval capped?
        return min(interval, conf['maxIvl'])

    def _constrainedIvl(self, ivl, conf, prev):
        """A new interval. Ivl multiplie by the interval
        factor of this conf. Greater than prev.
        """
        new = ivl * conf.get('ivlFct', 1)
        return int(max(new, prev+1))

    def _updateRevIvl(self, card, ease):
        """ Compute the next interval, fuzzy it, ensure ivl increase
        and is at most maxIvl.

        Card is assumed to be a review card."""
        idealIvl = self._nextRevIvl(card, ease)
        fuzzedIvl = self._adjRevIvl(card, idealIvl)
        increasedIvl = max(fuzzedIvl, card.ivl+1)
        card.ivl = min(increasedIvl, self._revConf(card)['maxIvl'])

    def _adjRevIvl(self, card, idealIvl):
        """Return an interval, similar to idealIvl, but randomized.
        See ../documentation/computing_intervals for the rule to
        generate this fuzziness.

        if _speadRev is to False (by an Add-on, I guess), it returns
        the input exactly.

        card is not used."""
        if self._spreadRev:
            idealIvl = self._fuzzedIvl(idealIvl)
        return idealIvl

    # Dynamic deck handling
    ##########################################################################

    def _fillDyn(self, deck):
        search, limit, order = deck['terms'][0]
        orderlimit = self._dynOrder(order, limit)
        if search.strip():
            search = "(%s)" % search
        search = "%s -is:suspended -is:buried -deck:filtered -is:learn" % search
        try:
            ids = self.col.findCards(search, order=orderlimit)
        except:
            ids = []
            return ids
        # move the cards over
        self.col.log(deck.getId(), ids)
        self._moveToDyn(deck.getId(), ids)
        return ids

    def emptyDyn(self, did, lim=None):
        """Moves cram cards to their deck
        Cards in learning mode move to their previous type.

        Keyword arguments:
        lim -- the query which decides which cards are used
        did -- assuming lim is not provided/false, the (filtered) deck concerned by this call
        """
        if not lim:
            lim = "did = %s" % did
        self.col.log(self.col.db.list("select id from cards where %s" % lim))
        # move out of cram queue
        self.col.db.execute(f"""
update cards set did = odid, queue = (case when type = {CARD_LRN} then {QUEUE_NEW}
else type end), type = (case when type = {CARD_LRN} then {CARD_NEW} else type end),
due = odue, odue = 0, odid = 0, usn = ? where %s""" % (lim),
                            self.col.usn())

    def _moveToDyn(self, did, ids):
        deck = self.col.decks.get(did)
        time = intTime(); usn = self.col.usn()
        # start at -100000 so that reviews are all due
        data = [(did, -100000+index, usn, id)
                for index, id in enumerate(ids)]
        # due reviews stay in the review queue. careful: can't use
        # "odid or did", as sqlite converts to boolean
        queue = f"""
(case when type={CARD_DUE} and (case when odue then odue <= %d else due <= %d end)
 then {QUEUE_REV} else {QUEUE_NEW} end)"""
        queue %= (self.today, self.today)
        self.col.db.executemany("""
update cards set
odid = (case when odid then odid else did end),
odue = (case when odue then odue else due end),
did = ?, queue = %s, due = ?, usn = ? where id = ?""" % queue, data)

    def _dynIvlBoost(self, card):
        """New interval for a review card in a dynamic interval.

        Maximum between old interval and
        elapsed*((card.factor/1000)+1.2)/2, with elapsed being the
        time between today and the last review.

        This number is constrained to be between 1 and the parameter
        ```maxIvl``` of the card's configuration.

        """
        assert card.isFiltered() and card.type == CARD_DUE
        assert card.factor
        lastReview = (card.odue - card.ivl)
        elapsed = self.today - lastReview
        factor = ((card.factor/1000)+1.2)/2
        ivl = int(max(card.ivl, elapsed * factor, 1))
        conf = self._revConf(card)
        return min(conf['maxIvl'], ivl)

    # Leeches
    ##########################################################################

    def _checkLeech(self, card, conf):
        """Leech handler. True if card was a leech.

        Potentially suspend the card if the deck config says so.  In
        this case, remove the card from filtered decks

        """
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
                # if it has an old due, remove it from cram/relearning
                if card.odue:
                    card.due = card.odue
                if card.isFiltered():
                    card.did = card.odid
                card.odue = card.odid = 0
                card.queue = QUEUE_SUSPENDED
            # notify UI
            runHook("leech", card)
            return True

    # Tools
    ##########################################################################

    def _delays(self, conf, oconf, type):
        if conf['delays']:
            r = conf['delays']
        else:
            r = oconf[type]['delays']
        return r

    def _resched(self, card):
        """Whether this review must be taken into account when this
        card to reschedule the card"""
        conf = card.currentConf()
        if not conf.isDyn():
            return True
        return conf['resched']

    # Daily cutoff
    ##########################################################################

    def _updateCutoff(self):
        """
        For each deck, set its entry *Today's first element to today's date
        if it's a new day:
        - log the new day
        - unbury new cards
        - change today and daycutoff
        """
        oldToday = self.today
        # days since col created
        self.today = int((time.time() - self.col.crt) // 86400)
        # end of day cutoff
        self.dayCutoff = self.col.crt + (self.today+1)*86400
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

    # Deck finished state
    ##########################################################################

    def haveBuried(self):
        return self.haveBuriedSiblings()

    # Next time reports
    ##########################################################################

    def nextIvl(self, card, ease):
        "Return the next interval for CARD, in seconds."
        if card.queue in (QUEUE_NEW, QUEUE_LRN, QUEUE_DAY_LRN):
            r = self._nextLrnIvl(card, ease)
            return r
        elif ease == BUTTON_ONE:
            # lapsed
            conf = self._lapseConf(card)
            if conf['delays']:
                return conf['delays'][0]*60
            r = self._nextLapseIvl(card, conf)*86400
            return r
        else:
            # review
            r = self._nextRevIvl(card, ease)*86400
            return r

    # this isn't easily extracted from the learn code
    def _nextLrnIvl(self, card, ease):
        if card.queue == QUEUE_NEW:
            card.left = self._startingLeft(card)
        conf = self._lrnConf(card)
        if ease == BUTTON_ONE:
            # fail
            return self._delayForGrade(conf, len(conf['delays']))
        elif ease == BUTTON_THREE:
            # early removal
            if not self._resched(card):
                return 0
            return self._graduatingIvl(card, conf, True, adj=False) * 86400
        else:
            left = card.left%1000 - 1
            if left <= 0:
                # graduate
                if not self._resched(card):
                    return 0
                return self._graduatingIvl(card, conf, False, adj=False) * 86400
            else:
                return self._delayForGrade(conf, left)

    # Suspending
    ##########################################################################

    def suspendCards(self, ids):
        "Suspend cards."
        self.col.log(ids)
        self.remFromDyn(ids)
        self.removeLrn(ids)
        self.col.db.execute(
            (f"update cards set queue={QUEUE_SUSPENDED},mod=?,usn=? where id in ")+
            ids2str(ids), intTime(), self.col.usn())

    def unsuspendCards(self, ids):
        "Unsuspend cards."
        self.col.log(ids)
        self.col.db.execute(
            (f"update cards set queue=type,mod=?,usn=? "
            f"where queue = {QUEUE_SUSPENDED} and id in ")+ ids2str(ids),
            intTime(), self.col.usn())

    def buryCards(self, cids):
        self.col.log(cids)
        self.remFromDyn(cids)
        self.removeLrn(cids)
        self.col.db.execute((f"""
        update cards set queue={QUEUE_SCHED_BURIED},mod=?,usn=? where id in """)+ids2str(cids),
                            intTime(), self.col.usn())

    # Sibling spacing
    ##########################################################################

    def _burySiblings(self, card):
        toBury = super()._burySiblings(card)
        # then bury
        if toBury:
            self.col.db.execute(
                (f"update cards set queue={QUEUE_SCHED_BURIED},mod=?,usn=? where id in ")+ids2str(toBury),
                intTime(), self.col.usn())
            self.col.log(toBury)
