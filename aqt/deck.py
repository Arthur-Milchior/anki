import anki.deck
from anki.consts import *
from anki.errors import DeckRenameError
from anki.hooks import runHook
from anki.lang import _, ngettext
from anki.utils import ids2str
from aqt.qt import *
from aqt.utils import askUser, getOnlyText, showWarning


class Deck(anki.deck.Deck):
    ## Deck Browser
    @staticmethod
    def _options():
        """html cell, to show gear opening options"""
        return f"""
      <td align=center class=opts>
        <a onclick='return pycmd("opts:{self.getId()}");'>
          <img src='/_anki/imgs/gears.svg' class=gears>
        </a>
      </td>"""

    def _renderDeckTree(self):
        """Html used to show the deck tree.

        keyword arguments
        depth -- the number of ancestors, excluding itself
        decks -- A list of decks, to render, with the same parent. See top of this file for detail"""
        if self.isLeaf():
            return ""
        buf = "".join(child._deckRow() for child in self.getChildren())
        return buf

    def _deckRow(self):
        """The HTML for a single deck (and its descendant)

        Keyword arguments:
        """
        name = self.getBaseName()
        did = self.getId()
        rev = self.count['due']['rev']
        lrn = self.count['due']['lrn']
        new = self.count['due']['new']
        if self.isDefault() and not self.getParent().isLeaf() and self.isLeaf():
            # if the default deck is empty, hide it
            if not self.manager.col.db.scalar("select 1 from cards where did = 1 limit 1"):
                return ""
        prefix = "-"
        if self['collapsed']:
            prefix = "+"
        due = rev + lrn
        def indent():
            return "&nbsp;"*6*self.depth()
        if did == self.manager.col.conf['curDeck']:
            klass = 'deck current'
        else:
            klass = 'deck'
        buf = """
  <tr class='%s' id='%d'>""" % (klass, did)
        # deck link
        if not self.isLeaf():
            collapse = """
      <a class=collapse href=# onclick='return pycmd(\"collapse:%d\")'>%s</a>""" % (did, prefix)
        else:
            collapse = """
      <span class=collapse></span>"""
        if self.isDyn():
            extraclass = "filtered"
        else:
            extraclass = ""
        buf += """

    <td class=decktd colspan=5>%s%s
       <a class="deck %s" href=# onclick="return pycmd('open:%d')">%s
       </a>
    </td>"""% (
            indent(), collapse, extraclass, did, name)
        # due counts
        def nonzeroColour(cnt, colour):
            if not cnt:
                colour = "#e0e0e0"
            if cnt >= 1000:
                cnt = "1000+"
            return """
      <font color='%s'>
         %s
      </font>""" % (colour, cnt)
        buf += """
    <td align=right>%s
    </td>
    <td align=right>%s
    </td>""" % (
            nonzeroColour(due, colDue),
            nonzeroColour(new, colNew))
        # options
        buf += ("""
    <td align=center class=opts>
      <a onclick='return pycmd(\"opts:%d\");'>
        <img src='/_anki/imgs/gears.svg' class=gears>
      </a>
    </td>
  </tr>""" % did)
        # children
        if not self['collapsed']:
            buf += self._renderDeckTree()
        return buf

    def _selDeck(self):
        self.select()
        self.manager.mw.onOverview()

    def _showOptions(self):
        menu = QMenu(self.manager.mw)
        action = menu.addAction(_("Rename"))
        action.triggered.connect(lambda button, deck=self: deck._askAndRename())
        action = menu.addAction(_("Options"))
        action.triggered.connect(lambda button, deck=self: deck._options())
        action = menu.addAction(_("Export"))
        action.triggered.connect(lambda button, deck=self: deck._export())
        action = menu.addAction(_("Delete"))
        action.triggered.connect(lambda button, deck=self: deck._delete())
        runHook("showDeckOptions", menu, self.getId())
        # still passing did, as add-ons have not updated to my fork.
        menu.exec_(QCursor.pos())

    def _export(self):
        self.manager.mw.onExport(deck=self)

    def _askAndRename(self):
        # can't be called _rename, as it would conflict with anki/deck.py
        self.manager.mw.checkpoint(_("Rename Deck"))
        oldName = self.getName()
        newName = getOnlyText(_("New deck name:"), default=oldName)
        newName = newName.replace('"', "")
        if not newName or newName == oldName:
            return
        try:
            self.rename(newName)
        except DeckRenameError as e:
            return showWarning(e.description)
        self.manager.mw.deckBrowser.show()

    def _delete(self):
        if self.isDefault():
            return showWarning(_("The default deck can't be deleted."))
        self.manager.mw.checkpoint(_("Delete Deck"))
        if self.isStd():
            dids = self.getDescendantsIds(includeSelf=True)
            cnt = self.manager.mw.col.db.scalar(
                "select count() from cards where did in {0} or "
                "odid in {0}".format(ids2str(dids)))
            if cnt:
                extra = ngettext(" It has %d card.", " It has %d cards.", cnt) % cnt
            else:
                extra = None
        if self.isDyn() or not extra or askUser(
            (_("Are you sure you wish to delete %s?") % self.getName()) +
            extra):
            self.manager.mw.progress.start(immediate=True)
            self.rem(True)
            self.manager.mw.progress.finish()
            self.manager.mw.deckBrowser.show()

    def _dragDeckOnto(self, ontoDeckDid):
        try:
            self.renameForDragAndDrop(ontoDeckDid)
        except DeckRenameError as e:
            return showWarning(e.description)

        self.manager.mw.deckBrowser.show()

    def _collapse(self):
        self.collapse()
        self.manager.mw.deckBrowser._renderPage(reuse=True)
