from anki.models import *
from anki.utils import intTime, splitFields
from anki.consts import *
from anki.hooks import runHook
from ..debug import debugFun
import re

@debugFun
#new function
def getChangedTemplates(m, oldModel = None, newTemplatesData=None):
    """Set of ord of templates which are not the same in the question side
    in oldModel and in newTemplatesData

    m -- A Model
    oldModel -- a previous version of the model, to which to compare templates
    newTemplatesData -- a list whose i-th element state which is the
    new position of the i-th template of the old model and whether the
    template is new. It is set only if oldModel is set.
    """
    if newTemplatesData is None:
        changedTemplates = set(range(len(m['tmpls'])))
        return changedTemplates
    changedTemplates = set()
    for idx, tmpl in enumerate(m['tmpls']):
        oldIdx = newTemplatesData[idx]["old idx"]
        if oldIdx is None:
            changedTemplates.add(idx)
        else:
            oldTmpl =oldModel['tmpls'][oldIdx]
            if tmpl['qfmt']!=oldTmpl['qfmt']:
                    changedTemplates.add(idx)
    return changedTemplates


@debugFun
def save(self, m=None, templates=False, oldModel=None, newTemplatesData = None, recomputeReq=True):
    # Adding: oldModel, newTemplatesData, recomputeReq, in order to limit the req to recompute
    """
    * Mark m modified if provided.
    * Schedule registry flush.
    * Calls hook newModel
     Keyword arguments:
    m -- A Model
    templates -- whether to check for cards not generated in this model
    oldModel -- a previous version of the model, to which to compare templates
    newTemplatesData -- a list whose i-th element state which is the
    new position of the i-th template of the old model and whether the
    template is new. It is set only if oldModel is set.
    recomputeReq -- whether to recompute req (it's false while a note type is modified. It should be true only when the note type editor is closed)
    """
    if m and m['id']: # old
        if newTemplatesData is None: # New
            newTemplatesData = [{"is new": True, # new
                                 "old idx":None}]*len(m['tmpls']) # new
        m['mod'] = intTime() # old
        m['usn'] = self.col.usn() # old
        if recomputeReq: # new
            changedOrNewReq = self._updateRequired(m, oldModel, newTemplatesData) # adding parameters
        else: # new
            changedOrNewReq = set() # new
        if templates: # old
            self._syncTemplates(m, changedOrNewReq) # adding the second parameter
    self.changed = True # old
    runHook("newModel") # old
ModelManager.save = save

@debugFun
def _updateRequired(self, m, oldModel = None, newTemplatesData = None):
    # The modification consists in adding  parameters oldModel and newTemplatesData. They allow to reduce computation of requirements to case where they are indeed usefull
    """Entirely recompute the model's req value.

    Return positions idx such that the req for idx in model is not the
    req for oldIdx in oldModel. Or such that this card is new.

    m -- A Model
    oldModel -- a previous version of the model, to which to compare templates
    newTemplatesData -- a list whose i-th element state which is the
    new position of the i-th template of the old model and whether the
    template is new. It is set only if oldModel is set.
    """
    if m['type'] == MODEL_CLOZE:
        # nothing to do
        return
    changedTemplates = getChangedTemplates(m, oldModel, newTemplatesData) # new
    req = []
    changedOrNewReq = set() # new
    flds = [f['name'] for f in m['flds']]
    for idx,t in enumerate(m['tmpls']):
        oldIdx = newTemplatesData[idx]["old idx"]# Assumed not None,
        oldTup = oldModel['req'][oldIdx] if oldIdx is not None and oldModel else None
        if oldModel is not None and idx not in changedTemplates :
            if oldTup is None:
                assert False
            oldIdx, oldType, oldReq_ = oldTup
            tup = (idx, oldType, oldReq_)
            req.append(tup)
            if newTemplatesData[idx]["is new"]:
                changedOrNewReq.add(idx)
            continue
        else:
            ret = self._reqForTemplate(m, flds, t)
            tup = (idx, ret[0], ret[1])
            if oldTup is None or oldTup[1]!=tup[1] or oldTup[2]!=tup[2]:
                changedOrNewReq.add(idx)
            req.append(tup)
    m['req'] = req
    return changedOrNewReq
ModelManager._updateRequired = _updateRequired

@debugFun
def _syncTemplates(self, m, changedOrNewReq = None):
    # The only change is that it pass the new parameter, changedOrNewReq, to genCards
    """Generate all cards not yet generated from, whose note's model is m"""
    rem = self.col.genCards(self.nids(m), changedOrNewReq)
ModelManager._syncTemplates = _syncTemplates

@debugFun
def availOrds(self, m, flds, changedOrNewReq = None):
    # new parameters:
    # changedOnNewReq. If it is present, only the ord it contains are recomputed
    """Given a joined field string, return template ordinals which should be
    seen. See ../documentation/templates_generation_rules.md for
    the detail
     """
    if m['type'] == MODEL_CLOZE:
        return self._availClozeOrds(m, flds)
    fields = {}
    for c, f in enumerate(splitFields(flds)):
        fields[c] = f.strip()
    avail = []#List of ord cards which would be generated
    for ord, type, req in m['req']:
        if changedOrNewReq is not None and ord not in changedOrNewReq:#This condition is new
            continue
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

ModelManager.availOrds = availOrds

def renameField(self, m, field, newName):
    # Only difference is that model is not saved at the end. Instead, we'll wait until we end edition of model to save it.
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
    # Only difference is here. Originally, the model is already saved, triggering a lot of recomputation which is currently useless.
ModelManager.renameField = renameField

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
        # only change: adding a reason when calling remCards
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
        self.col.remCards(deleted,reason=f"Changing notes {nids} from model {oldModel} to {newModel}, leading to deletion of {deleted}")# only change: adding a reason

ModelManager._changeCards=_changeCards

def rem(self, m):
    # only dif: adding a reason for deletion
        "Delete model, and all its cards/notes."
        self.col.modSchema(check=True)
        current = self.current()['id'] == m['id']
        # delete notes/cards
        cids=self.col.db.list("""
select id from cards where nid in (select id from notes where mid = ?)""",
                                           m['id'])
        self.col.remCards(cids, reason=f"Deleting cards {cids} because we delete the model {m}")
        # then the model
        del self.models[str(m['id'])]
        self.save()
        # GUI should ensure last model is not deleted
        if current:
            self.setCurrent(list(self.models.values())[0])
ModelManager.rem = rem

def remTemplate(self, m, template):
    # only dif: adding a reason for deletion
        "False if removing template would leave orphan notes."
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
        self.col.remCards(cids,reason=f"Removing card type {template} from model {m}")
        # shift ordinals
        self.col.db.execute("""
update cards set ord = ord - 1, usn = ?, mod = ?
 where nid in (select id from notes where mid = ?) and ord > ?""",
                             self.col.usn(), intTime(), m['id'], ord)
        m['tmpls'].remove(template)
        self._updateTemplOrds(m)
        self.save(m)
        return True
ModelManager.remTemplate=remTemplate
