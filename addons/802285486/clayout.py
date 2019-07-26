from aqt.clayout import CardLayout
from aqt.qt import *#for ngettext, QDialog
from anki.lang import _
from aqt.utils import showWarning, askUser, showInfo, getOnlyText, saveGeom
from anki.sound import clearAudioQueue
import copy
from .debug import debugFun


oldInit = CardLayout.__init__
@debugFun
def init(self,*args,**kwargs):
    try:
        oldInit(self,*args,**kwargs)
    except ValueError:
        print (f"recursive model is {self.model}")
        raise
    # self.oldIdxToNew = list(range(len(self.model['tmpls'])))
    self.newTemplatesData = [
        {"is new":False,
         "old idx":idx}
        for idx in (range(len(self.model['tmpls'])))]
    self.originalModel = copy.deepcopy(self.model)


CardLayout.__init__ = init
@debugFun
def onRemove(self):
    if len(self.model['tmpls']) < 2:
        return showInfo(_("At least one card type is required."))
    idx = self.ord
    originalIdx = self.newTemplatesData[idx]["old idx"]
    cards = self.mm.tmplUseCount(self.model, idx)
    cards = ngettext("%d card", "%d cards", cards) % cards
    msg = (_("Delete the '%(a)s' card type, and its %(b)s?") %
        dict(a=self.model['tmpls'][idx]['name'], b=cards))
    if not askUser(msg):
        return
    if not self.mm.remTemplate(self.model, self.cards[idx].template()):
        return showWarning(_("""\
Removing this card type would cause one or more notes to be deleted. \
Please create a new card type first."""))

    # if originalIdx is not None:
    #     oldIdxToNew[originalIdx] = None
    del self.newTemplatesData[idx]
    self.redraw()
CardLayout.onRemove = onRemove


@debugFun
def onReorder(self):
    n = len(self.cards)
    cur = self.ord+1
    pos = getOnlyText(
        _("Enter new card position (1...%s):") % n,
        default=str(cur))
    idx = self.ord
    originalMeta = self.newTemplatesData[idx]
    if not pos:
        return
    try:
        pos = int(pos)
    except ValueError:
        return
    if pos < 1 or pos > n:
        return
    if pos == cur:
        return
    pos -= 1
    self.mm.moveTemplate(self.model, self.card.template(), pos)
    del self.newTemplatesData[idx]
    self.newTemplatesData.insert(pos,originalMeta)
    self.ord = pos
    self.redraw()
CardLayout.onReorder = onReorder

@debugFun
def onAddCard(self):
    cnt = self.mw.col.models.useCount(self.model)
    txt = ngettext("This will create %d card. Proceed?",
                   "This will create %d cards. Proceed?", cnt) % cnt
    if not askUser(txt):
        return
    name = self._newCardName()
    t = self.mm.newTemplate(name)
    old = self.card.template()
    t['qfmt'] = old['qfmt']
    t['afmt'] = old['afmt']
    self.mm.addTemplate(self.model, t)
    self.newTemplatesData.append({"old idx":self.newTemplatesData[self.ord]["old idx"],
                            "is new": True})
    self.ord = len(self.cards)
    self.redraw()
CardLayout.onAddCard = onAddCard

@debugFun
def reject(self):#same as accept
    self.cancelPreviewTimer()
    clearAudioQueue()
    if self.addMode:
        # remove the filler fields we added
        for name in self.emptyFields:
            self.note[name] = ""
        self.mw.col.db.execute("delete from notes where id = ?",
                               self.note.id)
    self.mm.save(self.model, templates=True, oldModel = self.originalModel, newTemplatesData = self.newTemplatesData)
    self.mw.reset()
    saveGeom(self, "CardLayout")
    return QDialog.reject(self)
CardLayout.reject = reject
