from anki.utils import DictAugmentedDyn


class DConf(DictAugmentedDyn):
    """A configuration for decks

    """
    def load(self, manager, dict):
        super().load(manager, dict)
        # set limits to within bounds
        for type in ('rev', 'new'):
            pd = 'perDay'
            if self[type][pd] > 999999:
                self[type][pd] = 999999
                self.save()
                self.manager.changed = True

    # Basic tests
    #############################################################
    def isDefault(self):
        return str(self.getId()) == "1"
