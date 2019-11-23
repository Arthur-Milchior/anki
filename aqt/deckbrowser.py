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
            draggedDeckDid, ontoDeckDid = arg.split(',')
            self._dragDeckOnto(draggedDeckDid, ontoDeckDid)
        elif cmd == "collapse":
            self._collapse(arg)
        return False

    def _selDeck(self, did):
        self.mw.col.decks.select(did)
        self.mw.onOverview()

    # HTML generation
    ##########################################################################

    def _renderPage(self, reuse=False):
        """Write the HTML of the deck browser. Move to the last vertical position."""
        if not reuse:
            self._dueTree = self.mw.col.sched.deckDueTree()
            self.__renderPage(None)
            return
        self.web.evalWithCallback("window.pageYOffset", self.__renderPage)

    def __renderPage(self, offset):
        self.web.stdHtml(f"""
<center>
  <table cellspacing=0 cellpading=3>
{self._renderDeckTree(self._dueTree)}
  </table>

  <br>
{self._renderStats()}
{self._countWarn()}
</center>
""",
                         css=["deckbrowser.css"],
                         js=["jquery.js", "jquery-ui.js", "deckbrowser.js"])
        self.web.key = "deckBrowser"
        self._drawButtons()
        if offset is not None:
            self._scrollToOffset(offset)

    def _scrollToOffset(self, offset):
        self.web.eval(f"$(function() {{ window.scrollTo(0, {offset}, 'instant'); }});")

    def _renderStats(self):
        cards, thetime = self.mw.col.db.first("""
select count(), sum(time)/1000 from revlog
where id > ?""", (self.mw.col.sched.dayCutoff-86400)*1000)
        cards = cards or 0
        thetime = thetime or 0
        msgp1 = ngettext("""<!--studied-->%d card""", """<!--studied-->%d cards""", cards) % cards
        return _("""
  Studied %(mspg1)s %(theTime)s today.""") % dict(mspg1=msgp1,
                                                     theTime=fmtTimeSpan(thetime, unit=1, inTime=True))

    def _countWarn(self):
        if (self.mw.col.decks.count() < 25 or
                self.mw.pm.profile.get("hideDeckLotsMsg")):
            return ""
        aButton = f"""
    <a href=# onclick=\"return pycmd('lots')\">
      {_("this page")}
    </a>"""
        hide = f"""
    <br>
    <small>
      <a href=# onclick='return pycmd(\"hidelots\")'>
        ({_("hide")})
      </a>
    </small>
  </div>"""
        return """
  <br>
  <div style='width:50%;border: 1px solid #000;padding:5px;'>
    """+(_("""You have aButton lot of decks. Please see %(aButton)s. %(hide)s""") % dict(
        aButton=aButton,
        hide=hide))

    def _renderDeckTree(self, nodes, depth=0):
        """Html used to show the deck tree.

        keyword arguments
        depth -- the number of ancestors, excluding itself
        nodes -- A list of nodes, to render, with the same parent. See top of this file for detail"""
        if not nodes:
            return ""
        if depth == 0:
            #Toplevel
            buf = f"""
    <tr>
      <th colspan=5 align=left>
        {_("Deck")}
      </th>
      <th class=count>
        {_("Due")}
      </th>
      <th class=count>
        {_("New")}
      </th>
      <th class=optscol>
      </th>
    </tr>"""
            buf += self._topLevelDragRow()
        else:
            buf = ""
        for node in nodes:
            buf += self._deckRow(node, depth, len(nodes))
        if depth == 0:
            buf += self._topLevelDragRow()
        return buf

    @staticmethod
    def nonzeroColour(cnt, colour):
        if not cnt:
            colour = "#e0e0e0"
        if cnt >= 1000:
            cnt = "1000+"
        return f"""
        <font color='{colour}'>
          {cnt}
        </font>"""

    def _deckRow(self, node, depth, cnt):
        """The HTML for a single deck (and its descendant)

        Keyword arguments:
        node -- see in the introduction of the file for a node description
        depth -- indentation argument (number of ancestors)
        cnt --  the number of sibling, counting itself
        """
        name, did, rev, lrn, new, children = node
        deck = self.mw.col.decks.get(did)
        if did == 1 and cnt > 1 and not children:
            # if the default deck is empty, hide it
            if not self.mw.col.db.scalar("select 1 from cards where did = 1 limit 1"):
                return ""
        # parent toggled for collapsing
        for ancestor in self.mw.col.decks.get().ancestors():
            if ancestor['collapsed']:
                return ""
        prefix = "-"
        if self.mw.col.decks.get(did)['collapsed']:
            prefix = "+"
        due = rev + lrn
        if did == self.mw.col.conf['curDeck']:
            klass = 'deck current'
        else:
            klass = 'deck'
        # deck link
        if children:
            collapse = f"""<a class=collapse href=# onclick='return pycmd(\"collapse:{did}\")'>{prefix}</a>"""
        else:
            collapse = """<span class=collapse></span>"""
        if deck.isDyn():
            extraclass = """filtered"""
        else:
            extraclass = ""
        return f"""
    <tr class='{klass}' id='{did}'>
      <td class=decktd colspan=5>
        {"&nbsp;"*6*depth}{collapse}
        <a class="deck {extraclass}" href=# onclick="return pycmd('open:{did}')">
          {name}
        </a>
      </td>
      <!--- due counts -->
      <td align=right>
{DeckBrowser.nonzeroColour(due, colDue)}
      </td>
      <td align=right>
{DeckBrowser.nonzeroColour(new, colNew)}
      </td>
      <!--- options -->
      <td align=center class=opts>
        <a onclick='return pycmd(\"opts:{did}\");'>
          <img src='/_anki/imgs/gears.svg' class=gears>
        </a>
      </td>
    </tr>
    <!--- children -->
    # children
{self._renderDeckTree(children, depth+1)}"""

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
        action = menu.addAction(_("Rename"))
        action.triggered.connect(lambda button, did=did: self._rename(did))
        action = menu.addAction(_("Options"))
        action.triggered.connect(lambda button, did=did: self._options(did))
        action = menu.addAction(_("Export"))
        action.triggered.connect(lambda button, did=did: self._export(did))
        action = menu.addAction(_("Delete"))
        action.triggered.connect(lambda button, did=did: self._delete(did))
        runHook("showDeckOptions", menu, did)
        menu.exec_(QCursor.pos())

    def _export(self, did):
        self.mw.onExport(did=did)

    def _rename(self, did):
        self.mw.checkpoint(_("Rename Deck"))
        deck = self.mw.col.decks.get(did)
        oldName = deck['name']
        newName = getOnlyText(_("New deck name:"), default=oldName)
        newName = newName.replace('"', "")
        if not newName or newName == oldName:
            return
        try:
            deck.rename(newName)
        except DeckRenameError as e:
            return showWarning(e.description)
        self.show()

    def _options(self, did):
        # select the deck first, because the dyn deck conf assumes the deck
        # we're editing is the current one
        self.mw.col.decks.select(did)
        self.mw.onDeckConf()

    def _collapse(self, did):
        self.mw.col.decks.get(did).collapse()
        self._renderPage(reuse=True)

    def _dragDeckOnto(self, draggedDeckDid, ontoDeckDid):
        try:
            draggedDeck = self.get(draggedDeckDid)
            ontoDeck = self.get(ontoDeckDid)
            draggedDeck.dragOnte(ontoDeck)
        except DeckRenameError as e:
            return showWarning(e.description)

        self.show()

    def _delete(self, did):
        if str(did) == '1':
            return showWarning(_("The default deck can't be deleted."))
        self.mw.checkpoint(_("Delete Deck"))
        deck = self.mw.col.decks.get(did)
        if deck.isStd():
            dids = self.mw.col.decks.get(did).getDescendantsIds(True)
            cnt = self.mw.col.db.scalar(
                "select count() from cards where did in {0} or "
                "odid in {0}".format(ids2str(dids)))
            if cnt:
                extra = ngettext(" It has %d card.", " It has %d cards.", cnt) % cnt
            else:
                extra = None
        if deck.isDyn() or not extra or askUser(
            (_("Are you sure you wish to delete %s?") % deck['name']) +
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
        for (shortcut_, cmd, text) in drawLinks:
            if shortcut_:
                shortcut_ = _(f"Shortcut key: {shortcut(shortcut_)}")
            buf += f"""
<button title='{shortcut_}' onclick='pycmd(\"{cmd}\");'>
  {text}
</button>"""
        self.bottom.draw(buf)
        self.bottom.web.onBridgeCmd = self._linkHandler

    def _onShared(self):
        openLink(aqt.appShared+"decks/")
