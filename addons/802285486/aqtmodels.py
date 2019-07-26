from aqt.models import Models
from aqt.utils import getText
from aqt.models import AddModel

def onRename(self):
    txt = getText(_("New name:"), default=self.model['name'])
    if txt[1] and txt[0]:
        self.model['name'] = txt[0]
        self.mm.save(self.model, recomputeReq=False)
    self.updateModelsList()

Models.onRename = onRename

def modelChanged(self):
    idx = self.form.modelsList.currentRow()
    self.model = self.models[idx]
Models.modelChanged = modelChanged
