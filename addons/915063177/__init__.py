import copy

import aqt
from aqt.clayout import CardLayout
from aqt.qt import QWidget
from aqt.utils import downArrow

from .clayout_top_cloze import Ui_Form

oldInit = CardLayout.__init__
def __init__(self, mw, note, ord=0, parent=None, addMode=False):
        parent = parent or mw
        self.did = parent.deckChooser.selectedId() if hasattr(parent,"deckChooser") else None
        return oldInit(self, mw, note, ord, parent, addMode)

CardLayout.__init__ = __init__

def redraw(self):
        """TODO
        update the list of card
        """
        self.cards = self.col.previewCards(self.note, 2, did=self.did)
        #the list of cards of this note, with all templates
        if self.ord >= len(self.cards) and not self._isCloze():
            self.ord = len(self.cards) - 1
        self.redrawing = True
        self.updateTopArea()
        self.redrawing = False
        self.onCardSelected()
CardLayout.redraw = redraw
        
def setupTopArea(self):
        self.topArea = QWidget()
        self.topAreaForm = Ui_Form() if self._isCloze() else aqt.forms.clayout_top.Ui_Form()
        self.topAreaForm.setupUi(self.topArea)
        if self._isCloze():
            cardNumber = self.ord+1
            self.topAreaForm.clozeNumber.setValue(cardNumber)
            self.topAreaForm.clozeNumber.valueChanged.connect(self.onCardSelected)
        else:
            self.topAreaForm.templateOptions.setText(_("Options") + " "+downArrow())
            self.topAreaForm.templateOptions.clicked.connect(self.onMore)
            self.topAreaForm.templatesBox.currentIndexChanged.connect(self.onCardSelected)
CardLayout.setupTopArea = setupTopArea

oldUpdateCardNames = CardLayout.updateCardNames

def updateCardNames(self):
        """ In the list of card name, change them according to
        current's name"""
        if self._isCloze():
            return
        oldUpdateCardNames(self)
CardLayout.updateCardNames = updateCardNames

def onCardSelected(self, idx=None):
        if self.redrawing:
            return
        if idx is not None:
            self.ord = idx-1 if self._isCloze() else idx
        if self._isCloze():
            tmpl = copy.copy(self.note.model()['tmpls'][0])
            tmpl['ord'] = self.ord
            self.card = self.col._newCard(self.note, tmpl, 1, flush=False, did=self.did)
        else:
            self.card = self.cards[self.ord]
        self.playedAudio = {}
        self.readCard()
        self.renderPreview()
CardLayout.onCardSelected = onCardSelected

def updateMainArea(self):
        pass
CardLayout.updateMainArea = updateMainArea
