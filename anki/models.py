# -*- coding: utf-8 -*-
# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

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
the database.
tmp -- some values which should not be saved in json.
"""

"""A field object (flds) is an array composed of:
font -- "display font",
media -- "array of media. appears to be unused",
name -- "field name",
ord -- "ordinal of the field - goes from 0 to num fields -1",
rtl -- "boolean, right-to-left script",
size -- "font size",
sticky -- "sticky fields retain the value that was last added
when adding new notes"
tmp -- some values which should not be saved in json.
"""

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
tmp -- some values which should not be saved in json.
"""

import copy, re, json
from anki.utils import intTime, joinFields, splitFields, ids2str,\
    checksum
from anki.lang import _
from anki.consts import *
from anki.hooks import runHook
import time

# Models
##########################################################################

# - careful not to add any lists/dicts/etc here, as they aren't deep copied

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
""",
    'tmp': {},
}

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
    'tmp': {},
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
    'tmp': {},

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
        self.models = json.loads(json_)
        for mid, model in self.models.items():
            model["tmp"] = {}
            for template in model['tmpls']:
                template["tmp"] = {}
            for field in model['flds']:
                field["tmp"] = {}

    def save(self, m=None, templates=False):
        """
        * Mark m modified if provided.
        * Schedule registry flush.
        * Calls hook newModel

        Keyword arguments:
        m -- A Model
        templates -- whether to check for cards not generated in this model
        """
        if m and m['id']:
            assert "tmp" in m
            m['mod'] = intTime()
            m['usn'] = self.col.usn()
            self._updateRequired(m)
            if templates:
                self._syncTemplates(m)
        self.changed = True
        runHook("newModel") # By default, only refresh side bar of browser

    def flush(self):
        "Flush the registry if any models were changed."
        if self.changed:
            self.ensureNotEmpty()
            models = copy.deepcopy(self.models)
            for mid, model in self.models.items():
                if "tmp" in model: del model["tmp"]#if should be useless. But test fails and I don't see why
                for template in model['tmpls']:
                    if "tmp" in template: del template["tmp"]
                for field in model['flds']:
                    if "tmp" in field: del field["tmp"]

            self.col.db.execute("update col set models = ?",
                                 json.dumps(self.models))
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
        m = self.get(self.col.decks.current().get('mid'))
        if not forDeck or not m:
            m = self.get(self.col.conf['curModel'])
        return m or list(self.models.values())[0]

    def setCurrent(self, m):
        """Change curModel value and marks the collection as modified."""
        self.col.conf['curModel'] = m['id']
        self.col.setMod()

    def get(self, id):
        "Get model object with ID, or None."
        id = str(id)
        if id in self.models:
            return self.models[id]

    def all(self):
        "Get all model objects."
        return list(self.models.values())

    def allNames(self):
        "Get all model names."
        return [m['name'] for m in self.all()]

    def byName(self, name):
        """Get model whose name is name.

        keyword arguments
        name -- the name of the wanted model."""
        for m in list(self.models.values()):
            if m['name'] == name:
                return m

    def new(self, name):
        "Create a new model, save it in the registry, and return it."
        # caller should call save() after modifying
        m = defaultModel.copy()
        m['name'] = name
        m['mod'] = intTime()
        m['flds'] = []
        m['tmpls'] = []
        m['tags'] = []
        m['id'] = None
        return m

    def rem(self, m):
        "Delete model, and all its cards/notes."
        self.col.modSchema(check=True)
        current = self.current()['id'] == m['id']
        # delete notes/cards
        self.col.remCards(self.col.db.list("""
select id from cards where nid in (select id from notes where mid = ?)""",
                                      m['id']))
        # then the model
        del self.models[str(m['id'])]
        self.save()
        # GUI should ensure last model is not deleted
        if current:
            self.setCurrent(list(self.models.values())[0])

    def add(self, m):
        """Add a new model m in the database of models"""
        self._setID(m)
        self.update(m)
        self.setCurrent(m)
        self.save(m)

    def ensureNameUnique(self, m):
        """Transform the name of m into a new name.

        If a model with this name but a distinct id exists in the
        manager, the name of this object is appended by - and by a
        5 random digits generated using the current time.
        Keyword arguments
        m -- a model object"""
        for mcur in self.all():
            if (mcur['name'] == m['name'] and mcur['id'] != m['id']):
                m['name'] += "-" + checksum(str(time.time()))[:5]
                break

    def update(self, m):
        "Add or update an existing model. Used for syncing and merging."
        self.ensureNameUnique(m)
        self.models[str(m['id'])] = m
        # mark registry changed, but don't bump mod time
        self.save()

    def _setID(self, m):
        """Set the id of m to a new unique value."""
        while 1:
            id = str(intTime(1000))
            if id not in self.models:
                break
        m['id'] = id

    def have(self, id):
        """Whether there exists a model whose id is did."""
        return str(id) in self.models

    def ids(self):
        """The list of id of models"""
        return list(self.models.keys())

    # Tools
    ##################################################

    def nids(self, m):
        """The ids of notes whose model is m.

        Keyword arguments
        m -- a model object."""
        return self.col.db.list(
            "select id from notes where mid = ?", m['id'])

    def useCount(self, m):
        """Number of note using the model m.

        Keyword arguments
        m -- a model object."""
        return self.col.db.scalar(
            "select count() from notes where mid = ?", m['id'])

    def tmplUseCount(self, m, ord):
        """The number of cards which used template number ord of the
        model obj.

        Keyword arguments
        m -- a model object."""
        return self.col.db.scalar("""
select count() from cards, notes where cards.nid = notes.id
and notes.mid = ? and cards.ord = ?""", m['id'], ord)

    # Copying
    ##################################################

    def copy(self, m):
        "A copy of m, already in the collection."
        m2 = copy.deepcopy(m)
        m2['name'] = _("%s copy") % m2['name']
        self.add(m2)
        return m2

    # Fields
    ##################################################

    def newField(self, name):
        """A new field, similar to the default one, whose name is name."""
        f = defaultField.copy()
        f['name'] = name
        return f

    def fieldMap(self, m):
        """Mapping of (field name) -> (ord, field object).

        keyword arguments:
        m : a model
        """
        return dict((f['name'], (f['ord'], f)) for f in m['flds'])

    def fieldNames(self, m):
        """The list of names of fields of this model."""
        return [f['name'] for f in m['flds']]

    def sortIdx(self, m):
        """The index of the field used for sorting."""
        return m['sortf']

    def setSortIdx(self, m, idx):
        """State that the id of the sorting field of the model is idx.

        Mark the model as modified, change the cache.
        Keyword arguments
        m -- a model
        idx -- the identifier of a field
        """
        assert 0 <= idx < len(m['flds'])
        self.col.modSchema(check=True)
        m['sortf'] = idx
        self.col.updateFieldCache(self.nids(m))
        self.save(m)

    def addField(self, m, field):
        """Append the field field as last element of the model m.

        todo

        Keyword arguments
        m -- a model
        field -- a field object
        """
        # only mod schema if model isn't new
        if m['id']:
            self.col.modSchema(check=True)
        m['flds'].append(field)
        self._updateFieldOrds(m)
        self.save(m)
        def add(fields):
            fields.append("")
            return fields
        self._transformFields(m, add)

    def remField(self, m, field):
        """Remove a field from a model.
        Also remove it from each note of this model
        Move the position of the sortfield. Update the position of each field.

        Modify the template

        m -- the model
        field -- the field object"""
        self.col.modSchema(check=True)
        # save old sort field
        sortFldName = m['flds'][m['sortf']]['name']
        idx = m['flds'].index(field)
        m['flds'].remove(field)
        # restore old sort field if possible, or revert to first field
        m['sortf'] = 0
        for c, f in enumerate(m['flds']):
            if f['name'] == sortFldName:
                m['sortf'] = c
                break
        self._updateFieldOrds(m)
        def delete(fields):
            del fields[idx]
            return fields
        self._transformFields(m, delete)
        if m['flds'][m['sortf']]['name'] != sortFldName:
            # need to rebuild sort field
            self.col.updateFieldCache(self.nids(m))
        # saves
        self.renameField(m, field, None)

    def moveField(self, m, field, idx):
        """Move the field to position idx

        idx -- new position, integer
        field -- a field object
        """
        self.col.modSchema(check=True)
        oldidx = m['flds'].index(field)
        if oldidx == idx:
            return
        # remember old sort field
        sortf = m['flds'][m['sortf']]
        # move
        m['flds'].remove(field)
        m['flds'].insert(idx, field)
        # restore sort field
        m['sortf'] = m['flds'].index(sortf)
        self._updateFieldOrds(m)
        self.save(m)
        def move(fields, oldidx=oldidx):
            val = fields[oldidx]
            del fields[oldidx]
            fields.insert(idx, val)
            return fields
        self._transformFields(m, move)

    def renameField(self, m, field, newName):
        """Rename the field. In each template, find the mustache related to
        this field and change them.

        m -- the model dictionnary
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
        for t in m['tmpls']:
            for fmt in ('qfmt', 'afmt'):
                if newName:
                    t[fmt] = re.sub(
                        pat % re.escape(field['name']), wrap(newName), t[fmt])
                else:
                    t[fmt] = re.sub(
                        pat  % re.escape(field['name']), "", t[fmt])
        field['name'] = newName
        self.save(m)

    def _updateFieldOrds(self, m):
        """
        Change the order of the field of the model in order to copy
        the order in m['flds'].

        Keyword arguments
        m -- a model"""
        for c, f in enumerate(m['flds']):
            f['ord'] = c

    def _transformFields(self, m, fn):
        """For each note of the model m, apply m to the set of field's value,
        and save the note modified.

        fn -- a function taking and returning a list of field."""
        # model hasn't been added yet?
        if not m['id']:
            return
        r = []
        for (id, flds) in self.col.db.execute(
            "select id, flds from notes where mid = ?", m['id']):
            r.append((joinFields(fn(splitFields(flds))),
                      intTime(), self.col.usn(), id))
        self.col.db.executemany(
            "update notes set flds=?,mod=?,usn=? where id = ?", r)

    # Templates
    ##################################################

    def newTemplate(self, name):
        """A new template, whose content is the one of
        defaultTemplate, and name is name.

        It's used in order to import mnemosyn, and create the standard
        model during anki's first initialization. It's not used in day to day anki.
        """
        t = defaultTemplate.copy()
        t['name'] = name
        return t

    def addTemplate(self, m, template):
        """Add a new template in m, as last element. This template is a copy
        of the input template
        """

        "Note: should call col.genCards() afterwards."
        if m['id']:
            self.col.modSchema(check=True)
        m['tmpls'].append(template)
        self._updateTemplOrds(m)
        self.save(m)

    def remTemplate(self, m, template):
        """Remove the input template from the model m.

        Return False if removing template would leave orphan
        notes. Otherwise True
        """
        assert len(m['tmpls']) > 1
        # find cards using this template
        ord = m['tmpls'].index(template)
        cids = self.col.db.list("""
select c.id from cards c, notes f where c.nid=f.id and mid = ? and ord = ?""",
                                 m['id'], ord)
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
                             self.col.usn(), intTime(), m['id'], ord)
        m['tmpls'].remove(template)
        self._updateTemplOrds(m)
        self.save(m)
        return True

    def _updateTemplOrds(self, m):
        """Change the value of 'ord' in each template of this model to reflect its new position"""
        for c, t in enumerate(m['tmpls']):
            t['ord'] = c

    def moveTemplate(self, m, template, idx):
        """Move input template to position idx in m.

        Move also every other template to make this consistent.

        Comment again after that TODODODO
        """
        oldidx = m['tmpls'].index(template)
        if oldidx == idx:
            return
        oldidxs = dict((id(t), t['ord']) for t in m['tmpls'])
        m['tmpls'].remove(template)
        m['tmpls'].insert(idx, template)
        self._updateTemplOrds(m)
        # generate change map
        map = []
        for t in m['tmpls']:
            map.append("when ord = %d then %d" % (oldidxs[id(t)], t['ord']))
        # apply
        self.save(m)
        self.col.db.execute("""
update cards set ord = (case %s end),usn=?,mod=? where nid in (
select id from notes where mid = ?)""" % " ".join(map),
                             self.col.usn(), intTime(), m['id'])

    def _syncTemplates(self, m):
        """Generate all cards not yet generated, whose note's model is m.

        It's called only when model is saved, a new model is given and template is asked to be computed"""
        rem = self.col.genCards(self.nids(m))

    # Model changing
    ##########################################################################
    # - maps are ord->ord, and there should not be duplicate targets
    # - newModel should be self if model is not changing

    def change(self, m, nids, newModel, fmap, cmap):
        """Change the model of the nodes in nids to newModel

        currently, fmap and cmap are null only for tests.

        keyword arguments
        m -- the previous model of the notes
        nids -- a list of id of notes whose model is m
        newModel -- the model to which the cards must be converted
        fmap -- the dictionnary sending to each fields'ord of the old model a field'ord of the new model
        cmap -- the dictionnary sending to each card type's ord of the old model a card type's ord of the new model
        """
        self.col.modSchema(check=True)
        assert newModel['id'] == m['id'] or (fmap and cmap)
        if fmap:
            self._changeNotes(nids, newModel, fmap)
        if cmap:
            self._changeCards(nids, m, newModel, cmap)
        self.col.genCards(nids)

    def _changeNotes(self, nids, newModel, map):
        """Change the note whose ids are nid to the model newModel, reorder
        fields according to map. Write the change in the database

        Note that if a field is mapped to nothing, it is lost

        keyword arguments:
        nids -- the list of id of notes to change
        newmodel -- the model of destination of the note
        map -- the dictionnary sending to each fields'ord of the old model a field'ord of the new model
        """
        d = [] #The list of dictionnaries, containing the information relating to the new cards
        nfields = len(newModel['flds'])
        for (nid, flds) in self.col.db.execute(
            "select id, flds from notes where id in "+ids2str(nids)):
            newflds = {}
            flds = splitFields(flds)
            for old, new in list(map.items()):
                newflds[new] = flds[old]
            flds = []
            for c in range(nfields):
                flds.append(newflds.get(c, ""))
            flds = joinFields(flds)
            d.append(dict(nid=nid, flds=flds, mid=newModel['id'],
                      m=intTime(),u=self.col.usn()))
        self.col.db.executemany(
            "update notes set flds=:flds,mid=:mid,mod=:m,usn=:u where id = :nid", d)
        self.col.updateFieldCache(nids)

    def _changeCards(self, nids, oldModel, newModel, map):
        """Change the note whose ids are nid to the model newModel, reorder
        fields according to map. Write the change in the database

        Remove the cards mapped to nothing

        If the source is a cloze, it is (currently?) mapped to the
        card of same order in newModel, independtly of map.

        keyword arguments:
        nids -- the list of id of notes to change
        oldModel -- the soruce model of the notes
        newmodel -- the model of destination of the notes
        map -- the dictionnary sending to each card 'ord of the old model a card'ord of the new model or to None
        """
        d = []
        deleted = []
        for (cid, ord) in self.col.db.execute(
            "select id, ord from cards where nid in "+ids2str(nids)):
            # if the src model is a cloze, we ignore the map, as the gui
            # doesn't currently support mapping them
            if oldModel['type'] == MODEL_CLOZE:
                new = ord
                if newModel['type'] != MODEL_CLOZE:
                    # if we're mapping to a regular note, we need to check if
                    # the destination ord is valid
                    if len(newModel['tmpls']) <= ord:
                        new = None
            else:
                # mapping from a regular note, so the map should be valid
                new = map[ord]
            if new is not None:
                d.append(dict(
                    cid=cid,new=new,u=self.col.usn(),m=intTime()))
            else:
                deleted.append(cid)
        self.col.db.executemany(
            "update cards set ord=:new,usn=:u,mod=:m where id=:cid",
            d)
        self.col.remCards(deleted)

    # Schema hash
    ##########################################################################

    def scmhash(self, m):
        "Return a hash of the schema, to see if models are compatible."
        s = ""
        for f in m['flds']:
            s += f['name']
        for t in m['tmpls']:
            s += t['name']
        return checksum(s)

    # Required field/text cache
    ##########################################################################

    def _updateRequired(self, m):
        """Entirely recompute the model's req value"""
        if m['type'] == MODEL_CLOZE:
            # nothing to do
            return
        req = []
        flds = [f['name'] for f in m['flds']]
        for t in m['tmpls']:
            ret = self._reqForTemplate(m, flds, t)
            req.append((t['ord'], ret[0], ret[1]))
        m['req'] = req

    def _reqForTemplate(self, m, flds, t):
        """A rule which is supposed to determine whether a card should be
        generated or not according to its fields.

        See ../documentation/templates_generation_rules.md

        """
        a = []
        b = []
        for f in flds:
            a.append("ankiflag")
            b.append("")
        data = [1, 1, m['id'], 1, t['ord'], "", joinFields(a), 0]
        # The html of the card at position ord where each field's content is "ankiflag"
        full = self.col._renderQA(data)['q']
        data = [1, 1, m['id'], 1, t['ord'], "", joinFields(b), 0]
        # The html of the card at position ord where each field's content is the empty string ""
        empty = self.col._renderQA(data)['q']

        # if full and empty are the same, the template is invalid and there is
        # no way to satisfy it
        if full == empty:
            return "none", [], []
        type = 'all'
        req = []
        for i in range(len(flds)):
            tmp = a[:]
            tmp[i] = ""
            data[6] = joinFields(tmp)
            # if no field content appeared, field is required
            if "ankiflag" not in self.col._renderQA(data)['q']:
                req.append(i)
        if req:
            return type, req
        # if there are no required fields, switch to any mode
        type = 'any'
        req = []
        for i in range(len(flds)):
            tmp = b[:]
            tmp[i] = "1"
            data[6] = joinFields(tmp)
            # if not the same as empty, this field can make the card non-blank
            if self.col._renderQA(data)['q'] != empty:
                req.append(i)
        return type, req

    def availOrds(self, m, flds):
        """Given a joined field string, return ordinal of card type which
        should be generated. See
        ../documentation/templates_generation_rules.md for the detail

        """
        if m['type'] == MODEL_CLOZE:
            return self._availClozeOrds(m, flds)
        fields = {}
        for c, f in enumerate(splitFields(flds)):
            fields[c] = f.strip()
        avail = []#List of ord of cards which would be generated
        for ord, type, req in m['req']:
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

    def _availClozeOrds(self, m, flds, allowEmpty=True):
        """The list of fields F which are used in some {{cloze:F}} in a template

        keyword arguments:
        m: a model
        flds: a list of fields as in the database
        allowEmpty: allows to treat a note without cloze field as a note with a cloze number 1
        """
        sflds = splitFields(flds)
        map = self.fieldMap(m)#dictionnary (field name) -> (ord, field object)
        ords = set()#Will eventually contain the set of number of
                    #clozes in cloze fields (whether a field is a
                    #cloze field is determined according to template)
        matches = re.findall("{{[^}]*?cloze:(?:[^}]?:)*(.+?)}}", m['tmpls'][0]['qfmt'])
        matches += re.findall("<%cloze:(.+?)%>", m['tmpls'][0]['qfmt'])
        for fname in matches:
            if fname not in map:
                continue#Do not consider cloze not related to an existing field
            ord = map[fname][0]
            ords.update([int(m)-1 for m in re.findall(
                r"(?s){{c(\d+)::.+?}}", sflds[ord])])#The number of the cloze of this field, minus one
        if -1 in ords:#remove cloze 0
            ords.remove(-1)
        if not ords and allowEmpty:
            # empty clozes use first ord
            return [0]
        return list(ords)

    # Sync handling
    ##########################################################################

    def beforeUpload(self):
        for m in self.all():
            m['usn'] = 0
        self.save()
