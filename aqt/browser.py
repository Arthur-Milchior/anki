# -*- coding: utf-8 -*-
# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

import sre_constants
import html
import time
import re
import unicodedata
from operator import  itemgetter
from anki.lang import ngettext
import json

from aqt.qt import *
import anki
import aqt.forms
from anki.utils import fmtTimeSpan, ids2str, htmlToTextLine, \
    isWin, intTime, \
    isMac, bodyClass
from aqt.utils import saveGeom, restoreGeom, saveSplitter, restoreSplitter, \
    saveHeader, restoreHeader, saveState, restoreState, getTag, \
    showInfo, askUser, tooltip, openHelp, showWarning, shortcut, mungeQA, \
    getOnlyText, MenuList, SubMenu, qtMenuShortcutWorkaround
from anki.lang import _
from anki.hooks import runHook, addHook, remHook, runFilter
from aqt.webview import AnkiWebView
from anki.consts import *
from anki.sound import clearAudioQueue, allSounds, play


# Data model
##########################################################################

class DataModel(QAbstractTableModel):

    """
    The model for the table, showing informations on a list of cards in the browser.

    Implemented as a separate class because that is how QT show those tables.

    sortKey -- never used
    activeCols -- the list of name of columns to display in the browser
    cards -- the set of cards corresponding to current browser's search
    cardObjs -- dictionnady from card's id to the card object. It
    allows to avoid reloading cards already seen since browser was
    opened. If a nose is «refreshed» then it is remove from the
    dic. It is emptied during reset.
    focusedCard -- the last thing focused, assuming it was a single line. Used to restore a selection after edition/deletion. (Notes keep by compatibility, but it may be a note id)
    selectedCards -- a dictionnary containing the set of selected card's id, associating them to True. Seems that the associated value is never used. Used to restore a selection after some edition
    """
    def __init__(self, browser):
        QAbstractTableModel.__init__(self)
        self.browser = browser
        self.col = browser.col
        self.sortKey = None
        self.activeCols = self.col.conf.get(
            "activeCols", ["noteFld", "template", "cardDue", "deck"])
        self.cards = []
        self.cardObjs = {}

    def getCard(self, index):
        """The card object at position index in the list"""
        id = self.cards[index.row()]
        if not id in self.cardObjs:
            self.cardObjs[id] = self.col.getCard(id)
        return self.cardObjs[id]

    def refreshNote(self, note):
        """Remove cards of this note from cardObjs, and potentially signal
        that the layout need to be changed if one cards was in this dict."""
        refresh = False
        for c in note.cards():
            if c.id in self.cardObjs:
                del self.cardObjs[c.id]
                refresh = True
        if refresh:
            self.layoutChanged.emit()

    # Model interface
    ######################################################################

    def rowCount(self, parent):
        """The number of cards in the browser.

        Or 0 if parent is a valid index, as requested by QAbstractTableModel
        parent -- a QModelIndex
        """
        if parent and parent.isValid():
            return 0
        return len(self.cards)

    def columnCount(self, parent):
        """The number of columns to display in the browser.

        Or 0 if parent is a valid index, as requested by QAbstractTableModel
        parent -- a QModelIndex
        """
        if parent and parent.isValid():
            return 0
        return len(self.activeCols)

    def data(self, index, role):
        """Some information to display the content of the table, at index
        `index` for role `role`, as defined by QAbstractTableModel.

        index -- a QModelIndex, i.e. a pair row,column
        role -- a value of ItemDataRole; stating which information is requested to display this cell.

        """
        if not index.isValid():
            return
        if role == Qt.FontRole:
            # The font used for items rendered with the default delegate.
            if self.activeCols[index.column()] not in (
                "question", "answer", "noteFld"):
                return
            row = index.row()
            c = self.getCard(index)
            t = c.template()
            if not t.get("bfont"):
                return
            f = QFont()
            f.setFamily(t.get("bfont", "arial"))
            f.setPixelSize(t.get("bsize", 12))
            return f

        elif role == Qt.TextAlignmentRole:
            #The alignment of the text for items rendered with the default delegate.
            align = Qt.AlignVCenter
            if self.activeCols[index.column()] not in ("question", "answer",
               "template", "deck", "noteFld", "note"):
                align |= Qt.AlignHCenter
            return align
        elif role == Qt.DisplayRole or role == Qt.EditRole:
            #The key data to be rendered in the form of text.
            return self.columnData(index)
        else:
            return

    def headerData(self, section, orientation, role):
        """The localized name of the header of column `section`.

        Assuming role is displayrole, orientation is vertical, and
        section is a valid column. Otherwise, return Nothing.

        If the column exists but its local name is not known, return
        the first name in alphabetical order (Not clear why this
        choice)

        """
        if orientation == Qt.Vertical or not(role == Qt.DisplayRole and section < len(self.activeCols)):
            return
        type = self.columnType(section)
        txt = None
        for stype, name in self.browser.columns:
            if type == stype:
                txt = name
                break
        # handle case where extension has set an invalid column type
        if not txt:
            txt = self.browser.columns[0][1]
        return txt

    def flags(self, index):
        """Required by QAbstractTableModel. State that interaction is possible
        and it can be selected (not clear what it means right now)

        """
        return Qt.ItemFlag(Qt.ItemIsEnabled |
                           Qt.ItemIsSelectable)

    # Filtering
    ######################################################################

    def search(self, txt):
        """Given a query `txt` entered in the search browser, set self.cards
        to the result of the query, warn if the search is invalid, and
        reset the display.

        """
        self.beginReset()
        t = time.time()
        # the db progress handler may cause a refresh, so we need to zero out
        # old data first
        self.cards = []
        invalid = False
        try:
            self.cards = self.col.findCards(txt, order=True)
        except Exception as e:
            if str(e) == "invalidSearch":
                self.cards = []
                invalid = True
            else:
                raise
        #print "fetch cards in %dms" % ((time.time() - t)*1000)
        self.endReset()

        if invalid:
            showWarning(_("Invalid search - please check for typing mistakes."))


    def reset(self):
        self.beginReset()
        self.endReset()

    # caller must have called editor.saveNow() before calling this or .reset()
    def beginReset(self):
        self.browser.editor.setNote(None, hide=False)
        self.browser.mw.progress.start()
        self.saveSelection()
        self.beginResetModel()
        self.cardObjs = {}

    def endReset(self):
        t = time.time()
        self.endResetModel()
        self.restoreSelection()
        self.browser.mw.progress.finish()

    def reverse(self):
        """Save the current note, reverse the list of cards and update the display"""
        self.browser.editor.saveNow(self._reverse)

    def _reverse(self):
        """Reverse the list of cards and update the display"""
        self.beginReset()
        self.cards.reverse()
        self.endReset()

    def saveSelection(self):
        """Set selectedCards and focusedCards according to what their represent"""
        cards = self.browser.selectedCards()
        self.selectedCards = dict([(id, True) for id in cards])
        if getattr(self.browser, 'card', None):
            self.focusedCard = self.browser.card.id
        else:
            self.focusedCard = None

    def restoreSelection(self):
        """ Restore main selection as either:
        * focusedCard (which is set to None)
        * or first selected card in the list of cards

        If there are less than 500 selected card, select them back.
        """
        if not self.cards:
            return
        sm = self.browser.form.tableView.selectionModel()
        sm.clear()
        # restore selection
        items = QItemSelection()
        count = 0
        firstIdx = None
        focusedIdx = None
        for row, id in enumerate(self.cards):
            # if the id matches the focused card, note the index
            if self.focusedCard == id:
                focusedIdx = self.index(row, 0)
                items.select(focusedIdx, focusedIdx)
                self.focusedCard = None
            # if the card was previously selected, select again
            if id in self.selectedCards:
                count += 1
                idx = self.index(row, 0)
                items.select(idx, idx)
                # note down the first card of the selection, in case we don't
                # have a focused card
                if not firstIdx:
                    firstIdx = idx
        # focus previously focused or first in selection
        idx = focusedIdx or firstIdx
        tv = self.browser.form.tableView
        if idx:
            tv.selectRow(idx.row())
            # scroll if the selection count has changed
            if count != len(self.selectedCards):
                # we save and then restore the horizontal scroll position because
                # scrollTo() also scrolls horizontally which is confusing
                h = tv.horizontalScrollBar().value()
                tv.scrollTo(idx, tv.PositionAtCenter)
                tv.horizontalScrollBar().setValue(h)
            if count < 500:
                # discard large selections; they're too slow
                sm.select(items, QItemSelectionModel.SelectCurrent |
                          QItemSelectionModel.Rows)
        else:
            tv.selectRow(0)

    # Column data
    ######################################################################

    def columnType(self, column):
        """The name of the column in position `column`"""
        return self.activeCols[column]

    def columnData(self, index):
        """Return the text of the cell at a precise index.


        Only called from data. It does the computation for data, in
        the case where the content of a cell is asked.

        It is kept by compatibility with original anki, but could be incorporated in it.
        """
        row = index.row()
        col = index.column()
        type = self.columnType(col)
        card = self.getCard(index)
        method = getattr(self, f"{type}Content", None)
        if method:
            return method(card, row, col)

    def noteFldContent(self, card, row, col):
        """The content of the sorting field, on a single line."""
        f = card.note()
        model = f.model()
        sortIdx = self.col.models.sortIdx(model)
        sortField = f.fields[sortIdx]
        return htmlToTextLine(sortField)

    def templateContent(self, card, row, col):
        """Name of the card type. With its number if it's a cloze card"""
        t = card.template()['name']
        if card.model()['type'] == MODEL_CLOZE:
            t += " %d" % (card.ord+1)
        return t

    def cardDueContent(self, card, row, col):
        """
        The content of the 'due' column in the browser.
        * (filtered) if the card is in a filtered deck
        * the due integer if the card is new
        * the due date if the card is in learning or review mode.

        Parenthesis if suspended or buried
        """
        # catch invalid dates
        try:
            t = self.nextDue(card, None)
        except:
            t = ""
        if card.queue < 0:#supsended or buried
            t = "(" + t + ")"
        return t

    def noteCrtContent(self, card, row, col):
        """Date at wich the card's note was created"""
        return time.strftime("%Y-%m-%d", time.localtime(card.note().id/1000))

    def noteModContent(self, card, row, col):
        """Date at wich the card's note was last modified"""
        return time.strftime("%Y-%m-%d", time.localtime(card.note().mod))

    def cardModContent(self, card, row, col):
        """Date at wich the card note was last modified"""
        return time.strftime("%Y-%m-%d", time.localtime(card.mod))

    def cardRepsContent(self, card, row, col):
        """Number of reviews to do"""
        return str(card.reps)

    def cardLaspsesContent(self, card, row, col):
        """Number of times the card lapsed"""
        return str(card.lapses)

    def noteTagsContent(self, card, row, col):
        """The list of tags for this card's note."""
        return " ".join(card.note().tags)

    def noteContent(self, card, row, col):
        """The name of the card's note's type"""
        return card.model()['name']

    def cardIvlContent(self, card, row, col):
        """Whether card is new, in learning, or some representation of the
        interval as a number of days."""
        if card.type == 0:
            return _("(new)")
        elif card.type == 1:
            return _("(learning)")
        return fmtTimeSpan(card.ivl*86400)

    def cardEaseContent(self, card, row, col):
        """Either (new) or the ease fo the card as a percentage."""
        if card.type == 0:
            return _("(new)")
        return "%d%%" % (card.factor/10)

    def deckContent(self, card, row, col):
        """Name of the card's deck (with original deck in parenthesis if there
        is one)

        """
        if card.odid:
            # in a cram deck
            return "%s (%s)" % (
                self.browser.mw.col.decks.name(card.did),
                self.browser.mw.col.decks.name(card.odid))
        # normal deck
        return self.browser.mw.col.decks.name(card.did)

    def question(self, card, *args, **kwargs):
        """The question side of card, fitted in a single line"""
        # args because this allow questionContent to be equal to question
        return htmlToTextLine(card.q(browser=True))
    questionContent = question

    def answer(self, card, *args, **kwargs):
        """The answer side on a single line.

        Either bafmt if it is defined. Otherwise normal answer,
        removing the question if it starts with it.
        """
        # args because this allow questionContent to be equal to question
        if card.template().get('bafmt'):
            # they have provided a template, use it verbatim
            card.q(browser=True)
            return htmlToTextLine(card.a())
        # need to strip question from answer
        q = self.question(card)
        a = htmlToTextLine(card.a())
        if a.startswith(q):
            return a[len(q):].strip()
        return a
    answerContent = answer

    def nextDue(self, card, index):
        """
        The content of the 'due' column in the browser.
        * (filtered) if the card is in a filtered deck
        * the due integer if the card is new
        * the due date if the card is in learning or review mode.

        Only used in cardDueContent. It's kept outside of it only by consistency with original anki.

        index -- not used"""
        if card.odid:
            return _("(filtered)")
        elif card.queue == QUEUE_LRN:
            date = card.due
        elif card.queue == QUEUE_NEW_CRAM or card.type == CARD_NEW:
            return str(card.due)
        elif card.queue in (QUEUE_REV, QUEUE_DAY_LRN) or (card.type == CARD_DUE and
                                                          card.queue < 0#suspended or buried
        ):
            date = time.time() + ((card.due - self.col.sched.today)*86400)
        else:
            return ""
        return time.strftime("%Y-%m-%d", time.localtime(date))

    def isRTL(self, index):
        col = index.column()
        type = self.columnType(col)
        if type != "noteFld":
            return False

        row = index.row()
        card = self.getCard(index)
        nt = card.note().model()
        return nt['flds'][self.col.models.sortIdx(nt)]['rtl']

# Line painter
######################################################################

COLOUR_SUSPENDED = "#FFFFB2"
COLOUR_MARKED = "#ccc"

flagColours = {
    1: "#ffaaaa",
    2: "#ffb347",
    3: "#82E0AA",
    4: "#85C1E9",
}

class StatusDelegate(QItemDelegate):
    """Similar to QItemDelegate and ensure that the row is colored
    according to flag, marked or suspended."""
    def __init__(self, browser, model):
        QItemDelegate.__init__(self, browser)
        self.browser = browser
        self.model = model

    def paint(self, painter, option, index):
        self.browser.mw.progress.blockUpdates = True
        try:
            c = self.model.getCard(index)
        except:
            # in the the middle of a reset; return nothing so this row is not
            # rendered until we have a chance to reset the model
            return
        finally:
            self.browser.mw.progress.blockUpdates = True

        if self.model.isRTL(index):
            option.direction = Qt.RightToLeft

        col = None
        if c.userFlag() > 0:
            col = flagColours[c.userFlag()]
        elif c.note().hasTag("Marked"):
            col = COLOUR_MARKED
        elif c.queue == QUEUE_SUSPENDED:
            col = COLOUR_SUSPENDED
        if col:
            brush = QBrush(QColor(col))
            painter.save()
            painter.fillRect(option.rect, brush)
            painter.restore()

        return QItemDelegate.paint(self, painter, option, index)

# Browser window
######################################################################

# fixme: respond to reset+edit hooks

class Browser(QMainWindow):
    """model: the data model (and not a card model !)

    card -- the card in the reviewer when the browser was opened, or the last selected card.
    columns -- A list of pair of potential columns, with their internal name and their local name.
    card -- card selected if there is a single one
    _previewTimer -- progamming a call to _renderScheduledPreview,
    with a new card, at least 500 ms after the last call to this
    method
    _lastPreviewRender -- when was the last call to _renderScheduledPreview
    """

    def __init__(self, mw):
        QMainWindow.__init__(self, None, Qt.Window)
        self.mw = mw
        self.col = self.mw.col
        self.lastFilter = ""
        self.focusTo = None
        self._previewWindow = None
        self._closeEventHasCleanedUp = False
        self.form = aqt.forms.browser.Ui_Dialog()
        self.form.setupUi(self)
        self.setupSidebar()
        restoreGeom(self, "editor", 0)
        restoreState(self, "editor")
        restoreSplitter(self.form.splitter, "editor3")
        self.form.splitter.setChildrenCollapsible(False)
        self.card = None
        self.setupColumns()
        self.setupTable()
        self.setupMenus()
        self.setupHeaders()
        self.setupHooks()
        self.setupEditor()
        self.updateFont()
        self.onUndoState(self.mw.form.actionUndo.isEnabled())
        self.setupSearch()
        self.show()

    def setupMenus(self):
        # pylint: disable=unnecessary-lambda
        # actions
        f = self.form
        f.previewButton.clicked.connect(self.onTogglePreview)
        f.previewButton.setToolTip(_("Preview Selected Card (%s)") %
                                   shortcut(_("Ctrl+Shift+P")))

        f.filter.clicked.connect(self.onFilterButton)
        # edit
        f.actionUndo.triggered.connect(self.mw.onUndo)
        f.actionInvertSelection.triggered.connect(self.invertSelection)
        f.actionSelectNotes.triggered.connect(self.selectNotes)
        if not isMac:
            f.actionClose.setVisible(False)
        # notes
        f.actionAdd.triggered.connect(self.mw.onAddCard)
        f.actionAdd_Tags.triggered.connect(lambda: self.addTags())
        f.actionRemove_Tags.triggered.connect(lambda: self.deleteTags())
        f.actionClear_Unused_Tags.triggered.connect(self.clearUnusedTags)
        f.actionToggle_Mark.triggered.connect(lambda: self.onMark())
        f.actionChangeModel.triggered.connect(self.onChangeModel)
        f.actionFindDuplicates.triggered.connect(self.onFindDupes)
        f.actionFindReplace.triggered.connect(self.onFindReplace)
        f.actionManage_Note_Types.triggered.connect(self.mw.onNoteTypes)
        f.actionDelete.triggered.connect(self.deleteNotes)
        # cards
        f.actionChange_Deck.triggered.connect(self.setDeck)
        f.action_Info.triggered.connect(self.showCardInfo)
        f.actionReposition.triggered.connect(self.reposition)
        f.actionReschedule.triggered.connect(self.reschedule)
        f.actionToggle_Suspend.triggered.connect(self.onSuspend)
        f.actionRed_Flag.triggered.connect(lambda: self.onSetFlag(1))
        f.actionOrange_Flag.triggered.connect(lambda: self.onSetFlag(2))
        f.actionGreen_Flag.triggered.connect(lambda: self.onSetFlag(3))
        f.actionBlue_Flag.triggered.connect(lambda: self.onSetFlag(4))
        # jumps
        f.actionPreviousCard.triggered.connect(self.onPreviousCard)
        f.actionNextCard.triggered.connect(self.onNextCard)
        f.actionFirstCard.triggered.connect(self.onFirstCard)
        f.actionLastCard.triggered.connect(self.onLastCard)
        f.actionFind.triggered.connect(self.onFind)
        f.actionNote.triggered.connect(self.onNote)
        f.actionTags.triggered.connect(self.onFilterButton)
        f.actionSidebar.triggered.connect(self.focusSidebar)
        f.actionCardList.triggered.connect(self.onCardList)
        # help
        f.actionGuide.triggered.connect(self.onHelp)
        # keyboard shortcut for shift+home/end
        self.pgUpCut = QShortcut(QKeySequence("Shift+Home"), self)
        self.pgUpCut.activated.connect(self.onFirstCard)
        self.pgDownCut = QShortcut(QKeySequence("Shift+End"), self)
        self.pgDownCut.activated.connect(self.onLastCard)
        # add-on hook
        runHook('browser.setupMenus', self)
        self.mw.maybeHideAccelerators(self)

        # context menu
        self.form.tableView.setContextMenuPolicy(Qt.CustomContextMenu)
        self.form.tableView.customContextMenuRequested.connect(self.onContextMenu)

    def onContextMenu(self, _point):
        """Open, where mouse is, the context menu, with the content of menu
        cards, menu notes.

        This list can be changed by the hook browser.onContextMenu.

        _point -- not used

        """
        m = QMenu()
        for act in self.form.menu_Cards.actions():
            m.addAction(act)
        m.addSeparator()
        for act in self.form.menu_Notes.actions():
            m.addAction(act)
        runHook("browser.onContextMenu", self, m)

        qtMenuShortcutWorkaround(m)
        m.exec_(QCursor.pos())

    def updateFont(self):
        """Size for the line heights. 6 plus the max of the size of font of
        all models. At least 22."""

        # we can't choose different line heights efficiently, so we need
        # to pick a line height big enough for any card template
        curmax = 16
        for m in self.col.models.all():
            for t in m['tmpls']:
                bsize = t.get("bsize", 0)
                if bsize > curmax:
                    curmax = bsize
        self.form.tableView.verticalHeader().setDefaultSectionSize(
            curmax + 6)

    def closeEvent(self, evt):
        if self._closeEventHasCleanedUp:
            evt.accept()
            return
        self.editor.saveNow(self._closeWindow)
        evt.ignore()

    def _closeWindow(self):
        self._cancelPreviewTimer()
        self.editor.cleanup()
        saveSplitter(self.form.splitter, "editor3")
        saveGeom(self, "editor")
        saveState(self, "editor")
        saveHeader(self.form.tableView.horizontalHeader(), "editor")
        self.col.conf['activeCols'] = self.model.activeCols
        self.col.setMod()
        self.teardownHooks()
        self.mw.maybeReset()
        aqt.dialogs.markClosed("Browser")
        self._closeEventHasCleanedUp = True
        self.mw.gcWindow(self)
        self.close()

    def closeWithCallback(self, onsuccess):
        def callback():
            self._closeWindow()
            onsuccess()
        self.editor.saveNow(callback)

    def keyPressEvent(self, evt):
        """Ensure that window close on escape. Send other event to parent"""
        if evt.key() == Qt.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(evt)

    def setupColumns(self):
        """Set self.columns"""
        self.columns = [
            ('question', _("Question")),
            ('answer', _("Answer")),
            ('template', _("Card")),
            ('deck', _("Deck")),
            ('noteFld', _("Sort Field")),
            ('noteCrt', _("Created")),
            ('noteMod', _("Edited")),
            ('cardMod', _("Changed")),
            ('cardDue', _("Due")),
            ('cardIvl', _("Interval")),
            ('cardEase', _("Ease")),
            ('cardReps', _("Reviews")),
            ('cardLapses', _("Lapses")),
            ('noteTags', _("Tags")),
            ('note', _("Note")),
        ]
        self.columns.sort(key=itemgetter(1)) # allow to sort by
                                             # alphabetical order in
                                             # the local language


    # Searching
    ######################################################################

    def setupSearch(self):
        self.form.searchButton.clicked.connect(self.onSearchActivated)
        self.form.searchEdit.lineEdit().returnPressed.connect(self.onSearchActivated)
        self.form.searchEdit.setCompleter(None)
        self._searchPrompt = _("<type here to search; hit enter to show current deck>")
        self.form.searchEdit.addItems([self._searchPrompt] + self.mw.pm.profile['searchHistory'])
        self._lastSearchTxt = "is:current"
        self.search()
        # then replace text for easily showing the deck
        self.form.searchEdit.lineEdit().setText(self._searchPrompt)
        self.form.searchEdit.lineEdit().selectAll()
        self.form.searchEdit.setFocus()

    # search triggered by user
    def onSearchActivated(self):
        self.editor.saveNow(self._onSearchActivated)

    def _onSearchActivated(self):
        # convert guide text before we save history
        if self.form.searchEdit.lineEdit().text() == self._searchPrompt:
            self.form.searchEdit.lineEdit().setText("deck:current ")

        # grab search text and normalize
        txt = self.form.searchEdit.lineEdit().text()
        txt = unicodedata.normalize("NFC", txt)

        # update history
        sh = self.mw.pm.profile['searchHistory']
        if txt in sh:
            sh.remove(txt)
        sh.insert(0, txt)
        sh = sh[:30]
        self.form.searchEdit.clear()
        self.form.searchEdit.addItems(sh)
        self.mw.pm.profile['searchHistory'] = sh

        # keep track of search string so that we reuse identical search when
        # refreshing, rather than whatever is currently in the search field
        self._lastSearchTxt = txt
        self.search()

    # search triggered programmatically. caller must have saved note first.
    def search(self):
        """Search in the model, either reviewer's note if there is one and
        _lastSearchTxt contains "is:current", or otherwise the
        _lastSearchTxt query.

        """
        if "is:current" in self._lastSearchTxt:
            # show current card if there is one
            c = self.mw.reviewer.card
            self.card = self.mw.reviewer.card
            nid = c and c.nid or 0
            self.model.search("nid:%d"%nid)
        else:
            self.model.search(self._lastSearchTxt)

        if not self.model.cards:
            # no row change will fire
            self._onRowChanged(None, None)

    def updateTitle(self):
        """Set the browser's window title, to take into account the number of
        cards and of selected cards"""

        selected = len(self.form.tableView.selectionModel().selectedRows())
        cur = len(self.model.cards)
        self.setWindowTitle(ngettext("Browse (%(cur)d card shown; %(sel)s)",
                                     "Browse (%(cur)d cards shown; %(sel)s)",
                                 cur) % {
            "cur": cur,
            "sel": ngettext("%d selected", "%d selected", selected) % selected
            })
        return selected

    def onReset(self):
        """Remove the note from the browser's editor window. Redo the
        search"""
        self.editor.setNote(None)
        self.search()

    # Table view & editor
    ######################################################################

    def setupTable(self):
        self.model = DataModel(self)
        self.form.tableView.setSortingEnabled(True)
        self.form.tableView.setModel(self.model)
        self.form.tableView.selectionModel()
        self.form.tableView.setItemDelegate(StatusDelegate(self, self.model))
        self.form.tableView.selectionModel().selectionChanged.connect(self.onRowChanged)
        self.form.tableView.setStyleSheet("QTableView{ selection-background-color: rgba(127, 127, 127, 50);  }")
        self.singleCard = False

    def setupEditor(self):
        self.editor = aqt.editor.Editor(
            self.mw, self.form.fieldsArea, self)

    def onRowChanged(self, current, previous):
        """Save the none. Hide or show editor depending on which cards are
        selected.

        """
        self.editor.saveNow(lambda: self._onRowChanged(current, previous))

    def _onRowChanged(self, current, previous):
        """Hide or show editor depending on which cards are selected.

        """
        update = self.updateTitle()
        show = self.model.cards and update == 1
        self.form.splitter.widget(1).setVisible(not not show)
        idx = self.form.tableView.selectionModel().currentIndex()
        if idx.isValid():
            self.card = self.model.getCard(idx)

        if not show:
            self.editor.setNote(None)
            self.singleCard = False
        else:
            self.editor.setNote(self.card.note(reload=True), focusTo=self.focusTo)
            self.focusTo = None
            self.editor.card = self.card
            self.singleCard = True
        self._updateFlagsMenu()
        runHook("browser.rowChanged", self)
        self._renderPreview(True)

    def refreshCurrentCard(self, note):
        self.model.refreshNote(note)
        self._renderPreview(False)

    def onLoadNote(self, editor):
        self.refreshCurrentCard(editor.note)

    def refreshCurrentCardFilter(self, flag, note, fidx):
        self.refreshCurrentCard(note)
        return flag

    def currentRow(self):
        idx = self.form.tableView.selectionModel().currentIndex()
        return idx.row()

    # Headers & sorting
    ######################################################################

    def setupHeaders(self):
        vh = self.form.tableView.verticalHeader()
        hh = self.form.tableView.horizontalHeader()
        if not isWin:
            vh.hide()
            hh.show()
        restoreHeader(hh, "editor")
        hh.setHighlightSections(False)
        hh.setMinimumSectionSize(50)
        hh.setSectionsMovable(True)
        self.setColumnSizes()
        hh.setContextMenuPolicy(Qt.CustomContextMenu)
        hh.customContextMenuRequested.connect(self.onHeaderContext)
        self.setSortIndicator()
        hh.sortIndicatorChanged.connect(self.onSortChanged)
        hh.sectionMoved.connect(self.onColumnMoved)

    def onSortChanged(self, idx, ord):
        self.editor.saveNow(lambda: self._onSortChanged(idx, ord))

    def _onSortChanged(self, idx, ord):
        type = self.model.activeCols[idx]
        noSort = ("question", "answer", "template", "deck", "note", "noteTags")
        if type in noSort:
            if type == "template":
                showInfo(_("""\
This column can't be sorted on, but you can search for individual card types, \
such as 'card:1'."""))
            elif type == "deck":
                showInfo(_("""\
This column can't be sorted on, but you can search for specific decks \
by clicking on one on the left."""))
            else:
                showInfo(_("Sorting on this column is not supported. Please "
                           "choose another."))
            type = self.col.conf['sortType']
        if self.col.conf['sortType'] != type:
            self.col.conf['sortType'] = type
            # default to descending for non-text fields
            if type == "noteFld":
                ord = not ord
            self.col.conf['sortBackwards'] = ord
            self.search()
        else:
            if self.col.conf['sortBackwards'] != ord:
                self.col.conf['sortBackwards'] = ord
                self.model.reverse()
        self.setSortIndicator()

    def setSortIndicator(self):
        """Add the arrow indicating which column is used to sort, and
        in which order, in the column header"""
        hh = self.form.tableView.horizontalHeader()
        type = self.col.conf['sortType']
        if type not in self.model.activeCols:
            hh.setSortIndicatorShown(False)
            return
        idx = self.model.activeCols.index(type)
        if self.col.conf['sortBackwards']:
            ord = Qt.DescendingOrder
        else:
            ord = Qt.AscendingOrder
        hh.blockSignals(True)
        hh.setSortIndicator(idx, ord)
        hh.blockSignals(False)
        hh.setSortIndicatorShown(True)

    def onHeaderContext(self, pos):
        """Open the context menu related to the list of column.

        There is a button by potential column.
        """
        gpos = self.form.tableView.mapToGlobal(pos) # the position,
        # usable from the browser
        m = QMenu()
        for type, name in self.columns:
            a = m.addAction(name)
            a.setCheckable(True)
            a.setChecked(type in self.model.activeCols)
            a.toggled.connect(lambda b, t=type: self.toggleField(t))
        m.exec_(gpos)

    def toggleField(self, type):
        """
        Save the note in the editor

        Add or remove column type. If added, scroll to it. Can't
        remove if there are less than two columns.
        """
        self.editor.saveNow(lambda: self._toggleField(type))

    def _toggleField(self, type):
        """
        Add or remove column type. If added, scroll to it. Can't
        remove if there are less than two columns.
        """
        self.model.beginReset()
        if type in self.model.activeCols:
            if len(self.model.activeCols) < 2:
                self.model.endReset()
                return showInfo(_("You must have at least one column."))
            self.model.activeCols.remove(type)
            adding=False
        else:
            self.model.activeCols.append(type)
            adding=True
        # sorted field may have been hidden
        self.setSortIndicator()
        self.setColumnSizes()
        self.model.endReset()
        # if we added a column, scroll to it
        if adding:
            row = self.currentRow()
            idx = self.model.index(row, len(self.model.activeCols) - 1)
            self.form.tableView.scrollTo(idx)

    def setColumnSizes(self):
        hh = self.form.tableView.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.Interactive)
        hh.setSectionResizeMode(hh.logicalIndex(len(self.model.activeCols)-1),
                         QHeaderView.Stretch)
        # this must be set post-resize or it doesn't work
        hh.setCascadingSectionResizes(False)

    def onColumnMoved(self, a, b, c):
        self.setColumnSizes()

    # Sidebar
    ######################################################################

    class CallbackItem(QTreeWidgetItem):
        def __init__(self, root, name, onclick, oncollapse=None, expanded=False):
            QTreeWidgetItem.__init__(self, root, [name])
            self.setExpanded(expanded)
            self.onclick = onclick
            self.oncollapse = oncollapse

    class SidebarTreeWidget(QTreeWidget):
        def __init__(self):
            QTreeWidget.__init__(self)
            self.itemClicked.connect(self.onTreeClick)
            self.itemExpanded.connect(self.onTreeCollapse)
            self.itemCollapsed.connect(self.onTreeCollapse)

        def keyPressEvent(self, evt):
            if evt.key() in (Qt.Key_Return, Qt.Key_Enter):
                item = self.currentItem()
                self.onTreeClick(item, 0)
            else:
                super().keyPressEvent(evt)

        def onTreeClick(self, item, col):
            if getattr(item, 'onclick', None):
                item.onclick()

        def onTreeCollapse(self, item):
            if getattr(item, 'oncollapse', None):
                item.oncollapse()

    def setupSidebar(self):
        dw = self.sidebarDockWidget = QDockWidget(_("Sidebar"), self)
        dw.setFeatures(QDockWidget.DockWidgetClosable)
        dw.setObjectName("Sidebar")
        dw.setAllowedAreas(Qt.LeftDockWidgetArea)
        self.sidebarTree = self.SidebarTreeWidget()
        self.sidebarTree.mw = self.mw
        self.sidebarTree.header().setVisible(False)
        dw.setWidget(self.sidebarTree)
        p = QPalette()
        p.setColor(QPalette.Base, p.window().color())
        self.sidebarTree.setPalette(p)
        self.sidebarDockWidget.setFloating(False)
        self.sidebarDockWidget.visibilityChanged.connect(self.onSidebarVisChanged)
        self.sidebarDockWidget.setTitleBarWidget(QWidget())
        self.addDockWidget(Qt.LeftDockWidgetArea, dw)

    def onSidebarVisChanged(self, visible):
        if visible:
            self.buildTree()
        else:
            pass

    def focusSidebar(self):
        self.sidebarDockWidget.setVisible(True)
        self.sidebarTree.setFocus()

    def maybeRefreshSidebar(self):
        if self.sidebarDockWidget.isVisible():
            self.buildTree()

    def buildTree(self):
        self.sidebarTree.clear()
        root = self.sidebarTree
        self._stdTree(root)
        self._favTree(root)
        self._decksTree(root)
        self._modelTree(root)
        self._userTagTree(root)
        self.sidebarTree.setIndentation(15)

    def _stdTree(self, root):
        for name, filt, icon in [[_("Whole Collection"), "", "collection"],
                           [_("Current Deck"), "deck:current", "deck"]]:
            item = self.CallbackItem(
                root, name, self._filterFunc(filt))
            item.setIcon(0, QIcon(":/icons/{}.svg".format(icon)))

    def _favTree(self, root):
        saved = self.col.conf.get('savedFilters', {})
        for name, filt in sorted(saved.items()):
            item = self.CallbackItem(root, name, lambda s=filt: self.setFilter(s))
            item.setIcon(0, QIcon(":/icons/heart.svg"))

    def _userTagTree(self, root):
        for t in sorted(self.col.tags.all(), key=lambda t: t.lower()):
            item = self.CallbackItem(
                root, t, lambda t=t: self.setFilter("tag", t))
            item.setIcon(0, QIcon(":/icons/tag.svg"))

    def _decksTree(self, root):
        grps = self.col.sched.deckDueTree()
        def fillGroups(root, grps, head=""):
            for g in grps:
                item = self.CallbackItem(
                    root, g[0],
                    lambda g=g: self.setFilter("deck", head+g[0]),
                    lambda g=g: self.mw.col.decks.collapseBrowser(g[1]),
                    not self.mw.col.decks.get(g[1]).get('browserCollapsed', False))
                item.setIcon(0, QIcon(":/icons/deck.svg"))
                newhead = head + g[0]+"::"
                fillGroups(item, g[5], newhead)
        fillGroups(root, grps)

    def _modelTree(self, root):
        for m in sorted(self.col.models.all(), key=itemgetter("name")):
            mitem = self.CallbackItem(
                root, m['name'], lambda m=m: self.setFilter("note", m['name']))
            mitem.setIcon(0, QIcon(":/icons/notetype.svg"))

    # Filter tree
    ######################################################################

    def onFilterButton(self):
        ml = MenuList()

        ml.addChild(self._commonFilters())
        ml.addSeparator()

        ml.addChild(self._todayFilters())
        ml.addChild(self._cardStateFilters())
        ml.addChild(self._deckFilters())
        ml.addChild(self._noteTypeFilters())
        ml.addChild(self._tagFilters())
        ml.addSeparator()

        ml.addChild(self.sidebarDockWidget.toggleViewAction())
        ml.addSeparator()

        ml.addChild(self._savedSearches())

        ml.popupOver(self.form.filter)

    def setFilter(self, *args):
        if len(args) == 1:
            txt = args[0]
        else:
            txt = ""
            items = []
            for c, a in enumerate(args):
                if c % 2 == 0:
                    txt += a + ":"
                else:
                    txt += a
                    for chr in " 　()":
                        if chr in txt:
                            txt = '"%s"' % txt
                            break
                    items.append(txt)
                    txt = ""
            txt = " ".join(items)
        if self.mw.app.keyboardModifiers() & Qt.AltModifier:
            txt = "-"+txt
        if self.mw.app.keyboardModifiers() & Qt.ControlModifier:
            cur = str(self.form.searchEdit.lineEdit().text())
            if cur and cur != self._searchPrompt:
                txt = cur + " " + txt
        elif self.mw.app.keyboardModifiers() & Qt.ShiftModifier:
            cur = str(self.form.searchEdit.lineEdit().text())
            if cur:
                txt = cur + " or " + txt
        self.form.searchEdit.lineEdit().setText(txt)
        self.onSearchActivated()

    def _simpleFilters(self, items):
        ml = MenuList()
        for row in items:
            if row is None:
                ml.addSeparator()
            else:
                label, filter = row
                ml.addItem(label, self._filterFunc(filter))
        return ml

    def _filterFunc(self, *args):
        return lambda *, f=args: self.setFilter(*f)

    def _commonFilters(self):
        return self._simpleFilters((
            (_("Whole Collection"), ""),
            (_("Current Deck"), "deck:current")))

    def _todayFilters(self):
        subm = SubMenu(_("Today"))
        subm.addChild(self._simpleFilters((
            (_("Added Today"), "added:1"),
            (_("Studied Today"), "rated:1"),
            (_("Again Today"), "rated:1:1"))))
        return subm

    def _cardStateFilters(self):
        subm = SubMenu(_("Card State"))
        subm.addChild(self._simpleFilters((
            (_("New"), "is:new"),
            (_("Learning"), "is:learn"),
            (_("Review"), "is:review"),
            (_("Due"), "is:due"),
            None,
            (_("Suspended"), "is:suspended"),
            (_("Buried"), "is:buried"),
            None,
            (_("Red Flag"), "flag:1"),
            (_("Orange Flag"), "flag:2"),
            (_("Green Flag"), "flag:3"),
            (_("Blue Flag"), "flag:4"),
            (_("No Flag"), "flag:0"),
            (_("Any Flag"), "-flag:0"),
        )))
        return subm

    def _tagFilters(self):
        m = SubMenu(_("Tags"))

        m.addItem(_("Clear Unused"), self.clearUnusedTags)
        m.addSeparator()

        tagList = MenuList()
        for t in sorted(self.col.tags.all(), key=lambda s: s.lower()):
            tagList.addItem(t, self._filterFunc("tag", t))

        m.addChild(tagList.chunked())
        return m

    def _deckFilters(self):
        def addDecks(parent, decks):
            for head, did, rev, lrn, new, children in decks:
                name = self.mw.col.decks.get(did)['name']
                shortname = name.split("::")[-1]
                if children:
                    subm = parent.addMenu(shortname)
                    subm.addItem(_("Filter"), self._filterFunc("deck", name))
                    subm.addSeparator()
                    addDecks(subm, children)
                else:
                    parent.addItem(shortname, self._filterFunc("deck", name))

        # fixme: could rewrite to avoid calculating due # in the future
        alldecks = self.col.sched.deckDueTree()
        ml = MenuList()
        addDecks(ml, alldecks)

        root = SubMenu(_("Decks"))
        root.addChild(ml.chunked())

        return root

    def _noteTypeFilters(self):
        m = SubMenu(_("Note Types"))

        m.addItem(_("Manage..."), self.mw.onNoteTypes)
        m.addSeparator()

        noteTypes = MenuList()
        for nt in sorted(self.col.models.all(), key=lambda nt: nt['name'].lower()):
            # no sub menu if it's a single template
            if len(nt['tmpls']) == 1:
                noteTypes.addItem(nt['name'], self._filterFunc("note", nt['name']))
            else:
                subm = noteTypes.addMenu(nt['name'])

                subm.addItem(_("All Card Types"), self._filterFunc("note", nt['name']))
                subm.addSeparator()

                # add templates
                for c, tmpl in enumerate(nt['tmpls']):
                    name = _("%(n)d: %(name)s") % dict(n=c+1, name=tmpl['name'])
                    subm.addItem(name, self._filterFunc(
                        "note", nt['name'], "card", str(c+1)))

        m.addChild(noteTypes.chunked())
        return m

    # Favourites
    ######################################################################

    def _savedSearches(self):
        ml = MenuList()
        # make sure exists
        if "savedFilters" not in self.col.conf:
            self.col.conf['savedFilters'] = {}

        ml.addSeparator()

        if self._currentFilterIsSaved():
            ml.addItem(_("Remove Current Filter..."), self._onRemoveFilter)
        else:
            ml.addItem(_("Save Current Filter..."), self._onSaveFilter)

        saved = self.col.conf['savedFilters']
        if not saved:
            return ml

        ml.addSeparator()
        for name, filt in sorted(saved.items()):
            ml.addItem(name, self._filterFunc(filt))

        return ml

    def _onSaveFilter(self):
        name = getOnlyText(_("Please give your filter a name:"))
        if not name:
            return
        filt = self.form.searchEdit.lineEdit().text()
        self.col.conf['savedFilters'][name] = filt
        self.col.setMod()
        self.maybeRefreshSidebar()

    def _onRemoveFilter(self):
        name = self._currentFilterIsSaved()
        if not askUser(_("Remove %s from your saved searches?") % name):
            return
        del self.col.conf['savedFilters'][name]
        self.col.setMod()
        self.maybeRefreshSidebar()

    # returns name if found
    def _currentFilterIsSaved(self):
        filt = self.form.searchEdit.lineEdit().text()
        for k,v in self.col.conf['savedFilters'].items():
            if filt == v:
                return k
        return None

    # Info
    ######################################################################

    def showCardInfo(self):
        if not self.card:
            return
        info, cs = self._cardInfoData()
        reps = self._revlogData(cs)
        class CardInfoDialog(QDialog):
            silentlyClose = True

            def reject(self):
                saveGeom(self, "revlog")
                return QDialog.reject(self)
        d = CardInfoDialog(self)
        l = QVBoxLayout()
        l.setContentsMargins(0,0,0,0)
        w = AnkiWebView()
        l.addWidget(w)
        w.stdHtml(info + "<p>" + reps)
        bb = QDialogButtonBox(QDialogButtonBox.Close)
        l.addWidget(bb)
        bb.rejected.connect(d.reject)
        d.setLayout(l)
        d.setWindowModality(Qt.WindowModal)
        d.resize(500, 400)
        restoreGeom(d, "revlog")
        d.show()

    def _cardInfoData(self):
        from anki.stats import CardStats
        cs = CardStats(self.col, self.card)
        rep = cs.report()
        m = self.card.model()
        rep = """
<div style='width: 400px; margin: 0 auto 0;
border: 1px solid #000; padding: 3px; '>%s</div>""" % rep
        return rep, cs

    def _revlogData(self, cs):
        entries = self.mw.col.db.all(
            "select id/1000.0, ease, ivl, factor, time/1000.0, type "
            "from revlog where cid = ?", self.card.id)
        if not entries:
            return ""
        s = "<table width=100%%><tr><th align=left>%s</th>" % _("Date")
        s += ("<th align=right>%s</th>" * 5) % (
            _("Type"), _("Rating"), _("Interval"), _("Ease"), _("Time"))
        cnt = 0
        for (date, ease, ivl, factor, taken, type) in reversed(entries):
            cnt += 1
            s += "<tr><td>%s</td>" % time.strftime(_("<b>%Y-%m-%d</b> @ %H:%M"),
                                                   time.localtime(date))
            tstr = [_("Learn"), _("Review"), _("Relearn"), _("Filtered"),
                    _("Resched")][type]
            import anki.stats as st
            fmt = "<span style='color:%s'>%s</span>"
            if type == CARD_NEW:
                tstr = fmt % (st.colLearn, tstr)
            elif type == CARD_LRN:
                tstr = fmt % (st.colMature, tstr)
            elif type == CARD_DUE:
                tstr = fmt % (st.colRelearn, tstr)
            elif type == CARD_FILTERED:
                tstr = fmt % (st.colCram, tstr)
            else:
                tstr = fmt % ("#000", tstr)
            if ease == 1:
                ease = fmt % (st.colRelearn, ease)
            if ivl == 0:
                ivl = _("0d")
            elif ivl > 0:
                ivl = fmtTimeSpan(ivl*86400, short=True)
            else:
                ivl = cs.time(-ivl)
            s += ("<td align=right>%s</td>" * 5) % (
                tstr,
                ease, ivl,
                "%d%%" % (factor/10) if factor else "",
                cs.time(taken)) + "</tr>"
        s += "</table>"
        if cnt < self.card.reps:
            s += _("""\
Note: Some of the history is missing. For more information, \
please see the browser documentation.""")
        return s

    # Menu helpers
    ######################################################################

    def selectedCards(self):
        """The list of selected card's id"""
        return [self.model.cards[idx.row()] for idx in
                self.form.tableView.selectionModel().selectedRows()]

    def selectedNotes(self):
        return self.col.db.list("""
select distinct nid from cards
where id in %s""" % ids2str(
    [self.model.cards[idx.row()] for idx in
    self.form.tableView.selectionModel().selectedRows()]))

    def selectedNotesAsCards(self):
        return self.col.db.list(
            "select id from cards where nid in (%s)" %
            ",".join([str(s) for s in self.selectedNotes()]))

    def oneModelNotes(self):
        sf = self.selectedNotes()
        if not sf:
            return
        mods = self.col.db.scalar("""
select count(distinct mid) from notes
where id in %s""" % ids2str(sf))
        if mods > 1:
            showInfo(_("Please select cards from only one note type."))
            return
        return sf

    def onHelp(self):
        openHelp("browser")

    # Misc menu options
    ######################################################################

    def onChangeModel(self):
        """Starts a GUI letting the user change the model of notes.

        If multiple note type are selected, then show a warning
        instead.  It saves the editor content before doing any other
        change it.

        """
        self.editor.saveNow(self._onChangeModel)

    def _onChangeModel(self):
        """Starts a GUI letting the user change the model of notes.

        If multiple note type are selected, then show a warning instead.
        Don't call this directly, call onChangeModel. """
        nids = self.oneModelNotes()
        if nids:
            ChangeModel(self, nids)

    # Preview
    ######################################################################

    _previewTimer = None
    _lastPreviewRender = 0
    _lastPreviewState = None

    def onTogglePreview(self):
        if self._previewWindow:
            self._closePreview()
        else:
            self._openPreview()

    def _openPreview(self):
        self._previewState = "question"
        self._lastPreviewState = None
        self._previewWindow = QDialog(None, Qt.Window)
        self._previewWindow.setWindowTitle(_("Preview"))

        self._previewWindow.finished.connect(self._onPreviewFinished)
        self._previewWindow.silentlyClose = True
        vbox = QVBoxLayout()
        vbox.setContentsMargins(0,0,0,0)
        self._previewWeb = AnkiWebView()
        vbox.addWidget(self._previewWeb)
        bbox = QDialogButtonBox()

        self._previewReplay = bbox.addButton(_("Replay Audio"), QDialogButtonBox.ActionRole)
        self._previewReplay.setAutoDefault(False)
        self._previewReplay.setShortcut(QKeySequence("R"))
        self._previewReplay.setToolTip(_("Shortcut key: %s" % "R"))

        self._previewPrev = bbox.addButton("<", QDialogButtonBox.ActionRole)
        self._previewPrev.setAutoDefault(False)
        self._previewPrev.setShortcut(QKeySequence("Left"))
        self._previewPrev.setToolTip(_("Shortcut key: Left arrow"))

        self._previewNext = bbox.addButton(">", QDialogButtonBox.ActionRole)
        self._previewNext.setAutoDefault(True)
        self._previewNext.setShortcut(QKeySequence("Right"))
        self._previewNext.setToolTip(_("Shortcut key: Right arrow or Enter"))

        self._previewPrev.clicked.connect(self._onPreviewPrev)
        self._previewNext.clicked.connect(self._onPreviewNext)
        self._previewReplay.clicked.connect(self._onReplayAudio)

        self.previewShowBothSides = QCheckBox(_("Show Both Sides"))
        self.previewShowBothSides.setShortcut(QKeySequence("B"))
        self.previewShowBothSides.setToolTip(_("Shortcut key: %s" % "B"))
        bbox.addButton(self.previewShowBothSides, QDialogButtonBox.ActionRole)
        self._previewBothSides = self.col.conf.get("previewBothSides", False)
        self.previewShowBothSides.setChecked(self._previewBothSides)
        self.previewShowBothSides.toggled.connect(self._onPreviewShowBothSides)

        self._setupPreviewWebview()

        vbox.addWidget(bbox)
        self._previewWindow.setLayout(vbox)
        restoreGeom(self._previewWindow, "preview")
        self._previewWindow.show()
        self._renderPreview(True)

    def _onPreviewFinished(self, ok):
        saveGeom(self._previewWindow, "preview")
        self.mw.progress.timer(100, self._onClosePreview, False)
        self.form.previewButton.setChecked(False)

    def _onPreviewPrev(self):
        if self._previewState == "answer" and not self._previewBothSides:
            self._previewState = "question"
            self._renderPreview()
        else:
            self.editor.saveNow(lambda: self._moveCur(QAbstractItemView.MoveUp))

    def _onPreviewNext(self):
        if self._previewState == "question":
            self._previewState = "answer"
            self._renderPreview()
        else:
            self.editor.saveNow(lambda: self._moveCur(QAbstractItemView.MoveDown))

    def _onReplayAudio(self):
        self.mw.reviewer.replayAudio(self)

    def _updatePreviewButtons(self):
        if not self._previewWindow:
            return
        current = self.currentRow()
        canBack = (current > 0 or (current == 0 and self._previewState == "answer"
                                   and not self._previewBothSides))
        self._previewPrev.setEnabled(not not (self.singleCard and canBack))
        canForward = self.currentRow() < self.model.rowCount(None) - 1 or \
                     self._previewState == "question"
        self._previewNext.setEnabled(not not (self.singleCard and canForward))

    def _closePreview(self):
        if self._previewWindow:
            self._previewWindow.close()
            self._onClosePreview()

    def _onClosePreview(self):
        self._previewWindow = self._previewPrev = self._previewNext = None

    def _setupPreviewWebview(self):
        jsinc = ["jquery.js","browsersel.js",
                 "mathjax/conf.js", "mathjax/MathJax.js",
                 "reviewer.js"]
        self._previewWeb.stdHtml(self.mw.reviewer.revHtml(),
                                 css=["reviewer.css"],
                                 js=jsinc)


    def _renderPreview(self, cardChanged=False):
        """Call to _renderScheduledPreview(cardChanged), but ensure at
        least half a second spent since last call to it"""
        self._cancelPreviewTimer()
        # avoid rendering in quick succession
        elapMS = int((time.time() - self._lastPreviewRender)*1000)
        if elapMS < 500:
            self._previewTimer = self.mw.progress.timer(
                500-elapMS, lambda: self._renderScheduledPreview(cardChanged), False)
        else:
            self._renderScheduledPreview(cardChanged)

    def _cancelPreviewTimer(self):
        if self._previewTimer:
            self._previewTimer.stop()
            self._previewTimer = None

    def _renderScheduledPreview(self, cardChanged=False):
        self._cancelPreviewTimer()
        self._lastPreviewRender = time.time()

        if not self._previewWindow:
            return
        c = self.card
        func = "_showQuestion"
        if not c or not self.singleCard:
            txt = _("(please select 1 card)")
            bodyclass = ""
            self._lastPreviewState = None
        else:
            if self._previewBothSides:
                self._previewState = "answer"
            elif cardChanged:
                self._previewState = "question"

            currentState = self._previewStateAndMod()
            if currentState == self._lastPreviewState:
                # nothing has changed, avoid refreshing
                return

            # need to force reload even if answer
            txt = c.q(reload=True)

            questionAudio = []
            if self._previewBothSides:
                questionAudio = allSounds(txt)
            if self._previewState == "answer":
                func = "_showAnswer"
                txt = c.a()
            txt = re.sub(r"\[\[type:[^]]+\]\]", "", txt)

            bodyclass = bodyClass(self.mw.col, c)

            clearAudioQueue()
            if self.mw.reviewer.autoplay(c):
                # if we're showing both sides at once, play question audio first
                for audio in questionAudio:
                    play(audio)
                # then play any audio that hasn't already been played
                for audio in allSounds(txt):
                    if audio not in questionAudio:
                        play(audio)

            txt = mungeQA(self.col, txt)
            txt = runFilter("prepareQA", txt, c,
                            "preview"+self._previewState.capitalize())
            self._lastPreviewState = self._previewStateAndMod()
        self._updatePreviewButtons()
        self._previewWeb.eval(
            "{}({},'{}');".format(func, json.dumps(txt), bodyclass))

    def _onPreviewShowBothSides(self, toggle):
        self._previewBothSides = toggle
        self.col.conf["previewBothSides"] = toggle
        self.col.setMod()
        if self._previewState == "answer" and not toggle:
            self._previewState = "question"
        self._renderPreview()

    def _previewStateAndMod(self):
        c = self.card
        n = c.note()
        n.load()
        return (self._previewState, c.id, n.mod)

    # Card deletion
    ######################################################################

    def deleteNotes(self):
        focus = self.focusWidget()
        if focus != self.form.tableView:
            return
        self._deleteNotes()

    def _deleteNotes(self):
        nids = self.selectedNotes()
        if not nids:
            return
        self.mw.checkpoint(_("Delete Notes"))
        self.model.beginReset()
        # figure out where to place the cursor after the deletion
        curRow = self.form.tableView.selectionModel().currentIndex().row()
        selectedRows = [i.row() for i in
                self.form.tableView.selectionModel().selectedRows()]
        if min(selectedRows) < curRow < max(selectedRows):
            # last selection in middle; place one below last selected item
            move = sum(1 for i in selectedRows if i > curRow)
            newRow = curRow - move
        elif max(selectedRows) <= curRow:
            # last selection at bottom; place one below bottommost selection
            newRow = max(selectedRows) - len(nids) + 1
        else:
            # last selection at top; place one above topmost selection
            newRow = min(selectedRows) - 1
        self.col.remNotes(nids)
        self.search()
        if len(self.model.cards):
            newRow = min(newRow, len(self.model.cards) - 1)
            newRow = max(newRow, 0)
            self.model.focusedCard = self.model.cards[newRow]
        self.model.endReset()
        self.mw.requireReset()
        tooltip(ngettext("%d note deleted.", "%d notes deleted.", len(nids)) % len(nids))

    # Deck change
    ######################################################################

    def setDeck(self):
        self.editor.saveNow(self._setDeck)

    def _setDeck(self):
        from aqt.studydeck import StudyDeck
        cids = self.selectedCards()
        if not cids:
            return
        did = self.mw.col.db.scalar(
            "select did from cards where id = ?", cids[0])
        current=self.mw.col.decks.get(did)['name']
        ret = StudyDeck(
            self.mw, current=current, accept=_("Move Cards"),
            title=_("Change Deck"), help="browse", parent=self)
        if not ret.name:
            return
        did = self.col.decks.id(ret.name)
        deck = self.col.decks.get(did)
        if deck['dyn']:
            showWarning(_("Cards can't be manually moved into a filtered deck."))
            return
        self.model.beginReset()
        self.mw.checkpoint(_("Change Deck"))
        mod = intTime()
        usn = self.col.usn()
        # normal cards
        scids = ids2str(cids)
        # remove any cards from filtered deck first
        self.col.sched.remFromDyn(cids)
        # then move into new deck
        self.col.db.execute("""
update cards set usn=?, mod=?, did=? where id in """ + scids,
                            usn, mod, did)
        self.model.endReset()
        self.mw.requireReset()

    # Tags
    ######################################################################

    def addTags(self, tags=None, label=None, prompt=None, func=None):
        self.editor.saveNow(lambda: self._addTags(tags, label, prompt, func))

    def _addTags(self, tags, label, prompt, func):
        if prompt is None:
            prompt = _("Enter tags to add:")
        if tags is None:
            (tags, r) = getTag(self, self.col, prompt)
        else:
            r = True
        if not r:
            return
        if func is None:
            func = self.col.tags.bulkAdd
        if label is None:
            label = _("Add Tags")
        if label:
            self.mw.checkpoint(label)
        self.model.beginReset()
        func(self.selectedNotes(), tags)
        self.model.endReset()
        self.mw.requireReset()

    def deleteTags(self, tags=None, label=None):
        if label is None:
            label = _("Delete Tags")
        self.addTags(tags, label, _("Enter tags to delete:"),
                     func=self.col.tags.bulkRem)

    def clearUnusedTags(self):
        self.editor.saveNow(self._clearUnusedTags)

    def _clearUnusedTags(self):
        self.col.tags.registerNotes()

    # Suspending
    ######################################################################

    def isSuspended(self):
        return bool (self.card and self.card.queue == QUEUE_SUSPENDED)

    def onSuspend(self):
        self.editor.saveNow(self._onSuspend)

    def _onSuspend(self):
        sus = not self.isSuspended()
        c = self.selectedCards()
        if sus:
            self.col.sched.suspendCards(c)
        else:
            self.col.sched.unsuspendCards(c)
        self.model.reset()
        self.mw.requireReset()

    # Flags & Marking
    ######################################################################

    def onSetFlag(self, n):
        # flag needs toggling off?
        if n == self.card.userFlag():
            n = 0
        self.col.setUserFlag(n, self.selectedCards())
        self.model.reset()

    def _updateFlagsMenu(self):
        flag = self.card and self.card.userFlag()
        flag = flag or 0

        f = self.form
        flagActions = [f.actionRed_Flag,
                       f.actionOrange_Flag,
                       f.actionGreen_Flag,
                       f.actionBlue_Flag]

        for c, act in enumerate(flagActions):
            act.setChecked(flag == c+1)

        qtMenuShortcutWorkaround(self.form.menuFlag)

    def onMark(self, mark=None):
        if mark is None:
            mark = not self.isMarked()
        if mark:
            self.addTags(tags="marked", label=False)
        else:
            self.deleteTags(tags="marked", label=False)

    def isMarked(self):
        return not not (self.card and self.card.note().hasTag("Marked"))

    # Repositioning
    ######################################################################

    def reposition(self):
        self.editor.saveNow(self._reposition)

    def _reposition(self):
        cids = self.selectedCards()
        cids2 = self.col.db.list(
            f"select id from cards where type = {CARD_NEW} and id in " + ids2str(cids))
        if not cids2:
            return showInfo(_("Only new cards can be repositioned."))
        d = QDialog(self)
        d.setWindowModality(Qt.WindowModal)
        frm = aqt.forms.reposition.Ui_Dialog()
        frm.setupUi(d)
        (pmin, pmax) = self.col.db.first(
            f"select min(due), max(due) from cards where type={CARD_NEW} and odid=0")
        pmin = pmin or 0
        pmax = pmax or 0
        txt = _("Queue top: %d") % pmin
        txt += "\n" + _("Queue bottom: %d") % pmax
        frm.label.setText(txt)
        if not d.exec_():
            return
        self.model.beginReset()
        self.mw.checkpoint(_("Reposition"))
        self.col.sched.sortCards(
            cids, start=frm.start.value(), step=frm.step.value(),
            shuffle=frm.randomize.isChecked(), shift=frm.shift.isChecked())
        self.search()
        self.mw.requireReset()
        self.model.endReset()

    # Rescheduling
    ######################################################################

    def reschedule(self):
        self.editor.saveNow(self._reschedule)

    def _reschedule(self):
        d = QDialog(self)
        d.setWindowModality(Qt.WindowModal)
        frm = aqt.forms.reschedule.Ui_Dialog()
        frm.setupUi(d)
        if not d.exec_():
            return
        self.model.beginReset()
        self.mw.checkpoint(_("Reschedule"))
        if frm.asNew.isChecked():
            self.col.sched.forgetCards(self.selectedCards())
        else:
            fmin = frm.min.value()
            fmax = frm.max.value()
            fmax = max(fmin, fmax)
            self.col.sched.reschedCards(
                self.selectedCards(), fmin, fmax)
        self.search()
        self.mw.requireReset()
        self.model.endReset()

    # Edit: selection
    ######################################################################

    def selectNotes(self):
        self.editor.saveNow(self._selectNotes)

    def _selectNotes(self):
        nids = self.selectedNotes()
        # bypass search history
        self._lastSearchTxt = "nid:"+",".join([str(x) for x in nids])
        self.form.searchEdit.lineEdit().setText(self._lastSearchTxt)
        # clear the selection so we don't waste energy preserving it
        tv = self.form.tableView
        tv.selectionModel().clear()
        self.search()
        tv.selectAll()

    def invertSelection(self):
        sm = self.form.tableView.selectionModel()
        items = sm.selection()
        self.form.tableView.selectAll()
        sm.select(items, QItemSelectionModel.Deselect | QItemSelectionModel.Rows)

    # Edit: undo
    ######################################################################

    def setupHooks(self):
        addHook("undoState", self.onUndoState)
        addHook("reset", self.onReset)
        addHook("editTimer", self.refreshCurrentCard)
        addHook("loadNote", self.onLoadNote)
        addHook("editFocusLost", self.refreshCurrentCardFilter)
        for t in "newTag", "newModel", "newDeck":
            addHook(t, self.maybeRefreshSidebar)

    def teardownHooks(self):
        remHook("reset", self.onReset)
        remHook("editTimer", self.refreshCurrentCard)
        remHook("loadNote", self.onLoadNote)
        remHook("editFocusLost", self.refreshCurrentCardFilter)
        remHook("undoState", self.onUndoState)
        for t in "newTag", "newModel", "newDeck":
            remHook(t, self.maybeRefreshSidebar)

    def onUndoState(self, on):
        self.form.actionUndo.setEnabled(on)
        if on:
            self.form.actionUndo.setText(self.mw.form.actionUndo.text())

    # Edit: replacing
    ######################################################################

    def onFindReplace(self):
        self.editor.saveNow(self._onFindReplace)

    def _onFindReplace(self):
        sf = self.selectedNotes()
        if not sf:
            return
        import anki.find
        fields = anki.find.fieldNamesForNotes(self.mw.col, sf)
        d = QDialog(self)
        frm = aqt.forms.findreplace.Ui_Dialog()
        frm.setupUi(d)
        d.setWindowModality(Qt.WindowModal)
        frm.field.addItems([_("All Fields")] + fields)
        frm.buttonBox.helpRequested.connect(self.onFindReplaceHelp)
        restoreGeom(d, "findreplace")
        r = d.exec_()
        saveGeom(d, "findreplace")
        if not r:
            return
        if frm.field.currentIndex() == 0:
            field = None
        else:
            field = fields[frm.field.currentIndex()-1]
        self.mw.checkpoint(_("Find and Replace"))
        self.mw.progress.start()
        self.model.beginReset()
        try:
            changed = self.col.findReplace(sf,
                                            str(frm.find.text()),
                                            str(frm.replace.text()),
                                            frm.re.isChecked(),
                                            field,
                                            frm.ignoreCase.isChecked())
        except sre_constants.error:
            showInfo(_("Invalid regular expression."), parent=self)
            return
        else:
            self.search()
            self.mw.requireReset()
        finally:
            self.model.endReset()
            self.mw.progress.finish()
        showInfo(ngettext(
            "%(a)d of %(b)d note updated",
            "%(a)d of %(b)d notes updated", len(sf)) % {
                'a': changed,
                'b': len(sf),
            }, parent=self)

    def onFindReplaceHelp(self):
        openHelp("findreplace")

    # Edit: finding dupes
    ######################################################################

    def onFindDupes(self):
        self.editor.saveNow(self._onFindDupes)

    def _onFindDupes(self):
        d = QDialog(self)
        self.mw.setupDialogGC(d)
        frm = aqt.forms.finddupes.Ui_Dialog()
        frm.setupUi(d)
        restoreGeom(d, "findDupes")
        fields = sorted(anki.find.fieldNames(self.col, downcase=False),
                        key=lambda x: x.lower())
        frm.fields.addItems(fields)
        self._dupesButton = None
        # links
        frm.webView.onBridgeCmd = self.dupeLinkClicked
        def onFin(code):
            saveGeom(d, "findDupes")
        d.finished.connect(onFin)
        def onClick():
            field = fields[frm.fields.currentIndex()]
            self.duplicatesReport(frm.webView, field, frm.search.text(), frm)
        search = frm.buttonBox.addButton(
            _("Search"), QDialogButtonBox.ActionRole)
        search.clicked.connect(onClick)
        d.show()

    def duplicatesReport(self, web, fname, search, frm):
        self.mw.progress.start()
        res = self.mw.col.findDupes(fname, search)
        if not self._dupesButton:
            self._dupesButton = b = frm.buttonBox.addButton(
                _("Tag Duplicates"), QDialogButtonBox.ActionRole)
            b.clicked.connect(lambda: self._onTagDupes(res))
        t = "<html><body>"
        groups = len(res)
        notes = sum(len(r[1]) for r in res)
        part1 = ngettext("%d group", "%d groups", groups) % groups
        part2 = ngettext("%d note", "%d notes", notes) % notes
        t += _("Found %(a)s across %(b)s.") % dict(a=part1, b=part2)
        t += "<p><ol>"
        for val, nids in res:
            t += '''<li><a href=# onclick="pycmd('%s');return false;">%s</a>: %s</a>''' % (
                "nid:" + ",".join(str(id) for id in nids),
                ngettext("%d note", "%d notes", len(nids)) % len(nids),
                html.escape(val))
        t += "</ol>"
        t += "</body></html>"
        web.setHtml(t)
        self.mw.progress.finish()

    def _onTagDupes(self, res):
        if not res:
            return
        self.model.beginReset()
        self.mw.checkpoint(_("Tag Duplicates"))
        nids = set()
        for s, nidlist in res:
            nids.update(nidlist)
        self.col.tags.bulkAdd(nids, _("duplicate"))
        self.mw.progress.finish()
        self.model.endReset()
        self.mw.requireReset()
        tooltip(_("Notes tagged."))

    def dupeLinkClicked(self, link):
        self.form.searchEdit.lineEdit().setText(link)
        # manually, because we've already saved
        self._lastSearchTxt = link
        self.search()
        self.onNote()

    # Jumping
    ######################################################################

    def _moveCur(self, dir=None, idx=None):
        if not self.model.cards:
            return
        tv = self.form.tableView
        if idx is None:
            idx = tv.moveCursor(dir, self.mw.app.keyboardModifiers())
        tv.selectionModel().setCurrentIndex(
            idx,
            QItemSelectionModel.Clear|
            QItemSelectionModel.Select|
            QItemSelectionModel.Rows)

    def onPreviousCard(self):
        self.focusTo = self.editor.currentField
        self.editor.saveNow(self._onPreviousCard)

    def _onPreviousCard(self):
        self._moveCur(QAbstractItemView.MoveUp)

    def onNextCard(self):
        self.focusTo = self.editor.currentField
        self.editor.saveNow(self._onNextCard)

    def _onNextCard(self):
        self._moveCur(QAbstractItemView.MoveDown)

    def onFirstCard(self):
        sm = self.form.tableView.selectionModel()
        idx = sm.currentIndex()
        self._moveCur(None, self.model.index(0, 0))
        if not self.mw.app.keyboardModifiers() & Qt.ShiftModifier:
            return
        idx2 = sm.currentIndex()
        item = QItemSelection(idx2, idx)
        sm.select(item, QItemSelectionModel.SelectCurrent|
                  QItemSelectionModel.Rows)

    def onLastCard(self):
        sm = self.form.tableView.selectionModel()
        idx = sm.currentIndex()
        self._moveCur(
            None, self.model.index(len(self.model.cards) - 1, 0))
        if not self.mw.app.keyboardModifiers() & Qt.ShiftModifier:
            return
        idx2 = sm.currentIndex()
        item = QItemSelection(idx, idx2)
        sm.select(item, QItemSelectionModel.SelectCurrent|
                  QItemSelectionModel.Rows)

    def onFind(self):
        self.form.searchEdit.setFocus()
        self.form.searchEdit.lineEdit().selectAll()

    def onNote(self):
        self.editor.web.setFocus()

    def onCardList(self):
        self.form.tableView.setFocus()

    def focusCid(self, cid):
        try:
            row = self.model.cards.index(cid)
        except:
            return
        self.form.tableView.selectRow(row)

# Change model dialog
######################################################################

class ChangeModel(QDialog):

    """The dialog window, obtained in the browser by selecting cards and
    Cards>Change Note Type. It allows to change the type of a note
    from one type to another.

    """
    def __init__(self, browser, nids):
        """Create and open a dialog for changing model"""
        QDialog.__init__(self, browser)
        self.browser = browser
        self.nids = nids
        self.oldModel = browser.card.note().model()
        self.form = aqt.forms.changemodel.Ui_Dialog()
        self.form.setupUi(self)
        self.setWindowModality(Qt.WindowModal)
        self.setup()
        restoreGeom(self, "changeModel")
        addHook("reset", self.onReset)
        addHook("currentModelChanged", self.onReset)
        self.exec_()

    def setup(self):
        # maps
        self.flayout = QHBoxLayout()
        self.flayout.setContentsMargins(0,0,0,0)
        self.fwidg = None
        self.form.fieldMap.setLayout(self.flayout)
        self.tlayout = QHBoxLayout()
        self.tlayout.setContentsMargins(0,0,0,0)
        self.twidg = None
        self.form.templateMap.setLayout(self.tlayout)
        if self.style().objectName() == "gtk+":
            # gtk+ requires margins in inner layout
            self.form.verticalLayout_2.setContentsMargins(0, 11, 0, 0)
            self.form.verticalLayout_3.setContentsMargins(0, 11, 0, 0)
        # model chooser
        import aqt.modelchooser
        self.oldModel = self.browser.col.models.get(
            self.browser.col.db.scalar(
                "select mid from notes where id = ?", self.nids[0]))
        self.form.oldModelLabel.setText(self.oldModel['name'])
        self.modelChooser = aqt.modelchooser.ModelChooser(
            self.browser.mw, self.form.modelChooserWidget, label=False)
        self.modelChooser.models.setFocus()
        self.form.buttonBox.helpRequested.connect(self.onHelp)
        self.modelChanged(self.browser.mw.col.models.current())
        self.pauseUpdate = False

    def onReset(self):
        """Change the model changer GUI to the current note type."""
        self.modelChanged(self.browser.col.models.current())

    def modelChanged(self, model):
        """Change the model changer GUI to model

        This should be used if the destination model has been changed.
        """
        self.targetModel = model
        self.rebuildTemplateMap()
        self.rebuildFieldMap()

    def rebuildTemplateMap(self, key=None, attr=None):
        """Change the "Cards" subwindow of the Change Note Type.

        Actually, if key and attr are given, it may change another
        subwindow, so the same code is reused for fields.
        """
        if not key:
            key = "t"
            attr = "tmpls"
        map = getattr(self, key + "widg")
        lay = getattr(self, key + "layout")
        src = self.oldModel[attr]
        dst = self.targetModel[attr]
        if map:
            lay.removeWidget(map)
            map.deleteLater()
            setattr(self, key + "MapWidget", None)
        map = QWidget()
        l = QGridLayout()
        combos = []
        targets = [x['name'] for x in dst] + [_("Nothing")]
        indices = {}
        for i, x in enumerate(src):
            l.addWidget(QLabel(_("Change %s to:") % x['name']), i, 0)
            cb = QComboBox()
            cb.addItems(targets)
            idx = min(i, len(targets)-1)
            cb.setCurrentIndex(idx)
            indices[cb] = idx
            cb.currentIndexChanged.connect(
                lambda i, cb=cb, key=key: self.onComboChanged(i, cb, key))
            combos.append(cb)
            l.addWidget(cb, i, 1)
        map.setLayout(l)
        lay.addWidget(map)
        setattr(self, key + "widg", map)
        setattr(self, key + "layout", lay)
        setattr(self, key + "combos", combos)
        setattr(self, key + "indices", indices)

    def rebuildFieldMap(self):
        """Change the "Fields" subwindow of the Change Note Type."""
        return self.rebuildTemplateMap(key="f", attr="flds")

    def onComboChanged(self, i, cb, key):
        indices = getattr(self, key + "indices")
        if self.pauseUpdate:
            indices[cb] = i
            return
        combos = getattr(self, key + "combos")
        if i == cb.count() - 1:
            # set to 'nothing'
            return
        # find another combo with same index
        for c in combos:
            if c == cb:
                continue
            if c.currentIndex() == i:
                self.pauseUpdate = True
                c.setCurrentIndex(indices[cb])
                self.pauseUpdate = False
                break
        indices[cb] = i

    def getTemplateMap(self, old=None, combos=None, new=None):
        """A map from template's ord of the old model to template's ord of the new
        model. Or None if no template

        Contrary to what this name indicates, the method may be used
        without templates. In getFieldMap it is used for fields

        keywords parameter:
        old -- the list of templates of the old model
        combos -- the python list of gui's list of template
        new -- the list of templates of the new model
        If old is not given, the other two arguments are not used.
        """
        if not old:
            old = self.oldModel['tmpls']
            combos = self.tcombos
            new = self.targetModel['tmpls']
        map = {}
        for i, f in enumerate(old):
            idx = combos[i].currentIndex()
            if idx == len(new):
                # ignore. len(new) corresponds probably to nothing in the list
                map[f['ord']] = None
            else:
                f2 = new[idx]
                map[f['ord']] = f2['ord']
        return map

    def getFieldMap(self):
        """Associating to each field's ord of the source model a field's
        ord (or None) of the new model."""
        return self.getTemplateMap(
            old=self.oldModel['flds'],
            combos=self.fcombos,
            new=self.targetModel['flds'])

    def cleanup(self):
        """Actions to end this gui.

        Remove hook related to this window, and potentially its model chooser.
        Save the geometry of the current window in order to keep it for a new reordering
        """
        remHook("reset", self.onReset)
        remHook("currentModelChanged", self.onReset)
        self.modelChooser.cleanup()
        saveGeom(self, "changeModel")

    def reject(self):
        """Cancelling the changes."""
        self.cleanup()
        return QDialog.reject(self)

    def accept(self):
        """Procede to changing the model, according to the content of the GUI.

        TODO"""
        # check maps
        fmap = self.getFieldMap()
        cmap = self.getTemplateMap()
        #If there are cards which are sent to nothing:
        if any(True for c in list(cmap.values()) if c is None):
            if not askUser(_("""\
Any cards mapped to nothing will be deleted. \
If a note has no remaining cards, it will be lost. \
Are you sure you want to continue?""")):
                return
        self.browser.mw.checkpoint(_("Change Note Type"))
        b = self.browser
        b.mw.col.modSchema(check=True)
        b.mw.progress.start()
        b.model.beginReset()
        mm = b.mw.col.models
        mm.change(self.oldModel, self.nids, self.targetModel, fmap, cmap)
        b.search()
        b.model.endReset()
        b.mw.progress.finish()
        b.mw.reset()
        self.cleanup()
        QDialog.accept(self)

    def onHelp(self):
        openHelp("browsermisc")
