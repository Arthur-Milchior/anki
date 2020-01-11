import copy
import re
import time

from anki.consts import *
from anki.fields import Field
from anki.templates import Template
from anki.utils import DictAugmentedIdUsn, checksum, intTime, splitFields

defaultModel = {
    'sortf': 0,
    'did': 1,
    'latexPre': """\
\\documentclass[12pt]{article}
\\special{papersize=3in,5in}
\\usepackage[utf8]{inputenc}
\\usepackage{amssymb,amsmath}
\\pagestyle{empty}
\\setlength{\\parindent}{0in}
\\begin{document}
""",
    'latexPost': "\\end{document}",
    'mod': 0,
    'usn': 0,
    'vers': [], # FIXME: remove when other clients have caught up
    'type': MODEL_STD,
    'css': """\
.card {
 font-family: arial;
 font-size: 20px;
 text-align: center;
 color: black;
 background-color: white;
}
"""
}

class Model(DictAugmentedIdUsn):
    def load(self, manager, dict):
        super().load(manager, dict)
        self['tmpls'] = [Template(self, templateType) for templateType in self['tmpls']]
        self['flds'] = [Field(self, fieldType) for fieldType in self['flds']]

    def new(self, manager, name):
        model = defaultModel.copy()
        model['name'] = name
        model['mod'] = intTime()
        model['flds'] = []
        model['tmpls'] = []
        model['tags'] = []
        model['id'] = None
        self.load(manager, model)

    def save(self, templates=False, updateReqs=True):
        """
        * Mark model modified.
        Keyword arguments:
        model -- A Model
        templates -- whether to check for cards not generated in this model
        """
        if self.getId():
            if updateReqs:
                self._updateRequired()
            if templates:
                self._syncTemplates()
        super().save()

    def setCurrent(self):
        """Change curModel value and marks the collection as modified."""
        self.manager.col.conf['curModel'] = self.getId()
        self.manager.col.setMod()

    def rem(self):
        "Delete model, and all its cards/notes."
        self.manager.col.modSchema(check=True)
        current = self.manager.current().getId() == self.getId()
        # delete notes/cards
        self.manager.col.remCards(self.manager.col.db.list("""
select id from cards where nid in (select id from notes where mid = ?)""",
                                      self.getId()))
        # then the model
        del self.manager.models[str(self.getId())]
        self.manager.save()
        # GUI should ensure last model is not deleted
        if current:
            list(self.manager.models.values())[0].setCurrent()

    def ensureNameUnique(self):
        """Transform the name of model into a new name.
        If a model with this name but a distinct id exists in the
        manager, the name of this object is appended by - and by a
        5 random digits generated using the current time.
        Keyword arguments"""
        for mcur in self.manager.all():
            if (mcur.getName() == self.getName() and mcur.getId() != self.getId()):
                self.setName(self.getName() + "-" + checksum(str(time.time()))[:5])
                break

    def _setID(self):
        """Set the id of model to a new unique value."""
        while 1:
            id = str(intTime(1000))
            if id not in self.manager.models:
                break
        self['id'] = id

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
                image = [object.deepcopy() for object in self[key]]
            else:
                image = copy.deepcopy(self[key])
            dict[key] = image
        return self.__class__(self.manager, dict=dict)

    # Fields
    ##################################################

    def fieldMap(self):
        """Mapping of (field name) -> (ord, field object).
        keyword arguments:
        model : a model
        """
        return dict((fieldType.getName(), (fieldType['ord'], fieldType)) for fieldType in self['flds'])

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
            req.append([template['ord'], ret[0], ret[1]])
        self['req'] = req

    # Schema hash
    ##########################################################################

    def scmhash(self):
        """Return a hash of the schema, to see if models are
        compatible. Consider only name of fields and of card type, and
        not the card type itself.
        """
        scm = ""
        for fieldType in self['flds']:
            scm += fieldType.getName()
        for template in self['tmpls']:
            scm += template.getName()
        return checksum(scm)

    # Required field/text cache
    ##########################################################################

    def _availClozeOrds(self, flds, allowEmpty=True):
        """The list of fields F which are used in some {{cloze:F}} in a template
        keyword arguments:
        flds: a list of fields as in the database
        allowEmpty: allows to treat a note without cloze field as a note with a cloze number 1
        """
        sflds = splitFields(flds)
        map = self.fieldMap()
        ords = set()
        matches = re.findall("{{[^}]*?cloze:(?:[^}]?:)*(.+?)}}", self['tmpls'][0]['qfmt'])
        matches += re.findall("<%cloze:(.+?)%>", self['tmpls'][0]['qfmt'])
        for fname in matches:
            if fname not in map:
                continue#Do not consider cloze not related to an existing field
            ord = map[fname][0]
            ords.update([int(match)-1 for match in re.findall(
                r"(?s){{c(\d+)::.+?}}", sflds[ord])])#The number of the cloze of this field, minus one
        if -1 in ords:#remove cloze 0
            ords.remove(-1)
        if not ords and allowEmpty:
            # empty clozes use first ord
            return [0]
        return list(ords)
