from anki.consts import *
from anki.utils import DictAugmentedDyn


class Deck(DictAugmentedDyn):
    def addInModel(self):
        """Adding or replacing the deck with our id in the manager"""
        self.manager.decks[str(self.getId())] = self
