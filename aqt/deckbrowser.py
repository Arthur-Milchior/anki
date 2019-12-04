# Copyright: Ankitects Pty Ltd and contributors
# -*- coding: utf-8 -*-
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

from copy import deepcopy

import aqt
from anki.consts import *
from anki.errors import DeckRenameError
from anki.hooks import runHook
from anki.lang import _, ngettext
from anki.sound import clearAudioQueue
from anki.utils import fmtTimeSpan, ids2str
from aqt.qt import *
from aqt.utils import (askUser, getOnlyText, openHelp, openLink, shortcut,
                       showWarning)


class DeckBrowser:

    def __init__(self, mw):
        self.mw = mw
        self.web = mw.web
        self.bottom = aqt.toolbar.BottomBar(mw, mw.bottomWeb)
        self.scrollPos = QPoint(0, 0)

    def show(self):
        clearAudioQueue()
        self.web.resetHandlers()
        self.web.onBridgeCmd = self._linkHandler
        self._renderPage()

    def refresh(self):
        self._renderPage()

    # Event handlers
    ##########################################################################

    def _linkHandler(self, url):
        if ":" in url:
            (cmd, arg) = url.split(":")
            if "," in arg:
                arg, arg2 = arg.split(',')
            deck = self.mw.col.decks.get(arg2)
        else:
            cmd = url
        if cmd == "open":
            self._selDeck(arg)
        elif cmd == "opts":
            self._showOptions(arg)
        elif cmd == "shared":
            self._onShared()
        elif cmd == "import":
            self.mw.onImport()
        elif cmd == "lots":
            openHelp("using-decks-appropriately")
        elif cmd == "hidelots":
            self.mw.pm.profile['hideDeckLotsMsg'] = True
            self.refresh()
        elif cmd == "create":
            deck = getOnlyText(_("Name for deck:"))
            if deck:
                self.mw.col.decks.id(deck)
                self.refresh()
        elif cmd == "drag":
            self._dragDeckOnto(arg, arg2)
        elif cmd == "collapse":
            self._collapse(arg)
        return False

    def _selDeck(self, did):
        self.mw.col.decks.get(did).select()
        self.mw.onOverview()

    # HTML generation
    ##########################################################################

    _body = """
<center>
  <table cellspacing=0 cellpading=3>
%(tree)s
  </table>

  <br>
%(stats)s
%(countwarn)s
</center>
"""

    def _renderPage(self, reuse=False):
        """Write the HTML of the deck browser. Move to the last vertical position."""
        if not reuse:
            self.__renderPage(None)
            return
        self.web.evalWithCallback("window.pageYOffset", self.__renderPage)

    def __renderPage(self, offset):
        tree = self._renderDeckTree(self.mw.col.decks.topLevel)
        stats = self._renderStats()
        self.web.stdHtml(self._body%dict(
            tree=tree, stats=stats, countwarn=self._countWarn()),
                         css=["deckbrowser.css"],
                         js=["jquery.js", "jquery-ui.js", "deckbrowser.js"])
        self.web.key = "deckBrowser"
        self._drawButtons()
        if offset is not None:
            self._scrollToOffset(offset)

    def _scrollToOffset(self, offset):
        self.web.eval("$(function() { window.scrollTo(0, %d, 'instant'); });" % offset)

    def _renderStats(self):
        cards, thetime = self.mw.col.db.first("""
select count(), sum(time)/1000 from revlog
where id > ?""", (self.mw.col.sched.dayCutoff-86400)*1000)
        cards = cards or 0
        thetime = thetime or 0
        msgp1 = ngettext("<!--studied-->%d card", "<!--studied-->%d cards", cards) % cards
        buf = _("Studied %(mspg1)s %(theTime)s today.") % dict(mspg1=msgp1,
                                                     theTime=fmtTimeSpan(thetime, unit=1, inTime=True))
        return buf

    def _countWarn(self):
        if (self.mw.col.decks.count() < 25 or
                self.mw.pm.profile.get("hideDeckLotsMsg")):
            return ""
        return """
  <br>
  <div style='width:50%;border: 1px solid #000;padding:5px;'>"""+(
            _("You have aButton lot of decks. Please see %(aButton)s. %(hide)s") % dict(
                aButton=("""<a href=# onclick=\"return pycmd('lots')\">%s</a>""" % _(
                    "this page")),
                hide=("""
    <br>
    <small>
      <a href=# onclick='return pycmd(\"hidelots\")'>
        ("%s)
      </a>
    </small>""" % (_("hide"))+
                    """
  </div>""")))

    def _renderDeckTree(self, deck, depth=0):
        """Html used to show the deck tree.

        keyword arguments
        depth -- the number of ancestors, excluding itself
        decks -- A list of decks, to render, with the same parent. See top of this file for detail"""
        buf = """
  <tr>
    <th colspan=5 align=left>%s
    </th>
    <th class=count>%s
    </th>
    <th class=count>%s
    </th>
    <th class=optscol>
    </th>
  </tr>""" % (
            _("Deck"), _("Due"), _("New"))
        buf += self._topLevelDragRow()
        buf += self.mw.col.decks.topLevel._renderDeckTree()
        buf += self._topLevelDragRow()
        return buf

    @staticmethod
    def _topLevelDragRow():
        return """
  <tr class='top-level-drag-row'>
    <td colspan='6'>
      &nbsp;
    </td>
  </tr>"""
    # Options
    ##########################################################################

    def _showOptions(self, did):
        menu = QMenu(self.mw)
        deck = self.mw.col.decks.get(did)
        action = menu.addAction(_("Rename"))
        action.triggered.connect(lambda button, deck=deck: self._rename(deck))
        action = menu.addAction(_("Options"))
        action.triggered.connect(lambda button, deck=deck: deck._options())
        action = menu.addAction(_("Export"))
        action.triggered.connect(lambda button, deck=deck: self._export(deck))
        action = menu.addAction(_("Delete"))
        action.triggered.connect(lambda button, deck=deck: self._delete(deck))
        runHook("showDeckOptions", menu, did)
        # still passing did, as add-ons have not updated to my fork.
        menu.exec_(QCursor.pos())

    def _export(self, deck):
        self.mw.onExport(deck=deck)

    def _rename(self, deck):
        self.mw.checkpoint(_("Rename Deck"))
        oldName = deck.getName()
        newName = getOnlyText(_("New deck name:"), default=oldName)
        newName = newName.replace('"', "")
        if not newName or newName == oldName:
            return
        try:
            deck.rename(newName)
        except DeckRenameError as e:
            return showWarning(e.description)
        self.show()

    def _collapse(self, did):
        self.mw.col.decks.get(did).collapse()
        self._renderPage(reuse=True)

    def _dragDeckOnto(self, draggedDeckDid, ontoDeckDid):
        try:
            self.mw.col.decks.get(draggedDeckDid).renameForDragAndDrop(ontoDeckDid)
        except DeckRenameError as e:
            return showWarning(e.description)

        self.show()

    def _delete(self, deck):
        if deck.isDefault():
            return showWarning(_("The default deck can't be deleted."))
        self.mw.checkpoint(_("Delete Deck"))
        if deck.isStd():
            dids = deck.getDescendantsIds(includeSelf=True)
            cnt = self.mw.col.db.scalar(
                "select count() from cards where did in {0} or "
                "odid in {0}".format(ids2str(dids)))
            if cnt:
                extra = ngettext(" It has %d card.", " It has %d cards.", cnt) % cnt
            else:
                extra = None
        if deck.isDyn() or not extra or askUser(
            (_("Are you sure you wish to delete %s?") % deck.getName()) +
            extra):
            self.mw.progress.start(immediate=True)
            deck.rem(True)
            self.mw.progress.finish()
            self.show()

    # Top buttons
    ######################################################################

    drawLinks = [
            ["", "shared", _("Get Shared")],
            ["", "create", _("Create Deck")],
            ["Ctrl+I", "import", _("Import File")],  # Ctrl+I works from menu
    ]

    def _drawButtons(self):
        buf = ""
        drawLinks = deepcopy(self.drawLinks)
        for drawLink in drawLinks:
            if drawLink[0]:
                drawLink[0] = _("Shortcut key: %s") % shortcut(drawLink[0])
            buf += """
<button title='%s' onclick='pycmd(\"%s\");'>%s</button>""" % tuple(drawLink)
        self.bottom.draw(buf)
        self.bottom.web.onBridgeCmd = self._linkHandler

    def _onShared(self):
        openLink(aqt.appShared+"decks/")
