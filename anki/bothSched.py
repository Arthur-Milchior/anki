# -*- coding: utf-8 -*-
# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

import time
import datetime
import random
import itertools
from operator import itemgetter
from heapq import *

#from anki.cards import Card
from anki.utils import ids2str, intTime, fmtTimeSpan
from anki.lang import _
from anki.consts import *
from anki.hooks import runHook

# it uses the following elements from anki.consts
# card types: 0=new, 1=lrn, 2=rev, 3=relrn
# queue types: 0=new, 1=(re)lrn, 2=rev, 3=day (re)lrn,
#   4=preview, -1=suspended, -2=sibling buried, -3=manually buried
# revlog types: 0=lrn, 1=rev, 2=relrn, 3=early review
# positive revlog intervals are in days (rev), negative in seconds (lrn)
# odue/odid store original due/did when cards moved to filtered deck

class BothScheduler:
    """
    today -- difference between the last time scheduler is seen and creation of the collection.
    dayCutoff -- The timestamp of when today end.
    reportLimit -- the maximal number to show in main windows
    lrnCount --  The number of cards in learning in selected decks
    revCount -- number of cards to review today in selected decks
    newCount -- number of new cards to see today in selected decks
    _lrnDids, _revDids, _newDids -- a copy of the set of active decks where decks with no card to see today are removed.
    _newQueue, _lrnQueue, _revQueue -- list of ids of cards in the queue new, lrn and rev. At most queue limit (i.e. 50)
    queueLimit -- maximum number of cards to queue simultaneously. Always 50 unless changed by an addon.
    _lrnDayQueue -- todo
    newCardModulus -- each card in position 0 Modulo newCardModulus is a new card. Or it is 0 if new cards are not mixed with reviews.
    -- _haveQueues -- whether the number of cards to see today for current decks have been set.
    """
    haveCustomStudy = True
    _spreadRev = True
    _burySiblingsOnAnswer = True

    def __init__(self, col):
        self.col = col
        self.queueLimit = 50
        self.reportLimit = 1000
        self.reps = 0
        self.today = None
        self._haveQueues = False
        self._updateCutoff()

    def getCard(self):
        "Pop the next card from the queue. None if finished."
        self._checkDay()
        if not self._haveQueues:
            self.reset()
        card = self._getCard()
        if card:
            self.col.log(card)
            if not self._burySiblingsOnAnswer:
                self._burySiblings(card)
            self.reps += 1
            card.startTimer()
            return card

    def reset(self):
        """
        Deal with the fact that it's potentially a new day.
        Reset number of learning, review, new cards according to current decks
        empty queues. Set haveQueues to true
        """
        self._updateCutoff()
        self._resetLrn()
        self._resetRev()
        self._resetNew()
        self._haveQueues = True

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
        for d in range(days):
            d = self.today+d
            if d not in daysd:
                daysd[d] = 0
        # return in sorted order
        ret = [x[1] for x in sorted(daysd.items())]
        return ret

    # Rev/lrn/time daily stats
    ##########################################################################

    def _updateStats(self, card, type, cnt=1):
        """Change the number of review/new/learn cards to see today in card's
        deck, and in all of its ancestors. The number of card to see
        is decreased by cnt.

        if type is time, it adds instead the time taken in this card
        to this decks and all of its ancestors.
        """
        key = type+"Today"
        for g in self.col.decks.parents(card.did, includeSelf=True):
            # add
            g[key][1] += cnt
            self.col.decks.save(g)

    def extendLimits(self, new, rev):
        """Decrease the limit of new/rev card to see today to this deck, its
        ancestors and all of its descendant, by new/rev.

        This number is called from aqt.customstudy.CustomStudy.accept, with the number of card to study today.
        """
        cur = self.col.decks.current()
        parents = self.col.decks.parents(cur['id'])
        children = self.col.decks.childrenDecks(cur['id'])
        for g in [cur] + parents + children:
            # add
            g['newToday'][1] -= new
            g['revToday'][1] -= rev
            self.col.decks.save(g)

    def _walkingCount(self, limFn=None, cntFn=None):
        """The sum of cntFn applied to each active deck.

        limFn -- function which associate to each deck obejct the maximum number of card to consider
        cntFn -- function which, given a deck id and a limit, return a number of card at most equal to this limit."""
        tot = 0
        pcounts = {}# Associate from each id of a parent deck p, the maximal number of cards of deck p which can be seen, minus the card found for its descendant already considered
        # for each of the active decks
        nameMap = self.col.decks.nameMap()
        for did in self.col.decks.active():
            # early alphas were setting the active ids as a str
            did = int(did)
            # get the individual deck's limit
            lim = limFn(self.col.decks.get(did))
            if not lim:
                continue
            # check the parents
            parents = self.col.decks.parents(did, nameMap)
            for p in parents:
                # add if missing
                if p['id'] not in pcounts:
                    pcounts[p['id']] = limFn(p)
                # take minimum of child and parent
                lim = min(pcounts[p['id']], lim)
            # see how many cards we actually have
            cnt = cntFn(did, lim)
            # if non-zero, decrement from parent counts
            for p in parents:
                pcounts[p['id']] -= cnt
            # we may also be a parent
            pcounts[did] = lim - cnt
            # and add to running total
            tot += cnt
        return tot

    # Deck list
    ##########################################################################

    def _groupChildren(self, grps):
        """[subdeck name without parent parts,
        did, rev, lrn, new (counting subdecks)
        [recursively the same things for the children]]

        Keyword arguments:
        grps -- [deckname, did, rev, lrn, new]
        """
        # first, split the group names into components
        for g in grps:
            g[0] = g[0].split("::")
        # and sort based on those components
        grps.sort(key=itemgetter(0))
        # then run main function
        return self._groupChildrenMain(grps)

    # New cards
    ##########################################################################

    def _resetNewCount(self):
        """Set newCount to the counter of new cards for the active decks."""
        # Number of card in deck did, at most lim
        def cntFn(did, lim):
            ret = self.col.db.scalar(f"""
select count() from (select 1 from cards where
did = ? and queue = {QUEUE_NEW_CRAM} limit ?)""", did, lim)
            return ret
        self.newCount = self._walkingCount(self._deckNewLimitSingle, cntFn)

    def _resetNew(self):
        """Set newCount, newDids, newCardModulus. Empty newQueue. """
        self._resetNewCount()
        self._newDids = self.col.decks.active()[:]
        self._newQueue = []
        self._updateNewCardRatio()

    def _fillNew(self):
        """Whether there are new card in current decks to see today.

        If it is the case that the _newQueue is not empty
        """
        if self._newQueue:
            return True
        if not self.newCount:
            return False
        while self._newDids:
            did = self._newDids[0]
            lim = min(self.queueLimit, self._deckNewLimit(did))
            if lim:
                # fill the queue with the current did
                self._newQueue = self.col.db.list(f"""
                select id from cards where did = ? and queue = {QUEUE_NEW_CRAM} order by due,ord limit ?""" , did, lim)
                if self._newQueue:
                    self._newQueue.reverse()
                    return True
            # nothing left in the deck; move to next
            self._newDids.pop(0)
        if self.newCount:
            # if we didn't get a card but the count is non-zero,
            # we need to check again for any cards that were
            # removed from the queue but not buried
            self._resetNew()
            return self._fillNew()

    def _getNewCard(self):
        if self._fillNew():
            self.newCount -= 1
            return self.col.getCard(self._newQueue.pop())

    def _updateNewCardRatio(self):
        """set newCardModulus so that new cards are regularly mixed with review cards. At least 2.
        Only if new and review should be mixed"""
        if self.col.conf['newSpread'] == NEW_CARDS_DISTRIBUTE:
            if self.newCount:
                self.newCardModulus = (
                    (self.newCount + self.revCount) // self.newCount)
                # if there are cards to review, ensure modulo >= 2
                if self.revCount:
                    self.newCardModulus = max(2, self.newCardModulus)
                return
        self.newCardModulus = 0

    def _timeForNewCard(self):
        "True if it's time to display a new card when distributing."
        if not self.newCount:
            return False
        if self.col.conf['newSpread'] == NEW_CARDS_LAST:
            return False
        elif self.col.conf['newSpread'] == NEW_CARDS_FIRST:
            return True
        elif self.newCardModulus:
            return self.reps and self.reps % self.newCardModulus == 0

    def _deckNewLimit(self, did, fn=None):
        if not fn:
            fn = self._deckNewLimitSingle
        lim = -1
        # for the deck and each of its parents
        for g in self.col.decks.parents(did, includeSelf=True):
            rem = fn(g)
            if lim == -1:
                lim = rem
            else:
                lim = min(rem, lim)
        return lim

    def _newForDeck(self, did, lim):
        """The minimum between the number of new cards in this deck lim and self.reportLimit.

        keyword arguments:
        did -- id of a deck
        lim -- an upper bound for the returned number (in practice, the number of new cards to see by day for the deck's option) """
        if not lim:
            return 0
        lim = min(lim, self.reportLimit)
        return self.col.db.scalar(f"""
select count() from
(select 1 from cards where did = ? and queue = {QUEUE_NEW_CRAM} limit ?)""", did, lim)

    def totalNewForCurrentDeck(self):
        return self.col.db.scalar(
            f"""
select count() from cards where id in (
select id from cards where did in %s and queue = {QUEUE_NEW_CRAM} limit ?)"""
            % ids2str(self.col.decks.active(), self.reportLimit))

    # New cards
    ##########################################################################

    def _deckNewLimitSingle(self, g):
        """Maximum number of new card to see today for deck g, not considering parent limit.

        If g is a dynamic deck, then reportLimit.
        Otherwise the number of card to see in this deck option, plus the number of card exceptionnaly added to this deck today.

        keyword arguments:
        g -- a deck dictionnary
        """
        if g['dyn']:
            return self.reportLimit
        c = self.col.decks.confForDid(g['id'])
        return max(0, c['new']['perDay'] - g['newToday'][1])

    # Learning queues
    ##########################################################################

    def _resetLrn(self):
        """Set lrnCount and _lrnDids. Empty _lrnQueue, lrnDayQueu."""
        self._resetLrnCount()
        self._lrnQueue = []
        self._lrnDayQueue = []
        self._lrnDids = self.col.decks.active()[:]

    # sub-day learning
    def _fillLrn(self, cutoff, queueIn):
        if not self.lrnCount:
            return False
        if self._lrnQueue:
            return True
        self._lrnQueue = self.col.db.all(f"""
select due, id from cards where
did in %s and queue in {queueIn} and due < :lim
limit %d""" % (self._deckLimit(), self.reportLimit), lim=self.dayCutoff)
        # as it arrives sorted by did first, we need to sort it
        self._lrnQueue.sort()
        return self._lrnQueue

    # daily learning
    def _fillLrnDay(self):
        if not self.lrnCount:
            return False
        if self._lrnDayQueue:
            return True
        while self._lrnDids:
            did = self._lrnDids[0]
            # fill the queue with the current did
            self._lrnDayQueue = self.col.db.list(f"""
select id from cards where
did = ? and queue = {QUEUE_DAY_LRN} and due <= ? limit ?""",
                                    did, self.today, self.queueLimit)
            if self._lrnDayQueue:
                # order
                r = random.Random()
                r.seed(self.today)
                r.shuffle(self._lrnDayQueue)
                # is the current did empty?
                if len(self._lrnDayQueue) < self.queueLimit:
                    self._lrnDids.pop(0)
                return True
            # nothing left in the deck; move to next
            self._lrnDids.pop(0)

    def _getLrnDayCard(self):
        if self._fillLrnDay():
            self.lrnCount -= 1
            return self.col.getCard(self._lrnDayQueue.pop())

    def _leftToday(self, delays, left, now=None):
        """The number of the last ```left``` steps that can be completed
        before the day cutoff. Assuming the first step is done
        ```now```.

        delays -- the list of delays
        left -- the number of step to consider (at the end of the
        list)
        now -- the time at which the first step is done.
        """
        if not now:
            now = intTime()
        delays = delays[-left:]
        ok = 0
        for i in range(len(delays)):
            now += delays[i]*60
            if now > self.dayCutoff:
                break
            ok = i
        return ok+1

    def _delayForGrade(self, conf, left):
        """The number of second for the delay until the next time the card can
        be reviewed. Assuming the number of left steps is left,
        according to configuration conf

        """
        left = left % 1000
        try:
            delay = conf['delays'][-left]
        except IndexError:
            if conf['delays']:
                delay = conf['delays'][0]
            else:
                # user deleted final step; use dummy value
                delay = 1
        return delay*60

    def _rescheduleNew(self, card, conf, early):
        """Reschedule a new card that's graduated for the first time.

        Set its factor according to conf.
        Set its interval. If it's lapsed in dynamic deck, use
        _dynIvlBoost.
        Otherwise, the interval is found in conf['ints'][1 if early
        else 0].
        Change due date according to the interval.
        Put initial factor.
        """
        card.ivl = self._graduatingIvl(card, conf, early)
        card.due = self.today+card.ivl
        card.factor = conf['initialFactor']

    def _logLrn(self, card, ease, conf, leaving, type, lastLeft):
        lastIvl = -(self._delayForGrade(conf, lastLeft))
        ivl = card.ivl if leaving else -(self._delayForGrade(conf, card.left))
        def log():
            self.col.db.execute(
                "insert into revlog values (?,?,?,?,?,?,?,?,?)",
                int(time.time()*1000), card.id, self.col.usn(), ease,
                ivl, lastIvl, card.factor, card.timeTaken(), type)
        try:
            log()
        except:
            # duplicate pk; retry in 10ms
            time.sleep(0.01)
            log()

    # Reviews
    ##########################################################################

    def _deckRevLimitSingle(self, d):
        """Maximum number of card to review today in deck d.

        self.reportLimit for dynamic deck. Otherwise the number of review according to deck option, plus the number of review added in custom study today.
        keyword arguments:
        d -- a deck object"""
        # invalid deck selected?
        if not d:
            return 0

        if d['dyn']:
            return self.reportLimit
        c = self.col.decks.confForDid(d['id'])
        return max(0, c['rev']['perDay'] - d['revToday'][1])

    def _resetRev(self):
        """Set revCount, empty _revQueue, _revDids"""
        self._resetRevCount()
        self._revQueue = []

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

    # Interval management
    ##########################################################################

    def _fuzzedIvl(self, ivl):
        """Return a randomly chosen number of day for the interval,
        not far from ivl.

        See ../documentation/computing_intervals for a clearer version
        of this documentation
        """
        min, max = self._fuzzIvlRange(ivl)
        return random.randint(min, max)

    def _fuzzIvlRange(self, ivl):
        """Return an increasing pair of numbers.  The new interval will be a
        number randomly selected between the first and the second
        element.

        See ../documentation/computing_intervals for a clearer version
        of this documentation

        """
        if ivl < 2:
            return [1, 1]
        elif ivl == 2:
            return [2, 3]
        elif ivl < 7:
            fuzz = int(ivl*0.25)
        elif ivl < 30:
            fuzz = max(2, int(ivl*0.15))
        else:
            fuzz = max(4, int(ivl*0.05))
        # fuzz at least a day
        fuzz = max(fuzz, 1)
        return [ivl-fuzz, ivl+fuzz]

    def _daysLate(self, card):
        "Number of days later than scheduled."
        due = card.odue if card.odid else card.due
        return max(0, self.today - due)

    # Dynamic deck handling
    ##########################################################################

    def rebuildDyn(self, did=None):
        "Rebuild a dynamic deck."
        did = did or self.col.decks.selected()
        deck = self.col.decks.get(did)
        assert deck['dyn']
        # move any existing cards back first, then fill
        self.emptyDyn(did)
        ids = self._fillDyn(deck)
        if not ids:
            return
        # and change to our new deck
        self.col.decks.select(did)
        return ids

    def remFromDyn(self, cids):
        self.emptyDyn(None, "id in %s and odid" % ids2str(cids))

    def _dynOrder(self, o, l):
        if o == DYN_OLDEST:
            t = "(select max(id) from revlog where cid=c.id)"
        elif o == DYN_RANDOM:
            t = "random()"
        elif o == DYN_SMALLINT:
            t = "ivl"
        elif o == DYN_BIGINT:
            t = "ivl desc"
        elif o == DYN_LAPSES:
            t = "lapses desc"
        elif o == DYN_ADDED:
            t = "n.id"
        elif o == DYN_REVADDED:
            t = "n.id desc"
        elif o == DYN_DUE:
            t = "c.due"
        elif o == DYN_DUEPRIORITY:
            t = f"(case when queue={QUEUE_REV} and due <= %d then (ivl / cast(%d-due+0.001 as real)) else 100000+due end)" % (self.today, self.today)
        else:
            # if we don't understand the term, default to due order
            t = "c.due"
        return t + " limit %d" % l


    # Tools
    ##########################################################################

    def _cardConf(self, card):
        """The configuration of this card's deck. See decks.py
        documentation to read more about them."""
        return self.col.decks.confForDid(card.did)

    def _newConf(self, card):
        """The configuration for "new" of this card's deck.See decks.py
        documentation to read more about them.

        """
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
            delays=self._delays(conf, oconf, "new"),
            # overrides
            separate=conf['separate'],
            order=NEW_CARDS_DUE,
            perDay=self.reportLimit
        )

    def _lapseConf(self, card):
        """The configuration for "lapse" of this card's deck.See decks.py
        documentation to read more about them.

        """
        conf = self._cardConf(card)
        # normal deck
        if not card.odid:
            return conf['lapse']
        # dynamic deck; override some attributes, use original deck for others
        oconf = self.col.decks.confForDid(card.odid)
        delays = self._delays(conf, oconf, "lapse")
        return dict(
            # original deck
            minInt=oconf['lapse']['minInt'],
            leechFails=oconf['lapse']['leechFails'],
            leechAction=oconf['lapse']['leechAction'],
            mult=oconf['lapse']['mult'],
            delays=delays,
            # overrides
            resched=conf['resched'],
        )

    def _revConf(self, card):
        """The configuration for "review" of this card's deck.See decks.py
        documentation to read more about them.

        """
        conf = self._cardConf(card)
        # normal deck
        if not card.odid:
            return conf['rev']
        # dynamic deck
        return self.col.decks.confForDid(card.odid)['rev']

    def _deckLimit(self):
        """The list of active decks, as comma separated parenthesized
        string"""
        return ids2str(self.col.decks.active())

    # Daily cutoff
    ##########################################################################

    def _checkDay(self):
        # check if the day has rolled over
        if time.time() > self.dayCutoff:
            self.reset()

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
            (f"select 1 from cards where did in %s and queue = {QUEUE_NEW_CRAM} "
             "limit 1") % (self._deckLimit(),))

    def haveBuriedSiblings(self):
        sdids = ids2str(self.col.decks.active())
        cnt = self.col.db.scalar(
            f"select 1 from cards where queue = {QUEUE_USER_BURIED} and did in %s limit 1" % (sdids))
        return not not cnt

    # Next time reports
    ##########################################################################

    def nextIvlStr(self, card, ease, short=False):
        "Return the next interval for CARD as a string."
        ivl = self.nextIvl(card, ease)
        if not ivl:
            return _("(end)")
        s = fmtTimeSpan(ivl, short=short)
        if ivl < self.col.conf['collapseTime']:
            s = "<"+s
        return s

    # Suspending
    ##########################################################################

    def buryNote(self, nid):
        "Bury all cards for note until next session."
        cids = self.col.db.list(
            "select id from cards where nid = ? and queue >= 0", nid)
        self.buryCards(cids)

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
and (queue={QUEUE_NEW_CRAM} or (queue={QUEUE_REV} and due<=?))""",
                card.nid, card.id, self.today):
            if queue == QUEUE_REV:
                if buryRev:
                    toBury.append(cid)
                # if bury disabled, we still discard to give same-day spacing
                try:
                    self._revQueue.remove(cid)
                except ValueError:
                    pass
            else:#Queue new Cram
                # if bury disabled, we still discard to give same-day spacing
                if buryNew:
                    toBury.append(cid)
                try:
                    self._newQueue.remove(cid)
                except ValueError:
                    pass
        # burying is done by the concrete class
        return toBury

    # Resetting
    ##########################################################################

    def forgetCards(self, ids):
        "Put cards at the end of the new queue."
        self.remFromDyn(ids)
        self.col.db.execute(
            (f"update cards set type={CARD_NEW},queue={QUEUE_NEW_CRAM},ivl=0,due=0,odue=0,factor=?"
             " where id in ")+ids2str(ids), STARTING_FACTOR)
        pmax = self.col.db.scalar(
            f"select max(due) from cards where type={CARD_NEW}") or 0
        # takes care of mod + usn
        self.sortCards(ids, start=pmax+1)
        self.col.log(ids)

    def reschedCards(self, ids, imin, imax):
        "Put cards in review queue with a new interval in days (min, max)."
        d = []
        t = self.today
        mod = intTime()
        for id in ids:
            r = random.randint(imin, imax)
            d.append(dict(id=id, due=r+t, ivl=max(1, r), mod=mod,
                          usn=self.col.usn(), fact=STARTING_FACTOR))
        self.remFromDyn(ids)
        self.col.db.executemany(f"""
update cards set type={CARD_DUE},queue={QUEUE_REV},ivl=:ivl,due=:due,odue=0,
usn=:usn,mod=:mod,factor=:fact where id=:id""",
                                d)
        self.col.log(ids)

    def resetCards(self, ids):
        "Completely reset cards for export."
        sids = ids2str(ids)
        # we want to avoid resetting due number of existing new cards on export
        nonNew = self.col.db.list(
            f"select id from cards where id in %s and (queue != {QUEUE_NEW_CRAM} or type != {CARD_NEW})"
            % sids)
        # reset all cards
        self.col.db.execute(
            f"update cards set reps=0,lapses=0,odid=0,odue=0,queue={QUEUE_NEW_CRAM}"
            " where id in %s" % sids
        )
        # and forget any non-new cards, changing their due numbers
        self.forgetCards(nonNew)
        self.col.log(ids)

    # Repositioning new cards
    ##########################################################################

    def sortCards(self, cids, start=1, step=1, shuffle=False, shift=False):
        """Change the due of new cards in `cids`.

        Each card of the same note have the same due. The order of the
        due is random if shuffle. Otherwise the order of the note `n` is
        similar to the order of the first occurrence of a card of `n` in cids.

        Keyword arguments:
        cids -- list of card ids to reorder (i.e. change due). Not new cards are ignored
        start -- the first due to use
        step -- the difference between to successive due of notes
        shuffle -- whether to shuffle the note. By default, the order is similar to the created order
        shift -- whether to change the due of all new cards whose due is greater than start (to ensure that the new due of cards in cids is not already used)

        """
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
        for c, nid in enumerate(nids):
            due[nid] = start+c*step
        # pylint: disable=undefined-loop-variable
        high = start+c*step #Highest due which will be used
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
and due >= ? and queue = {QUEUE_NEW_CRAM}""" % scids, now, self.col.usn(), shiftby, low)
        # reorder cards
        d = []
        for id, nid in self.col.db.execute(
            (f"select id, nid from cards where type = {CARD_NEW} and id in ")+scids):
            d.append(dict(now=now, due=due[nid], usn=self.col.usn(), cid=id))
        self.col.db.executemany(
            "update cards set due=:due,mod=:now,usn=:usn where id = :cid", d)

    def randomizeCards(self, did):
        """Change the due value of new cards of deck `did`. The new due value
        is the same for every card of a note (as long as they are in the same
        deck.)"""
        cids = self.col.db.list("select id from cards where did = ?", did)
        self.sortCards(cids, shuffle=True)

    def orderCards(self, did):
        """Change the due value of new cards of deck `did`. The new due value
        is the same for every card of a note (as long as they are in the
        same deck.)

        The note are now ordered according to the smallest id of their
        cards. It generally means they are ordered according to date
        creation.
        """
        cids = self.col.db.list("select id from cards where did = ? order by id", did)
        self.sortCards(cids)

    def resortConf(self, conf):
        """When a deck configuration's order of new card is changed, apply
        this change to each deck having the same deck configuration."""
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
