# -*- coding: utf-8 -*-
# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

import copy
import json
import operator
import unicodedata

from anki.consts import *
from anki.dconf import DConf
from anki.deck import Deck
from anki.errors import DeckRenameError
from anki.hooks import runHook
from anki.lang import _
from anki.utils import ids2str, intTime, json

"""This module deals with decks and their configurations.

self.decks is the dictionnary associating an id to the deck with this id
self.dconf is the dictionnary associating an id to the dconf with this id

A deck is a dict composed of:
new/rev/lrnToday -- two number array.
            First one is currently unused
            The second one is equal to the number of cards seen today in this deck minus the number of new cards in custom study today.
 BEWARE, it's changed in anki.sched(v2).Scheduler._updateStats and anki.sched(v2).Scheduler._updateCutoff.update  but can't be found by grepping 'newToday', because it's instead written as type+"Today" with type which may be new/rev/lrnToday
timeToday -- two number array used somehow for custom study,  seems to be currently unused
conf -- (string) id of option group from dconf, or absent in dynamic decks
usn -- Update sequence number: used in same way as other usn vales in db
desc -- deck description, it is shown when cards are learned or reviewd
dyn -- 1 if dynamic (AKA filtered) deck,
collapsed -- true when deck is collapsed,
extendNew -- extended new card limit (for custom study). Potentially absent, only used in aqt/customstudy.py. By default 10
extendRev -- extended review card limit (for custom study), Potentially absent, only used in aqt/customstudy.py. By default 10.
name -- name of deck,
browserCollapsed -- true when deck collapsed in browser,
id -- deck ID (automatically generated long),
mod -- last modification time,
mid -- the model of the deck
"""



"""A configuration of deck is a dictionnary composed of:
name -- its name, including the parents, and the "::"




A configuration of deck (dconf) is composed of:
name -- its name
new -- The configuration for new cards, see below.
lapse -- The configuration for lapse cards, see below.
rev -- The configuration for review cards, see below.
maxTaken -- The number of seconds after which to stop the timer
timer -- whether timer should be shown (1) or not (0)
autoplay -- whether the audio associated to a question should be
played when the question is shown
replayq -- whether the audio associated to a question should be
played when the answer is shown
mod -- Last modification time
usn -- see USN documentation
dyn -- Whether this deck is dynamic. Not present in the default configurations
id -- deck ID (automatically generated long). Not present in the default configurations.

The configuration related to new cards is composed of:
delays -- The list of successive delay between the learning steps of
the new cards, as explained in the manual.
ints -- The delays according to the button pressed while leaving the
learning mode.
initial factor -- The initial ease factor
separate -- delay between answering Good on a card with no steps left, and seeing the card again. Seems to be unused in the code
order -- In which order new cards must be shown. NEW_CARDS_RANDOM = 0
and NEW_CARDS_DUE = 1
perDay -- Maximal number of new cards shown per day
bury -- Whether to bury cards related to new cards answered

The configuration related to lapses card is composed of:
delays -- The delays between each relearning while the card is lapsed,
as in the manual
mult -- percent by which to multiply the current interval when a card
goes has lapsed
minInt -- a lower limit to the new interval after a leech
leechFails -- the number of lapses authorized before doing leechAction
leechAction -- What to do to leech cards. 0 for suspend, 1 for
mark. Numbers according to the order in which the choices appear in
aqt/dconf.ui


The configuration related to review card is composed of:
perDay -- Numbers of cards to review per day
ease4 -- the number to add to the easyness when the easy button is
pressed
fuzz -- The new interval is multiplied by a random number between
-fuzz and fuzz
minSpace -- not currently used
ivlFct -- multiplication factor applied to the intervals Anki
generates
maxIvl -- the maximal interval for review
bury -- If True, when a review card is answered, the related cards of
its notes are buried
"""

# fixmes:
# - make sure users can't set grad interval < 1

defaultDeck = {
    'newToday': [0, 0], # currentDay, count
    'revToday': [0, 0],
    'lrnToday': [0, 0],
    'timeToday': [0, 0], # time in ms
    'conf': 1,
    'usn': 0,
    'desc': "",
    'dyn': DECK_STD,  # anki uses int/bool interchangably here
    'collapsed': False,
    # added in beta11
    'extendNew': 10,
    'extendRev': 50,
}

defaultDynamicDeck = {
    'newToday': [0, 0],
    'revToday': [0, 0],
    'lrnToday': [0, 0],
    'timeToday': [0, 0],
    'collapsed': False,
    'dyn': DECK_DYN,
    'desc': "",
    'usn': 0,
    'delays': None,
    'separate': True,
     # list of (search, limit, order); we only use first two elements for now
    'terms': [["", 100, 0]],
    'resched': True,
    'return': True, # currently unused

    # v2 scheduler
    "previewDelay": 10,
}

defaultConf = {
    'name': _("Default"),
    'new': {
        'delays': [1, 10],
        'ints': [1, 4, 7], # 7 is not currently used
        'initialFactor': STARTING_FACTOR,
        'separate': True,
        'order': NEW_CARDS_DUE,
        'perDay': 20,
        # may not be set on old decks
        'bury': False,
    },
    'lapse': {
        'delays': [10],
        'mult': 0,
        'minInt': 1,
        'leechFails': 8,
        # type 0=suspend, 1=tagonly
        'leechAction': LEECH_SUSPEND,
    },
    'rev': {
        'perDay': 200,
        'ease4': 1.3,
        'fuzz': 0.05,
        'minSpace': 1, # not currently used
        'ivlFct': 1,
        'maxIvl': 36500,
        # may not be set on old decks
        'bury': False,
        'hardFactor': 1.2,
    },
    'maxTaken': 60,
    'timer': 0,
    'autoplay': True,
    'replayq': True,
    'mod': 0,
    'usn': 0,
}

class DeckManager:

    """
    col -- the collection associated to this Deck manager
    decks -- associating to each id (as string) its deck
    dconf -- associating to each id (as string) its configuration(option)
    """
    # Registry save/load
    #############################################################

    def __init__(self, col):
        """State that the collection of the created object is the first argument."""
        self.col = col
        self.decks = {}
        self.dconf = {}

    def load(self, decks, dconf):
        """Assign decks and dconf of this object using the two parameters.

        It also ensures that the number of cards per day is at most
        999999 or correct this error.

        Keyword arguments:
        decks -- json dic associating to each id (as string) its deck.
        dconf -- json dic associating to each id (as string) its configuration(option)
        """
        self.changed = False
        self.loadDeck(decks)
        self.loadConf(dconf)

    def loadDeck(self, decks=None):
        """If decks is not provided, reload current deck collection"""
        if decks is None:
            decks = self.decks
        else:
            decks = json.loads(decks)
        self.decks = {}
        self.decksByNames = {}
        for deck in decks.values():
            deck = Deck(self, deck)
            deck.addInManager()

    def loadConf(self, dconf):
        self.dconf = {}
        for dconf in json.loads(dconf).values():
            dconf = DConf(self, dconf)
            self.dconf[str(dconf['id'])] = dconf

    def save(self):
        """State that the DeckManager has been changed. Changes the
        mod and usn of the potential argument.

        The potential argument can be either a deck or a deck
        configuration.
        """
        self.changed = True

    def flush(self):
        """Puts the decks and dconf in the db if the manager state that some
        changes happenned.
        """
        if self.changed:
            self.col.db.execute("update col set decks=?, dconf=?",
                                 json.dumps(self.decks, default=lambda model: model.dumps()),
                                 json.dumps(self.dconf, default=lambda model: model.dumps()))
            self.changed = False

    # Deck save/load
    #############################################################

    def id(self, name, create=True, deckToCopy=None):
        """Returns a deck's id with a given name. Potentially creates it.

        Keyword arguments:
        name -- the name of the new deck. " are removed.
        create -- States whether the deck must be created if it does
        not exists. Default true, otherwise return None
        deckToCopy -- A deck to copy in order to create this deck
        """
        deck = self.byName(name, create=create, deckToCopy=deckToCopy)
        if deck:
            return int(deck.getId())

    def rem(self, did, cardsToo=False, childrenToo=True):
        """Remove the deck whose id is did.

        Does not delete the default deck, but rename it.

        Log the removal, even if the deck does not exists, assuming it
        is not default.

        Keyword arguments:
        cardsToo -- if set to true, delete its card.
        ChildrenToo -- if set to false,
        """
        # Here and not directly in Deck, because we need to delete
        # decks from id non existing.
        if str(did) in self.decks:
            self.get(did, default=False).rem(cardsToo, childrenToo)
        else:
            # log the removal regardless of whether we have the deck or not.
            # This is done in rem when the deck exists.
            self.col._logRem([did], REM_DECK)

    def allNames(self, dyn=None, forceDefault=True, sort=False):
        """A list of all deck names.

        Keyword arguments:
        dyn -- What kind of decks to get
        sort -- whether to sort
        """
        decks = self.all(dyn=dyn, forceDefault=forceDefault, sort=sort)
        return [deck['name'] for deck in decks]

    def all(self, sort=False, forceDefault=True, dyn=None):
        """A list of all deck objects.

        dyn -- What kind of decks to get
        standard -- whether to incorporate non dynamic deck
        """
        decks = list(self.decks.values())
        if not forceDefault and not self.col.db.scalar("select 1 from cards where did = 1 limit 1") and len(decks)>1:
            decks = [deck for deck in decks if deck['id'] != 1]
        if dyn is not None:
            decks = [deck for deck in decks if deck['dyn']==dyn]
        if sort:
            decks.sort(key=lambda deck: deck.getPath())
        return decks

    def allIds(self, sort=False, dyn=None):
        """A list of all deck's id.

        sort -- whether to sort by name"""
        return [deck["id"] for deck in self.all(sort=sort, dyn=dyn)]

    def count(self):
        """The number of decks."""
        return len(self.decks)

    def get(self, did, default=True):
        """Returns the deck objects whose id is did.

        If Default, return the default deck, otherwise None.

        """
        id = str(did)
        if id in self.decks:
            return self.decks[id]
        elif default:
            return self.decks['1']

    def byName(self, name, create=False, deckToCopy=None):
        """Get deck with NAME, ignoring case.

        Keyword arguments:
        name -- the name of the new deck. " are removed.
        create -- States whether the deck must be created if it does
        not exists. Default true, otherwise return None
        deckToCopy -- A deck to copy in order to create this deck
        """
        name = name.replace('"', '')
        name = unicodedata.normalize("NFC", name)
        normalized = self.normalizeName(name)
        if normalized in self.decksByNames:
            return self.decksByNames[normalized]

        if create is False:
            return None
        if deckToCopy is None:
            deckToCopy = defaultDeck
        if isinstance(deckToCopy, dict):
            # useful mostly in tests where decks are given directly as dic
            deck = Deck(self, copy.deepcopy(deckToCopy))
            deck.cleanCopy(name)
            return deck
        else:
            assert isinstance(deckToCopy, Deck)
            return deckToCopy.copy_(name)

    def _isParent(self, parentDeckName, childDeckName, normalize=True):
        """Whether childDeckName is a direct child of parentDeckName."""
        if normalize:
            parentDeckName = self.normalizeName(parentDeckName)
            childDeckName = self.normalizeName(childDeckName)
        return self._path(childDeckName) == self._path(parentDeckName) + [ self._basename(childDeckName) ]

    def _isAncestor(self, ancestorDeckName, descendantDeckName, normalize=True):
        """Whether ancestorDeckName is an ancestor of
        descendantDeckName; or itself."""
        if normalize:
            ancestorDeckName = self.normalizeName(ancestorDeckName)
            descendantDeckName = self.normalizeName(descendantDeckName)
        ancestorPath = self._path(ancestorDeckName)
        return ancestorPath == self._path(descendantDeckName)[0:len(ancestorPath)]

    @staticmethod
    def _path(name):
        """The list of decks and subdecks of name"""
        return name.split("::")

    @staticmethod
    def _basename(name):
        """The name of the last subdeck, without its ancestors"""
        return DeckManager._path(name)[-1]

    @staticmethod
    def parentName(name):
        """The name of the parent of this deck, or None if there is none"""
        return "::".join(DeckManager._path(name)[:-1])

    def _ensureParents(self, name):
        """Ensure parents exist, and return name with case matching parents.

        Parents are created if they do not already exists.
        If a dynamic deck is found, return false
        """
        ancestorName = ""
        path = self._path(name)
        if len(path) < 2:
            return name
        for pathPiece in path[:-1]:
            if not ancestorName:
                ancestorName += pathPiece
            else:
                ancestorName += "::" + pathPiece
            # fetch or create
            deck = self.byName(ancestorName, create=True)
            if deck.isDyn():
                return False
            # get original case
            ancestorName = deck.getName()
        name = ancestorName + "::" + path[-1]
        return name

    # Deck configurations
    #############################################################

    def allConf(self):
        "A list of all deck config object."
        return list(self.dconf.values())

    def getConf(self, confId):
        """The dconf object whose id is confId."""
        return self.dconf[str(confId)]

    def updateConf(self, conf):
        """Add g to the set of dconf's. Potentially replacing a dconf with the
same id."""
        self.dconf[str(conf.getId())] = conf
        self.save()

    def confId(self, name, cloneFrom=None):
        """Create a new configuration and return its id.

        Keyword arguments
        cloneFrom -- The configuration copied by the new one."""
        if cloneFrom is None:
            cloneFrom = defaultConf
        if not isinstance(cloneFrom, DConf):
            # This is in particular the case in tests, where confs are
            # given directly as dic.
            cloneFrom = DConf(self, cloneFrom)
        conf = cloneFrom.deepcopy()
        while 1:
            id = intTime(1000)
            if str(id) not in self.dconf:
                break
        conf['id'] = id
        conf.setName(name)
        self.dconf[str(id)] = conf
        conf.save()
        return id

    def remConf(self, id):
        """Remove a configuration and update all decks using it.

        The new conf of the deck using this configuation is the
        default one.

        Keyword arguments:
        id -- The id of the configuration to remove. Should not be the
        default conf."""
        assert int(id) != 1
        self.col.modSchema(check=True)
        del self.dconf[str(id)]
        for deck in self.all():
            # ignore cram decks
            if 'conf' not in deck:
                continue
            if str(deck.getConfId()) == str(id):
                deck.setDefaultConf()
                deck.save()

    def didsForConf(self, conf):
        """The dids of the decks using the configuration conf."""
        dids = []
        for deck in list(self.decks.values()):
            if 'conf' in deck and deck.getConfId() == conf.getId():
                dids.append(deck.getId())
        return dids

    def restoreToDefault(self, conf):
        """Change the configuration to default.

        The only remaining part of the configuration are: the order of
        new card, the name and the id.
        """
        oldOrder = conf['new']['order']
        new = copy.deepcopy(defaultConf)
        new['id'] = conf.getId()
        new.setName(conf.getName())
        self.dconf[str(conf.getId())] = new
        new.save()
        # if it was previously randomized, resort
        if not oldOrder:
            self.col.sched.resortConf(new)

    # Deck utils
    #############################################################

    def name(self, did, default=False):
        """The name of the deck whose id is did.

        If no such deck exists: if default is set to true, then return
        default deck's name. Otherwise return "[no deck]".
        """
        deck = self.get(did, default=default)
        if deck:
            return deck.getName()
        return _("[no deck]")

    def nameOrNone(self, did):
        """The name of the deck whose id is did, if it exists. None
        otherwise."""
        deck = self.get(did, default=False)
        if deck:
            return deck.getName()
        return None

    def maybeAddToActive(self):
        """reselect current deck, or default if current has
        disappeared."""
        #It seems that nothing related to default happen in this code
        #nor in the function called by this code.
        #maybe is not appropriate, since no condition occurs
        deck = self.current()
        deck.select()

    def _recoverOrphans(self):
        """Move the cards whose deck does not exists to the default
        deck, without changing the mod date."""
        dids = list(self.decks.keys())
        mod = self.col.db.mod
        self.col.db.execute("update cards set did = 1 where did not in "+
                            ids2str(dids))
        self.col.db.mod = mod

    def _checkDeckTree(self):
        decks = self.col.decks.all()
        decks.sort(key=operator.itemgetter('name'))
        names = set()

        for deck in decks:
            # two decks with the same name?
            if self.normalizeName(deck.getName()) in names:
                self.col.log("fix duplicate deck name", deck.getName())
                deck.setName(deck.getName() + "%d" % intTime(1000))
                deck.save()

            # ensure no sections are blank
            if not all(deck.getName().split("::")):
                self.col.log("fix deck with missing sections", deck.getName())
                deck['name'] = "recovered%d" % intTime(1000)
                deck.save()

            # immediate parent must exist
            immediateParent = self.parentName(deck.getName())
            if immediateParent and immediateParent not in names:
                self.col.log("fix deck with missing parent", deck.getName())
                self._ensureParents(deck.getName())
                names.add(self.normalizeName(immediateParent))

            names.add(self.normalizeName(deck.getName()))

    def checkIntegrity(self):
        self._recoverOrphans()
        self._checkDeckTree()

    # Deck selection
    #############################################################

    def active(self):
        "The currrently active dids. Make sure to copy before modifying."
        return self.col.conf['activeDecks']

    def selected(self):
        """The did of the currently selected deck."""
        return self.col.conf['curDeck']

    def current(self):
        """The currently selected deck object"""
        return self.get(self.selected())

    # Sync handling
    ##########################################################################

    def beforeUpload(self):
        for deck in self.all():
            deck.beforeUpload()
        for conf in self.allConf():
            conf.beforeUpload()
        self.save()

    # Dynamic decks
    ##########################################################################

    def newDyn(self, name):
        "Return a new dynamic deck and set it as the current deck."
        deck = self.byName(name, create=True, deckToCopy=defaultDynamicDeck)
        deck.select()
        return deck

    @staticmethod
    def normalizeName(name):
        return unicodedata.normalize("NFC", name.lower())

    @staticmethod
    def equalName(name1, name2):
        return DeckManager.normalizeName(name1) == DeckManager.normalizeName(name2)
