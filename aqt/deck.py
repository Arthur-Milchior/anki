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
    def _option():
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
        due = rev + lrn
        prefix = "+" if self['collapsed'] else "-"
        indent = "&nbsp;"*6*self.depth()
        klass = 'deck current' if did == self.manager.col.conf['curDeck'] else 'deck'
        buf = f"""
  <tr class='{klass}' id='{did}'>"""
        # deck link

        collapse = f"""
      <a class=collapse href=# onclick='return pycmd(\"collapse:{did}\")'>{prefix}</a>""" if not self.isLeaf() else """
      <span class=collapse></span>"""
        extraclass = "filtered" if self.isDyn() else ""
        buf += f"""

    <td class=decktd colspan=5>{indent}{collapse}
       <a class="deck {extraclass}" href=# onclick="return pycmd('open:{did}')">{name}
       </a>
    </td>"""
        # due counts
        def nonzeroColour(cnt, colour):
            if not cnt:
                colour = "#e0e0e0"
            if cnt >= 1000:
                cnt = "1000+"
            return f"""
      <font color='{colour}'>
         {cnt}
      </font>"""
        buf += f"""
    <td align=right>{nonzeroColour(due, colDue)}
    </td>
    <td align=right>{nonzeroColour(new, colNew)}
    </td>"""
        # options
        buf += (f"""
    <td align=center class=opts>
      <a onclick='return pycmd(\"opts:{did}\");'>
        <img src='/_anki/imgs/gears.svg' class=gears>
      </a>
    </td>
  </tr>""")
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
