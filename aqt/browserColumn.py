import time

from anki.consts import *
from anki.lang import _
from anki.utils import fmtTimeSpan, htmlToTextLine


class BrowserColumn:
    """A subclass represents a potential column of the browser. The
    instance has no interest, and thus only one is created when the
    subclass is created.

    hide -- whether the column should not be shown (a column of type unknown)
    type -- The internal name of the column
    name -- the localized name of the column
    content -- a method which, given a card and a collection, return a string in order to display this card in this column.
    sort -- returns the ORDER BY clause of the query in order to correctly sort
    the column. The ORDER BY clause has access to tables "c" and
    "n" for cards and notes, respectively.

    Return None if it can't be sorted"""

    def __init__(self, type, name, content, hide=False, sort=None, menu=[], description=None):
        self.type = type
        self.name = _(name)
        self.hide = hide
        self.sort = sort
        self.content = content
        self.menu = menu
        self.description = description

    def __eq__(self, other):
        if isinstance(other, BrowserColumn):
            b = self.type == other.type
        else:
            b = self.type == other
        return b

    def __repr__(self):
        """A string telling the column's name, for debugging only"""
        t= _("Browser's column: %s") % self.name
        if self.hide:
            t += _(" (hidden)")
        return t

    def show(self, browser):
        """Whether this column should be shown.

        It may not be the case either if the column should be hidden,
        or if other feature developped later requires it.

        """
        if (self.hide
        ):
            return False
        return True

    def showAsPotential(self, browser):
        """Whether this column existence should be shown as something we can
        potentially use, depending on the features.

        While .show corresponds to what we consider in current mode,
        this consider what can be shown in any mode.
        """

        if (self.hide
        ):
            return False
        return True

def cardDueContent(card, browser):
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
            date = time.time() + ((card.due - browser.col.sched.today)*86400)
        if date:
            t = time.strftime("%Y-%m-%d", time.localtime(date))
    if card.queue < 0:#supsended or buried
        t = "(" + t + ")"
    return t

basicColumns = [
BrowserColumn(
    type="noteFld",
    name="Sort Field",
    content=(lambda card, browser: htmlToTextLine(card.note().getSField())),
    sort="n.sfld collate nocase, c.ord",
    menu=["Note"],
),

BrowserColumn(
    type="template",
    name="Card",
    content=lambda card, browser: card.templateName() + (f" {card.ord+1}" if card.model()['type'] == MODEL_CLOZE else ""),
    menu=["Card"],
    sort="nameByMidOrd(n.mid, c.ord)",
),

BrowserColumn(
    type="cardDue",
    name="Due",
    content=cardDueContent,
    sort="c.type, c.due",
    menu=["Card"],
),

BrowserColumn(
    type="noteCrt",
    name="Created",
    content=lambda card, browser: time.strftime("%Y-%m-%d", time.localtime(card.note().id/1000)),
    sort="n.id, c.ord",
    menu=["Note"],
    description="""Date at wich the card's note was created""",
),

BrowserColumn(
    type="noteMod",
    name="Edited",
    content=lambda card, browser: time.strftime("%Y-%m-%d", time.localtime(card.note().mod)),
    sort="n.mod, c.ord",
    menu=["Note"],
    description="""Date at wich the card's note was last modified""",
),

BrowserColumn(
    type="cardMod",
    name="Changed",
    content=lambda card, browser: time.strftime("%Y-%m-%d", time.localtime(card.mod)),
    sort="c.mod",
    menu=["Card"],
    description="""Date at wich the card note was last modified""",
),

BrowserColumn(
    type="cardReps",
    name="Reviews",
    content=lambda card, browser: str(card.reps),
    sort="c.reps",
    menu=["Card"],
    description="""Number of reviews to do""",
),

BrowserColumn(
    type="cardLapses",
    name="Lapses",
    content=lambda card, browser: str(card.lapses),
    sort="c.lapses",
    menu=["Card"],
    description="""Number of times the card lapsed""",
),

BrowserColumn(
    type="noteTags",
    name="Tags",
    content=lambda card, browser: " ".join(card.note().tags),
    menu=["Note"],
    description="""The list of tags for this card's note.""",
    sort="n.tags",
),

BrowserColumn(
    type="note",
    name="Note",
    content=lambda card, browser: card.model()['name'],
    menu=["Note"],
    description="""The name of the card's note's type""",
    sort="nameByMid(n.mid)",
),

BrowserColumn(
    type="cardIvl",
    name="Interval",
    content=lambda card, browser: {0: _("(new)"), 1:_("(learning)")}.get(card.type, fmtTimeSpan(card.ivl*86400)),
    sort="c.ivl",
    menu=["Card"],
    description="""Whether card is new, in learning, or some representation of the
interval as a number of days.""",
),

BrowserColumn(
    type="cardEase",
    name="Ease",
    content=lambda card, browser:_("(new)") if card.type == CARD_NEW else  f"{card.factor/10}%",
    sort=f"c.type == {CARD_NEW}, c.factor",
    menu=["Card"],
    description="""Either (new) or the ease fo the card as a percentage.""",
),

BrowserColumn(
    type="deck",
    name="Deck",
    content=lambda card, browser: f"{browser.col.decks.name(card.did)} ({browser.col.decks.name(card.odid)})" if card.odid else browser.col.decks.name(card.did),
    menu=["Card"],
    description="""Name of the card's deck (with original deck in parenthesis if there
is one)""",
    sort="nameForDeck(c.did)",
),

BrowserColumn(
    type="question",
    name="Question",
    content=lambda card, browser: htmlToTextLine(card.q(browser=True)),
    menu=["Card"],
    sort="questionContentByCid(c.id)"
),

BrowserColumn(
    type="answer",
    name="Answer",
    content=lambda card, browser: card.answerContent(),
    menu=["Card"],
    sort="answerContentByCid(c.id)"
),
]

def unknownContent(card, browser):
    raise Exception("You should inherit from BrowserColumn and not use it directly from unknown")

def unknownColumn(type):
    return BrowserColumn(
        type=type,
        name=_("Unknown")+" "+type,
        hide=True,
        content=unknownContent,
        menu=["Note"],
)

class ColumnList(list):
    """Similar to list, but allow to check whether a column belongs to the list by giving its type"""
    def index(self, type):
        for idx, column in enumerate(self):
            if column.type == type:
                return idx
        raise ValueError

    def __contains__(self, type):
        for idx, column in enumerate(self):
            if column.type == type:
                return True
        return False

def fieldColumn(fieldName, model, dataModel):
    return BrowserColumn(
        type = f"_field_{fieldName}",
        name = fieldName,
        content = lambda card, browser:  card.note().get(fieldName, ""),
        menu = ["Fields"] if dataModel.fieldsTogether else ["Fields", model['name']],
    )
