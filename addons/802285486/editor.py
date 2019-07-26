from aqt.editor import Editor

def saveAddModeVars(self):
    if self.addMode:
        # save tags to model
        m = self.note.model()
        m['tags'] = self.note.tags
        self.mw.col.models.save(m, recomputeReq=False)
Editor.saveAddModeVars = saveAddModeVars
