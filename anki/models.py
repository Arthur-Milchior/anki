# -*- coding: utf-8 -*-
# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

import copy
import json
import re
import time

from anki.consts import *
from anki.fields import Field
from anki.hooks import runHook
from anki.lang import _
from anki.model import Model
from anki.templates import Template
from anki.utils import checksum, ids2str, intTime, joinFields, splitFields

"""This module deals with models, known as note type in Anki's documentation.

A model is composed of:
css -- CSS, shared for all templates of the model
did -- Long specifying the id of the deck that cards are added to by
default
flds -- JSONArray containing object for each field in the model. See flds
id -- model ID, matches notes.mid
latexPost -- String added to end of LaTeX expressions (usually \\end{document}),
latexPre -- preamble for LaTeX expressions,
mod -- modification time in milliseconds,
name -- the name of the model,
req -- Array of arrays describing which fields are required. See req
sortf -- Integer specifying which field is used for sorting in the
browser,
tags -- Anki saves the tags of the last added note to the current
model, use an empty array [],
tmpls -- The list of templates. See below
      -- In db:JSONArray containing object of CardTemplate for each card in
model.
type -- Integer specifying what type of model. 0 for standard, 1 for
cloze,
usn -- Update sequence number: used in same way as other usn vales in
db,
vers -- Legacy version number (unused), use an empty array []
changed -- Whether the Model has been changed and should be written in
the database."""


"""A field object (flds) is an array composed of:
font -- "display font",
media -- "array of media. appears to be unused",
name -- "field name",
ord -- "ordinal of the field - goes from 0 to num fields -1",
rtl -- "boolean, right-to-left script",
size -- "font size",
sticky -- "sticky fields retain the value that was last added
when adding new notes" """

"""req' fields are:
"the 'ord' value of the template object from the 'tmpls' array you are setting the required fields of",
'? string, "all" or "any"',
["? another array of 'ord' values from field object you
want to require from the 'flds' array"]"""


"""tmpls (a template): a dict with
afmt -- "answer template string",
bafmt -- "browser answer format:
used for displaying answer in browser",
bqfmt -- "browser question format:
used for displaying question in browser",
did -- "deck override (null by default)",
name -- "template name",
ord -- "template number, see flds",
qfmt -- "question format string"
"""


# Models
##########################################################################

# - careful not to add any lists/dicts/etc here, as they aren't deep copied


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

defaultTemplate = {
    'name': "",
    'ord': None,
    'qfmt': "",
    'afmt': "",
    'did': None,
    'bqfmt': "",
    'bafmt': "",
    # we don't define these so that we pick up system font size until set
    #'bfont': "Arial",
    #'bsize': 12,
}

class ModelManager:

    """This object is usually denoted mm as a variable. Or .models in
    collection."""
    # Saving/loading registry
    #############################################################

    def __init__(self, col):
        """Returns a ModelManager whose collection is col."""
        self.col = col

    def load(self, json_):
        "Load registry from JSON."
        self.changed = False
        self.models = dict()
        for model in json.loads(json_).values():
            model = Model(self, model)
            self.models[str(model['id'])] = model

    def save(self):
        """
        * Mark model modified if provided.
        * Schedule registry flush.
        * Calls hook newModel

        Keyword arguments:
        model -- A Model
        templates -- whether to check for cards not generated in this model
        """
        self.changed = True
        runHook("newModel") # By default, only refresh side bar of browser

    def flush(self):
        "Flush the registry if any models were changed."
        if self.changed:
            self.ensureNotEmpty()
            self.col.db.execute("update col set models = ?",
                                 json.dumps(self.models, default=lambda model: model.dumps()))
            self.changed = False

    def ensureNotEmpty(self):
        if not self.models:
            from anki.stdmodels import addBasicModel
            addBasicModel(self.col)
            return True

    # Retrieving and creating models
    #############################################################

    def current(self, forDeck=True):
        """Get current model.

        This mode is first considered using the current deck's mid, if
        forDeck is true(default).

        Otherwise, the curModel configuration value is used.

        Otherwise, the first model is used.

        Keyword arguments:
        forDeck -- Whether ther model of the deck should be considered; assuming it exists."""
        "Get current model."
        model = self.get(self.col.decks.current().get('mid'))
        if not forDeck or not model:
            model = self.get(self.col.conf['curModel'])
        return model or list(self.models.values())[0]

    def get(self, id):
        "Get model object with ID, or None."
        id = str(id)
        if id in self.models:
            return self.models[id]

    def all(self, type=None):
        "Get all model objects."
        models = self.models.values()
        if type is not None:
            models = [model for model in models if model['type'] == type]
        return models

    def allNames(self, type=None):
        "Get all model names."
        return map(lambda model:model.getName(), self.all(type=type))

    def byName(self, name):
        """Get model whose name is name.

        keyword arguments
        name -- the name of the wanted model."""
        for model in list(self.models.values()):
            if model.getName() == name:
                return model

    def new(self, name):
        "Create a new model, save it in the registry, and return it."
        # caller should call save() after modifying
        return Model(self, name=name)

    def add(self, model):
        """Add a new model model in the database of models"""
        model._setID()
        self.update(model)
        model.setCurrent()
        model.save()

    def update(self, model):
        "Add or update an existing model. Used for syncing and merging."
        model.ensureNameUnique()
        self.models[str(model.getId())] = model
        # mark registry changed, but don't bump mod time
        self.save()

    def have(self, id):
        """Whether there exists a model whose id is did."""
        return str(id) in self.models

    def ids(self):
        """The list of id of models"""
        return list(self.models.keys())

    # Tools
    ##################################################

    def useCount(self, model):
        """Number of note using the model model.

        Keyword arguments
        model -- a model object."""
        return self.col.db.scalar(
            "select count() from notes where mid = ?", model.getId())

    def tmplUseCount(self, model, ord):
        """The number of cards which used template number ord of the
        model obj.

        Keyword arguments
        model -- a model object."""
        return self.col.db.scalar("""
select count() from cards, notes where cards.nid = notes.id
and notes.mid = ? and cards.ord = ?""", model.getId(), ord)

    # Copying
    ##################################################

    def copy(self, model):
        "A copy of model, already in the collection."
        m2 = model.deepcopy()
        m2['name'] = _("%s copy") % m2.getName()
        self.add(m2)
        return m2

    # Fields
    ##################################################

    def newField(self, model, name):
        """A new field, similar to the default one, whose name is name."""
        assert(isinstance(name, str))
        fieldType = defaultField.copy()
        fieldType = Field(model, fieldType)
        fieldType.setName(name)
        return fieldType

    def fieldNames(self, model):
        """The list of names of fields of this model."""
        return [fieldType.getName() for fieldType in model['flds']]

    def sortIdx(self, model):
        """The index of the field used for sorting."""
        return model['sortf']

    def setSortIdx(self, model, idx):
        """State that the id of the sorting field of the model is idx.

        Mark the model as modified, change the cache.
        Keyword arguments
        model -- a model
        idx -- the identifier of a field
        """
        assert 0 <= idx < len(model['flds'])
        self.col.modSchema(check=True)
        model['sortf'] = idx
        self.col.updateFieldCache(model.nids())
        model.save()

    def addField(self, model, fieldType):
        """Append the field field as last element of the model model.

        todo

        Keyword arguments
        model -- a model
        field -- a field object
        """
        # only mod schema if model isn't new
        if model.getId():
            self.col.modSchema(check=True)
        model['flds'].append(fieldType)
        self._updateFieldOrds(model)
        model.save()
        def add(fieldsContents):
            fieldsContents.append("")
            return fieldsContents
        self._transformFields(model, add)

    def remField(self, model, fieldTypeToRemove):
        """Remove a field from a model.
        Also remove it from each note of this model
        Move the position of the sortfield. Update the position of each field.

        Modify the template

        model -- the model
        field -- the field object"""
        self.col.modSchema(check=True)
        # save old sort field
        sortFldName = model['flds'][model['sortf']].getName()
        idx = model['flds'].index(fieldTypeToRemove)
        model['flds'].remove(fieldTypeToRemove)
        # restore old sort field if possible, or revert to first field
        model['sortf'] = 0
        for index, fieldType in enumerate(model['flds']):
            if fieldType.getName() == sortFldName:
                model['sortf'] = index
                break
        self._updateFieldOrds(model)
        def delete(fieldsContents):
            del fieldsContents[idx]
            return fieldsContents
        self._transformFields(model, delete)
        if model['flds'][model['sortf']].getName() != sortFldName:
            # need to rebuild sort field
            self.col.updateFieldCache(model.nids())
        # saves
        self.renameField(model, fieldTypeToRemove, None)

    def moveField(self, model, fieldType, idx):
        """Move the field to position idx

        idx -- new position, integer
        field -- a field object
        """
        self.col.modSchema(check=True)
        oldidx = model['flds'].index(fieldType)
        if oldidx == idx:
            return
        # remember old sort fieldType
        sortf = model['flds'][model['sortf']]
        # move
        model['flds'].remove(fieldType)
        model['flds'].insert(idx, fieldType)
        # restore sort fieldType
        model['sortf'] = model['flds'].index(sortf)
        self._updateFieldOrds(model)
        model.save()
        def move(fields, oldidx=oldidx):
            val = fields[oldidx]
            del fields[oldidx]
            fields.insert(idx, val)
            return fields
        self._transformFields(model, move)

    def renameField(self, model, fieldType, newName):
        """Rename the field. In each template, find the mustache related to
        this field and change them.

        model -- the model dictionnary
        field -- the field dictionnary
        newName -- either a name. Or None if the field is deleted.

        """
        self.col.modSchema(check=True)
        #Regexp associating to a mustache the name of its field
        pat = r'{{([^{}]*)([:#^/]|[^:#/^}][^:}]*?:|)%s}}'
        def wrap(txt):
            def repl(match):
                return '{{' + match.group(1) + match.group(2) + txt +  '}}'
            return repl
        for template in model['tmpls']:
            for fmt in ('qfmt', 'afmt'):
                if newName:
                    template[fmt] = re.sub(
                        pat % re.escape(fieldType.getName()), wrap(newName), template[fmt])
                else:
                    template[fmt] = re.sub(
                        pat  % re.escape(fieldType.getName()), "", template[fmt])
        fieldType.setName(newName)
        model.save()

    def _updateFieldOrds(self, model):
        """
        Change the order of the field of the model in order to copy
        the order in model['flds'].

        Keyword arguments
        model -- a model"""
        for index, fieldType in enumerate(model['flds']):
            fieldType['ord'] = index

    def _transformFields(self, model, fn):
        """For each note of the model model, apply model to the set of field's value,
        and save the note modified.

        fn -- a function taking and returning a list of field."""
        # model hasn't been added yet?
        if not model.getId():
            return
        notesUpdates = []
        for (id, flds) in self.col.db.execute(
            "select id, flds from notes where mid = ?", model.getId()):
            notesUpdates.append((joinFields(fn(splitFields(flds))),
                      intTime(), self.col.usn(), id))
        self.col.db.executemany(
            "update notes set flds=?,mod=?,usn=? where id = ?", notesUpdates)

    # Templates
    ##################################################

    def newTemplate(self, model, name):
        """A new template, whose content is the one of
        defaultTemplate, and name is name.

        It's used in order to import mnemosyn, and create the standard
        model during anki's first initialization. It's not used in day to day anki.
        """
        template = defaultTemplate.copy()
        template = Template(model, template)
        template.setName(name)
        return template

    def addTemplate(self, model, template):
        """Add a new template in model, as last element. This template is a copy
        of the input template
        """
        if model.getId():
            self.col.modSchema(check=True)
        model['tmpls'].append(template)
        self._updateTemplOrds(model)
        model.save()

    def remTemplate(self, model, template):
        """Remove the input template from the model model.

        Return False if removing template would leave orphan
        notes. Otherwise True
        """
        assert len(model['tmpls']) > 1
        # find cards using this template
        ord = model['tmpls'].index(template)
        cids = self.col.db.list("""
select card.id from cards card, notes note where card.nid=note.id and mid = ? and ord = ?""",
                                 model.getId(), ord)
        # all notes with this template must have at least two cards, or we
        # could end up creating orphaned notes
        if self.col.db.scalar("""
select nid, count() from cards where
nid in (select nid from cards where id in %s)
group by nid
having count() < 2
limit 1""" % ids2str(cids)):
            return False
        # ok to proceed; remove cards
        self.col.modSchema(check=True)
        self.col.remCards(cids)
        # shift ordinals
        self.col.db.execute("""
update cards set ord = ord - 1, usn = ?, mod = ?
 where nid in (select id from notes where mid = ?) and ord > ?""",
                             self.col.usn(), intTime(), model.getId(), ord)
        model['tmpls'].remove(template)
        self._updateTemplOrds(model)
        model.save()
        return True

    def _updateTemplOrds(self, model):
        """Change the value of 'ord' in each template of this model to reflect its new position"""
        for index, template in enumerate(model['tmpls']):
            template['ord'] = index

    def moveTemplate(self, model, template, idx):
        """Move input template to position idx in model.

        Move also every other template to make this consistent.

        Comment again after that TODODODO
        """
        oldidx = model['tmpls'].index(template)
        if oldidx == idx:
            return
        oldidxs = dict((id(template), template['ord']) for template in model['tmpls'])
        model['tmpls'].remove(template)
        model['tmpls'].insert(idx, template)
        self._updateTemplOrds(model)
        # generate change map
        map = []
        for template in model['tmpls']:
            map.append("when ord = %d then %d" % (oldidxs[id(template)], template['ord']))
        # apply
        model.save()
        self.col.db.execute("""
update cards set ord = (case %s end),usn=?,mod=? where nid in (
select id from notes where mid = ?)""" % " ".join(map),
                             self.col.usn(), intTime(), model.getId())

    # Sync handling
    ##########################################################################

    def beforeUpload(self):
        for model in self.all():
            model.beforeUpload()
        self.save()
