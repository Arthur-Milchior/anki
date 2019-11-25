from anki.utils import DictAugmentedIdUsn


class DConf(DictAugmentedIdUsn):
    """A configuration for decks

    """
    def isDefault(self):
        return str(self.getId()) == "1"
