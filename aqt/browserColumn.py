from anki.lang import _
import time
from anki.utils import htmlToTextLine
from anki.consts import *

class BrowserColumn(str):
    """
    type -- the internal name of the column
    name -- the localized name of the column
    noSort -- whether the column can't be sorted
    hide -- whether the column should not be shown (a column of type unknown)
    """
    typeToObject = dict()

    def __init_subclass__(self, type, name, noSort=False, hide=False):
        self.type = type
        self.name = _(name)
        self.noSort = noSort
        self.typeToObject[type] = self()
        self.hide = hide

    @staticmethod
    def content(card, col):
        #col here is column and not collection
        """card -- The card considered
        col -- the collection"""
        raise Exception("You should inherit from BrowserColumn and not use it directly")

    def __eq__(self, other):
        if isinstance(other, BrowserColumn):
            b = self.type == other.type
        else:
            b = self.type == other
        return b

    def __str__(self):
        t= _("Browser's column: %s") % self.name
        if self.hide:
            t+= _(" (unknown)")
        return t

class noteFldColumn(BrowserColumn, type="noteFld", name="Sort Field"):

    @staticmethod
    def content(card, col):
        """The content of the sorting field, on a single line."""
        f = card.note()
        model = f.model()
        sortIdx = col.models.sortIdx(model)
        sortField = f.fields[sortIdx]
        return htmlToTextLine(sortField)

class templateColumn(BrowserColumn, type="template", name="Card", noSort=True):

    @staticmethod
    def content(card, col):
        """Name of the card type. With its number if it's a cloze card"""
        t = card.template()['name']
        if card.model()['type'] == MODEL_CLOZE:
            t += " %d" % (card.ord+1)
        return t

class cardDueColumn(BrowserColumn, type="cardDue", name="Due"):

    @staticmethod
    def content(card, col):
        """
        The content of the 'due' column in the browser.
        * (filtered) if the card is in a filtered deck
        * the due integer if the card is new
        * the due date if the card is in learning or review mode.

        Parenthesis if suspended or buried
        """
        # catch invalid dates
        t = ""
        if card.odid:
            t = _("(filtered)")
        elif card.queue == QUEUE_NEW_CRAM or card.type == CARD_NEW:
            t = str(card.due)
        else:
            date = None
            if card.queue == QUEUE_LRN:
                date = card.due
            if card.queue in (QUEUE_REV, QUEUE_DAY_LRN) or (card.type == CARD_DUE and
                                                            card.queue < 0#suspended or buried
            ):
                date = time.time() + ((card.due - col.sched.today)*86400)
            if date:
                t = time.strftime("%Y-%m-%d", time.localtime(date))
        if card.queue < 0:#supsended or buried
            t = "(" + t + ")"
        return t

class noteCrtColumn(BrowserColumn, type="noteCrt", name="Created"):

    @staticmethod
    def content(card, col):
        """Date at wich the card's note was created"""
        return time.strftime("%Y-%m-%d", time.localtime(card.note().id/1000))

class noteModColumn(BrowserColumn, type="noteMod", name="Edited"):

    @staticmethod
    def content(card, col):
        """Date at wich the card's note was last modified"""
        return time.strftime("%Y-%m-%d", time.localtime(card.note().mod))

class cardModColumn(BrowserColumn, type="cardMod", name="Changed"):

    @staticmethod
    def content(card, col):
        """Date at wich the card note was last modified"""
        return time.strftime("%Y-%m-%d", time.localtime(card.mod))

class cardRepsColumn(BrowserColumn, type="cardReps", name="Reviews"):

    @staticmethod
    def content(card, col):
        """Number of reviews to do"""
        return str(card.reps)

class cardLaspsesColumn(BrowserColumn, type="cardLaspses", name="Lapses"):

    @staticmethod
    def content(card, col):
        """Number of times the card lapsed"""
        return str(card.lapses)

class noteTagsColumn(BrowserColumn, type="noteTags", name="Tags", noSort=True):

    @staticmethod
    def content(card, col):
        """The list of tags for this card's note."""
        return " ".join(card.note().tags)

class noteColumn(BrowserColumn, type="note", name="Note", noSort=True):

    @staticmethod
    def content(card, col):
        """The name of the card's note's type"""
        return card.model()['name']

class cardIvlColumn(BrowserColumn, type="cardIvl", name="Interval"):

    @staticmethod
    def content(card, col):
        """Whether card is new, in learning, or some representation of the
        interval as a number of days."""
        if card.type == 0:
            return _("(new)")
        elif card.type == 1:
            return _("(learning)")
        return fmtTimeSpan(card.ivl*86400)

class cardEaseColumn(BrowserColumn, type="cardEase", name="Ease"):

    @staticmethod
    def content(card, col):
        """Either (new) or the ease fo the card as a percentage."""
        if card.type == 0:
            return _("(new)")
        return "%d%%" % (card.factor/10)

class deckColumn(BrowserColumn, type="deck", name="Deck", noSort=True):

    @staticmethod
    def content(card, col):
        """Name of the card's deck (with original deck in parenthesis if there
        is one)

        """
        if card.odid:
            # in a cram deck
            return "%s (%s)" % (
                col.decks.name(card.did),
                col.decks.name(card.odid))
        # normal deck
        return col.decks.name(card.did)

class questionColumn(BrowserColumn, type="question", name="Question", noSort=True):

    @staticmethod
    def content(card, *args, **kwargs):
        # args because this allow content to be equal to question
        return htmlToTextLine(card.q(browser=True))

class answerColumn(BrowserColumn, type="answer", name="Answer", noSort=True):

    @staticmethod
    def content(card, *args, **kwargs):
        """The answer side on a single line.

        Either bafmt if it is defined. Otherwise normal answer,
        removing the question if it starts with it.
        """
        # args because this allow questionContent to be equal to question
        if card.template().get('bafmt'):
            # they have provided a template, use it verbatim
            card.q(browser=True)
            return htmlToTextLine(card.a())
        # need to strip question from answer
        q = htmlToTextLine(card.q(browser=True))
        a = htmlToTextLine(card.a())
        if a.startswith(q):
            return a[len(q):].strip()
        return a

class UnknownColumn(BrowserColumn, type="Unknown", name="Unknown", hide=True):
    def __init__(self, type="Unknown"):
        self.type = type
        self.name = _(type)
