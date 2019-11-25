# -*- coding: utf-8 -*-
# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

import copy
import json
import time

from anki.consts import *
from anki.fields import Field
from anki.hooks import runHook
from anki.lang import _
from anki.model import Model
from anki.templates import Template
from anki.utils import checksum, intTime, joinFields, splitFields

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

    # Sync handling
    ##########################################################################

    def beforeUpload(self):
        for model in self.all():
            model.beforeUpload()
        self.save()
