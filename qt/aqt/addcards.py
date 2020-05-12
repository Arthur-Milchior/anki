# Copyright: Ankitects Pty Ltd and contributors
# -*- coding: utf-8 -*-
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
from typing import Callable, List, Optional

import aqt.deckchooser
import aqt.editor
import aqt.forms
import aqt.modelchooser
from anki.consts import MODEL_CLOZE
from anki.lang import _
from anki.notes import Note
from anki.utils import htmlToTextLine, isMac
from aqt import AnkiQt, gui_hooks
from aqt.qt import *
from aqt.sound import av_player
from aqt.utils import (
    addCloseShortcut,
    askUser,
    downArrow,
    openHelp,
    restoreGeom,
    saveGeom,
    shortcut,
    showWarning,
    tooltip,
)


class AddCards(QDialog):
    """The window obtained from main by pressing A, or clicking on "Add"."""

    def __init__(self, mw: AnkiQt) -> None:
        QDialog.__init__(self, None, Qt.Window)
        mw.setupDialogGC(self)
        self.mw = mw
        self.form = aqt.forms.addcards.Ui_Dialog()
        self.form.setupUi(self)
        self.setWindowTitle(_("Add"))
        self.setMinimumHeight(300)
        self.setMinimumWidth(400)
        self.setupChoosers()
        self.setupEditor()
        self.setupButtons()
        self.onReset()
        self.history: List[int] = []
        self.previousNote = None
        restoreGeom(self, "add")
        gui_hooks.state_did_reset.append(self.onReset)
        gui_hooks.current_note_type_did_change.append(self.onModelChange)
        addCloseShortcut(self)
        gui_hooks.add_cards_did_init(self)
        self.show()

    def setupEditor(self) -> None:
        self.editor = aqt.editor.Editor(self.mw, self.form.fieldsArea, self, True)

    def setupChoosers(self) -> None:
        self.modelChooser = aqt.modelchooser.ModelChooser(self.mw, self.form.modelArea)
        self.deckChooser = aqt.deckchooser.DeckChooser(self.mw, self.form.deckArea)

    def helpRequested(self):
        openHelp("addingnotes")

    def setupButtons(self) -> None:
        bb = self.form.buttonBox
        ar = QDialogButtonBox.ActionRole
        # add
        self.addButton = bb.addButton(_("Add"), ar)
        qconnect(self.addButton.clicked, self.addCards)
        self.addButton.setShortcut(QKeySequence("Ctrl+Return"))
        self.addButton.setToolTip(shortcut(_("Add (shortcut: ctrl+enter)")))
        # close
        self.closeButton = QPushButton(_("Close"))
        self.closeButton.setAutoDefault(False)
        bb.addButton(self.closeButton, QDialogButtonBox.RejectRole)
        # help
        self.helpButton = QPushButton(_("Help"), clicked=self.helpRequested)  # type: ignore
        self.helpButton.setAutoDefault(False)
        bb.addButton(self.helpButton, QDialogButtonBox.HelpRole)
        # history
        button = bb.addButton(_("History") + " " + downArrow(), ar)
        if isMac:
            sc = "Ctrl+Shift+H"
        else:
            sc = "Ctrl+H"
        button.setShortcut(QKeySequence(sc))
        button.setToolTip(_("Shortcut: %s") % shortcut(sc))
        qconnect(button.clicked, self.onHistory)
        button.setEnabled(False)
        self.historyButton = button

    def setAndFocusNote(self, note: Note) -> None:
        """Add note as the content of the editor. Focus in the first element."""
        self.editor.setNote(note, focusTo=0)

    def onModelChange(self, unused=None) -> None:
        oldNote = self.editor.note
        note = self.mw.col.newNote()
        self.previousNote = None
        if oldNote:
            oldFields = list(oldNote.keys())
            newFields = list(note.keys())
            for index, fldType in enumerate(note.model()["flds"]):
                fieldName = fldType["name"]
                # copy identical fields
                if fieldName in oldFields:
                    note[fieldName] = oldNote[fieldName]
                elif index < len(oldNote.model()["flds"]):
                    # set non-identical fields by field index
                    oldFieldName = oldNote.model()["flds"][index]["name"]
                    if oldFieldName not in newFields:
                        note.fields[index] = oldNote.fields[index]
        self.editor.note = note
        # When on model change is called, reset is necessarily called.
        # Reset load note, so it is not required to load it here.

    def onReset(self, model: None = None, keep: bool = False) -> None:
        """Create a new note and set it with the current field values.

        keyword arguments
        model -- not used
        keep -- Whether the old note was saved in the collection. In
        this case, remove non sticky fields. Otherwise remove the last
        temporary note (it is replaced by a new one).
        """
        # Called with keep set to True from  _addCards
        # Called with default keep __init__, from hook "reset"
        # Meaning of the word keep guessed. Not clear.
        oldNote = self.editor.note
        note = self.mw.col.newNote()
        flds = note.model()["flds"]
        # copy fields from old note
        if oldNote:
            for index in range(min(len(note.fields), len(oldNote.fields))):
                if not keep or flds[index]["sticky"]:
                    note.fields[index] = oldNote.fields[index]
        self.setAndFocusNote(note)

    def removeTempNote(self, note: Note) -> None:
        print("removeTempNote() will go away")

    def addHistory(self, note):
        self.history.insert(0, note.id)
        self.history = self.history[:15]
        self.historyButton.setEnabled(True)

    def onHistory(self) -> None:
        menu = QMenu(self)
        for nid in self.history:
            if self.mw.col.findNotes("nid:%s" % nid):
                note = self.mw.col.getNote(nid)
                fields = note.fields
                txt = htmlToTextLine(", ".join(fields))
                if len(txt) > 30:
                    txt = txt[:30] + "..."
                line = _('Edit "%s"') % txt
                line = gui_hooks.addcards_will_add_history_entry(line, note)
                action = menu.addAction(line)
                qconnect(
                    action.triggered, lambda button, nid=nid: self.editHistory(nid)
                )
            else:
                action = menu.addAction(_("(Note deleted)"))
                action.setEnabled(False)
        gui_hooks.add_cards_will_show_history_menu(self, menu)
        menu.exec_(self.historyButton.mapToGlobal(QPoint(0, 0)))

    def editHistory(self, nid):
        browser = aqt.dialogs.open("Browser", self.mw)
        browser.form.searchEdit.lineEdit().setText("nid:%d" % nid)
        browser.onSearchActivated()

    def addNote(self, note) -> Optional[Note]:
        """check whether first field is not empty, that clozes appear in cloze
        note, and that some card will be generated. In those case, save the
        note and return it. Otherwise show a warning and return None"""
        note.model()["did"] = self.deckChooser.selectedId()
        ret = note.dupeOrEmpty()
        problem = None
        if ret == 1:
            problem = _("The first field is empty.")
        problem = gui_hooks.add_cards_will_add_note(problem, note)
        if problem is not None:
            showWarning(problem, help="AddItems#AddError")
            return None
        if note.model()["type"] == MODEL_CLOZE:
            if not note.cloze_numbers_in_fields():
                if not askUser(
                    _(
                        "You have a cloze deletion note type "
                        "but have not made any cloze deletions. Proceed?"
                    )
                ):
                    return None
        self.mw.col.add_note(note, self.deckChooser.selectedId())
        self.mw.col.clearUndo()
        self.addHistory(note)
        self.mw.requireReset()
        self.previousNote = note
        gui_hooks.add_cards_did_add_note(note)
        return note

    def addCards(self):
        """Adding the content of the fields as a new note"""
        # Save edits in the fields, and call _addCards
        self.editor.saveNow(self._addCards)

    def _addCards(self):
        """Adding the content of the fields as a new note.

        Assume that the content of the GUI saved in the model."""
        self.editor.saveAddModeVars()
        if not self.addNote(self.editor.note):
            return
        tooltip(_("Added"), period=500)
        av_player.stop_and_clear_queue()
        self.onReset(keep=True)
        self.mw.col.autosave()

    def keyPressEvent(self, evt):
        "Show answer on RET or register answer."
        if evt.key() in (Qt.Key_Enter, Qt.Key_Return) and self.editor.tags.hasFocus():
            evt.accept()
            return
        return QDialog.keyPressEvent(self, evt)

    def reject(self) -> None:
        """Close the window.

        If data would be lost, ask for confirmation"""
        self.ifCanClose(self._reject)

    def _reject(self) -> None:
        """Close the window.

        Don't check whether data will be lost"""
        gui_hooks.state_did_reset.remove(self.onReset)
        gui_hooks.current_note_type_did_change.remove(self.onModelChange)
        av_player.stop_and_clear_queue()
        self.editor.cleanup()
        self.modelChooser.cleanup()
        self.deckChooser.cleanup()
        self.mw.maybeReset()
        saveGeom(self, "add")
        aqt.dialogs.markClosed("AddCards")
        QDialog.reject(self)

    def ifCanClose(self, onOk: Callable) -> None:
        def afterSave():
            ok = self.editor.fieldsAreBlank(self.previousNote) or askUser(
                _("Close and lose current input?"), defaultno=True
            )
            if ok:
                onOk()

        self.editor.saveNow(afterSave)

    def closeWithCallback(self, cb):
        def doClose():
            self._reject()
            cb()

        self.ifCanClose(doClose)
