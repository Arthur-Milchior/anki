from anki.consts import *
from anki.dconf import DConf
from anki.model import Model
from anki.utils import DictAugmentedDyn


class Deck(DictAugmentedDyn):
    def addInModel(self):
        """Adding or replacing the deck with our id in the manager"""
        self.manager.decks[str(self.getId())] = self

    # Name family
    #############################################################

    def isTopLevel(self):
        return "::" not in self.getName()

    def getParentName(self):
        return self.manager.parentName(self.getName())

    def getParent(self):
        return self.manager.byName(self.getParentName())

    def getAncestorsNames(self, includeSelf=False):
        l = []
        lastName = ""
        path = self.getPath()
        if not includeSelf:
            path = path[:-1]
        for part in path:
            lastName += "::" + part
            l.append(lastName)
        return l

    def getAncestors(self, nameMap=None, includeSelf=False):
        """The list of all ancestors of did, as deck objects.

        The list starts with the toplevel ancestors of did and its
        i-th element is the ancestor with i times ::.

        Keyword arguments:
        did -- the id of the deck
        nameMap -- dictionnary: deck id-> Node
        """
        ancestorsNames = []
        last = ""
        parts = self.getName().split("::")
        if not includeSelf:
            parts = parts[:-1]
        for part in parts:
            current = last + part
            ancestorsNames.append(current)
            last = current + "::"
        # convert to objects
        for index, ancestor in enumerate(ancestorsNames):
            if nameMap:
                deck = nameMap[ancestor]
            else:
                deck = self.manager.get(self.manager.id(ancestor))
            ancestorsNames[index] = deck
        return ancestorsNames

    def getBaseName(self):
        return self.manager._basename(self.getName())

    def getPath(self):
        return self.manager._path(self.getName())

    ## Descendants

    def getDescendants(self, includeSelf=False, sort=False):
        name = self.getName()
        actv = []
        return [deck for deck in self.manager.all(sort=sort) if deck.getName().startswith(name+"::") or (includeSelf and deck.getName() == name)]
    #todo, maybe sort only this smaller list, at least until all() memoize

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

    # Conf
    #############################################################

    def getConfId(self):
        return self.get('conf')

    def getConf(self):
        if 'conf' in self:
            conf = self.manager.getConf(self['conf'])
            conf.setStd()
            return conf
        # dynamic decks have embedded conf
        return self

    def setConf(self, conf):
        """Takes a deck objects, switch his id to id and save it as
        edited.

        Currently used in tests only."""
        if isinstance(conf, int):
            self['conf'] = conf
        else:
            assert isinstance(conf, DConf)
            self['conf'] = conf.getId()
        self.save()

    def isDefaultConf(self):
        return self.getConfId() == 1

    def setDefaultConf(self):
        self.setConf(1)

    # Model
    #############################################################

    def getModel(self):
        self.manager.col.models.get(self.get('mid'))

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
