# -*- coding: utf-8 -*-
# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

import copy
import json
import operator
import unicodedata

from anki.consts import *
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

    def load(self, decks, dconf):
        """Assign decks and dconf of this object using the two parameters.

        It also ensures that the number of cards per day is at most
        999999 or correct this error.

        Keyword arguments:
        decks -- json dic associating to each id (as string) its deck
        dconf -- json dic associating to each id (as string) its configuration(option)
        """
        self.decks = json.loads(decks)
        self.dconf = json.loads(dconf)
        # set limits to within bounds
        found = False
        for conf in list(self.dconf.values()):
            for type in ('rev', 'new'):
                pd = 'perDay'
                if conf[type][pd] > 999999:
                    conf[type][pd] = 999999
                    self.save(conf)
                    found = True
        if not found:
            self.changed = False

    def save(self, deckOrOption=None):
        """State that the DeckManager has been changed. Changes the
        mod and usn of the potential argument.

        The potential argument can be either a deck or a deck
        configuration.
        """
        if deckOrOption:
            deckOrOption['mod'] = intTime()
            deckOrOption['usn'] = self.col.usn()
        self.changed = True

    def flush(self):
        """Puts the decks and dconf in the db if the manager state that some
        changes happenned.
        """
        if self.changed:
            self.col.db.execute("update col set decks=?, dconf=?",
                                 json.dumps(self.decks),
                                 json.dumps(self.dconf))
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
        if deckToCopy is None:
            deckToCopy = defaultDeck
        name = name.replace('"', '')
        name = unicodedata.normalize("NFC", name)
        deck = self.byName(name)
        if deck:
            return int(deck["id"])
        if not create:
            return None
        deck = copy.deepcopy(deckToCopy)
        if "::" in name:
            # not top level; ensure all parents exist
            name = self._ensureParents(name)
        deck['name'] = name
        while 1:
            id = intTime(1000)
            if str(id) not in self.decks:
                break
        deck['id'] = id
        self.decks[str(id)] = deck
        self.save(deck)
        self.maybeAddToActive()
        runHook("newDeck")
        return int(id)

    def rem(self, did, cardsToo=False, childrenToo=True):
        """Remove the deck whose id is did.

        Does not delete the default deck, but rename it.

        Log the removal, even if the deck does not exists, assuming it
        is not default.

        Keyword arguments:
        cardsToo -- if set to true, delete its card.
        ChildrenToo -- if set to false,
        """
        if str(did) == '1':
            # we won't allow the default deck to be deleted, but if it's a
            # child of an existing deck then it needs to be renamed
            deck = self.get(did)
            if '::' in deck['name']:
                base = deck['name'].split("::")[-1]
                suffix = ""
                while True:
                    # find an unused name
                    name = base + suffix
                    if not self.byName(name):
                        deck['name'] = name
                        self.save(deck)
                        break
                    suffix += "1"
            return
        # log the removal regardless of whether we have the deck or not
        self.col._logRem([did], REM_DECK)
        # do nothing else if doesn't exist
        if not str(did) in self.decks:
            return
        deck = self.get(did)
        if deck['dyn']:
            # deleting a cramming deck returns cards to their previous deck
            # rather than deleting the cards
            self.col.sched.emptyDyn(did)
            if childrenToo:
                for name, id in self.children(did):
                    self.rem(id, cardsToo)
        else:
            # delete children first
            if childrenToo:
                # we don't want to delete children when syncing
                for name, id in self.children(did):
                    self.rem(id, cardsToo)
            # delete cards too?
            if cardsToo:
                # don't use cids(), as we want cards in cram decks too
                cids = self.col.db.list(
                    "select id from cards where did=? or odid=?", did, did)
                self.col.remCards(cids)
        # delete the deck and add a grave (it seems no grave is added)
        del self.decks[str(did)]
        # ensure we have an active deck.
        if did in self.active():
            self.select(int(list(self.decks.keys())[0]))
        self.save()

    def allNames(self, dyn=True):
        "An unsorted list of all deck names."
        if dyn:
            return [deck['name'] for deck in list(self.decks.values())]
        else:
            return [deck['name'] for deck in list(self.decks.values()) if not deck['dyn']]

    def all(self):
        "A list of all decks."
        return list(self.decks.values())

    def allIds(self):
        return list(self.decks.keys())

    def collapse(self, did):
        """Change the collapsed state of deck whose id is did. Then
        save the change."""
        deck = self.get(did)
        deck['collapsed'] = not deck['collapsed']
        self.save(deck)

    def collapseBrowser(self, did):
        """Change the browserCollapsed state of deck whose id is did. Then
        save the change."""
        deck = self.get(did)
        collapsed = deck.get('browserCollapsed', False)
        deck['browserCollapsed'] = not collapsed
        self.save(deck)

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

    def byName(self, name):
        """Get deck with NAME, ignoring case."""
        for deck in list(self.decks.values()):
            if self.equalName(deck['name'], name):
                return deck

    def update(self, deck):
        "Add or update an existing deck. Used for syncing and merging."
        self.decks[str(deck['id'])] = deck
        self.maybeAddToActive()
        # mark registry changed, but don't bump mod time
        self.save()

    def rename(self, deck, newName):
        """Rename the deck object g to newName. Updates
        children. Creates parents of newName if required.

        If newName already exists or if it a descendant of a filtered
        deck, the operation is aborted."""
        # make sure target node doesn't already exist
        if self.byName(newName):
            raise DeckRenameError(_("That deck already exists."))
        # make sure we're not nesting under a filtered deck
        for ancestor in self.parentsByName(newName):
            if ancestor['dyn']:
                raise DeckRenameError(_("A filtered deck cannot have subdecks."))
        # ensure we have parents
        newName = self._ensureParents(newName)
        # rename children
        for child in self.all():
            if child['name'].startswith(deck['name'] + "::"):
                child['name'] = child['name'].replace(deck['name']+ "::",
                                                  newName + "::", 1)
                self.save(child)
        # adjust name
        deck['name'] = newName
        # ensure we have parents again, as we may have renamed parent->child
        newName = self._ensureParents(newName)
        self.save(deck)
        # renaming may have altered active did order
        self.maybeAddToActive()

    def renameForDragAndDrop(self, draggedDeckDid, ontoDeckDid):
        """Rename the deck whose id is draggedDeckDid as a children of
        the deck whose id is ontoDeckDid."""
        draggedDeck = self.get(draggedDeckDid)
        draggedDeckName = draggedDeck['name']
        ontoDeckName = self.get(ontoDeckDid)['name']

        if ontoDeckDid is None or ontoDeckDid == '':
            #if the deck is dragged to toplevel
            if len(self._path(draggedDeckName)) > 1:
                #And is not already at top level
                self.rename(draggedDeck, self._basename(draggedDeckName))
        elif self._canDragAndDrop(draggedDeckName, ontoDeckName):
            #The following three lines seems to be useless, as they
            #repeat lines above
            draggedDeck = self.get(draggedDeckDid)
            draggedDeckName = draggedDeck['name']
            ontoDeckName = self.get(ontoDeckDid)['name']
            assert ontoDeckName.strip()
            self.rename(draggedDeck, ontoDeckName + "::" + self._basename(draggedDeckName))

    def _canDragAndDrop(self, draggedDeckName, ontoDeckName):
        """Whether draggedDeckName can be moved as a children of
        ontoDeckName.

        draggedDeckName should not be dragged onto a descendant of
        itself (nor itself).
        It should not either be dragged to its parent because the
        action would be useless.
        """
        if draggedDeckName == ontoDeckName \
            or self._isParent(ontoDeckName, draggedDeckName) \
            or self._isAncestor(draggedDeckName, ontoDeckName):
            return False
        else:
            return True

    def _isParent(self, parentDeckName, childDeckName):
        """Whether childDeckName is a direct child of parentDeckName."""
        return self._path(childDeckName) == self._path(parentDeckName) + [ self._basename(childDeckName) ]

    def _isAncestor(self, ancestorDeckName, descendantDeckName):
        """Whether ancestorDeckName is an ancestor of
        descendantDeckName; or itself."""
        ancestorPath = self._path(ancestorDeckName)
        return ancestorPath == self._path(descendantDeckName)[0:len(ancestorPath)]

    def _path(self, name):
        """Given a name, split according to ::"""
        return name.split("::")
    def _basename(self, name):
        """The part of name after the last ::"""
        return self._path(name)[-1]

    def _ensureParents(self, name):
        """Ensure parents exist, and return name with case matching parents.

        Parents are created if they do not already exists.
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
            did = self.id(ancestorName)
            # get original case
            ancestorName = self.name(did)
        name = ancestorName + "::" + path[-1]
        return name

    # Deck configurations
    #############################################################

    def allConf(self):
        "A list of all deck config object."
        return list(self.dconf.values())

    def confForDid(self, did):
        """The dconf object of the deck whose id is did.

        If did is the id of a dynamic deck, the deck is
        returned. Indeed, it has embedded conf.
        """
        deck = self.get(did, default=False)
        assert deck
        if 'conf' in deck:
            conf = self.getConf(deck['conf'])
            conf['dyn'] = False
            return conf
        # dynamic decks have embedded conf
        return deck

    def getConf(self, confId):
        """The dconf object whose id is confId."""
        return self.dconf[str(confId)]

    def updateConf(self, conf):
        """Add g to the set of dconf's. Potentially replacing a dconf with the
same id."""
        self.dconf[str(conf['id'])] = conf
        self.save()

    def confId(self, name, cloneFrom=None):
        """Create a new configuration and return its id.

        Keyword arguments
        cloneFrom -- The configuration copied by the new one."""
        if cloneFrom is None:
            cloneFrom = defaultConf
        conf = copy.deepcopy(cloneFrom)
        while 1:
            id = intTime(1000)
            if str(id) not in self.dconf:
                break
        conf['id'] = id
        conf['name'] = name
        self.dconf[str(id)] = conf
        self.save(conf)
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
            if str(deck['conf']) == str(id):
                deck['conf'] = 1
                self.save(deck)

    def setConf(self, deck, id):
        """Takes a deck objects, switch his id to id and save it as
        edited.

        Currently used in tests only."""
        deck['conf'] = id
        self.save(deck)

    def didsForConf(self, conf):
        """The dids of the decks using the configuration conf."""
        dids = []
        for deck in list(self.decks.values()):
            if 'conf' in deck and deck['conf'] == conf['id']:
                dids.append(deck['id'])
        return dids

    def restoreToDefault(self, conf):
        """Change the configuration to default.

        The only remaining part of the configuration are: the order of
        new card, the name and the id.
        """
        oldOrder = conf['new']['order']
        new = copy.deepcopy(defaultConf)
        new['id'] = conf['id']
        new['name'] = conf['name']
        self.dconf[str(conf['id'])] = new
        self.save(new)
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
            return deck['name']
        return _("[no deck]")

    def nameOrNone(self, did):
        """The name of the deck whose id is did, if it exists. None
        otherwise."""
        deck = self.get(did, default=False)
        if deck:
            return deck['name']
        return None

    def setDeck(self, cids, did):
        """Change the deck of the cards of cids to did.

        Keyword arguments:
        did -- the id of the new deck
        cids -- a list of ids of cards
        """
        self.col.db.execute(
            "update cards set did=?,usn=?,mod=? where id in "+
            ids2str(cids), did, self.col.usn(), intTime())

    def maybeAddToActive(self):
        """reselect current deck, or default if current has
        disappeared."""
        #It seems that nothing related to default happen in this code
        #nor in the function called by this code.
        #maybe is not appropriate, since no condition occurs
        deck = self.current()
        self.select(deck['id'])

    def cids(self, did, children=False):
        """Return the list of id of cards whose deck's id is did.

        If Children is set to true, returns also the list of the cards
        of the descendant."""
        if not children:
            return self.col.db.list("select id from cards where did=?", did)
        dids = [did]
        for name, id in self.children(did):
            dids.append(id)
        return self.col.db.list("select id from cards where did in "+
                                ids2str(dids))

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
            if self.normalizeName(deck['name']) in names:
                self.col.log("fix duplicate deck name", deck['name'])
                deck['name'] += "%d" % intTime(1000)
                self.save(deck)

            # ensure no sections are blank
            if not all(deck['name'].split("::")):
                self.col.log("fix deck with missing sections", deck['name'])
                deck['name'] = "recovered%d" % intTime(1000)
                self.save(deck)

            # immediate parent must exist
            if "::" in deck['name']:
                immediateParent = "::".join(deck['name'].split("::")[:-1])
                if self.normalizeName(immediateParent) not in names:
                    self.col.log("fix deck with missing parent", deck['name'])
                    self._ensureParents(deck['name'])
                    names.add(self.normalizeName(immediateParent))

            names.add(self.normalizeName(deck['name']))

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

    def select(self, did):
        """Change activeDecks to the list containing did and the did
        of its children.

        Also mark the manager as changed."""
        # make sure arg is an int
        did = int(did)
        # current deck
        self.col.conf['curDeck'] = did
        # and active decks (current + all children)
        actv = self.children(did)
        actv.sort()
        self.col.conf['activeDecks'] = [did] + [a[1] for a in actv]
        self.changed = True

    def children(self, did):
        "All children of did, as (name, id)."
        name = self.get(did)['name']
        actv = []
        for deck in self.all():
            if deck['name'].startswith(name + "::"):
                actv.append((deck['name'], deck['id']))
        return actv

    def childDids(self, did, childMap):
        #childmap is useless. Keep for consistency with anki.
        #sort was True by default, but never used.
        """The list of all ancestors of did, as deck objects.

        The list starts with the toplevel ancestors of did and its
        i-th element is the ancestor with i times ::.

        Keyword arguments:
        did -- the id of the deck we consider
        childMap -- dictionnary, associating to a deck id its node as returned by .childMap()"""
        def gather(node, arr):
            for did, child in node.items():
                arr.append(did)
                gather(child, arr)

        arr = []
        gather(childMap[did], arr)
        return arr

    def childMap(self):
        nameMap = self.nameMap()
        childMap = {}

        # go through all decks, sorted by name
        for deck in sorted(self.all(), key=operator.itemgetter("name")):
            node = {}
            childMap[deck['id']] = node

            # add note to immediate parent
            parts = deck['name'].split("::")
            if len(parts) > 1:
                immediateParent = "::".join(parts[:-1])
                pid = nameMap[immediateParent]['id']
                childMap[pid][deck['id']] = node

        return childMap

    def parents(self, did, nameMap=None):
        "All parents of did."
        # get parent and grandparent names
        ancestorsNames = []
        for part in self.get(did)['name'].split("::")[:-1]:
            if not ancestorsNames:
                ancestorsNames.append(part)
            else:
                ancestorsNames.append(ancestorsNames[-1] + "::" + part)
        # convert to objects
        for index, ancestor in enumerate(ancestorsNames):
            if nameMap:
                deck = nameMap[ancestor]
            else:
                deck = self.get(self.id(ancestor))
            ancestorsNames[index] = deck
        return ancestorsNames

    def parentsByName(self, name):
        "All existing parents of name"
        if "::" not in name:
            return []
        names = name.split("::")[:-1]
        head = []
        ancestorsNames = []

        while names:
            head.append(names.pop(0))
            deck = self.byName("::".join(head))
            if deck:
                ancestorsNames.append(deck)

        return ancestorsNames

    def nameMap(self):
        """
        Dictionnary from deck name to deck object.
        """
        return dict((deck['name'], deck) for deck in self.decks.values())

    # Sync handling
    ##########################################################################

    def beforeUpload(self):
        for deck in self.all():
            deck['usn'] = 0
        for conf in self.allConf():
            conf['usn'] = 0
        self.save()

    # Dynamic decks
    ##########################################################################

    def newDyn(self, name):
        "Return a new dynamic deck and set it as the current deck."
        did = self.id(name, deckToCopy=defaultDynamicDeck)
        self.select(did)
        return did

    def isDyn(self, did):
        return self.get(did)['dyn']

    @staticmethod
    def normalizeName(name):
        return unicodedata.normalize("NFC", name.lower())

    @staticmethod
    def equalName(name1, name2):
        return DeckManager.normalizeName(name1) == DeckManager.normalizeName(name2)
