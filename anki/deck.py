from anki.consts import *
from anki.utils import DictAugmentedDyn


class Deck(DictAugmentedDyn):
    def addInModel(self):
        """Adding or replacing the deck with our id in the manager"""
        self.manager.decks[str(self.getId())] = self

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

    def isDefaultConf(self):
        return self.getConfId() == 1
