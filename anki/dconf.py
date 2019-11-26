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

    def update(self):
        """Add g to the set of dconf's. Potentially replacing a dconf with the
same id."""
        self.manager.dconf[str(self.getId())] = self
        self.manager.save()
