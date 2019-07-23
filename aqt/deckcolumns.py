# Copyright: Ankitects Pty Ltd and contributors
# -*- coding: utf-8 -*-
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
from operator import itemgetter

from anki.consts import *
from aqt.qt import *
import aqt
from aqt.utils import showInfo, showWarning, openHelp, getOnlyText, askUser, \
    tooltip, saveGeom, restoreGeom
from anki.lang import _
from anki.utils import intTime
"""
dict associating to a column name:
* description: a text to show to explain what represents this column
* header: text to put in the top of the deck browser
* type: what is counted (card, notes, reflog),
* table: in which table the squel is take (default type)
* where: the where query which allows to count what we are currently interested in (absent if it does not exists)
* percentable: whether it makes sens to ask for this percent(default true)
* select: what to sum (default: count (1))
* sum: the set of column name to add to obtain this column (default empty)
* substract: the set of column name to substract to obtain this column (default empty)
* advanced: whether this column is used mainly to compute more interesting column (default None)
* always: a column which is always computed by anki, and not required to compute here (default False)
"""
possibleColumns = {
    # Special cases
    #######################################################
    "name":{
        "description": "The name of the deck",
        "header": _("Deck"),
        "always": True
    },
    "gear":{
        "description": "The gear to open options",
        "header": _(""),
        "always": True
    },
    "option name":{
        "description": "The name of the option",
        "header": _("Option"),
        "type": "cards",
        "always": True
    },
    # Cards
    #######################################################

    "cards":{
        "description": "Number of cards in the deck",
        "header": _("Total")+"<br/>"+_("Cards"),
        "type": "cards",
        "where": "true",
    },
    ## Cards in learning
    #######################

    ### Repetition
    "reps learning today":{
        "description": "Repetition of cards in learning to see today",
        "header": _("In learning"),
        "table": "cards",
        "type": "reps",
        "always": True
    },
    "reps learning today from today":{
        "description": "Number of step remaining today for cards in learning supposed to be seen the same day as last review.",
        #"header": _("Reps learning today from today"),
        "type": "reps",
        "where": f"queue = {QUEUE_LRN}",
        "select": "left/1000",
        "table": "cards",
        "advanced": True,
    },
    "reps learning today from past":{
        "description": "Number of step remaining today for cards in learning supposed to be seen after the day of last review.",
        #"header": _("reps learning today from past"),
        "type": "reps",
        "table": "cards",
        "where": f"queue = {QUEUE_DAY_LRN}",
        "select": "left/1000",
        "advanced": True,
    },
    "lrn":{
#    "reps learning today":{
        "description": "Number of step remaining today of cards in learning.",
        "header": _("Reps of learning today"),
        "type": "reps",
        "sum": {"reps learning today from today","reps learning today from past"},
    },

    "reps learning from past":{
        "description": "Number of step remaining for cards in learning supposed to be seen after the day of last review.",
        "type": "reps",
        "where": f"queue = {QUEUE_DAY_LRN}",
        "select": "left%1000",
        "table": "cards",
        "advanced": True,
    },
    "reps learning from today":{
        "description": "Number of step remaining for cards in learning supposed to be seen the same day as last review.",
        "type": "reps",
        "where": f"queue = {QUEUE_LRN}",
        "select": "left%1000",
        "table": "cards",
        "advanced": True,
    },
    "reps learning":{
        "description": "Number of step remaining of cards in learning.",
        "header": "Remaining step in learning",
        "type": "reps",
        "sum": {"reps learning from today","reps learning from past"},
    },
    "reps learning not today":{
        "description": "Number of step remaining of cards in learning you won't see today.",
        "header": None,
        "type": "reps",
        "sum": {"reps learning"},
        "substract": {"reps learning today"},
    },
    ### Number of cards
    "learning now from today":{
        "description": "Cards in learning which are due now and were seen last today",
        "header": _("Learning now from today"),
        "type": "cards",
        "where": f"queue = {QUEUE_LRN} and due <= :cutoff",
        "advanced": True,
    },
    "learning today from past":{
        "description": "Cards in learning which are due now and where there was at least a day to wait before this review",
        "header": _("Learning now from past"),
        "type": "cards",
        "where": f"queue = {QUEUE_DAY_LRN} and due <= :today",
        "advanced": True,
    },
    "learning later today":{
        "description": "Cards in learning which are due a future day",
        "header": _("Learning later today"),
        "type": "cards",
        "where": f"queue = {QUEUE_LRN} and due > :cutoff",
        "advanced": True,
    },
    "learning not today":{
        "description": "Cards in learning which are due a future day",
        "header": _("Learning another day"),
        "type": "cards",
        "where": f"queue = {QUEUE_DAY_LRN} and due > :today",
        "advanced": True,
    },
    "learning now":{
        "description": "Cards in learning which are due now",
        "header": _("Learning now"),
        "type": "cards",
        "sum": {"learning now from today","learning today from past"}
    },
    "learning today":{
        "description": "Number of cards in learning you're supposed to see again today.",
        "header": _("Learning today"),
        "type": "cards",
        "sum": {"learning later today", "learning now"}
    },
    "learning later":{
        "description": "Review which will happen later. Either because a review happened recently, or because the card have many review left.",
        "header": _("Learning")+"<br/>"+_("now") ,
        "type": "cards",
        "sum":{"learning later today","learning not today"},
    },
    "learning":{
        "description": "Cards in learning (either new cards you see again, or cards which you have forgotten recently. Assuming those cards didn't graduate)",
        "header": _("Learning")+"<br/>"+_("now")+"<br/>"+_("and later"),
        "type": "cards",
        "sum": {"learning now","learning later"},
    },

    ## New cards
    #######################
    "new":{
        "description": "Cards you never saw, and will see today",
        "header": _("New")+"<br/>"+_("today"),
        "type": "cards",
        "always": True
    },
    "unseen":{
        "description": "Cards that have never been answered. Neither buried nor suspended.",
        "header": _("New"),
        "type": "cards",
        "where": f"queue = {QUEUE_NEW_CRAM}",
    },
    "unseen later":{
        "description": "Cards you never saw and won't see today",
        "header": _("Unseen")+"<br/>"+_("later")  ,
        "type": "cards",
        "sum": {"unseen"},
        "substract": {"new"},
    },


    ## Review cards
    #######################
    "rev":{
        "description": "Cards you'll have to review today",
        "header": _("Total"),
        "type": "cards",
        "always": True
    },
    "reviewed":{
        "description": "Number of cards reviewed, not yet due",
        "header": _("Reviewed"),
        "type": "cards",
        "where": f"queue = {QUEUE_REV}",
        "sum": {},
        "substract": {},
    },
    "reviewed not due":{
        "description": "Review cards you won't see today",
        "header": _("Reviewed")+"<br/>"+_("not today")  ,
        "type": "cards",
        "sum": {"review due"},
        "substract": {"rev"},
    },

    ## Buried
    ######################
    "userBuried":{
        "description": "number of cards buried by you",
        "header": None,
        "type": "cards",
        "where":f"queue = {QUEUE_USER_BURIED}",
    },
    "schedBuried":{
        "description": "number of buried cards by a sibling",
        "header": "Buried by<br/>a sibling",
        "type": "cards",
        "where":f"queue = {QUEUE_SCHED_BURIED}",
    },
    "buried":{
        "description": "number of buried cards, (cards you decided not to see today. Or such that you saw a sibling.)",
        "sum": {"schedBuried", "userBuried"},
        "header": _("Buried"),
        "type": "cards",
    },
    "suspended":{
        "description": "number of suspended cards, (cards you will never see unless you unsuspend them in the browser)",
        "header": "Suspended",
        "type": "cards",
        "where": f"queue = {QUEUE_SUSPENDED}",
    },

    ## Flags
    #######################
    "no flag":{
        "description": "Cards without Flag",
        "header": "No flag",
        "type": "cards",
        "where": f"(flags & 7) == 0",
    },
    **{f"flag{i}":{
        "description":f"Flag {i}",
        "header": f"Flag {i}",
        "type": "cards",
        "where": f"(flags & 7) == {i}",
    } for i in range (1,5)},

    "flagged":{
        "description": "Flags from 1 to 4",
        "header": _("Flagged"),
        "type": "cards",
        "sum": {f"flag{i}" for i in range(1,5)},
    },
    ## Past reps
    ###############################
    "repeated today":{
        "description": "Number of review done today",
        "header": _("repeated"),
        "where":f"revlog.id>:yesterdayLimit",
        "type": "reps",
        "percentable": False,
        "table": "revlog inner join cards on revlog.cid = cards.id"
    },
    "repeated":{
        "description": "Number of time you saw a question from a card currently in this deck",
        "header": None,
        "where": "true",
        "type": "reps",
        "percentable": False,
        "table": f"revlog inner join cards on revlog.cid = cards.id",
    },

    ## Other properties
    ###############################
    "mature":{
        "description": "Number of cards reviewed, with interval at least 3 weeks",
        "header": _("Mature"),
        "type": "cards",
        "where": f"queue = {QUEUE_REV} and ivl >= 21",
    },
    "young":{
        "description": " Number of cards reviewed, with interval less than 3 weeks,",
        "header": _("Young"),
        "type": "cards",
        "where": f"queue = {QUEUE_REV} and 0<ivl and ivl <21",
    },
    "leech card":{
        "description": " Number of cards reviewed, with interval less than 3 weeks,",
        "header": _("Leech")+" "+_("cards"),
        "type": "cards",
        "where": f"lapses>7",
    },
    "reviewed today":{
        "description": "Number of review cards seen, to see today",
        "header": _("reviewed")+"<br/>"+_("today")  ,
        "type": "cards",
        "where":f"queue = {QUEUE_REV} and due>0 and due-ivl = :today",
    },
    "due tomorrow":{
        "description": "Review cards which are due tomorrow",
        "header": _("Due")+"<br/>"+_("tomorrow") ,
        "where": f"queue in ({QUEUE_REV}, {QUEUE_DAY_LRN}) and due = :tomorrow",
        "type": "cards",
    },

    ## Sum of different types
    ###################################a
    "due":{
        "description": "Number of cards you already saw and are supposed to see today",
        "header": _("Due"),
        "type": "reps",
        "sum": {"rev", "lrn"},
    },

    "to see today":{
        "description": "Number of cards you will see today (new, review and learning)",
        "header": _("Today"),
        "type": "cards",
        "sum": {"rev", "new", "learning today"},
    },

    "reps":{
        "description": "Number of time you'll see a card today.",
        "header": _("Reps")+" "+ _("today"),
        "type": "reps",
        "sum": {"due", "new"},
    },
    # "learning all":{
    #     "description": "Cards in learning which are due now (and in parenthesis, the number of reviews which are due later)",
    #     "header": _("Learning")+"<br/>"+_("now")+"<br/>("+_("later today")+"<br/>("+_("other day")+"))",
    #     "type": "cards",
    # },
    # "unseen new":{
    #     "description": "Unseen cards you will see today, not buried nor suspended.(what anki calls new cards). Followed by the unseen cards not buried nor suspended that you will not see today.",
    #     "header": _("New")+"<br/>"+"("+_("Unseen")+")",
    #     "type": "cards",
    # },

    # "buried/suspended":{
    #     "description": "number of buried (cards you decided not to see today)/number of suspended cards, (cards you will never see unless you unsuspend them in the browser)",
    #     "header": _("Suspended"),
    #     "type": "cards",
    # },
    # "notes/cards":{
    #     "description": "Number of cards/notes in the deck",
    #     "header": _("Total")+"/<br/>"+_("Card/Note"),
    #     "type": "cards",
    # },
    # "mature/young":{
    #     "description": "Number of cards reviewed, with interval at least 3 weeks/less than 3 weeks ",
    #     "header":  _("Young"),
    #     "type": "cards",
    # },
    # "reviewed today/repeated today":{
    #     "description": "Number of review cards seen, to see today and number of review",
    #     "header": _("reviewed")+"/"+"<br/>"+_("repeated")+"<br/>"+_("today")  ,
    #     "type": "cards",
    # },
    # "bar":{
    #     "header": _("Progress"),
    #     "type": "cards",
    # },
    # "bar":{
    #     "header": "Total",
    #     "type": "cards",
    # },
    # Notes
    #########
    "marked":{
        "description": "Number of marked note",
        "header": _("Marked"),
        "type": "notes",
        "sqlByDids": "select count(distinct nid) from notes inner join cards on cards.nid = notes.id  where tags like '%marked%' and did in ",
    },
    "notes":{
        "description": "Number of notes in the deck",
        "header": _("Total")+"<br/>"+_("Notes"),
        "sqlByDids": "select count(distinct nid) from cards where did in ",
    },

    "leech note":{
        "description": "Number of note with a leech card",
        "header": _("Leech")+" "+_("note"),
        "type": "cards",
        "sqlByDids": "select count(distinct nid) from notes inner join cards on cards.nid = notes.id  where tags like '%leech%' and did in ",    },

}

possibleColumns = {name: {"name":name, **dict} for name, dict in possibleColumns.items()}
def sqlDict(col):
    #it's a function because it depends on the current day
    return dict(
        cutoff= intTime() + col.conf['collapseTime'],
        today = col.sched.today,
        tomorrow = col.sched.today+1,
        yesterdayLimit = (col.sched.dayCutoff-86400)*1000,
    )


class DeckBrowserColumnOption(QDialog):
    def __init__(self, deckbrowser, column):
        QDialog.__init__(self, deckbrowser.mw)
        self.mw = deckbrowser.mw
        self.deckbrowser = deckbrowser
        self.column = column
        self.form = aqt.forms.deckbrowsercolumnoption.Ui_Dialog()
        self.form.setupUi(self)
        self.mw.checkpoint(_("Column options"))
        self.color = self.deckbrowser.getColor(self.column)
        self.setupColumns()
        self.setWindowModality(Qt.WindowModal)
        if column:
            title = _("New column in deck browser")
        else:
            title = _("Edit column %s") % column['name']
        self.setWindowTitle(title)
        # qt doesn't size properly with altered fonts otherwise
        restoreGeom(self, "deckbrowsercolumnoption", adjustSize=True)
        self.show()
        self.exec_()
        saveGeom(self, "deckbrowsercolumnoption")

    # Column list
    ######################################################################

    def setupColumns(self):
        self.possibleColumns = self.deckbrowser._allPossibleColumns()
        startOn = 0
        self.ignoreColumnChange = True
        self.form.column.clear()
        for idx, name in enumerate(self.possibleColumns):
            header = self.deckbrowser.getHeader(possibleColumns[name])
            header = header.replace("<br/>", " ")
            self.form.column.addItem(header)
            if name == self.column['name']:
                startOn = idx
        self.ignoreColumnChange = False
        self.form.column.setCurrentIndex(startOn)
        self.form.percent.setChecked(self.column.get("percent", False))
        self.form.withSubdecks.setChecked(self.column.get("withSubdecks", True))
        self.form.defaultColor.setChecked(self.column.get("defaultColor", True))
        self.form.header.setText(self.column.get("header", ""))
        self.form.defaultColor.clicked.connect(self.changeColor)
        self.changeColor()
        self.setupDescription()
        self.form.colorButton.clicked.connect(self._onColor)
        self.form.column.currentIndexChanged.connect(self.setupDescription)

    def setupDescription(self):
        description = possibleColumns[self.getSelectedName()]["description"]
        self.form.description.setText(description)


    def changeColor(self):
        hide = self.form.defaultColor.isChecked()
        self.form.colorLabel.setHidden(hide)
        self.form.colorButton.setHidden(hide)
        self.form.colorButton.setStyleSheet(f"background-color: {self.color}")

    def _onColor(self):
        new = QColorDialog.getColor(QColor(self.color), self, f"Choose the color for {self.getSelectedName()}")
        if new.isValid():
            newColor = new.name()
            self.color = newColor
            self.form.colorButton.setStyleSheet(f"background-color: {newColor}")

    def updateColumn(self):
        self.column["withSubdecks"] = self.form.withSubdecks.isChecked()
        self.column["defaultColor"] = self.form.defaultColor.isChecked()
        self.column["color"] = self.color
        self.column["percent"] = self.form.percent.isChecked()
        self.column["header"] = self.form.header.text()
        if not self.column["header"]:
            del self.column["header"]
        self.column["name"] = self.getSelectedName()

    def getSelectedName(self):
        return self.possibleColumns[self.form.column.currentIndex()]

    def reject(self):
        self.accept()
        # self.column.clear()
        # super().reject()

    def accept(self):
        self.updateColumn()
        super().accept()
