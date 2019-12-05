from aqt.models import AddModel, Models
from aqt.utils import getText


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
