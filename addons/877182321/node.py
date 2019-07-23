import time
from aqt.qt import *
from aqt.utils import downArrow
from anki.utils import intTime, ids2str
from aqt import mw
import copy
import sys
from .config import getUserOption, writeConfig, getFromName
from .htmlAndCss import start_header, css, js, deck_header, column_header, option_header, option_name_header, end_header, start_line, collapse_children_html, collapse_no_child, deck_name, number_cell, gear, deck_option_name, end_line, bar, progress
from .printing import conditionString, nowLater
from .strings import getHeader, getOverlay, getColor
from .debug import debug
from . import tree

debugWrongLine = debug


# Dict from deck id to deck node
idToNode = dict()
idToOldNode = dict()
def idFromOldNode(node):
    #Look at aqt/deckbrowser.py for a description of node
    (_,did,_,_,_,_) = node
    return did

#The list of column in configuration which does not exists, and such that the user was already warned about it.
warned = set()


class DeckNode:
    """A node in the new more advanced deck tree.

    name -- the name of the deck
    did -- the id of the deck
    dueRevCards -- number of review to see today
    dueLrnReps -- numbers of cards in learning
    newCards -- number of new cards to see today
    children -- the set of children, as decknode
    deck -- the deck objects

    Information to potentially display
    count -- associate to [absolute/percent][deck/subdeck][isThisAString][value] the number/percent of cards satisfying value in the deck (and its subdeck)
    set -- associate to [deck/subdeck][value] the set of nids satisfying "value" in the deck (and its subdeck)
    markedNotesRec -- the set of marked notes in the deck and its subdkc
    endedMarkedDescendant -- whether the deck has a descendant ended with marked cards
    timeDue[deck/subdeck] -- the number of seconds before the first card in learning will be seen
    isEmpty -- whether deck and subdecks has no unseen cards

    Conf parameters
    isFiltered -- whether this is a filtered deck
    confName -- the name of the configuration of this deck ('Filtered' if filtered)

    content of the deck's name:
    containsEndSymbol -- whether the deck's name contains the end symbol
    containsPauseSymbol
    containsBookSymbol
    containsGivenUpSymbol

    content of the deck's parent:
    endedParent -- whether an ancestor's name contains the end symbol
    givenUpParent
    pauseParent

    content of the deck:
    ended -- whether the deck is ended according to a symbol
    givenUp
    """

    def __init__(self, mw, oldNode, endedParent = False, givenUpParent = False, pauseParent = False):
        #Look at aqt/deckbrowser.py for a description of oldNode
        "Build the new deck tree or subtree (with extra info) by traversing the old one."

        # Associate each of the potentially interesting parameters of this node
        self.param = dict()
        #CSS Style
        self.style = dict()
        self.mw = mw
        self.endedParent = endedParent
        self.pauseParent = pauseParent
        self.givenUpParent = givenUpParent
        self.name, self.did, self.dueRevCards, self.dueLrnReps, self.newCardsToday, self.oldChildren = oldNode
        self.deck = mw.col.decks.get(self.did)

        self.initDicts()
        self.setSymbolsParameters()
        self.setChildren()
        self.setDeckLevel()
        self.setSubdeck()

        self.fromSetToCount()
        self.setText()


    def setDeckLevel(self):
        """Compute every informations which does not need access to
        children """
        self.setConfParameters()
        self.initCountFromDb() # count information of card from database
        self.initNid() # set of note from database
        self.initTagged() # set of marked/lapsed notes
        self.initTimeDue()
        self.initFromAlreadyComputed()
        self.initCountSum() # basic sum from database information


    def setSubdeck(self):
        self.setEndedMarkedDescendant()
        self.setSubdeckCount() # Sum of subdecks value
        self.setSubdeckSets() #Union of subdecks set
        self.setTimeDue()
        self.setEmpty()
        self.setPercentAndBoth()


    def setConfParameters(self):
        """ Find the configuration and its name """
        if "conf" in self.deck:#a classical deck
            confId = str(self.deck["conf"])
            conf = mw.col.decks.dconf[confId]
            self.isFiltered = False
            self.confName = conf['name']
        else:
            self.isFiltered = True
            self.confName = "Filtered"

    def testSymbolInName(self, symbolName):
        """ Whether the symbol associate to symbol name in the
        configuration occurs in the deck's name"""
        symbol = getUserOption(symbolName)
        if symbol is None:
            return False
        return symbol in self.name

    def setSymbolsParameters(self):
        """ Read the deck name and gather information from it"""
        self.containsEndSymbol = self.testSymbolInName("end symbol")
        self.containsPauseSymbol = self.testSymbolInName("pause symbol")
        self.containsBookSymbol = self.testSymbolInName("book symbol")
        self.containsGivenUpSymbol = self.testSymbolInName("given up symbol")
        self.ended = self.endedParent or self.containsEndSymbol
        self.givenUp = self.givenUpParent or self.containsGivenUpSymbol
        self.pause = self.pauseParent or self.containsPauseSymbol

    def initDicts(self):
        """ Ensure that each dictionarry are created"""
        self.count =  dict()
        for absoluteOrPercent in ["absolute", "percent","both"]:
            self.count[absoluteOrPercent] = dict()
            for kind in ["deck","subdeck"]:
                self.count[absoluteOrPercent][kind]= dict()
                for isString in [True,False]:
                    self.count[absoluteOrPercent][kind][isString]= dict()
        self.noteSet =  dict()
        for kind in ["deck","subdeck"]:
            self.noteSet[kind]= dict()

    def initCountFromDb(self):
        for name in tree.values:
            self.addCount("absolute", "deck", False, name, tree.values[name].get(self.did,0))

    def initFromAlreadyComputed(self):
        """Put in dict values already computed by anki"""
        for subdeckNumber, name in  [(self.dueRevCards, "review today"), (self.newCardsToday,"new today"),(self.dueLrnReps,"repetition of today learning")]:
            deckNumber = subdeckNumber
            for child in self.children:
                deckNumber -= child.count["absolute"]["subdeck"][False][name]
            self.addCount("absolute", "deck", False, name, deckNumber)
            self.addCount("absolute", "subdeck", False, name, subdeckNumber)

    def absoluteDeckSum(self,newName, sum1, sum2, negate = False):
        sum1 = self.count["absolute"]["deck"][False][sum1]
        sum2 = self.count["absolute"]["deck"][False][sum2]
        if negate:
            sum2 = -sum2
        self.addCount("absolute","deck", False, newName,(sum1+sum2))

    def initCountSum(self):
        self.absoluteDeckSum("learning now","learning now from today","learning today from past")
        self.absoluteDeckSum("learning later","learning later today","learning future")
        self.absoluteDeckSum("learning card","learning now","learning later")
        self.absoluteDeckSum("learning today","learning later today","learning now")

        # Repetition
        self.absoluteDeckSum("learning today repetition","learning today repetition from today","learning today repetition from past")
        self.absoluteDeckSum("learning repetition","learning repetition from today","learning repetition from past")
        self.absoluteDeckSum("learning future repetition","learning repetition","learning today repetition", negate=True)

        # Review
        self.absoluteDeckSum("review later","review due","review today", negate=True)
        self.absoluteDeckSum("unseen later", "unseen","new today", negate=True)
        self.absoluteDeckSum("repetition seen today", "repetition of today learning", "review today")
        self.absoluteDeckSum("repetition today", "repetition seen today", "new today")
        self.absoluteDeckSum("cards seen today", "learning today", "review today")
        self.absoluteDeckSum("today", "cards seen today", "new today")


    def initNid(self):
        """ set the set of nids of this deck"""
        self.addSet("deck", "notes",set(mw.col.db.list("""select  nid from cards where did = ?""", self.did)))

    def initTagged(self):
        """ set the set of marked cards of this deck, and someMarked"""
        self.addSet("deck","marked",set(mw.col.db.list("""select  id from notes where tags like '%marked%' and (not (tags like '%notMain%')) and id in """+ ids2str(self.noteSet["deck"]["notes"]))))
        self.addSet("deck","leech",set(mw.col.db.list("""select  id from notes where tags like '%leech%' and (not (tags like '%notMain%')) and id in """+ ids2str(self.noteSet["deck"]["notes"]))))
        self.someMarked = bool(self.noteSet["deck"]["marked"])


        # if self.containsBookSymbol:
        #     self.endedMarkedDescendant = self.endedMarkedDescendant and self.containsEndSymbol and self.isEmpty
        # if self.markedNotes and self.containsEndSymbol and self.isEmpty:
        #     self.endedMarkedDescendant = True
        # self.addCount("absolute","deck","marked", len(self.markedNotes))
        # self.addCount("absolute","subdeck","marked", len(self.markedNotesRec))
        # self.param["someMarked"] = self.count["absolute"]["subdeck"]["marked"]>0

        # self.endedMarkedDescendant = False

    def initTimeDue(self):
        """find the time before the first element in learning can be seen"""
        self.timeDue = dict()
        fromTree = tree.times.get(self.did,0)
        self.timeDue["deck"] = fromTree or 0
        debug("""For deck {self.name} with id {self.did!r}, we get from tree {fromTree} and thus {self.timeDue["deck"]}.""")



    def setChildren(self):
        """ create node from every child and save them in
        self.children """
        self.children = list()
        for oldChild in self.oldChildren:
            childNode = make(oldChild, self.ended, self.givenUp, self.pause)
            self.children.append(childNode)

    def setEndedMarkedDescendant(self):
        """ check whether there is a descendant empty with marked note. Set background color appropriately"""
        self.endedMarkedDescendant = False
        if self.ended and self.someMarked:
            self.endedMarkedDescendant = True
            return
        for child in self.children:
            if child.endedMarkedDescendant:
                self.endedMarkedDescendant = True
                return
        if self.someMarked and getUserOption("do color marked",False):
            if self.endedMarkedDescendant:
                self.style["background-color"] = getUserOption("ended marked background color")
            else:
                self.style["background-color"] = getUserOption("marked background color")

    def setSubdeckCount(self):
        """Compute subdeck value, as the sum of deck, and children's subdeck value"""
        for name in self.count["absolute"]["deck"][False]:
            count = self.count["absolute"]["deck"][False][name]
            for child in self.children:
                childNb = child.count["absolute"]["subdeck"][False][name]
                if not isinstance(childNb,int):
                    debugWrongLine("For child {child.name}, the value of {name} is not an int but {childNb}")
                if not isinstance(childNb,int):
                    debugWrongLine(f"childNb for «{name}» is «{childNb}»")
                count += childNb
            self.addCount("absolute", "subdeck", False, name, count)

    def setSubdeckSets(self):
        """ Compute subdeck's set as union of the deck set and children subdecks set"""
        for name in self.noteSet["deck"]:
            newSet = self.noteSet["deck"][name]
            for child in self.children:
                newSet |= child.noteSet["subdeck"][name]
            self.addSet("subdeck",name,newSet)

    def setTimeDue(self):
        """Compute first time due for subdeck using the timedue of this deck,
        and the one of subdecks"""
        self.timeDue["subdeck"] = self.timeDue["deck"]
        for child in self.children:
            if self.timeDue["subdeck"]:
                if child.timeDue["subdeck"]:
                    self.timeDue["subdeck"] = min(self.timeDue["subdeck"],child.timeDue["subdeck"])
            else:
                self.timeDue["subdeck"] = child.timeDue["subdeck"]

    def setEmpty(self):
        """Set value of isEmpty and hasEmptyDescendant. Set the colors appropriately."""
        if not getUserOption("do color empty"):
            return
        self.isEmpty = self.count["absolute"]["subdeck"][False]["unseen"] == 0
        self.hasEmptyDescendant = self.isEmpty

        if self.isEmpty:
            if not self.ended and not self.givenUp and not self.pause:
                self.style["color"] = getUserOption("color empty","black")
            return
        for child in self.children:
            if (child.hasEmptyDescendant and (not child.ended) and (not child.givenUp) and (not child.pause)):
                self.hasEmptyDescendant = True
                self.style['color'] = getUserOption("color empty descendant","black")
                return

    def _setPercentAndBoth(self, kind, column, base):
        """Set percent and both count values for this kind and column. In theory, column is a subset of base.

        Returns the numerator if its non null and there are no cards."""
        ret = None
        numerator = self.count["absolute"][kind][False][column]
        denominator = self.count["absolute"][kind][False][base]
        if numerator == 0:
            percent = 0
            percentText = "0%"
        #base can't be empty since a subset of it is not empty, as ensured by the above test
        else:
            if denominator ==0:
                percent = 0
                percentText = f"{numerator}/{denominator} ?"
                ret = numerator
            else:
                percent = (100*numerator)/denominator
                percentText = f"{int(percent)}%"
        self.addCount("percent", kind, False, column, percent)
        self.addCount("percent", kind, True, column, percentText)
        both = conditionString(numerator,f"{numerator}|{percentText}")
        self.addCount("both", kind, True, column, both)
        return ret

    def makeBar(self, kind, names):
        total = 0
        for name in names:
            total +=self.count['absolute'][kind][False].get(name,0)
        if total == 0: #empty decks don't get progress bars
            return ""
        cumulative = 0
        content = ""
        for name in names:
            conf = getFromName(name) or {"name":name}
            color = getColor(conf)
            number =self.count['absolute'][kind][False].get(name,0)
            overlay =f"{number}: {getOverlay(conf)}"
            width = number*100/total
            content+=bar(name, width, cumulative, color, overlay)
            cumulative += width
        return progress (content)

    def setPercentAndBoth(self):
        """Set percent and both count values for each kind and column
        percent. Only considering cards.

        Print in case of division by 0 for the percent computation.
        """
        for kind in self.count["absolute"]:
            for column in self.count["absolute"][kind][False]:
                ret = self._setPercentAndBoth(kind,column,"cards")
                if ret is not None:
                    debugWrongLine(f"""{self.name}.count["absolute"]["{kind}"]["{column}"] is {ret}, while for cards its 0: """+str(self.count["absolute"][kind][True]["cards"]))

    def fromSetToCount(self):
        """Add numbers according to number of notes, for deck, subdeck, absolute, percent, both"""
        for kind in ["deck","subdeck"]:
            for name in self.noteSet[kind]:
                self.addCount("absolute", kind, False, name,len(self.noteSet[kind][name]))
            for name in self.noteSet[kind]:
                self._setPercentAndBoth(kind,name,"notes")

    def setLearningAll(self):
        """Set text for learning all"""
        for absoluteOrPercent in self.count:
            for kind in ["deck", "subdeck"]:
                future = self.count[absoluteOrPercent][kind][True]["learning future"]
                if future:
                    later = nowLater(self.count[absoluteOrPercent][kind][True]["learning later today"],future)
                else:
                    later = conditionString(self.count[absoluteOrPercent][kind][True]["learning later today"],parenthesis = True)
                string = nowLater(self.count[absoluteOrPercent][kind][True]["learning now"],later)
                self.addCount(absoluteOrPercent, kind, True, "learning all", string)

    def setTextTime(self):
        """set text for the time remaining before next card"""
        for kind in ["deck", "subdeck"]:
            learningNow = self.count["absolute"][kind][False]["learning now"]
            debug("""{self.name}[{kind}]=={learningNow}. Time due is {self.timeDue[kind]}.""")
            for absoluteOrPercent in self.count:
                if ((not learningNow)) and (self.timeDue[kind] is not 0):
                    remainingSeconds = self.timeDue[kind] - intTime()
                    if remainingSeconds >= 60:
                        self.addCount(absoluteOrPercent, kind, True, "learning now", "[%dm]" % (remainingSeconds // 60))
                    else :
                        self.addCount(absoluteOrPercent, kind, True, "learning now", "[%ds]" % remainingSeconds)
                    debug("""Thus we set it to be time {self.count[absoluteOrPercent][kind][True]["learning now"]}""")

    def setFlags(self):
        flagColor = {1:"red", 2:"orange",3:"green", 4:"blue"}
        for absoluteOrPercent in self.count:
            for kind in ["deck", "subdeck"]:
                hasFlag = False
                for i in range(1,5):
                    if self.count[absoluteOrPercent][kind][False].get(f"flag {i}"):
                        hasFlag = True
                        break
                value = "/".join([f"""<font color = {flagColor[i]}>{self.count[absoluteOrPercent][kind][True][f"flag {i}"]}</font>""" for i in range(1,5)])
                self.addCount(absoluteOrPercent, kind, True, "flags", conditionString(hasFlag, value))
                value = self.count[absoluteOrPercent][kind][True]["flag 0"]+"/"+value
                self.addCount(absoluteOrPercent,kind, True, "all flags", conditionString(hasFlag or self.count[absoluteOrPercent][kind][False].get("flag 0"), value))

    def setPairs(self):
        """Set text for columns which are pair"""
        for absoluteOrPercent in self.count:
            for kind in ["deck", "subdeck"]:
                for first,second in [("mature","young"),("notes","cards"), ("buried","suspended"), ("reviewed today","repeated today")]:
                    name = f"{first}/{second}"
                    firstValue = self.count[absoluteOrPercent][kind][True][first]
                    secondValue = self.count[absoluteOrPercent][kind][True][second]
                    values = conditionString(firstValue or secondValue, f"{firstValue}/{secondValue}")
                    self.addCount(absoluteOrPercent, kind, True, name, values)

    def setNowLaters(self):
        """ Set text for the pairs with cards to see now, and other to see later/another day"""
        for absoluteOrPercent in self.count:
            for kind in ["deck", "subdeck"]:
                for name, left, right in [
                    ("review",         "review today", "review later"),
                    ("unseen new",     "new today",    "unseen later"),
                    ("learning today", "learning now", "learning later today"),
                ]:
                    value = nowLater(self.count[absoluteOrPercent][kind][True][left], self.count[absoluteOrPercent][kind][True][right])
                    self.addCount(absoluteOrPercent, kind, True, name, value)

    def setText(self):
        self.setTextTime()
        self.setLearningAll()
        self.setFlags()
        self.setPairs()
        self.setNowLaters()

    # End of initialization
    ###########
    # Initialization tool

    def addCount(self, absoluteOrPercent, kind, isString, name,  value):
        """Ensure that self.count[absoluteOrPercent][kind][name] is defined and equals value"""
        debug("Adding {self.did}, {absoluteOrPercent}, {kind}, {isString}, {name}, {value}")
        self.count[absoluteOrPercent][kind][isString][name] = value
        if isString is False:
            if value:
                self.count[absoluteOrPercent][kind][True][name] = "{:,}".format(value)
            else:
                self.count[absoluteOrPercent][kind][True][name] = ""

    def addSet(self,kind,name,value):
        """Ensure that self.noteSet[kind][name] is defined and equals value"""
        self.noteSet[kind][name] = value

    ########################
    # Printing
    def emptyRow(self, cnt):
        if self.did == 1 and cnt > 1 and not self.children:
            # if the default deck is empty, hide it
            if not self.count["absolute"]["subdeck"][False]["cards"]:
                return True
        # parent toggled for collapsing
        for parent in mw.col.decks.parents(self.did):
            if parent['collapsed']:
                return True

    def getOpenTr(self):
        if self.did == mw.col.conf['curDeck']:
            klass = 'deck current'
        else:
            klass = 'deck'
        return start_line(klass,self.did)
    def getCss(self):
        cssStyle = ""
        for name, value in self.style.items():
            cssStyle += "%s:%s;" %(name,value)
        return cssStyle

    def getCollapse(self):
        self.deck = mw.col.decks.get(self.did) # We reload the deck. The collapsed state may have changed.
        prefix = "+" if self.deck['collapsed'] else "-"
        # deck link
        if self.children:
            return collapse_children_html(self.did,self.deck["name"],prefix)
        else:
            return collapse_no_child

    def getExtraClass(self):
        if self.deck['dyn']:
            return " filtered"
        else:
            return ""

    def getName(self, depth):
        return deck_name(depth,self.getCollapse(),self.getExtraClass(),self.did,self.getCss(),self.name)

    def getNumberColumns(self):
        buf = ""
        for conf in getUserOption("columns"):
          if conf.get("present",True):
            name = conf["name"]
            if name == "new":
                name = "new today" #It used to be called "new". Introduced back for retrocomputability.
                conf["name"] = "new today"
                writeConfig()
            if conf.get("percent",False):
                if conf.get("absolute",False):
                    number = "both"
                else:
                    number = "percent"
            else:
                number = "absolute"
            kind = "subdeck" if conf.get("subdeck",False) else "deck"
            if name == "bar":
                if not "names" in conf:
                    print("""A configuration whose name is "bar", should have a field "names".""", file = sys.stderr)
                    continue
                contents = self.makeBar(kind, conf["names"])
            else:
                countNumberKind = self.count[number][kind][True]
                if name not in countNumberKind:
                    if name not in warned :
                        warned.add(name)
                        debug("The add-on enhance main window does not know any column whose name is {name}. It thus won't be displayed. Please correct your add-on's configuration.", file = sys.stderr)
                    continue
                contents = countNumberKind[name]
            colour = getColor(conf)
            if contents == "": #In some case, we decided contents is empty. Instead of having complex value such as "0/0%" or "0(0)". Then we set it back to 0, which nicely summarize everything.
                contents = 0
            if contents in [0,"0","0%",""]:
                whatToDo = getUserOption("color zero")
                if whatToDo is False:
                    contents = ""
                elif isinstance(whatToDo,str):
                    colour = whatToDo
            buf += number_cell(colour, contents, getOverlay(conf))
        return buf

    def getOptionName(self):
        if getUserOption("option"):#If it's not filtered
            return deck_option_name(self.confName)
        return ""

    def htmlRow(self, col, depth, cnt):
        "Generate the HTML table cells for this row of the deck tree."
        if self.emptyRow(cnt):
            return ""
        return (
            self.getOpenTr()+
            self.getName(depth)+
            self.getNumberColumns()+
            gear(self.did)+
            self.getOptionName()+
            end_line +
            col._renderDeckTree(self.children, depth+1)
        )



def make(oldNode, endedParent = False, givenUpParent = False, pauseParent = False):
    """Essentially similar to DeckNode, but return an element already computed if it exists in the base"""
    did = idFromOldNode(oldNode)
    if oldNode is not idToOldNode.get(did):
       node = DeckNode(mw, oldNode, endedParent, givenUpParent, pauseParent)
       idToNode[did] = node
       idToOldNode[did]=oldNode
    return idToNode[did]

#based on Anki 2.0.36 aqt/deckbrowser.py DeckBrowser._renderDeckTree
def renderDeckTree(self, nodes, depth = 0):
    #Look at aqt/deckbrowser.py for a description of oldNode
    if not nodes:
        return ""
    if depth == 0:
        start = time.time()
        tree.computeValues()
        tree.computeTime()
        buf = f"""<style>{css}</style><script>{js}</script>{start_header}{deck_header}"""
        for colpos, conf in enumerate(getUserOption("columns")):
          if conf.get("present",True):
                buf += column_header(getHeader(conf),colpos)
        buf += option_header #for deck's option
        if getUserOption("option"):
            buf += option_name_header
        buf += end_header

        #convert nodes
        nodes = [make(node) for node in nodes]

        buf += self._topLevelDragRow()
    else:
        buf = ""
    for node in nodes:
        buf += self._deckRow(node, depth, len(nodes))
    if depth == 0:
        buf += self._topLevelDragRow()
        end = time.time()
        debug("printing tree was done in {end - start}")
    return buf



#based on Anki 2.0.45 aqt/main.py AnkiQt.onRefreshTimer
def onRefreshTimer():
    if mw.state == "deckBrowser":
        mw.deckBrowser._renderPage()  #was refresh, but we're disabling that
