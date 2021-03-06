# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""The window used to:
* edit a note type
* preview the different cards of a note."""
import copy
import json
import re
from typing import List, Optional

import aqt
from anki.cards import Card
from anki.consts import *
from anki.lang import _, ngettext
from anki.notes import Note
from anki.rsbackend import TemplateError
from anki.template import TemplateRenderContext
from aqt import AnkiQt, gui_hooks
from aqt.qt import *
from aqt.schema_change_tracker import ChangeTracker
from aqt.sound import av_player, play_clicked_audio
from aqt.theme import theme_manager
from aqt.utils import (
    TR,
    askUser,
    downArrow,
    getOnlyText,
    openHelp,
    restoreGeom,
    restoreSplitter,
    saveGeom,
    saveSplitter,
    shortcut,
    showInfo,
    showWarning,
    tooltip,
    tr,
)
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

    def __init__(
        self,
        mw: AnkiQt,
        note: Note,
        ord=0,
        parent: Optional[QWidget] = None,
        fill_empty: bool = False,
    ):
        QDialog.__init__(self, parent or mw, Qt.Window)
        mw.setupDialogGC(self)
        self.mw = aqt.mw
        self.note = note
        self.ord = ord
        self.col = self.mw.col.weakref()
        self.mm = self.mw.col.models
        self.model = note.model()
        self.templates = self.model["tmpls"]
        self._want_fill_empty_on = fill_empty
        self.have_autoplayed = False
        self.mm._remove_from_cache(self.model["id"])
        self.mw.checkpoint(_("Card Types"))
        self.change_tracker = ChangeTracker(self.mw)
        self.setupTopArea()
        self.setupMainArea()
        self.setupButtons()
        self.setupShortcuts()
        self.setWindowTitle(_("Card Types for %s") % self.model["name"])
        v1 = QVBoxLayout()
        v1.addWidget(self.topArea)
        v1.addWidget(self.mainArea)
        v1.addLayout(self.buttons)
        v1.setContentsMargins(12, 12, 12, 12)
        self.setLayout(v1)
        gui_hooks.card_layout_will_show(self)
        self.redraw_everything()
        restoreGeom(self, "CardLayout")
        restoreSplitter(self.mainArea, "CardLayoutMainArea")
        self.setWindowModality(Qt.ApplicationModal)
        self.show()
        # take the focus away from the first input area when starting up,
        # as users tend to accidentally type into the template
        self.setFocus()

    def redraw_everything(self):
        """TODO
        update the list of card
        """
        self.ignore_change_signals = True
        self.updateTopArea()
        self.ignore_change_signals = False
        self.update_current_ordinal_and_redraw(self.ord)

    def update_current_ordinal_and_redraw(self, idx):
        if self.ignore_change_signals:
            return
        self.ord = idx
        self.have_autoplayed = False
        self.fill_fields_from_template()
        self.renderPreview()

    def _isCloze(self):
        return self.model["type"] == MODEL_CLOZE

    # Top area
    ##########################################################################

    def setupTopArea(self):
        self.topArea = QWidget()
        self.topArea.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.topAreaForm = aqt.forms.clayout_top.Ui_Form()
        self.topAreaForm.setupUi(self.topArea)
        self.topAreaForm.templateOptions.setText(_("Options") + " " + downArrow())
        qconnect(self.topAreaForm.templateOptions.clicked, self.onMore)
        qconnect(
            self.topAreaForm.templatesBox.currentIndexChanged,
            self.update_current_ordinal_and_redraw,
        )
        self.topAreaForm.card_type_label.setText(tr(TR.CARD_TEMPLATES_CARD_TYPE))

    def updateTopArea(self):
        self.updateCardNames()

    def updateCardNames(self):
        """ In the list of card name, change them according to
        current's name"""
        self.ignore_change_signals = True
        combo = self.topAreaForm.templatesBox
        combo.clear()
        combo.addItems(
            self._summarizedName(idx, tmpl) for (idx, tmpl) in enumerate(self.templates)
        )
        combo.setCurrentIndex(self.ord)
        combo.setEnabled(not self._isCloze())
        self.ignore_change_signals = False

    def _summarizedName(self, idx: int, tmpl: Dict):
        """Compute the text appearing in the list of templates, on top of the window

        tmpl -- a template object
        """
        return "{}: {}: {} -> {}".format(
            idx + 1,
            tmpl["name"],
            self._fieldsOnTemplate(tmpl["qfmt"]),
            self._fieldsOnTemplate(tmpl["afmt"]),
        )

    def _fieldsOnTemplate(self, fmt):
        """List of tags found in fmt, separated by +, limited to 30 characters
        (not counting the +), in lexicographic order, with +... if some are
        missings."""
        matches = re.findall("{{[^#/}]+?}}", fmt)
        chars_allowed = 30
        field_names: List[str] = []
        for match in matches:
            # strip off mustache
            match = re.sub(r"[{}]", "", match)
            # strip off modifiers
            match = match.split(":")[-1]
            # don't show 'FrontSide'
            if match == "FrontSide":
                continue

            field_names.append(match)
            chars_allowed -= len(match)
            if chars_allowed <= 0:
                break

        s = "+".join(field_names)
        if chars_allowed <= 0:
            s += "+..."
        return s

    def setupShortcuts(self):
        self.tform.front_button.setToolTip(shortcut("Ctrl+1"))
        self.tform.back_button.setToolTip(shortcut("Ctrl+2"))
        self.tform.style_button.setToolTip(shortcut("Ctrl+3"))
        QShortcut(  # type: ignore
            QKeySequence("Ctrl+1"), self, activated=self.tform.front_button.click,
        )
        QShortcut(  # type: ignore
            QKeySequence("Ctrl+2"), self, activated=self.tform.back_button.click,
        )
        QShortcut(  # type: ignore
            QKeySequence("Ctrl+3"), self, activated=self.tform.style_button.click,
        )

    # Main area setup
    ##########################################################################

    def setupMainArea(self):
        split = self.mainArea = QSplitter()
        split.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        split.setOrientation(Qt.Horizontal)
        left = QWidget()
        tform = self.tform = aqt.forms.template.Ui_Form()
        tform.setupUi(left)
        split.addWidget(left)
        split.setCollapsible(0, False)

        right = QWidget()
        self.pform = aqt.forms.preview.Ui_Form()
        pform = self.pform
        pform.setupUi(right)
        pform.preview_front.setText(tr(TR.CARD_TEMPLATES_FRONT_PREVIEW))
        pform.preview_back.setText(tr(TR.CARD_TEMPLATES_BACK_PREVIEW))
        pform.preview_box.setTitle(tr(TR.CARD_TEMPLATES_PREVIEW_BOX))

        self.setup_edit_area()
        self.setup_preview()
        split.addWidget(right)
        split.setCollapsible(1, False)

    def setup_edit_area(self):
        tform = self.tform

        tform.front_button.setText(tr(TR.CARD_TEMPLATES_FRONT_TEMPLATE))
        tform.back_button.setText(tr(TR.CARD_TEMPLATES_BACK_TEMPLATE))
        tform.style_button.setText(tr(TR.CARD_TEMPLATES_TEMPLATE_STYLING))
        tform.groupBox.setTitle(tr(TR.CARD_TEMPLATES_TEMPLATE_BOX))

        cnt = self.mw.col.models.useCount(self.model)
        self.tform.changes_affect_label.setText(
            self.col.tr(TR.CARD_TEMPLATES_CHANGES_WILL_AFFECT_NOTES, count=cnt)
        )

        qconnect(tform.edit_area.textChanged, self.write_edits_to_template_and_redraw)
        qconnect(tform.front_button.clicked, self.on_editor_toggled)
        qconnect(tform.back_button.clicked, self.on_editor_toggled)
        qconnect(tform.style_button.clicked, self.on_editor_toggled)

        self.current_editor_index = 0
        self.tform.edit_area.setAcceptRichText(False)
        self.tform.edit_area.setFont(QFont("Courier"))
        if qtminor < 10:
            self.tform.edit_area.setTabStopWidth(30)
        else:
            tab_width = self.fontMetrics().width(" " * 4)
            self.tform.edit_area.setTabStopDistance(tab_width)

        widg = tform.search_edit
        widg.setPlaceholderText("Search")
        qconnect(widg.textChanged, self.on_search_changed)
        qconnect(widg.returnPressed, self.on_search_next)

    def setup_cloze_number_box(self):
        names = (_("Cloze %d") % n for n in self.cloze_numbers)
        self.pform.cloze_number_combo.addItems(names)
        try:
            idx = self.cloze_numbers.index(self.ord + 1)
            self.pform.cloze_number_combo.setCurrentIndex(idx)
        except ValueError:
            # invalid cloze
            pass
        qconnect(
            self.pform.cloze_number_combo.currentIndexChanged, self.on_change_cloze
        )

    def on_change_cloze(self, idx: int) -> None:
        self.ord = self.cloze_numbers[idx] - 1
        self.have_autoplayed = False
        self._renderPreview()

    def on_editor_toggled(self):
        if self.tform.front_button.isChecked():
            self.current_editor_index = 0
            self.pform.preview_front.setChecked(True)
            self.on_preview_toggled()
            self.add_field_button.setHidden(False)
        elif self.tform.back_button.isChecked():
            self.current_editor_index = 1
            self.pform.preview_back.setChecked(True)
            self.on_preview_toggled()
            self.add_field_button.setHidden(False)
        else:
            self.current_editor_index = 2
            self.add_field_button.setHidden(True)

        self.fill_fields_from_template()

    def on_search_changed(self, text: str):
        editor = self.tform.edit_area
        if not editor.find(text):
            # try again from top
            cursor = editor.textCursor()
            cursor.movePosition(QTextCursor.Start)
            editor.setTextCursor(cursor)
            if not editor.find(text):
                tooltip("No matches found.")

    def on_search_next(self):
        text = self.tform.search_edit.text()
        self.on_search_changed(text)

    def setup_preview(self):
        pform = self.pform
        self.preview_web = AnkiWebView(title="card layout")
        pform.verticalLayout.addWidget(self.preview_web)
        pform.verticalLayout.setStretch(1, 99)
        pform.preview_front.isChecked()
        qconnect(pform.preview_front.clicked, self.on_preview_toggled)
        qconnect(pform.preview_back.clicked, self.on_preview_toggled)
        if self._want_fill_empty_on:
            pform.fill_empty.setChecked(True)
        qconnect(pform.fill_empty.toggled, self.on_preview_toggled)
        if not self.note_has_empty_field():
            pform.fill_empty.setHidden(True)
        pform.fill_empty.setText(tr(TR.CARD_TEMPLATES_FILL_EMPTY))
        jsinc = [
            "jquery.js",
            "browsersel.js",
            "mathjax/conf.js",
            "mathjax/MathJax.js",
            "reviewer.js",
        ]
        self.preview_web.stdHtml(
            self.mw.reviewer.revHtml(), css=["reviewer.css"], js=jsinc, context=self,
        )
        self.preview_web.set_bridge_command(self._on_bridge_cmd, self)

        if self._isCloze():
            nums = list(self.note.cloze_numbers_in_fields())
            if self.ord + 1 not in nums:
                # current card is empty
                nums.append(self.ord + 1)
            self.cloze_numbers = sorted(nums)
            self.setup_cloze_number_box()
        else:
            self.cloze_numbers = []
            self.pform.cloze_number_combo.setHidden(True)

    def on_preview_toggled(self):
        """Remove the current template, except if it would leave a note
        without card.  Ask user for confirmation

        """
        self.have_autoplayed = False
        self._renderPreview()

    def _on_bridge_cmd(self, cmd: str) -> Any:
        if cmd.startswith("play:"):
            play_clicked_audio(cmd, self.rendered_card)

    def note_has_empty_field(self) -> bool:
        for field in self.note.fields:
            if not field.strip():
                # ignores HTML, but this should suffice
                return True
        return False

    # Buttons
    ##########################################################################

    def setupButtons(self):
        layout = self.buttons = QHBoxLayout()
        help = QPushButton(_("Help"))
        help.setAutoDefault(False)
        layout.addWidget(help)
        qconnect(help.clicked, self.onHelp)
        layout.addStretch()
        self.add_field_button = QPushButton(_("Add Field"))
        self.add_field_button.setAutoDefault(False)
        layout.addWidget(self.add_field_button)
        qconnect(self.add_field_button.clicked, self.onAddField)
        if not self._isCloze():
            flip = QPushButton(_("Flip"))
            flip.setAutoDefault(False)
            layout.addWidget(flip)
            qconnect(flip.clicked, self.onFlip)
        layout.addStretch()
        save = QPushButton(_("Save"))
        save.setAutoDefault(False)
        layout.addWidget(save)
        qconnect(save.clicked, self.accept)

        close = QPushButton(_("Cancel"))
        close.setAutoDefault(False)
        layout.addWidget(close)
        qconnect(close.clicked, self.reject)

    # Reading/writing question/answer/css
    ##########################################################################

    def current_template(self) -> Dict:
        if self._isCloze():
            return self.templates[0]
        return self.templates[self.ord]

    def fill_fields_from_template(self):
        template = self.current_template()
        self.ignore_change_signals = True

        if self.current_editor_index == 0:
            textemplate = template["qfmt"]
        elif self.current_editor_index == 1:
            text = template["afmt"]
        else:
            text = self.model["css"]

        self.tform.edit_area.setPlainText(text)
        self.ignore_change_signals = False

    def write_edits_to_template_and_redraw(self):
        if self.ignore_change_signals:
            return

        self.change_tracker.mark_basic()

        text = self.tform.edit_area.toPlainText()

        if self.current_editor_index == 0:
            self.current_template()["qfmt"] = text
        elif self.current_editor_index == 1:
            self.current_template()["afmt"] = text
        else:
            self.model["css"] = text

        self.renderPreview()

    # Preview
    ##########################################################################

    _previewTimer = None

    def renderPreview(self):
        # schedule a preview when timing stops
        self.cancelPreviewTimer()
        self._previewTimer = self.mw.progress.timer(200, self._renderPreview, False)

    def cancelPreviewTimer(self):
        if self._previewTimer:
            self._previewTimer.stop()
            self._previewTimer = None

    def _renderPreview(self) -> None:
        """
        change the answer and question side of the preview
        windows. Change the list of name of cards.
        """
        self.cancelPreviewTimer()

        card = self.rendered_card = self.ephemeral_card_for_rendering()
        ti = self.maybeTextInput

        bodyclass = theme_manager.body_classes_for_card_ord(card.ord)

        # deal with [[type:, image and remove sound of the card's
        # question and answer
        if self.pform.preview_front.isChecked():
            questionHtmlPreview = ti(self.mw.prepare_card_text_for_display(card.q()))
            questionHtmlPreview = gui_hooks.card_will_show(
                questionHtmlPreview, card, "clayoutQuestion"
            )
            text = questionHtmlPreview
        else:
            answerHtml = ti(
                self.mw.prepare_card_text_for_display(card.a()),
                type="answerHtml",
            )
            answerHtml = gui_hooks.card_will_show(answerHtml, card, "clayoutAnswer")
            text = answerHtml

        # use _showAnswer to avoid the longer delay
        self.preview_web.eval("_showAnswer(%s,'%s');" % (json.dumps(text), bodyclass))

        if not self.have_autoplayed:
            self.have_autoplayed = True

            if card.autoplay():
                if self.pform.preview_front.isChecked():
                    audio = card.question_av_tags()
                else:
                    audio = card.answer_av_tags()
                av_player.play_tags(audio)
            else:
                av_player.clear_queue_and_maybe_interrupt()

        self.updateCardNames()

    def maybeTextInput(self, txt, type="q"):
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

        repl: Union[str, Callable]

        if type == "q":
            repl = "<input id='typeans' type=text value='exomple' readonly='readonly'>"
            repl = "<center>%s</center>" % repl
        else:
            repl = answerRepl
        return re.sub(r"\[\[type:.+?\]\]", repl, txt)

    def ephemeral_card_for_rendering(self) -> Card:
        card = Card(self.col)
        card.ord = self.ord
        card.did = 1
        template = copy.copy(self.current_template())
        # may differ in cloze case
        template["ord"] = card.ord
        output = TemplateRenderContext.from_card_layout(
            self.note,
            card,
            notetype=self.model,
            template=template,
            fill_empty=self.pform.fill_empty.isChecked(),
        ).render()
        card.set_render_output(output)
        return card

    # Card operations
    ######################################################################

    def onRemove(self):
        if len(self.templates) < 2:
            return showInfo(_("At least one card type is required."))

        def get_count():
            return self.mm.template_use_count(self.model["id"], self.ord)

        def on_done(fut):
            card_cnt = fut.result()

            template = self.current_template()
            cards = ngettext("%d card", "%d cards", card_cnt) % card_cnt
            msg = _("Delete the '%(a)s' card type, and its %(b)s?") % dict(
                a=template["name"], b=cards
            )
            if not askUser(msg):
                return

            if not self.change_tracker.mark_schema():
                return

            self.onRemoveInner(template)

        self.mw.taskman.with_progress(get_count, on_done)

    def onRemoveInner(self, template) -> None:
        self.mm.remove_template(self.model, template)

        # ensure current ordinal is within bounds
        idx = self.ord
        if idx >= len(self.templates):
            self.ord = len(self.templates) - 1

        self.redraw_everything()

    def onRename(self):
        template = self.current_template()
        name = getOnlyText(_("New name:"), default=template["name"])
        if not name.strip():
            return

        if not self.change_tracker.mark_schema():
            return
        template["name"] = name
        self.redraw_everything()

    def onReorder(self):
        """Asks user for a new position for current template. Move to this position if it is a valid position."""
        numberOfCard = len(self.templates)
        template = self.current_template()
        current_pos = self.templates.index(template) + 1
        pos = getOnlyText(
            _("Enter new card position (1...%s):") % numberOfCard,
            default=str(current_pos),
        )
        if not pos:
            return
        try:
            pos = int(pos)
        except ValueError:
            return
        if pos < 1 or pos > numberOfCard:
            return
        if pos == current_pos:
            return
        new_idx = pos - 1
        if not self.change_tracker.mark_schema():
            return
        self.mm.reposition_template(self.model, template, new_idx)
        self.ord = new_idx
        self.redraw_everything()

    def _newCardName(self):
        cardUserIndex = len(self.templates) + 1
        while 1:
            name = _("Card %d") % cardUserIndex
            if name not in [t["name"] for t in self.templates]:
                break
            cardUserIndex += 1
        return name

    def onAddCard(self):
        """Ask for confirmation and create a copy of current card as the last template"""
        cnt = self.mw.col.models.useCount(self.model)
        txt = (
            ngettext(
                "This will create %d card. Proceed?",
                "This will create %d cards. Proceed?",
                cnt,
            )
            % cnt
        )
        if not askUser(txt):
            return
        if not self.change_tracker.mark_schema():
            return
        name = self._newCardName()
        template = self.mm.newTemplate(name)
        old = self.current_template()
        template["qfmt"] = old["qfmt"]
        template["afmt"] = old["afmt"]
        self.mm.add_template(self.model, template)
        self.ord = len(self.templates) - 1
        self.redraw_everything()

    def onFlip(self):
        old = self.current_template()
        self._flipQA(old, old)
        self.redraw_everything()

    def _flipQA(self, src, dst):
        match = re.match("(?s)(.+)<hr id=answer>(.+)", src["afmt"])
        if not match:
            showInfo(
                _(
                    """\
Anki couldn't find the line between the question and answer. Please \
adjust the template manually to switch the question and answer."""
                )
            )
            return
        self.change_tracker.mark_basic()
        dst["afmt"] = "{{FrontSide}}\n\n<hr id=answer>\n\n%s" % src["qfmt"]
        dst["qfmt"] = match.group(2).strip()
        return True

    def onMore(self):
        menu = QMenu(self)

        if not self._isCloze():
            action = menu.addAction(_("Add Card Type..."))
            qconnect(action.triggered, self.onAddCard)

            action = menu.addAction(_("Remove Card Type..."))
            qconnect(action.triggered, self.onRemove)

            action = menu.addAction(_("Rename Card Type..."))
            qconnect(action.triggered, self.onRename)

            action = menu.addAction(_("Reposition Card Type..."))
            qconnect(action.triggered, self.onReorder)

            menu.addSeparator()

            template = self.current_template()
            if template["did"]:
                toggle = _(" (on)")
            else:
                toggle = _(" (off)")
            action = menu.addAction(_("Deck Override...") + toggle)
            qconnect(action.triggered, self.onTargetDeck)

        action = menu.addAction(_("Browser Appearance..."))
        qconnect(action.triggered, self.onBrowserDisplay)

        menu.exec_(self.topAreaForm.templateOptions.mapToGlobal(QPoint(0, 0)))

    def onBrowserDisplay(self):
        dialog = QDialog()
        form = aqt.forms.browserdisp.Ui_Dialog()
        form.setupUi(dialog)
        template = self.current_template()
        form.qfmt.setText(template.get("bqfmt", ""))
        form.afmt.setText(template.get("bafmt", ""))
        if template.get("bfont"):
            form.overrideFont.setChecked(True)
        form.font.setCurrentFont(QFont(template.get("bfont", "Arial")))
        form.fontSize.setValue(template.get("bsize", 12))
        qconnect(form.buttonBox.accepted, lambda: self.onBrowserDisplayOk(form))
        dialog.exec_()

    def onBrowserDisplayOk(self, dialog):
        template = self.current_template()
        self.change_tracker.mark_basic()
        template["bqfmt"] = dialog.qfmt.text().strip()
        template["bafmt"] = dialog.afmt.text().strip()
        if dialog.overrideFont.isChecked():
            template["bfont"] = dialog.font.currentFont().family()
            template["bsize"] = dialog.fontSize.value()
        else:
            for key in ("bfont", "bsize"):
                if key in template:
                    del template[key]

    def onTargetDeck(self):
        from aqt.tagedit import TagEdit

        template = self.current_template()
        dialog = QDialog(self)
        dialog.setWindowTitle("Anki")
        dialog.setMinimumWidth(400)
        layout = QVBoxLayout()
        lab = QLabel(
            _(
                """\
Enter deck to place new %s cards in, or leave blank:"""
            )
            % self.current_template()["name"]
        )
        lab.setWordWrap(True)
        layout.addWidget(lab)
        te = TagEdit(dialog, type=1)
        te.setCol(self.col)
        layout.addWidget(te)
        if template["did"]:
            te.setText(self.col.decks.get(template["did"])["name"])
            te.selectAll()
        bb = QDialogButtonBox(QDialogButtonBox.Close)
        qconnect(bb.rejected, dialog.close)
        layout.addWidget(bb)
        dialog.setLayout(layout)
        dialog.exec_()
        self.change_tracker.mark_basic()
        if not te.text().strip():
            template["did"] = None
        else:
            template["did"] = self.col.decks.id(te.text())

    def onAddField(self):
        diag = QDialog(self)
        form = aqt.forms.addfield.Ui_Dialog()
        form.setupUi(diag)
        fields = [fldType["name"] for fldType in self.model["flds"]]
        form.fields.addItems(fields)
        form.fields.setCurrentRow(0)
        form.font.setCurrentFont(QFont("Arial"))
        form.size.setValue(20)
        if not diag.exec_():
            return
        row = form.fields.currentIndex().row()
        if row >= 0:
            self._addField(
                fields[row], form.font.currentFont().family(), form.size.value(),
            )

    def _addField(self, fldName, font, size):
        text = self.tform.edit_area.toPlainText()
        text += "\n<div style='font-family: %s; font-size: %spx;'>{{%s}}</div>\n" % (
            font,
            size,
            fldName,
        )
        self.tform.edit_area.setPlainText(text)
        self.change_tracker.mark_basic()
        self.write_edits_to_template_and_redraw()

    # Closing & Help
    ######################################################################

    def accept(self) -> None:
        def save():
            self.mm.save(self.model)

        def on_done(fut):
            try:
                fut.result()
            except TemplateError as e:
                showWarning("Unable to save changes: " + str(e))
                return
            self.mw.reset()
            tooltip("Changes saved.", parent=self.parent())
            self.cleanup()
            gui_hooks.sidebar_should_refresh_notetypes()
            return QDialog.accept(self)

        self.mw.taskman.with_progress(save, on_done)

    def reject(self) -> None:
        """ Close the window and save the current version of the model"""
        if self.change_tracker.changed():
            if not askUser("Discard changes?"):
                return
        self.cleanup()
        return QDialog.reject(self)

    def cleanup(self) -> None:
        self.cancelPreviewTimer()
        av_player.stop_and_clear_queue()
        saveGeom(self, "CardLayout")
        saveSplitter(self.mainArea, "CardLayoutMainArea")
        self.preview_web = None
        self.model = None
        self.rendered_card = None
        self.mw = None

    def onHelp(self):
        openHelp("templates")
