import copy

from anki.consts import *
from anki.fields import Field
from anki.templates import Template
from anki.utils import DictAugmentedIdUsn


class Model(DictAugmentedIdUsn):
    def load(self, manager, dict):
        super().load(manager, dict)
        self['tmpls'] = list(map(lambda tmpl: Template(self, tmpl), self['tmpls']))
        self['flds'] = list(map(lambda fld: Field(self, fld), self['flds']))

    def save(self, template=False):
        """
        * Mark model modified.
        Keyword arguments:
        model -- A Model
        templates -- whether to check for cards not generated in this model
        """
        if self.getId():
            self._updateRequired()
            if template:
                self._syncTemplates()
        super().save()

    def setCurrent(self):
        """Change curModel value and marks the collection as modified."""
        self.manager.col.conf['curModel'] = self.getId()
        self.manager.col.setMod()

    # Tools
    ##################################################

    def nids(self):
        """The ids of notes whose model is model.
        Keyword arguments
        model -- a model object."""
        return self.manager.col.db.list(
            "select id from notes where mid = ?", self.getId())

    def deepcopy(self):
        dict = {}
        for key in self:
            if key in {'tmpls', 'flds'}:
                image = list(map(lambda object: object.deepcopy(), self[key]))
            else:
                image = copy.deepcopy(self[key])
            dict[key] = image
        return self.__class__(self.manager, dict=dict)

    # Templates
    ##################################################

    def _syncTemplates(self):
        """Generate all cards not yet generated, whose note's model is model.
        It's called only when model is saved, a new model is given and template is asked to be computed"""
        self.manager.col.genCards(self.nids())

    # Required field/text cache
    ##########################################################################

    def _updateRequired(self):
        """Entirely recompute the model's req value"""
        if self['type'] == MODEL_CLOZE:
            # nothing to do
            return
        req = []
        flds = [fieldType['name'] for fieldType in self['flds']]
        for template in self['tmpls']:
            ret = template._req(flds)
            req.append((template['ord'], ret[0], ret[1]))
        self['req'] = req
