# -*- coding: utf-8 -*-
# Github: https://github.com/Arthur-Milchior/anki-keep-model-in-add-cards
# Original code from Anki, copyright Damien Elmes <anki@ichi2.net>
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
# Add-on number 424778276 https://ankiweb.net/shared/info/424778276
import aqt
import aqt.addcards
import aqt.modelchooser
from anki.hooks import addHook, remHook
from anki.lang import _
from anki.notes import Note
from anki.sound import clearAudioQueue
from aqt.deckchooser import DeckChooser
from aqt.qt import QPushButton
from aqt.utils import tooltip


def debug(t):
    #print(t)
    pass

class AddCards(aqt.addcards.AddCards):
    def __init__(self,mw):
        debug("Call newInit")
        super().__init__(mw)
        remHook("currentModelChanged",self.onModelChange)
        remHook('reset', self.onReset)
        addHook("reset",self.onResetSameModel)

    def setupChoosers(self):
        debug("Call setupChoosers")
        class ModelChooser(aqt.modelchooser.ModelChooser):
            # def __init__(self, mw, widget, label=True):
            #     super().__init__( mw, widget, label=label)
            #     remHook('reset', self.onReset)
            def updateModels(selfModel):
                if hasattr(self,"editor"):#self's init has ended
                    modelName=self.editor.note._model["name"]
                else:# initialisation of the window
                    modelName=selfModel.deck.models.current()['name']
                selfModel.models.setText(modelName)

            def onModelChange(selfModel):
                """Open Choose Note Type window"""
                #Method called when we want to change the current model
                debug("Call newOnModelChange")
                from aqt.studydeck import StudyDeck
                current = selfModel.deck.models.current()['name']
                # edit button
                edit = QPushButton(_("Manage"), clicked=selfModel.onEdit)
                def nameFunc():
                    return sorted(selfModel.deck.models.allNames())
                ret = StudyDeck(
                    selfModel.mw, names=nameFunc,
                    accept=_("Choose"), title=_("Choose Note Type"),
                    help="_notes", current=current, parent=selfModel.widget,
                    buttons=[edit], cancel=True, geomKey="selectModel")
                if not ret.name:
                    return
                m = selfModel.deck.models.byName(ret.name)
                selfModel.deck.conf['curModel'] = m['id']
                cdeck = selfModel.deck.decks.current()
                cdeck['mid'] = m['id']
                selfModel.deck.decks.save(cdeck)
                #runHook("currentModelChanged")
                #selfModel.mw.reset()
                ### New line:
                debug("Call AddCard.onModelChange")
                self.onModelChange() #this is onModelChange from card, and note from ModelChange
                selfModel.updateModels()
        self.modelChooser = ModelChooser(
            self.mw, self.form.modelArea)
        self.deckChooser = DeckChooser(
            self.mw, self.form.deckArea)


    def onReset(self, model=None, keep=False):
        """Create a new note and set it.

        keyword arguments
        model -- A model object. Used for the new note.
        keep -- whether to keep sticky values from old note
        """
        flds = note.model()['flds']
        # copy fields from old note
        if oldNote:
            if not keep:
                self.removeTempNote(oldNote)
            for n in range(len(note.fields)):
                try:
                    if not keep or flds[n]['sticky']:
                        note.fields[n] = oldNote.fields[n]
                    else:
                        note.fields[n] = ""
                except IndexError:
                    break
        self.setAndFocusNote(note)

    def onResetSameModel(self,keep=False):#this is a new method
        debug("Call onResetSameModel")
        return self.onReset(model=self.editor.note._model,keep=keep)

    def _addCards(self):
        """Adding the content of the fields as a new note.

        Assume that the content of the GUI saved in the model."""
        debug("Call _addCards")
        self.editor.saveAddModeVars()
        note = self.editor.note
        note = self.addNote(note)
        if not note:
            return
        tooltip(_("Added"), period=500)
        # stop anything playing
        clearAudioQueue()
        self.onResetSameModel(keep=True)#Only difference is calling onResetSameModel instead of onReset
        self.mw.col.autosave()

    def _reject(self):
        debug("Call _reject")
        remHook('reset', self.onResetSameModel)
        super()._reject()
aqt.addcards.AddCards= AddCards
#The window opener contains information about the class, and not its adress. Thus it must be updated.
aqt.dialogs._dialogs["AddCards"]=[AddCards,None]
