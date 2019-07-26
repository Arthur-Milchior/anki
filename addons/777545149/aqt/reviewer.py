from aqt.reviewer import *
from anki.lang import _
def onDelete(self):
    # only diff: adding a reason for deletion
        # need to check state because the shortcut is global to the main
        # window
        if self.mw.state != "review" or not self.card:
            return
        self.mw.checkpoint(_("Delete"))
        cnt = len(self.card.note().cards())
        id = self.card.note().id
        self.mw.col.remNotes([id],reason=f"Deletion of note {id} requested from the reviewer.")
        self.mw.reset()
        tooltip(ngettext(
            "Note and its %d card deleted.",
            "Note and its %d cards deleted.",
            cnt) % cnt)
Reviewer.onDelete=onDelete
