from anki.consts import *
from anki.lang import _
from anki.utils import intTime
"""
dict associating to a column name:
* description: a text to show to explain what represents this column
* header: text to put in the top of the deck browser
* type: what is counted (card, notes, reflog),
* table: in which table the squel is take (default type)
* sql: the sql query which allows to count what we are currently interested in (absent if it does not exists)
* sqlSum: what to sum (default: count (1))
* sum: the set of column name to add to obtain this column (default empty)
* substract: the set of column name to substract to obtain this column (default empty)
* advanced: whether this column is used mainly to compute more interesting column (default None)
* always: a column which is always computed by anki, and not required to compute here (default False)
"""
columns = {
    "name":{
        "description":"The name of the deck",
        "header": "Deck",
        "always": True
    },
    "lrn":{
        "description":"Cards in learning",
        "header": "In learning",
        "type": "cards",
        "always": True
    },
    "rev":{
        "description":"Cards you'll have to review today",
        "header": _("Total"),
        "type": "cards",
        "always": True
    },
    "gear":{
        "description":"The gear to open options",
        "header": "",
        "always": True
    },
    "option name":{
        "description":"The name of the option",
        "header": "Option",
        "type": "cards",
        "always": True
    },
    "due":{
        "description":"Number of cards you already saw and are supposed to see today",
        "header": "Due",
        "type": "cards",
        "always": True
    },
    "new":{
        "description":"Cards you never saw, and will see today",
        "header": _("Today"),
        "type": "cards",
        "always": True
    },
    "today":{
        "description":"Number of review you will see today (new, review and learning)",
        "header": "Today-",
        "type": "cards",
        "sum": {"cards seen today", "new"},
    },
    "cards seen today":{
        "description": "Cards you'll see today which are not new card",
        "header": "Due-",
        "type": "cards",
        "sum": { "learning today", "rev"},
    },
    "learning card":{
        "description":"Cards in learning (either new cards you see again, or cards which you have forgotten recently. Assuming those cards didn't graduate)",
        "header": _("Learning")+"<br/>"+_("now")+"<br/>"+_("and later"),
        "type": "cards",
        "sum": {"learning now","learning later"},
    },
    "learning later":{
        "description":"Review which will happen later. Either because a review happened recently, or because the card have many review left.",
        "header": _("Learning")+"<br/>"+_("now") ,
        "type": "cards",
        "sum":{"learning later today","learning future"},
    },
    # "learning all":{
    #     "description":"Cards in learning which are due now (and in parenthesis, the number of reviews which are due later)",
    #     "header": _("Learning")+"<br/>"+_("now")+"<br/>("+_("later today")+"<br/>("+_("other day")+"))",
    #     "type": "cards",
    # },
    "learning now":{
        "description":"Cards in learning which are due now",
        "header": "Learning now",
        "type": "cards",
        "sum": {"learning now from today","learning today from past"}
    },
    "learning now from today":{
        "description":"Cards in learning which are due now and where seen last today",
        "header": "Learning now from today",
        "type": "cards",
        "sql": f"queue = {QUEUE_LRN} and due <= :cutoff",
        "advanced": True,
    },
    "learning today from past":{
        "description":"Cards in learning which are due now and where there was at least a day to wait before this review",
        "header": "Learning now from past",
        "type": "cards",
        "sql": f"queue = {QUEUE_DAY_LRN} and due <= :today",
        "advanced": True,
    },
    "learning later today":{
        "description":"Cards in learning which are due a future day",
        "header": "Learning later today",
        "type": "cards",
        "sql": f"queue = {QUEUE_LRN} and due > :cutoff",
        "advanced": True,
    },
    "learning future":{
        "description":"Cards in learning which are due a future day",
        "header": "Learning another day",
        "type": "cards",
        "sql": f"queue = {QUEUE_DAY_LRN} and due > :today",
        "advanced": True,
    },
    "learning today repetition from today":{
        "description":"Number of step remaining today for cards in learning supposed to be seen the same day as last review.",
        "header": "Learning today repetition from today",
        "type": "reps",
        "sql": f"queue = {QUEUE_LRN}",
        "sqlSum": "left/1000",
        "advanced": True,
    },
    "learning today repetition from past":{
        "description":"Number of step remaining today for cards in learning supposed to be seen after the day of last review.",
        "header": "Learning today repetition from past",
        "type": "cards",
        "sql": f"queue = {QUEUE_DAY_LRN}",
        "sqlSum": "left/1000",
        "advanced": True,
    },
    "learning today":{
        "description":"Number of cards in learning you're supposed to see again today.",
        "header": "Learning today-",
        "type": "cards",
        "sum": {"learning later today", "learning now"}
    },
    "learning today repetition":{
        "description":"Number of step remaining today of cards in learning.",
        "header": "Learning today",
        "type": "reps",
        "sum": {"learning today repetition from today","learning today repetition from past"},
    },
    "learning repetition":{
        "description":"Number of step remaining of cards in learning.",
        "header": "Remaining step in learning",
        "type": "reps",
        "sum": {"learning repetition from today","learning repetition from past"},
    },
    "repetition seen today":{
        "description":"Number of cards you already saw, and will see today.",
        "header": "Learning seen today-",
        "type": "cards",
        "sum": {"repetition of today learning", "rev"},
    },
    "repetition today":{
        "description":"Number of time you'll see a card today.",
        "header": "Cards today",
        "type": "cards",
        "sum": {"repetition seen learning", "new"},
    },
    "learning future repetition":{
        "description":"Number of step remaining of cards in learning you won't see today.",
        "header": None,
        "type": "reps",
        "sum": {"learning repetition"},
        "substract": {"learning today repetition"},
    },
    "learning repetition from today":{
        "description":"Number of step remaining for cards in learning supposed to be seen the same day as last review.",
        "header": None,
        "type": "reps",
        "sql": f"queue = {QUEUE_LRN}",
        "sqlSum": "left%1000",
        "advanced": True,
    },
    "learning repetition from past":{
        "description":"Number of step remaining for cards in learning supposed to be seen after the day of last review.",
        "header": None,
        "type": "reps",
        "sql": f"queue = {QUEUE_DAY_LRN}",
        "sqlSum": "left%1000",
        "advanced": True,
    },

    "review":{
        "description":"Review cards cards you will see today (and the ones you will not see today)",
        "header": None,
        "type": "cards",
    },
    "review later":{
        "description":"Review cards you won't see today",
        "header": _("review")+"<br/>"+_("later")  ,
        "type": "cards",
        "sum": {"review due"},
        "substract": {"rev"},
    },
    "unseen later":{
        "description":"Cards you never saw and won't see today",
        "header": _("Unseen")+"<br/>"+_("later")  ,
        "type": "cards",
        "sum": {"unseen"},
        "substract": {"new"},
    },
    "review due":{
        "description":"Review cards which are due today (not counting the one in learning)",
        "header": _("Unseen")+"<br/>"+_("all")  ,
        "type": "cards",
        "sql": f"queue = {QUEUE_REV} and due <= :today",
    },
    "review today":{
        "description":"Review cards you will see today",
        "header": _("Due")+"<br/>"+_("today") ,
        "type": "cards",
    },

    "unseen new":{
        "description":"Unseen cards you will see today, not buried nor suspended.(what anki calls new cards). Followed by the unseen cards not buried nor suspended that you will not see today.",
        "header": _("New")+"<br/>"+"("+_("Unseen")+")",
        "type": "cards",
    },
    "unseen":{
        "description":"Cards that have never been answered. Neither buried nor suspended.",
        "header": None,
        "type": "cards",
        "sql": f"queue = {QUEUE_NEW_CRAM}",
    },
    "new today":{
        "description":"Unseen cards you will see today, not buried nor suspended. (what anki calls new cards)",
        "header": _("New")+"<br/>"+_("Today"),
        "type": "cards",
    },

    # "buried/suspended":{
    #     "description":"number of buried (cards you decided not to see today)/number of suspended cards, (cards you will never see unless you unsuspend them in the browser)",
    #     "header": _("Suspended"),
    #     "type": "cards",
    # },
    "userBuried":{
        "description":"number of cards buried by you",
        "header": None,
        "type": "cards",
        "sql":f"queue = {QUEUE_USER_BURIED}",
    },
    "schedBuried":{
        "description":"number of buried cards by a sibling",
        "header": "Buried by<br/>a sibling",
        "type": "cards",
        "sql":f"queue = {QUEUE_SCHED_BURIED}",
    },
    "buried":{
        "description":"number of buried cards, (cards you decided not to see today. Or such that you saw a sibling.)",
        "sum": {"schedBuried", "userBuried"},
        "header": _("Buried"),
        "type": "cards",
    },
    "suspended":{
        "description":"number of suspended cards, (cards you will never see unless you unsuspend them in the browser)",
        "header": "Suspended",
        "type": "cards",
        "sql": f"queue = {QUEUE_SUSPENDED}",
    },
    # "notes/cards":{
    #     "description":"Number of cards/notes in the deck",
    #     "header": _("Total")+"/<br/>"+_("Card/Note"),
    #     "type": "cards",
    # },
    "cards":{
        "description":"Number of cards in the deck",
        "header": _("Total")+"<br/>"+_("Cards"),
        "type": "cards",
        "sql":"true",
    },
    "notes":{
        "description":"Number of notes in the deck",
        "header": _("Total")+"<br/>"+_("Notes"),
        "sql":"true",
        "type": "notes",
    },
    # "mature/young":{
    #     "description":"Number of cards reviewed, with interval at least 3 weeks/less than 3 weeks ",
    #     "header":  _("Young"),
    #     "type": "cards",
    # },
    "undue":{
        "description":"Number of cards reviewed, not yet due",
        "header": _("Undue"),
        "type": "cards",
        "sql": f"queue = {QUEUE_REV} and due >  :today",
    },
    "mature":{
        "description":"Number of cards reviewed, with interval at least 3 weeks",
        "header": _("Mature"),
        "type": "cards",
        "sql": f"queue = {QUEUE_REV} and ivl >= 21",
    },
    "young":{
        "description":" Number of cards reviewed, with interval less than 3 weeks,",
        "header": _("Young"),
        "type": "cards",
        "young": f"queue = {QUEUE_REV} and 0<ivl and ivl <21",
    },
    "marked":{
        "description":"Number of marked note",
        "header": _("Marked"),
        "type": "cards",
    },
    "leech":{
        "description":"Number of note with a leech card",
        "header": _("Leech"),
        "type": "cards",
    },
    "reviewed today":{
        "description":"Number of review cards seen today",
        "header": _("reviewed")+"<br/>"+_("today")  ,
        "type": "cards",
        "sql":f"queue = {QUEUE_REV} and due>0 and due-ivl = :today",

    },
    "repeated today":{
        "description":"Number of review done today",
        "header": _("repeated"),
        "sql":f"revlog.id>:yesterdayLimit",
        "type":"reps",
        "table":"revlog inner join cards on revlog.cid = cards.id"
    },
    # "reviewed today/repeated today":{
    #     "description":"Number of review cards seen today and number of review",
    #     "header": _("reviewed")+"/"+"<br/>"+_("repeated")+"<br/>"+_("today")  ,
    #     "type": "cards",
    # },
    "repeated":{
        "description":"Number of time you saw a question from a card currently in this deck",
        "header": None,
        "sql":"true",
        "type": "reps",
        "table": f"revlog inner join cards on revlog.cid = cards.id",
    },
    # "bar":{
    #     "header": _("Progress"),
    #     "type": "cards",
    # },
    # "bar":{
    #     "header": "Total",
    #     "type": "cards",
    # },
    "due tomorrow":{
        "description":"Review cards which are due tomorrow",
        "header": _("Due")+"<br/>"+_("tomorrow") ,
        "sql": f"queue in ({QUEUE_REV}, {QUEUE_DAY_LRN}) and due = :tomorrow",
        "type": "cards",
    },
    "all flags":{
        "description":"Flags from 0 to 4",
        "header": _("Flags"),
        "type": "cards",
        "sum": {f"flag{i}" for i in range(1,5)},
    },
    "flags":{
        "description":"Flags from 1 to 4",
        "header": "Flags",
        "type": "cards",
    },
    "no flag":{
        "description":"Cards without Flag",
        "header": "Flag 1",
        "type": "cards",
        "sql": f"(flags & 7) == 0",
    },
    "flag1":{
        "description":"Flag 1",
        "header": "Flag 1",
        "type": "cards",
        "sql": f"(flags & 7) == 1",
    },
    "flag2":{
        "description":"Flag 2",
        "header": "Flag 2",
        "type": "cards",
        "sql": f"(flags & 7) == 2",
    },
    "flag3":{
        "description":"Flag 3",
        "header": "Flag 3",
        "type": "cards",
        "sql": f"(flags & 7) == 3",
    },
    "flag4":{
        "description":"Flag 4",
        "header": "Flag 4",
        "type": "cards",
        "sql": f"(flags & 7) == 4",
    },
}

columns = {name: {"name":name, **dict} for name, dict in columns.items()}
def sqlDict(col):
    #it's a function because it depends on the current day
    return dict(
        cutoff= intTime() + col.conf['collapseTime'],
        today = col.sched.today,
        tomorrow = col.sched.today+1,
        yesterdayLimit = (col.sched.dayCutoff-86400)*1000,
    )
