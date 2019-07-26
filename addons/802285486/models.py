from anki.models import ModelManager
from anki.utils import intTime, splitFields
from anki.consts import *
from anki.hooks import runHook
from .debug import debugFun
import re

@debugFun
def getChangedTemplates(m, oldModel = None, newTemplatesData=None):
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
    """
    * Mark m modified if provided.
    * Schedule registry flush.
    * Calls hook newModel
     Keyword arguments:
    m -- A Model
    templates -- whether to check for cards not generated in this model
    oldModel -- a previous version of the model, to which to compare
    newTemplatesData -- a list whose i-th element state which is the
    new position of the i-th template of the old model and whether the
    template is new. It is set only if oldModel is set.
    """
    # print(f"""oldModel is: «
# {oldModel}
# », newTemplatesData is «
# {newTemplatesData}
# »""")
    if m and m['id']:
        if newTemplatesData is None:
            newTemplatesData = [{"is new": True,
                           "old idx":None}]*len(m['tmpls'])
        m['mod'] = intTime()
        m['usn'] = self.col.usn()
        if recomputeReq:
            changedOrNewReq = self._updateRequired(m, oldModel, newTemplatesData)
        else:
            changedOrNewReq = set()
        if templates:
            self._syncTemplates(m, changedOrNewReq)
    self.changed = True
    runHook("newModel")
    #print(f"""After saving, model is «
# {m}
# »""")

ModelManager.save = save
@debugFun
def _updateRequired(self, m, oldModel = None, newTemplatesData = None):
    """Entirely recompute the model's req value.

    Return positions idx such that the req for idx in model is not the
    req for oldIdx in oldModel. Or such that this card is new.
    """
    if m['type'] == MODEL_CLOZE:
        # nothing to do
        return
    changedTemplates = getChangedTemplates(m, oldModel, newTemplatesData)
    req = []
    changedOrNewReq = set()
    flds = [f['name'] for f in m['flds']]
    for idx,t in enumerate(m['tmpls']):
        oldIdx = newTemplatesData[idx]["old idx"]# Assumed not None,
        oldTup = oldModel['req'][oldIdx] if oldIdx is not None and oldModel else None
        if oldModel is not None and idx not in changedTemplates :
            if oldTup is None:
                print(f"newTemplatesData is «{newTemplatesData}»")
                print(f"oldIdx is «{oldIdx}»")
                print(f"oldReq is «oldModel['req']»")
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
    """Generate all cards not yet generated from, whose note's model is m"""
    rem = self.col.genCards(self.nids(m), changedOrNewReq)
ModelManager._syncTemplates = _syncTemplates

@debugFun
def availOrds(self, m, flds, changedOrNewReq = None):
    #oldModel = None, newTemplatesData = None
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
    for tup in m['req']:
        # print(f"""tup is {tup}.
        # m['req'] is {m['req']}
        # m is {m}""")
        ord, type, req = tup
        if changedOrNewReq is not None and ord not in changedOrNewReq:
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
    #self.save(m, oldModel = m, newTemplatesData = list(range(len(m['tmpls'])))
ModelManager.renameField = renameField
