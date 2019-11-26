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

    def getBaseName(self):
        return self.manager._basename(self.getName())

    def getPath(self):
        return self.manager._path(self.getName())

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
