from anki.utils import DictAugmentedInModel

defaultField = {
    'name': "",
    'ord': None,
    'sticky': False,
    # the following alter editing, and are used as defaults for the
    # template wizard
    'rtl': False,
    'font': "Arial",
    'size': 20,
    # reserved for future use
    'media': [],
}

class Field(DictAugmentedInModel):
    """Field are not necessarily in the model. If they are not, method add
    must be used to add them.  Only use them once the field is
    entirely configured (so that compilation of req is done correction
    for example)

    """

    def new(self, manager, name):
        """A new field, similar to the default one, whose name is name."""
        super().new(manager, name, defaultField)
