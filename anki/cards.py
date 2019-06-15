# -*- coding: utf-8 -*-
# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
import pprint
import time

from anki.consts import *
from anki.hooks import runHook
from anki.utils import intTime, joinFields, timestampID

# Cards
##########################################################################

class Card:

    """
    Cards are what you review.
    There can be multiple cards for each note, as determined by the Template.

    id -- the epoch milliseconds of when the card was created
    nid -- The card's note's id
    did -- The card's deck id
    ord -- ordinal : identifies which of the card templates it corresponds to
    valid values are from 0 to num templates - 1
    mod -- modificaton time as epoch seconds
    usn -- update sequence number : see README.synchronization
    type -- -- 0=new, 1=learning, 2=due, 3=filtered. Only for cards
    queue --
         -- QUEUE_SCHED_BURIED: card buried by scheduler, -3
         -- QUEUE_USER_BURIED: card buried by user, -2
         -- QUEUE_SUSPENDED: Card suspended, -1
         -- QUEUE_NEW: new card,  0
         -- QUEUE_LRN: cards in learning, which should be seen again today, 1
         -- QUEUE_REV: cards already learned, 2
         -- QUEUE_DAY_LRN: cards in learning but won't be seen today again, 3
         -- QUEUE_PREVIEW: cards for the preview mode, sched 2 :4
    due -- Due is used differently for different card types:
        --   new: note id or random int.
                  Allow to select in which order new cards are seens.
        --   due: integer day in which the card is due for the next time,
                  relative to the collection's creation time
        --   learning: integer timestamp of when the next review is due
    ivl -- interval (used in SRS algorithm). Negative = seconds, positive = days
    factor -- easyness factor (used in SRS algorithm)
    reps -- number of reviews to do
    lapses -- the number of times the card went from a "was answered correctly"
           --   to "was answered incorrectly" state
    left
      -- of the form a*1000+b, with:
      -- b the number of reps left till graduation
      -- a the number of reps left today
    odue -- original due: only used when the card is currently in filtered deck
    odid -- original did: only used when the card is currently in filtered deck
    flags -- an integer. This integer mod 8 represents a "flag", which can be see in browser and while reviewing a note. Red 1, Orange 2, Green 3, Blue 4, no flag: 0. This integer divided by 8 represents currently nothing
    data -- currently unused

    Values not in the database:
    col -- its collection
    timerStarted -- The time at which the timer started
    _qa -- the dictionnary whose element q and a are questions and answers html
    _note -- the note object of the card
    wasNew --
    """

    def __init__(self, col, id=None):
        """
        This function returns a card object from the collection given in argument.

        If an id is given, then the card is the one with this id from the collection.
        Otherwise a new card, assumed to be from this collection, is created.

        Keyword arguments:
        col -- a collection
        id -- an identifier of a card. Int.
        """
        self.col = col
        self.timerStarted = None
        self._qa = None
        self._note = None
        if id:
            self.id = id
            self.load()
        else:
            # to flush, set nid, ord, and due
            self.id = timestampID(col.db, "cards")
            self.did = 1
            self.crt = intTime()
            self.type = CARD_NEW
            self.queue = QUEUE_NEW
            self.ivl = 0
            self.factor = 0
            self.reps = 0
            self.lapses = 0
            self.left = 0
            self.odue = 0
            self.odid = 0
            self.flags = 0
            self.data = ""

    def load(self):
        """
        Given a card, complete it with the information extracted from the database.

        It is assumed that the card's id and col are already known."""
        (self.id,
         self.nid,
         self.did,
         self.ord,
         self.mod,
         self.usn,
         self.type,
         self.queue,
         self.due,
         self.ivl,
         self.factor,
         self.reps,
         self.lapses,
         self.left,
         self.odue,
         self.odid,
         self.flags,
         self.data) = self.col.db.first(
             "select * from cards where id = ?", self.id)
        self._qa = None
        self._note = None

    def flush(self):
        """Insert the card into the database.

        If the cards is already in the database, it is replaced,
        otherwise it is created."""
        self.mod = intTime()
        self.usn = self.col.usn()
        # bug check
        if self.queue == QUEUE_REV and self.odue and not self.col.decks.isDyn(self.did):
            runHook("odueInvalid")
        assert self.due < 4294967296
        self.col.db.execute(
            """
insert or replace into cards values
(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            self.id,
            self.nid,
            self.did,
            self.ord,
            self.mod,
            self.usn,
            self.type,
            self.queue,
            self.due,
            self.ivl,
            self.factor,
            self.reps,
            self.lapses,
            self.left,
            self.odue,
            self.odid,
            self.flags,
            self.data)
        self.col.log(self)

    def flushSched(self):
        """Update the card into the database.

        This card is supposed to already
        exists in the db."""
        self.mod = intTime()
        self.usn = self.col.usn()
        # bug checks
        if self.queue == QUEUE_REV and self.odue and not self.col.decks.isDyn(self.did):
            runHook("odueInvalid")
        assert self.due < 4294967296
        self.col.db.execute(
            """update cards set
mod=?, usn=?, type=?, queue=?, due=?, ivl=?, factor=?, reps=?,
lapses=?, left=?, odue=?, odid=?, did=? where id = ?""",
            self.mod,
            self.usn,
            self.type,
            self.queue,
            self.due,
            self.ivl,
            self.factor,
            self.reps,
            self.lapses,
            self.left,
            self.odue,
            self.odid,
            self.did,
            self.id)
        self.col.log(self)

    def q(self, reload=False, browser=False):
        """The card question with its css.

        Keyword arguments:
        reload -- whether the card should be reloaded even if it is already known
        browser -- whether its called from the browser (in which case the format strings are
        bqfmt and not qfmt)
        """
        return self.css() + self._getQA(reload, browser)['q']

    def a(self):
        """Return the card answer with its css"""
        return self.css() + self._getQA()['a']

    def css(self):
        """Return the css of the card's model, as html code"""
        return "<style>%s</style>" % self.model()['css']

    def _getQA(self, reload=False, browser=False):
        """The QA dictionnary of the card. This dictionnary is added to the card.

        If the QA dictionnary already exists and reload is not set to true, it is directly returned.

        Keyword arguments:
        browser -- ???TODO
        """
        if not self._qa or reload:
            note = self.note(reload)
            model = self.model()
            template = self.template()
            data = [self.id, note.id, model['id'], self.odid or self.did, self.ord,
                    note.stringTags(), note.joinedFields(), self.flags]
            if browser:
                args = (template.get('bqfmt'), template.get('bafmt'))
            else:
                args = tuple()
            self._qa = self.col._renderQA(data, *args)
        return self._qa

    def note(self, reload=False):
        """The note object of the card.

        If the cards already knows its object, and reload is not true,
        this object is used.
        """
        if not self._note or reload:
            self._note = self.col.getNote(self.nid)
        return self._note

    def model(self):
        """The card's note's model (note type) object. This object is
        described in models.py."""
        return self.col.models.get(self.note().mid)

    def template(self):
        """The card's template object. See models.py for a comment of this
        object."""
        model = self.model()
        if model['type'] == MODEL_STD:
            return self.model()['tmpls'][self.ord]
        else: #In case of cloze
            return self.model()['tmpls'][0]

    def startTimer(self):
        """Start the timer of the card"""
        self.timerStarted = time.time()

    def timeLimit(self):
        """Time limit for answering in milliseconds.

        According to the deck's information."""
        conf = self.col.decks.confForDid(self.odid or self.did)
        return conf['maxTaken']*1000

    def shouldShowTimer(self):
        """Whether timer should be shown.

        According to the deck's information."""
        conf = self.col.decks.confForDid(self.odid or self.did)
        return conf['timer']

    def timeTaken(self):
        "Time taken to answer card, in integer MS."
        total = int((time.time() - self.timerStarted)*1000)
        return min(total, self.timeLimit())

    def isEmpty(self):
        """TODO"""
        ords = self.col.models.availOrds(
            self.model(), joinFields(self.note().fields))
        if self.ord not in ords:
            return True

    def __repr__(self):
        values = dict(self.__dict__)
        # remove non-useful elements
        del values['_note']
        del values['_qa']
        del values['col']
        del values['timerStarted']
        return pprint.pformat(values, width=300)

    def userFlag(self):
        return self.flags & 0b111

    def setUserFlag(self, flag):
        assert 0 <= flag <= 7
        self.flags = (self.flags & ~0b111) | flag
