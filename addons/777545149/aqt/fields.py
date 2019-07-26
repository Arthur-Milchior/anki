import copy

from aqt.fields import FieldDialog
from aqt.qt import *  # for QDialog
from aqt.utils import getOnlyText, showWarning

"""Similar to the former FieldDialog class. With the following:
originalModel -- a copy of the model, before the change. To allow  were changed and limit the recomputation to do"""

oldInit = FieldDialog.__init__
def init(self, mw, note, *args,**kwargs):
    self.originalModel = copy.deepcopy(note.model())
    oldInit(self, mw, note, *args,**kwargs)

FieldDialog.__init__ = init

def _uniqueName(self, prompt, ignoreOrd=None, old=""):
    """Ask for a new name using prompt, and default value old. Return it.

    Unles this name is already used elsewhere, in this case, return None and show a warning.
    If the default name is given, also return None. This avoid to recompute values while the fields stay exactly the same"""
    # only difference: return nothing if the answered name is the initial name
    txt = getOnlyText(prompt, default=old)
    if not txt:
        return
    for f in self.model['flds']:
        if ignoreOrd is not None and f['ord'] == ignoreOrd:
            if f['name'] == txt:# This condition is new
                return
            continue
        if f['name'] == txt:
            showWarning(_("That field name is already used."))
            return
    return txt
FieldDialog._uniqueName = _uniqueName


#TODO: Recompute template having a field changed.
# def reject(self):
#     print("Calling field's new reject")
#     self.saveField()
#     if self.oldSortField != self.model['sortf']:
#         self.mw.progress.start()
#         self.mw.col.updateFieldCache(self.mm.nids(self.model))
#         self.mw.progress.finish()
#     self.mm.save(self.model, templates = True, oldModel = self.originalModel, recomputeReq = True)# only dif is the new parameters.
#     self.mw.reset()
#     QDialog.reject(self)
# FieldDialog.reject = reject
