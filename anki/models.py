# -*- coding: utf-8 -*-
# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

import copy
import json
import re
import time

from anki.consts import *
from anki.hooks import runHook
from anki.lang import _
from anki.utils import checksum, ids2str, intTime, joinFields, splitFields

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
"""
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

    # Saving/loading registry
    #############################################################

    def __init__(self, col):
        self.col = col

    def load(self, json_):
        "Load registry from JSON."
        self.changed = False
        self.models = json.loads(json_)

    def save(self, model=None, templates=False):
        "Mark MODEL modified if provided, and schedule registry flush."
        if model and model['id']:
            model['mod'] = intTime()
            model['usn'] = self.col.usn()
            self._updateRequired(model)
            if templates:
                self._syncTemplates(model)
        self.changed = True
        runHook("newModel")

    def flush(self):
        "Flush the registry if any models were changed."
        if self.changed:
            self.ensureNotEmpty()
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
        "Get current model."
        model = self.get(self.col.decks.current().get('mid'))
        if not forDeck or not model:
            model = self.get(self.col.conf['curModel'])
        return model or list(self.models.values())[0]

    def setCurrent(self, model):
        self.col.conf['curModel'] = model['id']
        self.col.setMod()

    def get(self, id):
        "Get model with ID, or None."
        id = str(id)
        if id in self.models:
            return self.models[id]

    def all(self):
        "Get all models."
        return list(self.models.values())

    def allNames(self):
        return [model['name'] for model in self.all()]

    def byName(self, name):
        "Get model with NAME."
        for model in list(self.models.values()):
            if model['name'] == name:
                return model

    def new(self, name):
        "Create a new model, save it in the registry, and return it."
        # caller should call save() after modifying
        model = defaultModel.copy()
        model['name'] = name
        model['mod'] = intTime()
        model['flds'] = []
        model['tmpls'] = []
        model['tags'] = []
        model['id'] = None
        return model

    def rem(self, model):
        "Delete model, and all its cards/notes."
        self.col.modSchema(check=True)
        current = self.current()['id'] == model['id']
        # delete notes/cards
        self.col.remCards(self.col.db.list("""
select id from cards where nid in (select id from notes where mid = ?)""",
                                      model['id']))
        # then the model
        del self.models[str(model['id'])]
        self.save()
        # GUI should ensure last model is not deleted
        if current:
            self.setCurrent(list(self.models.values())[0])

    def add(self, model):
        self._setID(model)
        self.update(model)
        self.setCurrent(model)
        self.save(model)

    def ensureNameUnique(self, model):
        for mcur in self.all():
            if (mcur['name'] == model['name'] and mcur['id'] != model['id']):
                model['name'] += "-" + checksum(str(time.time()))[:5]
                break

    def update(self, model):
        "Add or update an existing model. Used for syncing and merging."
        self.ensureNameUnique(model)
        self.models[str(model['id'])] = model
        # mark registry changed, but don't bump mod time
        self.save()

    def _setID(self, model):
        while 1:
            id = str(intTime(1000))
            if id not in self.models:
                break
        model['id'] = id

    def have(self, id):
        return str(id) in self.models

    def ids(self):
        return list(self.models.keys())

    # Tools
    ##################################################

    def nids(self, model):
        "Note ids for MODEL."
        return self.col.db.list(
            "select id from notes where mid = ?", model['id'])

    def useCount(self, model):
        "Number of note using MODEL."
        return self.col.db.scalar(
            "select count() from notes where mid = ?", model['id'])

    def tmplUseCount(self, model, ord):
        return self.col.db.scalar("""
select count() from cards, notes where cards.nid = notes.id
and notes.mid = ? and cards.ord = ?""", model['id'], ord)

    # Copying
    ##################################################

    def copy(self, model):
        "Copy, save and return."
        m2 = copy.deepcopy(model)
        m2['name'] = _("%s copy") % m2['name']
        self.add(m2)
        return m2

    # Fields
    ##################################################

    def newField(self, name):
        assert(isinstance(name, str))
        fieldType = defaultField.copy()
        fieldType['name'] = name
        return fieldType

    def fieldMap(self, model):
        "Mapping of field name -> (ord, field)."
        return dict((fieldType['name'], (fieldType['ord'], fieldType)) for fieldType in model['flds'])

    def fieldNames(self, model):
        return [fieldType['name'] for fieldType in model['flds']]

    def sortIdx(self, model):
        return model['sortf']

    def setSortIdx(self, model, idx):
        assert 0 <= idx < len(model['flds'])
        self.col.modSchema(check=True)
        model['sortf'] = idx
        self.col.updateFieldCache(self.nids(model))
        self.save(model)

    def addField(self, model, fieldType):
        # only mod schema if model isn't new
        if model['id']:
            self.col.modSchema(check=True)
        model['flds'].append(fieldType)
        self._updateFieldOrds(model)
        self.save(model)
        def add(fieldsContents):
            fieldsContents.append("")
            return fieldsContents
        self._transformFields(model, add)

    def remField(self, model, fieldTypeToRemove):
        self.col.modSchema(check=True)
        # save old sort field
        sortFldName = model['flds'][model['sortf']]['name']
        idx = model['flds'].index(fieldTypeToRemove)
        model['flds'].remove(fieldTypeToRemove)
        # restore old sort field if possible, or revert to first field
        model['sortf'] = 0
        for index, fieldType in enumerate(model['flds']):
            if fieldType['name'] == sortFldName:
                model['sortf'] = index
                break
        self._updateFieldOrds(model)
        def delete(fieldsContents):
            del fieldsContents[idx]
            return fieldsContents
        self._transformFields(model, delete)
        if model['flds'][model['sortf']]['name'] != sortFldName:
            # need to rebuild sort field
            self.col.updateFieldCache(self.nids(model))
        # saves
        self.renameField(model, fieldTypeToRemove, None)

    def moveField(self, model, fieldType, idx):
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
        self.save(model)
        def move(fields, oldidx=oldidx):
            val = fields[oldidx]
            del fields[oldidx]
            fields.insert(idx, val)
            return fields
        self._transformFields(model, move)

    def renameField(self, model, fieldType, newName):
        self.col.modSchema(check=True)
        pat = r'{{([^{}]*)([:#^/]|[^:#/^}][^:}]*?:|)%s}}'
        def wrap(txt):
            def repl(match):
                return '{{' + match.group(1) + match.group(2) + txt +  '}}'
            return repl
        for template in model['tmpls']:
            for fmt in ('qfmt', 'afmt'):
                if newName:
                    template[fmt] = re.sub(
                        pat % re.escape(fieldType['name']), wrap(newName), template[fmt])
                else:
                    template[fmt] = re.sub(
                        pat  % re.escape(fieldType['name']), "", template[fmt])
        fieldType['name'] = newName
        self.save(model)

    def _updateFieldOrds(self, model):
        for index, fieldType in enumerate(model['flds']):
            fieldType['ord'] = index

    def _transformFields(self, model, fn):
        # model hasn't been added yet?
        if not model['id']:
            return
        r = []
        for (id, flds) in self.col.db.execute(
            "select id, flds from notes where mid = ?", model['id']):
            r.append((joinFields(fn(splitFields(flds))),
                      intTime(), self.col.usn(), id))
        self.col.db.executemany(
            "update notes set flds=?,mod=?,usn=? where id = ?", r)

    # Templates
    ##################################################

    def newTemplate(self, name):
        template = defaultTemplate.copy()
        template['name'] = name
        return template

    def addTemplate(self, model, template):
        "Note: should col.genCards() afterwards."
        if model['id']:
            self.col.modSchema(check=True)
        model['tmpls'].append(template)
        self._updateTemplOrds(model)
        self.save(model)

    def remTemplate(self, model, template):
        "False if removing template would leave orphan notes."
        assert len(model['tmpls']) > 1
        # find cards using this template
        ord = model['tmpls'].index(template)
        cids = self.col.db.list("""
select card.id from cards card, notes note where card.nid=note.id and mid = ? and ord = ?""",
                                 model['id'], ord)
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
                             self.col.usn(), intTime(), model['id'], ord)
        model['tmpls'].remove(template)
        self._updateTemplOrds(model)
        self.save(model)
        return True

    def _updateTemplOrds(self, model):
        for index, template in enumerate(model['tmpls']):
            template['ord'] = index

    def moveTemplate(self, model, template, idx):
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
        self.save(model)
        self.col.db.execute("""
update cards set ord = (case %s end),usn=?,mod=? where nid in (
select id from notes where mid = ?)""" % " ".join(map),
                             self.col.usn(), intTime(), model['id'])

    def _syncTemplates(self, model):
        rem = self.col.genCards(self.nids(model))

    # Model changing
    ##########################################################################
    # - maps are ord->ord, and there should not be duplicate targets
    # - newModel should be self if model is not changing

    def change(self, model, nids, newModel, fmap, cmap):
        self.col.modSchema(check=True)
        assert newModel['id'] == model['id'] or (fmap and cmap)
        if fmap:
            self._changeNotes(nids, newModel, fmap)
        if cmap:
            self._changeCards(nids, model, newModel, cmap)
        self.col.genCards(nids)

    def _changeNotes(self, nids, newModel, map):
        d = []
        nfields = len(newModel['flds'])
        for (nid, flds) in self.col.db.execute(
            "select id, flds from notes where id in "+ids2str(nids)):
            newflds = {}
            flds = splitFields(flds)
            for old, new in list(map.items()):
                newflds[new] = flds[old]
            flds = []
            for index in range(nfields):
                flds.append(newflds.get(index, ""))
            flds = joinFields(flds)
            d.append(dict(nid=nid, flds=flds, mid=newModel['id'],
                      mod=intTime(),u=self.col.usn()))
        self.col.db.executemany(
            "update notes set flds=:flds,mid=:mid,mod=:mod,usn=:u where id = :nid", d)
        self.col.updateFieldCache(nids)

    def _changeCards(self, nids, oldModel, newModel, map):
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
                    cid=cid,new=new,u=self.col.usn(),mod=intTime()))
            else:
                deleted.append(cid)
        self.col.db.executemany(
            "update cards set ord=:new,usn=:u,mod=:mod where id=:cid",
            d)
        self.col.remCards(deleted)

    # Schema hash
    ##########################################################################

    def scmhash(self, model):
        "Return a hash of the schema, to see if models are compatible."
        s = ""
        for fieldType in model['flds']:
            s += fieldType['name']
        for template in model['tmpls']:
            s += template['name']
        return checksum(s)

    # Required field/text cache
    ##########################################################################

    def _updateRequired(self, model):
        if model['type'] == MODEL_CLOZE:
            # nothing to do
            return
        req = []
        flds = [fieldType['name'] for fieldType in model['flds']]
        for template in model['tmpls']:
            ret = self._reqForTemplate(model, flds, template)
            req.append((template['ord'], ret[0], ret[1]))
        model['req'] = req

    def _reqForTemplate(self, model, flds, template):
        a = ["ankiflag"] * len(flds)
        b = [""] * len(flds)
        data = [1, 1, model['id'], 1, template['ord'], "", joinFields(a), 0]
        full = self.col._renderQA(data)['q']
        data = [1, 1, model['id'], 1, template['ord'], "", joinFields(b), 0]
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

    def availOrds(self, model, flds):
        "Given a joined field string, return available template ordinals."
        if model['type'] == MODEL_CLOZE:
            return self._availClozeOrds(model, flds)
        fields = {}
        for index, fieldType in enumerate(splitFields(flds)):
            fields[index] = fieldType.strip()
        avail = []
        for ord, type, req in model['req']:
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

    def _availClozeOrds(self, model, flds, allowEmpty=True):
        sflds = splitFields(flds)
        map = self.fieldMap(model)
        ords = set()
        matches = re.findall("{{[^}]*?cloze:(?:[^}]?:)*(.+?)}}", model['tmpls'][0]['qfmt'])
        matches += re.findall("<%cloze:(.+?)%>", model['tmpls'][0]['qfmt'])
        for fname in matches:
            if fname not in map:
                continue
            ord = map[fname][0]
            ords.update([int(match)-1 for match in re.findall(
                r"(?s){{c(\d+)::.+?}}", sflds[ord])])
        if -1 in ords:
            ords.remove(-1)
        if not ords and allowEmpty:
            # empty clozes use first ord
            return [0]
        return list(ords)

    # Sync handling
    ##########################################################################

    def beforeUpload(self):
        for model in self.all():
            model['usn'] = 0
        self.save()
