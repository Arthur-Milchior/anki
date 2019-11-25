from anki.utils import DictAugmentedIdUsn


class Deck(DictAugmentedIdUsn):
    def addInModel(self):
        """Adding or replacing the deck with our id in the manager"""
        self.manager.decks[str(self.getId())] = self
