# -*- coding: utf-8 -*-
# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""The window used to:
* edit a note type
* preview the different cards of a note."""
import collections
import json
import re

import aqt
from anki.consts import *
from anki.hooks import runFilter
from anki.lang import _, ngettext
from anki.sound import clearAudioQueue, playFromText
from anki.utils import bodyClass, isMac, isWin, joinFields
from aqt.qt import *
from aqt.utils import (askUser, downArrow, getOnlyText, mungeQA, openHelp,
                       restoreGeom, saveGeom, showInfo, showWarning)
from aqt.webview import AnkiWebView


class CardLayout(QDialog):
    """TODO

    An object of class CardLayout contains:
    nw -- the main window
    parent -- the parent of the caller, by default the main window
    note -- the note object considered
    ord -- the order of the card considered
    col -- the current collection
    mm -- The model manager
    model -- the model of the note
    addMode -- if the card layout is called for a new card (in this case, it is temporary added to the db). True if its called from models.py, false if its called from edit.py
    emptyFields -- the list of fields which are empty. Used only if addMode is true
    redrawing -- is it currently redrawing (forbid savecard and onCardSelected)
    cards -- the list of cards of the current note, each with their template.
    """

    def __init__(self, mw, note, ord=0, parent=None, addMode=False):
        QDialog.__init__(self, parent or mw, Qt.Window)
        mw.setupDialogGC(self)
        self.mw = aqt.mw
        self.parent = parent or mw
        self.note = note
        self.ord = ord
        self.col = self.mw.col
        self.mm = self.mw.col.models
        self.model = note.model()
        self.mw.checkpoint(_("Card Types"))
        self.addMode = addMode
        if addMode:
            # save it to DB temporarily
            self.emptyFields = []
            for name, val in list(note.items()):
                if val.strip():
                    continue
                self.emptyFields.append(name)
                note[name] = "(%s)" % name
            note.flush()
        self.setupTopArea()
        self.setupMainArea()
        self.setupButtons()
        self.setupShortcuts()
        self.setWindowTitle(_("Card Types for %s") % self.model['name'])
        v1 = QVBoxLayout()
        v1.addWidget(self.topArea)
        v1.addWidget(self.mainArea)
        v1.addLayout(self.buttons)
        v1.setContentsMargins(12,12,12,12)
        self.setLayout(v1)
        self.redraw()
        restoreGeom(self, "CardLayout")
        self.setWindowModality(Qt.ApplicationModal)
        self.show()
        # take the focus away from the first input area when starting up,
        # as users tend to accidentally type into the template
        self.setFocus()

    def redraw(self):
        """TODO
        update the list of card
        """
        did = None
        if hasattr(self.parent,"deckChooser"):
            did = self.parent.deckChooser.selectedId()
        self.cards = self.col.previewCards(self.note, 2, did=did)
        #the list of cards of this note, with all templates
        idx = self.ord
        if idx >= len(self.cards):
            self.ord = len(self.cards) - 1

        self.redrawing = True
        self.updateTopArea()
        self.updateMainArea()
        self.redrawing = False
        self.onCardSelected(self.ord)

    def setupShortcuts(self):
        for i in range(1,9):
            QShortcut(QKeySequence("Ctrl+%d" % i), self, activated=lambda i=i: self.selectCard(i))

    def selectCard(self, number):
        """Change ord to n-1 and redraw."""
        self.ord = number-1
        self.redraw()

    def setupTopArea(self):
        self.topArea = QWidget()
        self.topAreaForm = aqt.forms.clayout_top.Ui_Form()
        self.topAreaForm.setupUi(self.topArea)
        self.topAreaForm.templateOptions.setText(_("Options") + " "+downArrow())
        self.topAreaForm.templateOptions.clicked.connect(self.onMore)
        self.topAreaForm.templatesBox.currentIndexChanged.connect(self.onCardSelected)

    def updateTopArea(self):
        cnt = self.mw.col.models.useCount(self.model)
        #number of notes using this model
        self.topAreaForm.changesLabel.setText(ngettext(
            "Changes below will affect the %(cnt)d note that uses this card type.",
            "Changes below will affect the %(cnt)d notes that use this card type.",
            cnt) % dict(cnt=cnt))
        self.updateCardNames()

    def updateCardNames(self):
        """ In the list of card name, change them according to
        current's name"""
        self.redrawing = True
        combo = self.topAreaForm.templatesBox
        combo.clear()
        combo.addItems(self._summarizedName(template) for template in self.model['tmpls'])
        combo.setCurrentIndex(self.ord)
        combo.setEnabled(not self._isCloze())
        self.redrawing = False

    def _summarizedName(self, tmpl):
        """Compute the text appearing in the list of templates, on top of the window

        tmpl -- a template object
        """
        return "{}: {} -> {}".format(
            tmpl['name'],
            self._fieldsOnTemplate(tmpl['qfmt']),
            self._fieldsOnTemplate(tmpl['afmt']))

    def _fieldsOnTemplate(self, fmt):
        """List of tags found in fmt, separated by +, limited to 30 characters
        (not counting the +), in lexicographic order, with +... if some are
        missings."""
        matches = re.findall("{{[^#/}]+?}}", fmt)
        charsAllowed = 30
        result = collections.OrderedDict()
        for match in matches:
            # strip off mustache
            match = re.sub(r"[{}]", "", match)
            # strip off modifiers
            match = match.split(":")[-1]
            # don't show 'FrontSide'
            if match == "FrontSide":
                continue

            if match not in result:
                result[match] = True
                charsAllowed -= len(match)
                if charsAllowed <= 0:
                    break

        str = "+".join(result.keys())
        if charsAllowed <= 0:
            str += "+..."
        return str

    def _isCloze(self):
        return self.model['type'] == MODEL_CLOZE

    def setupMainArea(self):
        self.mainArea = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(0,0,0,0)
        layout.setSpacing(3)
        left = QWidget()
        # template area
        tform = self.tform = aqt.forms.template.Ui_Form()
        tform.setupUi(left)
        tform.label1.setText(" →")
        tform.label2.setText(" →")
        tform.labelc1.setText(" ↗")
        tform.labelc2.setText(" ↘")
        if self.style().objectName() == "gtk+":
            # gtk+ requires margins in inner layout
            tform.tlayout1.setContentsMargins(0, 11, 0, 0)
            tform.tlayout2.setContentsMargins(0, 11, 0, 0)
            tform.tlayout3.setContentsMargins(0, 11, 0, 0)
        tform.groupBox_3.setTitle(_(
            "Styling (shared between cards)"))
        tform.front.textChanged.connect(self.saveCard)
        tform.css.textChanged.connect(self.saveCard)
        tform.back.textChanged.connect(self.saveCard)
        layout.addWidget(left, 5)
        # preview area
        right = QWidget()
        pform = self.pform = aqt.forms.preview.Ui_Form()
        pform.setupUi(right)
        if self.style().objectName() == "gtk+":
            # gtk+ requires margins in inner layout
            pform.frontPrevBox.setContentsMargins(0, 11, 0, 0)
            pform.backPrevBox.setContentsMargins(0, 11, 0, 0)

        self.setupWebviews()

        layout.addWidget(right, 5)
        self.mainArea.setLayout(layout)

    def setupWebviews(self):
        pform = self.pform
        pform.frontWeb = AnkiWebView()
        pform.frontPrevBox.addWidget(pform.frontWeb)
        pform.backWeb = AnkiWebView()
        pform.backPrevBox.addWidget(pform.backWeb)
        jsinc = ["jquery.js","browsersel.js",
                 "mathjax/conf.js", "mathjax/MathJax.js",
                 "reviewer.js"]
        pform.frontWeb.stdHtml(self.mw.reviewer.revHtml(),
                               css=["reviewer.css"],
                               js=jsinc)
        pform.backWeb.stdHtml(self.mw.reviewer.revHtml(),
                              css=["reviewer.css"],
                               js=jsinc)

    def updateMainArea(self):
        if self._isCloze():
            cnt = len(self.mm.availOrds(
                self.model, joinFields(self.note.fields)))
            for groupBox in self.pform.groupBox, self.pform.groupBox_2:
                groupBox.setTitle(groupBox.title() + _(" (1 of %d)") % max(cnt, 1))

    def onRemove(self):
        """ Remove the current template, except if it would leave a note without card. Ask user for confirmation"""
        if len(self.model['tmpls']) < 2:
            return showInfo(_("At least one card type is required."))
        idx = self.ord
        cards = self.mm.tmplUseCount(self.model, idx)
        cards = ngettext("%d card", "%d cards", cards) % cards
        msg = (_("Delete the '%(modelName)s' card type, and its %(cards)s?") %
            dict(modelName=self.model['tmpls'][idx]['name'], cards=cards))
        if not askUser(msg):
            return
        if not self.mm.remTemplate(self.model, self.cards[idx].template()):
            return showWarning(_("""\
Removing this card type would cause one or more notes to be deleted. \
Please create a new card type first."""))
        self.redraw()

    # Buttons
    ##########################################################################

    def setupButtons(self):
        layout = self.buttons = QHBoxLayout()
        help = QPushButton(_("Help"))
        help.setAutoDefault(False)
        layout.addWidget(help)
        help.clicked.connect(self.onHelp)
        layout.addStretch()
        addField = QPushButton(_("Add Field"))
        addField.setAutoDefault(False)
        layout.addWidget(addField)
        addField.clicked.connect(self.onAddField)
        if not self._isCloze():
            flip = QPushButton(_("Flip"))
            flip.setAutoDefault(False)
            layout.addWidget(flip)
            flip.clicked.connect(self.onFlip)
        layout.addStretch()
        close = QPushButton(_("Close"))
        close.setAutoDefault(False)
        layout.addWidget(close)
        close.clicked.connect(self.accept)

    # Cards
    ##########################################################################

    def onCardSelected(self, idx):
        if self.redrawing:
            return
        self.card = self.cards[idx]
        self.ord = idx
        self.playedAudio = {}
        self.readCard()
        self.renderPreview()

    def readCard(self):
        template = self.card.template()
        self.redrawing = True
        self.tform.front.setPlainText(template['qfmt'])
        self.tform.css.setPlainText(self.model['css'])
        self.tform.back.setPlainText(template['afmt'])
        self.tform.front.setAcceptRichText(False)
        self.tform.css.setAcceptRichText(False)
        self.tform.back.setAcceptRichText(False)
        self.tform.front.setTabStopWidth(30)
        self.tform.css.setTabStopWidth(30)
        self.tform.back.setTabStopWidth(30)
        self.redrawing = False

    def saveCard(self):
        if self.redrawing:
            return
        text = self.tform.front.toPlainText()
        self.card.template()['qfmt'] = text
        text = self.tform.css.toPlainText()
        self.card.model()['css'] = text
        text = self.tform.back.toPlainText()
        self.card.template()['afmt'] = text
        self.renderPreview()

    # Preview
    ##########################################################################

    _previewTimer = None

    def renderPreview(self):
        # schedule a preview when timing stops
        self.cancelPreviewTimer()
        self._previewTimer = self.mw.progress.timer(500, self._renderPreview, False)

    def cancelPreviewTimer(self):
        if self._previewTimer:
            self._previewTimer.stop()
            self._previewTimer = None

    def _renderPreview(self):
        """
        change the answer and question side of the preview
        windows. Change the list of name of cards.
        """
        self.cancelPreviewTimer()

        card = self.card
        ti = self.maybeTextInput

        bodyclass = bodyClass(self.mw.col, card)

        # deal with [[type:, image and remove sound of the card's
        # question and answer
        questionHtmlPreview = ti(mungeQA(self.mw.col, card.q(reload=True)))
        questionHtmlPreview = runFilter("prepareQA", questionHtmlPreview, card, "clayoutQuestion")

        answerHtmlPreview = ti(mungeQA(self.mw.col, card.a()), type='a')
        answerHtmlPreview = runFilter("prepareQA", answerHtmlPreview, card, "clayoutAnswer")

        # use _showAnswer to avoid the longer delay
        self.pform.frontWeb.eval("_showAnswer(%s,'%s');" % (json.dumps(questionHtmlPreview), bodyclass))
        self.pform.backWeb.eval("_showAnswer(%s, '%s');" % (json.dumps(answerHtmlPreview), bodyclass))

        clearAudioQueue()
        if card.id not in self.playedAudio:# this ensure that audio is
            # played only once until a card is selected again
            playFromText(card.q())
            playFromText(card.a())
            self.playedAudio[card.id] = True

        self.updateCardNames()

    def maybeTextInput(self, txt, type='q'):
        """HTML: A default example for [[type:, which is shown in the preview
        window.

        On the question side, it shows "exomple", on the answer side
        it shows the correction, for when the right answer is "an
        example".

        txt -- the card type
        type -- a side. 'q' for question, 'a' for answer
        """
        if "[[type:" not in txt:
            return txt
        origLen = len(txt)
        txt = txt.replace("<hr id=answer>", "")
        hadHR = origLen != len(txt)
        def answerRepl(match):
            res = self.mw.reviewer.correct("exomple", "an example")
            if hadHR:
                res = "<hr id=answer>" + res
            return res
        if type == 'q':
            repl = "<input id='typeans' type=text value='exomple' readonly='readonly'>"
            repl = "<center>%s</center>" % repl
        else:
            repl = answerRepl
        return re.sub(r"\[\[type:.+?\]\]", repl, txt)

    # Card operations
    ######################################################################

    def onRename(self):
        name = getOnlyText(_("New name:"),
                           default=self.card.template()['name'])
        if not name:
            return
        if name in [card.template()['name'] for card in self.cards
                    if card.template()['ord'] != self.ord]:
            return showWarning(_("That name is already used."))
        self.card.template()['name'] = name
        self.redraw()

    def onReorder(self):
        """Asks user for a new position for current template. Move to this position if it is a valid position."""
        numberOfCard = len(self.cards)
        cur = self.card.template()['ord']+1
        pos = getOnlyText(
            _("Enter new card position (1...%s):") % numberOfCard,
            default=str(cur))
        if not pos:
            return
        try:
            pos = int(pos)
        except ValueError:
            return
        if pos < 1 or pos > numberOfCard:
            return
        if pos == cur:
            return
        pos -= 1
        self.mm.moveTemplate(self.model, self.card.template(), pos)
        self.ord = pos
        self.redraw()

    def _newCardName(self):
        cardUserIndex = len(self.cards) + 1
        while 1:
            name = _("Card %d") % cardUserIndex
            if name not in [card.template()['name'] for card in self.cards]:
                break
            cardUserIndex += 1
        return name

    def onAddCard(self):
        """Ask for confirmation and create a copy of current card as the last template"""
        cnt = self.mw.col.models.useCount(self.model)
        txt = ngettext("This will create %d card. Proceed?",
                       "This will create %d cards. Proceed?", cnt) % cnt
        if not askUser(txt):
            return
        name = self._newCardName()
        template = self.mm.newTemplate(name)
        old = self.card.template()
        template['qfmt'] = old['qfmt']
        template['afmt'] = old['afmt']
        self.mm.addTemplate(self.model, template)
        self.ord = len(self.cards)
        self.redraw()

    def onFlip(self):
        old = self.card.template()
        self._flipQA(old, old)
        self.redraw()

    def _flipQA(self, src, dst):
        match = re.match("(?s)(.+)<hr id=answer>(.+)", src['afmt'])
        if not match:
            showInfo(_("""\
Anki couldn't find the line between the question and answer. Please \
adjust the template manually to switch the question and answer."""))
            return
        dst['afmt'] = "{{FrontSide}}\n\n<hr id=answer>\n\n%s" % src['qfmt']
        dst['qfmt'] = match.group(2).strip()
        return True

    def onMore(self):
        menu = QMenu(self)

        if not self._isCloze():
            action = menu.addAction(_("Add Card Type..."))
            action.triggered.connect(self.onAddCard)

            action = menu.addAction(_("Remove Card Type..."))
            action.triggered.connect(self.onRemove)

            action = menu.addAction(_("Rename Card Type..."))
            action.triggered.connect(self.onRename)

            action = menu.addAction(_("Reposition Card Type..."))
            action.triggered.connect(self.onReorder)

            menu.addSeparator()

            template = self.card.template()
            if template['did']:
                toggle = _(" (on)")
            else:
                toggle = _(" (off)")
            action = menu.addAction(_("Deck Override...") + toggle)
            action.triggered.connect(self.onTargetDeck)

        action = menu.addAction(_("Browser Appearance..."))
        action.triggered.connect(self.onBrowserDisplay)

        menu.exec_(self.topAreaForm.templateOptions.mapToGlobal(QPoint(0,0)))

    def onBrowserDisplay(self):
        dialog = QDialog()
        dialog = aqt.forms.browserdisp.Ui_Dialog()
        dialog.setupUi(dialog)
        template = self.card.template()
        dialog.qfmt.setText(template.get('bqfmt', ""))
        dialog.afmt.setText(template.get('bafmt', ""))
        if template.get("bfont"):
            dialog.overrideFont.setChecked(True)
        dialog.font.setCurrentFont(QFont(template.get('bfont', "Arial")))
        dialog.fontSize.setValue(template.get('bsize', 12))
        dialog.buttonBox.accepted.connect(lambda: self.onBrowserDisplayOk(dialog))
        dialog.exec_()

    def onBrowserDisplayOk(self, form):
        template = self.card.template()
        template['bqfmt'] = form.qfmt.text().strip()
        template['bafmt'] = form.afmt.text().strip()
        if form.overrideFont.isChecked():
            template['bfont'] = form.font.currentFont().family()
            template['bsize'] = form.fontSize.value()
        else:
            for key in ("bfont", "bsize"):
                if key in template:
                    del template[key]

    def onTargetDeck(self):
        from aqt.tagedit import TagEdit
        template = self.card.template()
        dialog = QDialog(self)
        dialog.setWindowTitle("Anki")
        dialog.setMinimumWidth(400)
        layout = QVBoxLayout()
        lab = QLabel(_("""\
Enter deck to place new %s cards in, or leave blank:""") %
                           self.card.template()['name'])
        lab.setWordWrap(True)
        layout.addWidget(lab)
        te = TagEdit(dialog, type=1)
        te.setCol(self.col)
        layout.addWidget(te)
        if template['did']:
            te.setText(self.col.decks.get(template['did'])['name'])
            te.selectAll()
        bb = QDialogButtonBox(QDialogButtonBox.Close)
        bb.rejected.connect(dialog.close)
        layout.addWidget(bb)
        dialog.setLayout(layout)
        dialog.exec_()
        if not te.text().strip():
            template['did'] = None
        else:
            template['did'] = self.col.decks.id(te.text())

    def onAddField(self):
        diag = QDialog(self)
        form = aqt.forms.addfield.Ui_Dialog()
        form.setupUi(diag)
        fields = [fldType['name'] for fldType in self.model['flds']]
        form.fields.addItems(fields)
        form.font.setCurrentFont(QFont("Arial"))
        form.size.setValue(20)
        diag.show()
        # Work around a Qt bug,
        # https://bugreports.qt-project.org/browse/QTBUG-1894
        if isMac or isWin:
            # No problems on Macs or Windows.
            form.fields.showPopup()
        else:
            # Delay showing the pop-up.
            self.mw.progress.timer(200, form.fields.showPopup, False)
        if not diag.exec_():
            return
        if form.radioQ.isChecked():
            obj = self.tform.front
        else:
            obj = self.tform.back
        self._addField(obj,
                       fields[form.fields.currentIndex()],
                       form.font.currentFont().family(),
                       form.size.value())

    def _addField(self, widg, fldName, font, size):
        templateHtml = widg.toPlainText()
        templateHtml +="\n<div style='font-family: %s; font-size: %spx;'>{{%s}}</div>\n" % (
            font, size, fldName)
        widg.setPlainText(templateHtml)
        self.saveCard()

    # Closing & Help
    ######################################################################

    def accept(self):
        """Same as reject."""
        self.reject()

    def reject(self):
        """ Close the window and save the current version of the model"""
        self.cancelPreviewTimer()
        clearAudioQueue()
        if self.addMode:
            # remove the filler fields we added
            for name in self.emptyFields:
                self.note[name] = ""
            self.mw.col.db.execute("delete from notes where id = ?",
                                   self.note.id)
        self.mm.save(self.model, templates=True)
        self.mw.reset()
        saveGeom(self, "CardLayout")
        self.pform.frontWeb = None
        self.pform.backWeb = None
        return QDialog.reject(self)

    def onHelp(self):
        openHelp("templates")
