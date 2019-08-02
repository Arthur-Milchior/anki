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

    def __init__(self, type, name, content, hide=False, sort=None, menu=[], advanced=False, description=None):
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

# Columns from Advanced Browser
##############################
def timeFmt(tm):
    # stole this from anki.stats.CardStats#time()
    str = ""
    if tm is None:
        return str
    if tm >= 60:
        str = fmtTimeSpan((tm / 60) * 60, short=True, point=-1, unit=1)
    if tm % 60 != 0 or not str:
        str += fmtTimeSpan(tm % 60, point=2 if not str else -1, short=True)
    return str

def strftimeIfArgument(timeString):
    if timeString:
        return time.strftime("%Y-%m-%d", time.localtime(timeString / 1000))
    else:
        return ""

def overdueSort():
    from aqt import mw #todo: find a way to take collection without using mw, if possible without transforming sort into a function.
    return f"""
(select
  (case
    when odid then ""
    when queue =1 then ""
    when queue = 0 then ""
    when type=0 then "",
    when due<{mw.col.sched.today} and (queue in (2, 3) or (type=2 and queue<0)),
    then {mw.col.sched.today}-due
    else ""
  end)
  from cards where id = c.id)"""

def overdueContent(card, col):
    if card.odid or card.queue == QUEUE_LRN:
        return
    elif card.queue == QUEUE_NEW_CRAM or card.type == CARD_NEW:
        return
    elif card.queue in (QUEUE_REV, QUEUE_DAY_LRN) or (card.type == CARD_DUE and card.queue < 0):
        lateness = col.sched.today - card.due
        if lateness > 0 :
            return f"{lateness} day{'s' if lateness > 1 else ''}"
        else:
            return

def previewContent(card, col):
    ivl = col.db.scalar(
        "select ivl from revlog where cid = ? "
        "order by id desc limit 1 offset 1", card.id)
    if ivl is None:
        return
    elif ivl == 0:
        return "0 days"
    elif ivl > 0:
        return fmtTimeSpan(ivl*86400)
    else:
        return timeFmt(-ivl)

advancedColumns = [
BrowserColumn(
    # First review
    type='cfirst',
    name='First Review',
    content=lambda card,browser : strftimeIfArgument(browser.col.db.scalar("select min(id) from revlog where cid = ?", card.id)),
    sort="(select min(id) from revlog where cid = c.id)",
    menu=["Card"],
),

BrowserColumn(
    # Last review
    type='clast',
    name='Last Review',
    content=lambda card,browser :strftimeIfArgument(browser.col.db.scalar(
            "select max(id) from revlog where cid = ?", card.id)),
    sort="(select max(id) from revlog where cid = c.id)",
    menu=["Card"],
),

BrowserColumn(
    # Average time
    type='cavgtime',
    name='Time (Average)',
    content=lambda card,browser :strftimeIfArgument(browser.col.db.scalar(
            "select avg(time)/1000.0 from revlog where cid = ?", card.id)),
    sort="(select avg(time) from revlog where cid = c.id)",
    menu=["Card"],
),

BrowserColumn(
    # Total time
    type='ctottime',
    name='Time (Total)',
    content=lambda card,browser :timeFmt(browser.col.db.scalar(
            "select sum(time)/1000.0 from revlog where cid = ?", card.id)),
    sort="(select sum(time) from revlog where cid = c.id)",
    menu=["Card"],
),


BrowserColumn(
    # Fastest time
    type='cfasttime',
    name='Fastest Review',
    content=lambda card,browser : timeFmt(browser.col.db.scalar(
            "select time/1000.0 from revlog where cid = ? "
            "order by time asc limit 1", card.id)),
    sort="""(select time/1000.0 from revlog where cid = c.id)
           order by time asc limit 1)""",
    menu=["Card"],
),

BrowserColumn(
        # Slowest time
    type='cslowtime',
    name='Slowest Review',
    content=lambda card,browser :timeFmt(browser.col.db.scalar(
            "select time/1000.0 from revlog where cid = ? "
            "order by time desc limit 1", card.id)),
    sort="""(select time/1000.0 from revlog where cid = c.id)
           order by time desc limit 1)""",
    menu=["Card"],
),

# Tags
BrowserColumn(
    type='noteTags',
    name='Tags',
    content=lambda card,browser : " ".join(card.note().tags),
    sort="(select tags from notes where id = c.nid)",
    menu=["Note"],
),

BrowserColumn(
    # Overdue interval
    type='coverdueivl',
    name="Overdue Interval",
    content=overdueContent,
    sort=overdueSort,
    menu=["Card"],
),

BrowserColumn(
    # Previous interval
    type='cprevivl',
    name="Previous Interval",
    content=previewContent,
    sort= """(select ivl from revlog where cid = c.id order by id desc limit 1
           offset 1)""",
    menu=["Card"],
),

BrowserColumn(
    # Percent correct
    type='cpct',
    name='Percent Correct',
    content=lambda card,browser : "" if card.reps <= 0 else "{:2.0f}%".format(
        100 - ((card.lapses / float(card.reps)) * 100)),
    sort="cast(c.lapses as real)/c.reps",
    menu=["Card"],
),

BrowserColumn(
    # Previous duration
    type='cprevdur',
    name="Previous Duration",
    content=lambda card,browser : timeFmt(browser.col.db.scalar(
            "select time/1000.0 from revlog where cid = ? "
            "order by id desc limit 1", card.id)),
    sort="""(select time/1000.0 from revlog where cid = c.id)
           order by id desc limit 1)""",
    menu=["Card"],
),
]
# Internal columns
##################
internalColumns = [
BrowserColumn(
    type="nid",
    name="Note ID",
    advanced=True,
    content=lambda card,browser : card.note().id,
    sort="n.id",
    menu=["Note"],
),

BrowserColumn(
    type="nguid",
    name="Note Guid",
    advanced=True,
    content=lambda card,browser : card.note().guid,
    sort="n.guid",
    menu=["Note"],
),

BrowserColumn(
    type="nmid",
    name="Model ID",
    advanced=True,
    content=lambda card,browser : card.note().mid,
    sort="n.mid",
    menu=["Note"],
),

BrowserColumn(
    type="nusn",
    name="Note USN",
    advanced=True,
    content=lambda card,browser : card.note().usn,
    sort="n.usn",
    menu=["Note"],
),

BrowserColumn(
    type="nfields",
    name="Note Fields",
    advanced=True,
    content=lambda card,browser : u"\u25A0".join(card.note().fields),
    sort="n.flds",
    menu=["Note"],
),

BrowserColumn(
    type="nflags",
    name="Note Flags",
    advanced=True,
    content=lambda card,browser : card.note().flags,
    sort="n.flags",
    menu=["Note"],
),

BrowserColumn(
    type="ndata",
    name="Note Data",
    advanced=True,
    content=lambda card,browser : card.note().data,
    sort="n.data",
    menu=["Note"],
),

BrowserColumn(
    type="cid",
    name="ID",
    advanced=True,
    content=lambda card,browser : card.id,
    sort="c.id",
    menu=["Card"],
),

BrowserColumn(
    type="cdid",
    name="Deck ID",
    advanced=True,
    content=lambda card,browser : card.did,
    sort="c.did",
    menu=["Card"],
),

BrowserColumn(
    type="codid",
    name="Original Deck ID",
    advanced=True,
    content=lambda card,browser : card.odid,
    sort="c.odid",
    menu=["Card"],
),

BrowserColumn(
    type="cord",
    name="Ordinal",
    advanced=True,
    content=lambda card,browser : card.ord,
    sort="c.ord",
    menu=["Card"],
),

BrowserColumn(
    type="cusn",
    name="USN",
    advanced=True,
    content=lambda card,browser : card.usn,
    sort="c.usn",
    menu=["Card"],
),

BrowserColumn(
    type="ctype",
    name="Type",
    advanced=True,
    content=lambda card,browser : card.type,
    sort="c.type",
    menu=["Card"],
),

BrowserColumn(
    type="cqueue",
    name="Queue",
    advanced = True,
    content=lambda card,browser : card.queue,
    sort="c.queue",
    menu=["Card"],
),

BrowserColumn(
    type="cleft",
    name="Left",
    advanced=True,
    content=lambda card,browser : card.left,
    sort="c.left",
    menu=["Card"],
),

BrowserColumn(
    type="codue",
    name="Original Due",  # I think,
    advanced=True,
    content=lambda card,browser : card.odue,
    sort="c.odue",
    menu=["Card"],
),

BrowserColumn(
    type="cflags",
    name="Flags",
    advanced=True,
    content=lambda card,browser : card.flags,
    sort="c.flags",
    menu=["Card"],
),
]
