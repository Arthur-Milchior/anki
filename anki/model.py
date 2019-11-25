import copy

from anki.fields import Field
from anki.templates import Template
from anki.utils import DictAugmentedIdUsn


class Model(DictAugmentedIdUsn):
    def load(self, manager, dict):
        super().load(manager, dict)
        self['tmpls'] = list(map(lambda tmpl: Template(self, tmpl), self['tmpls']))
        self['flds'] = list(map(lambda fld: Field(self, fld), self['flds']))

    def deepcopy(self):
        dict = {}
        for key in self:
            if key in {'tmpls', 'flds'}:
                image = list(map(lambda object: object.deepcopy(), self[key]))
            else:
                image = copy.deepcopy(self[key])
            dict[key] = image
        return self.__class__(self.manager, dict=dict)

    # Tools
    ##################################################

    def nids(self):
        """The ids of notes whose model is model.
        Keyword arguments
        model -- a model object."""
        return self.manager.col.db.list(
            "select id from notes where mid = ?", self.getId())
    # Templates
    ##################################################

    def _syncTemplates(self):
        """Generate all cards not yet generated, whose note's model is model.
        It's called only when model is saved, a new model is given and template is asked to be computed"""
        self.manager.col.genCards(self.nids())
