import copy
import re
import time

from anki.consts import *
from anki.fields import Field
from anki.templates import Template
from anki.utils import (DictAugmentedIdUsn, checksum, ids2str, intTime,
                        joinFields, splitFields)

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
        self['tmpls'] = list(map(lambda tmpl: Template(self, tmpl), self['tmpls']))
        self['flds'] = list(map(lambda fld: Field(self, fld), self['flds']))

    def new(self, manager, name):
        model = defaultModel.copy()
        model['name'] = name
        model['mod'] = intTime()
        model['flds'] = []
        model['tmpls'] = []
        model['tags'] = []
        model['id'] = None
        self.load(manager, model)

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
                image = list(map(lambda object: object.deepcopy(), self[key]))
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
            req.append((template['ord'], ret[0], ret[1]))
        self['req'] = req

    # Model changing
    ##########################################################################
    # - maps are ord->ord, and there should not be duplicate targets
    # - newModel should be self if model is not changing

    def change(self, oldModel, nids, fmap, cmap):
        """Change the model of the nodes in nids to self
        currently, fmap and cmap are null only for tests.
        keyword arguments
        oldModel -- the previous oldModel of the notes
        nids -- a list of id of notes whose oldModel is oldModel
        self -- the model to which the cards must be converted
        fmap -- the dictionnary sending to each fields'ord of the old model a field'ord of the new model
        cmap -- the dictionnary sending to each card type's ord of the old model a card type's ord of the new model
        """
        # changeNote does not uses oldModel, so self has been chosen to be the new model.
        self.manager.col.modSchema(check=True)
        assert self.getId() == oldModel.getId() or (fmap and cmap)
        assert not self.manager.col.db.list("select id from notes where mid <> ? and id in "+ids2str(nids), oldModel.getId())
        if fmap:
            self._changeNotes(nids, fmap)
        if cmap:
            self._changeCards(nids, oldModel, cmap)
        self.manager.col.genCards(nids)

    def _changeNotes(self, nids, map):
        """Change the note whose ids are nid to the model self, reorder
        fields according to map. Write the change in the database
        Note that if a field is mapped to nothing, it is lost
        keyword arguments:
        nids -- the list of id of notes to change
        newmodel -- the model of destination of the note
        map -- the dictionnary sending to each fields'ord of the old model a field'ord of the new model
        """
        noteData = []
        #The list of dictionnaries, containing the information relating to the new cards
        nfields = len(self['flds'])
        for (nid, flds) in self.manager.col.db.execute(
            "select id, flds from notes where id in "+ids2str(nids)):
            newflds = {}
            flds = splitFields(flds)
            for old, new in list(map.items()):
                newflds[new] = flds[old]
            flds = []
            for index in range(nfields):
                flds.append(newflds.get(index, ""))
            flds = joinFields(flds)
            noteData.append(dict(nid=nid, flds=flds, mid=self.getId(),
                      mod=intTime(),usn=self.manager.col.usn()))
        self.manager.col.db.executemany(
            "update notes set flds=:flds,mid=:mid,mod=:mod,usn=:usn where id = :nid", noteData)
        self.manager.col.updateFieldCache(nids)

    def _changeCards(self, nids, oldModel, map):
        """Change the note whose ids are nid to the model self, reorder
        fields according to map. Write the change in the database
        Remove the cards mapped to nothing
        If the source is a cloze, it is (currently?) mapped to the
        card of same order in self, independtly of map.
        keyword arguments:
        nids -- the list of id of notes to change
        oldModel -- the soruce model of the notes
        newmodel -- the model of destination of the notes
        map -- the dictionnary sending to each card 'ord of the old model a card'ord of the new model or to None
        """
        cardData = []
        deleted = []
        for (cid, ord) in self.manager.col.db.execute(
            "select id, ord from cards where nid in "+ids2str(nids)):
            # if the src model is a cloze, we ignore the map, as the gui
            # doesn't currently support mapping them
            if oldModel['type'] == MODEL_CLOZE:
                new = ord
                if self['type'] != MODEL_CLOZE:
                    # if we're mapping to a regular note, we need to check if
                    # the destination ord is valid
                    if len(self['tmpls']) <= ord:
                        new = None
            else:
                # mapping from a regular note, so the map should be valid
                new = map[ord]
            if new is not None:
                cardData.append(dict(
                    cid=cid,new=new,usn=self.manager.col.usn(),mod=intTime()))
            else:
                deleted.append(cid)
        self.manager.col.db.executemany(
            "update cards set ord=:new,usn=:usn,mod=:mod where id=:cid",
            cardData)
        self.manager.col.remCards(deleted)

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

    def _updateRequired(self):
        """Entirely recompute the model's req value"""
        if self['type'] == MODEL_CLOZE:
            # nothing to do
            return
        req = []
        flds = [fieldType.getName() for fieldType in self['flds']]
        for template in self['tmpls']:
            ret = template._req(flds)
            req.append((template['ord'], ret[0], ret[1]))
        self['req'] = req

    # Required field/text cache
    ##########################################################################

    def availOrds(self, flds):
        """Given a joined field string, return ordinal of card type which
        should be generated. See
        ../documentation/templates_generation_rules.md for the detail
        """
        if self['type'] == MODEL_CLOZE:
            return self._availClozeOrds(flds)
        fields = {}
        for index, fieldType in enumerate(splitFields(flds)):
            fields[index] = fieldType.strip()
        avail = []
        for ord, type, req in self['req']:
            # unsatisfiable template
            if type == "none":
                continue
            # AND requirement?
            elif type == "all":
                ok = True
                for idx in req:
                    if not fields[idx]:
                        # missing and was required
                        ok = False
                        break
                if not ok:
                    continue
            # OR requirement?
            elif type == "any":
                ok = False
                for idx in req:
                    if fields[idx]:
                        ok = True
                        break
                if not ok:
                    continue
            avail.append(ord)
        return avail

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
