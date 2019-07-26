from aqt.editor import Editor


def saveAddModeVars(self):
    """During creation of new notes, save tags to the note's model"""
    # State that the requirements of the current model should not be recomputed.
    if self.addMode:
        # save tags to model
        m = self.note.model()
        m['tags'] = self.note.tags
        self.mw.col.models.save(m, recomputeReq=False)# Modified: do not do recomputeReq
Editor.saveAddModeVars = saveAddModeVars
