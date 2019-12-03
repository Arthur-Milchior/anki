import bisect
import copy

import anki.consts
from anki.consts import *
from anki.dconf import DConf
from anki.errors import DeckRenameError
from anki.hooks import runHook
from anki.lang import _
from anki.model import Model
from anki.utils import DictAugmentedDyn, ids2str, intTime

NO_VALUES = 0
LIMS = 1
NUMS = 2

class Deck(DictAugmentedDyn):
    """

    childrenBaseNames -- the ordered list of base names
    childrenDict -- dict from base name to children
    parent -- parent deck. For top level, it's the set of toplevel elements. For this set, it's None.
    """
    def __init__(self, manager, dict, parent, exporting=False):
        self.resetted = NO_VALUES
        self.parent = parent
        self.childrenBaseNames = []
        self.childrenDict = {}
        self.exporting = exporting
        self.count = {}
        super().__init__(manager, dict)
        if self.parent is not None:
            self.parent.addChild(self)
        else:
            assert self.exporting or self.isAboveTopLevel()
            # no need for parent when exporting, since the deck won't be modified

    def addInModel(self):
        """Adding or replacing the deck with our id in the manager"""
        self.manager.decks[str(self.getId())] = self
        self.manager.decksByNames[self.getNormalizedName()] = self

    def copy_(self, name):
        deck = self.deepcopy()
        deck.cleanCopy(name)
        return deck

    def cleanCopy(self, name):
        """To be called when a deck is copied"""
        if "::" in name:
            # not top level; ensure all parents exist
            parent, name = self.manager._ensureParents(name)
        self.setName(name)
        while 1:
            id = intTime(1000)
            if str(id) not in self.manager.decks:
                break
        self.setId(id)
        self.addInModel()
        self.save()
        self.manager.maybeAddToActive()
        runHook("newDeck")

    def rem(self, cardsToo=False, childrenToo=True):
        """Remove the deck whose id is did.

        Does not delete the default deck, but rename it.

        Log the removal, even if the deck does not exists, assuming it
        is not default.

        Keyword arguments:
        cardsToo -- if set to true, delete its card.
        ChildrenToo -- if set to false,
        """
        assert not self.exporting
        if str(self.getId()) == '1':
            # we won't allow the default deck to be deleted, but if it's a
            # child of an existing deck then it needs to be renamed
            if '::' in self.getName():
                base = self.manager._basename(self.getName())
                suffix = ""
                while True:
                    # find an unused name
                    name = base + suffix
                    if not self.manager.byName(name):
                        self.setName(name)
                        self.save()
                        break
                    suffix += "1"
            return
        # log the removal regardless of whether we have the deck or not
        self.manager.col._logRem([self.getId()], REM_DECK)
        if self.isDyn():
            # deleting a cramming deck returns cards to their previous deck
            # rather than deleting the cards
            self.manager.col.sched.emptyDyn(self.getId())
            if childrenToo:
                for id in self.getDescendantsIds():
                    self.manager.rem(id, cardsToo)
        else:
            # delete children first
            if childrenToo:
                # we don't want to delete children when syncing
                for id in self.getDescendantsIds():
                    self.manager.rem(id, cardsToo)
            # delete cards too?
            if cardsToo:
                # don't use cids(), as we want cards in cram decks too
                cids = self.manager.col.db.list(
                    "select id from cards where did=? or odid=?", self.getId(), self.getId())
                self.manager.col.remCards(cids)
        # delete the deck and add a grave (it seems no grave is added)
        if not self.isAboveTopLevel():
            self.parent.removeChild(self)
        del self.manager.decks[str(self.getId())]
        del self.manager.decksByNames[self.getNormalizedName()]
        # ensure we have an active deck.
        if self.getId() in self.manager.active():
            self.manager.all()[0].select()
        self.manager.save()

    def rename(self, newName):
        """Rename the deck object g to newName. Updates
        children. Creates parents of newName if required.

        If newName already exists or if it a descendant of a filtered
        deck, the operation is aborted."""
        # ensure we have parents
        assert not self.exporting
        parent, newName = self.manager._ensureParents(newName)
        # make sure we're not nesting under a filtered deck
        if newName is False:
            raise DeckRenameError(_("A filtered deck cannot have subdecks."))
        # make sure target node doesn't already exist
        if self.manager.byName(newName):
            raise DeckRenameError(_("That deck already exists."))
        self.parent.removeChild(self)
        # rename children
        oldName = self.getName()
        for child in self.getDescendants(includeSelf=True):
            del self.manager.decksByNames[child.getNormalizedName()]
            child.setName(child.getName().replace(oldName, newName, 1))
            child.addInModel()
            child.save()
        # ensure we have parents again, as we may have renamed parent->child
        parent, newName = self.manager._ensureParents(newName)
        self.parent = parent
        self.parent.addChild(self)
        # renaming may have altered active did order
        self.manager.maybeAddToActive()

    def renameForDragAndDrop(self, ontoDeckDid):
        """Rename the deck whose id is draggedDeckDid as a children of
        the deck whose id is ontoDeckDid."""
        assert not self.exporting
        draggedDeckName = self.getName()
        ontoDeck = self.manager.get(ontoDeckDid)
        ontoDeckName = ontoDeck.getName()
        if ontoDeckDid is None or ontoDeckDid == '':
            #if the deck is dragged to toplevel
            if not self.isTopLevel():
                #And is not already at top level
                self.rename(self.manager._basename(draggedDeckName))
        elif self._canDragAndDrop(ontoDeck):
            #The following three lines seems to be useless, as they
            #repeat lines above
            draggedDeckName = self.getName()
            ontoDeckName = self.manager.get(ontoDeckDid).getName()
            assert ontoDeckName.strip()
            self.rename(ontoDeckName + "::" + self.manager._basename(draggedDeckName))

    def _canDragAndDrop(self, ontoDeck):
        """Whether draggedDeckName can be moved as a children of
        ontoDeckName.

        draggedDeckName should not be dragged onto a descendant of
        itself (nor itself).
        It should not either be dragged to its parent because the
        action would be useless.
        """
        if self == ontoDeck \
            or ontoDeck.isParentOf(self) \
            or self.isAncestorOf(ontoDeck):
            return False
        else:
            return True

    def update(self):
        "Add or update an existing deck. Used for syncing and merging."
        self.manager.decks[str(self.getId())] = self
        self.manager.maybeAddToActive()
        # mark registry changed, but don't bump mod time
        self.addInModel()

    # Name family
    #############################################################

    def isTopLevel(self):
        return "::" not in self.getName() and not self.isAboveTopLevel()

    def isAboveTopLevel(self):
        return self.getName() == ""

    def directLine(self):
        return self.getAncestors(includeSelf=True) + self.getDescendants()

    def getParentName(self):
        return self.manager.parentName(self.getName())

    def getParent(self):
        return self.manager.byName(self.getParentName())

    def getAncestorsNames(self, includeSelf=False):
        return [deck.getName() for deck in self.getAncestors(includeSelf)]

    def getAncestors(self, includeSelf=False):
        l = []
        current = self if includeSelf else self.parent
        while not current.isAboveTopLevel() :
            l.append(current)
            current = current.parent
        l.reverse()
        return l

    def getBaseName(self):
        return self.manager._basename(self.getName())

    def getNormalizedName(self):
        return self.manager.normalizeName(self.getName())

    def getNormalizedBaseName(self):
        return self.manager.normalizeName(self.getBaseName())

    def getPath(self):
        return self.manager._path(self.getName())

    ## Child

    def getChildren(self):
        return [self.childrenDict.get(name) for name in self.getChildrenNormalizedBaseNames()]

    def getChild(self, name):
        name = self.manager.normalizeName(name)
        return self.childrenDict.get(name)

    def getChildrenIds(self):
        return [child.getId() for child in self.getChildren()]

    def getChildrenNormalizedBaseNames(self):
        return self.childrenBaseNames

    def addChild(self, child, loading=False):
        if self.exporting:
            return
        childNormalizedBaseName = child.getNormalizedBaseName()
        if self.isDyn():
            if loading:
                child.renameForDragOnto(self.manager.topLevel)
            else:
                raise DeckRenameError(_("A filtered deck cannot have subdecks. This action should have not gone so far."))
        if childNormalizedBaseName in self.childrenDict:
            if loading:
                # two decks with the same name?
                self.manager.col.log("fix duplicate deck name", deck['name'])
                child.changeBaseName(child.getBaseName + "%d" % intTime(1000))
            else:
                raise DeckRenameError(_("We're trying to add twice the same child. This should not have gono so far."))
        bisect.insort(self.childrenBaseNames, childNormalizedBaseName)
        self.childrenDict[childNormalizedBaseName] = child

    def removeChild(self, child):
        # as in example https://docs.python.org/fr/3/library/bisect.html
        assert not self.exporting
        baseName = child.getNormalizedBaseName()
        i = bisect.bisect_left(self.childrenBaseNames, baseName)
        if i != len(self.childrenBaseNames) and self.childrenBaseNames[i] == baseName:
            self.childrenBaseNames.pop(i)
        del self.childrenDict[baseName]

    def getDescendants(self, includeSelf=False):
        l = [greatChildren for child in self.getChildren() for greatChildren in child.getDescendants(includeSelf=True)]
        if includeSelf:
            l = [self] + l
        return l

    def getDescendantsIds(self, includeSelf=False, sort=False):
        #sort was True by default, but never used.
        """The list of all descendant of did, as deck ids, ordered alphabetically

        The list starts with the toplevel ancestors of did and its
        i-th element is the ancestor with i times ::.

        Keyword arguments:
        did -- the id of the deck we consider
        """
        # get ancestors names
        return [deck.getId() for deck in self.getDescendants(includeSelf=includeSelf)]

    ## Tests:
    def isParentOf(self, other):
        otherParent = other.getParent()
        if otherParent is None:
            return False
        return otherParent == self

    def isChildOf(self, other):
        return other.isParentOf(self)

    def isAncestorOf(self, other, includeSelf=False):
        if includeSelf and self == other:
            return True
        return self.manager._isAncestor(self.getName(), other.getName())

    def isDescendantOf(self, other, includeSelf=False):
        if includeSelf and self == other:
            return True
        return self.manager._isAncestor(other.getName(), self.getName())

    # Getter/Setter
    #############################################################

    def isDefault(self):
        return str(self.getId()) == "1"

    # Deck utils
    #############################################################

    def getCids(self, children=False):
        """Return the list of id of cards whose deck's id is did.

        If Children is set to true, returns also the list of the cards
        of the descendant."""
        if not children:
            return self.col.db.list("select id from cards where did=?", self.getId())
        dids = self.getDescendantsIds(includeSelf=True)
        return self.manager.col.db.list("select id from cards where did in "+
                                ids2str(dids))

    # Conf
    #############################################################

    def getConfId(self):
        return self.get('conf')

    def getConf(self):
        if self.isStd():
            conf = self.manager.getConf(self['conf'])
            conf.setStd()
            return conf
        # dynamic decks have embedded conf
        return self

    def setConf(self, conf):
        """Takes a deck objects, switch his id to id and save it as
        edited.

        Currently used in tests only."""
        assert not self.isAboveTopLevel()
        if isinstance(conf, int):
            self['conf'] = conf
        else:
            assert isinstance(conf, DConf)
            self['conf'] = conf.getId()
        self.save()
        # if limit changed, it may change actual limits of
        # descendants, and thus the total number of cards of ancestors
        if not self.exporting:
            for deck in self.directLine():
                deck.resetted = NO_VALUES

    def isDefaultConf(self):
        return self.getConfId() == 1

    def setDefaultConf(self):
        self.setConf(1)

    # Model
    #############################################################

    def getModel(self):
        self.manager.col.models.get(self.get('mid'), orNone=True)

    def setModel(self, model):
        if isinstance(model, int):
            self['mid'] = model
        else:
            assert(isinstance(model, Model))
            self['mid'] = model.getId()

    # Graphical
    #############################################################

    def collapse(self):
        self['collapsed'] = not self['collapsed']
        self.save()

    def collapseBrowser(self):
        deck['browserCollapsed'] = not deck.get('browserCollapsed', False)
        self.save()

    # Deck selection
    #############################################################

    def select(self):
        """Change activeDecks to the list containing did and the did
        of its children.

        Also mark the manager as changed."""
        assert not self.isAboveTopLevel()
        # make sure arg is an int
        did = int(self.getId())
        # current deck
        self.manager.col.conf['curDeck'] = did
        # and active decks (current + all children)
        self.manager.col.conf['activeDecks'] = self.getDescendantsIds(sort=True, includeSelf=True)
        self.manager.changed = True

    # Cards informations
    #############################################################

    def setLims(self):
        """Set all limits.

        """
        if self.resetted >= LIMS:
            return
        if not self.isTopLevel():
            self.parent.setLims()
        self.count['lim'] = {}
        for what in ('rev', 'new'):
            limName = f'_{what}Lim'
            if self.isDyn():
                self.count['lim'][what] = self.manager.col.sched.reportLimit
            else:
                self.count['lim'][what] = max(0, self.getConf()[what]['perDay'] - self[what+'Today'][1])
            if not self.isTopLevel():
                self.count['lim'][what] = min(self.count['lim'][what], self.parent.count['lim'][what])
        self.resetted = LIMS

    def setNums(self):
        """Set numbers related to this deck.

        """
        if self.resetted < LIMS:
            self.setLims()
        if self.resetted >= NUMS:
            return
        self.resetted = NUMS # this can create a problem in case of asynchronous. Currently ok.
        self.count['single'] = dict()
        d = {'did': self.getId(),
             'today': self.manager.col.sched.today,
             'cutoff': self.manager.col.sched.dayCutoff
        }
        for keys, query in [
                # unseen: cards which never graduated and are not in learning.
                # new: unseen cards to see today (limits are are applied below)
                (['unseen', 'new'], f"""select count() from cards where did = :did and queue = {QUEUE_NEW}"""),
                # allrev: number of cards already seen that should be reviewed
                # today and are not in learning
                # rev: same as due, with deck limit taken into account
                (['allRev', 'rev'], f"""select count() from cards where did = :did and queue = {QUEUE_REV} and due <= :today """),
                # lrn today/other day: cards in learning mode to see now,
                # where next review is the same day/another day as last review
                (['lrn today'], f""" select sum(left/1000) from
        (select left from cards where did = :did and queue = {QUEUE_LRN}
        and due < :cutoff)"""),
                (['lrn other day'], f"""
        select count() from cards where did = :did and queue = {QUEUE_DAY_LRN}
        and due <= :today """),
                ]:
            value = self.manager.col.db.scalar(query, **d) or 0
            for key in keys:
                self.count['single'][key] = value
        # lrn: cards that must be learn now
        self.count['single']['lrn'] = self.count['single']['lrn today'] + self.count['single']['lrn other day']

        self.count[''] = self.count['single'].copy()
        for child in self.childrenDict.values():
            child.setNums()
            for kind in self.count['single']:
                self.count[''][kind] += child.count[''][kind]

        self.count['']['new'] = min(self.count['']['new'], self.getCount('new', 'lim'))
        if self.manager.col.sched.name == "std2":
            self.count['']['rev'] =  self.count['']['allRev']
            # in scheduler 2, we don't respect children limit of review
        self.count['']['rev'] =  min(self.count['']['rev'], self.getCount('rev', 'lim'))


    def getCount(self, key, key1=''):
        if self.resetted < LIMS:
            self.setLims()
        if key1 != 'lim' and self.resetted < NUMS:
            self.setNums()
        try:
            return self.count[key1][key]
        except KeyError:
            print(f"Error in deck {self.getName()} with key1={key1}")
            raise

    def reset(self):
        self.resetted = NO_VALUES

    def increaseValue(self, key, value):
        self.count['single'][key] += value
        for ancestor in self.getAncestors(includeSelf=True):
            self.count[''][key] += value
            if key in self.count['lim']:
                self.count['lim'][key] += value
