# Copyright: Ankitects Pty Ltd and contributors
# -*- coding: utf-8 -*-
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

from copy import deepcopy

import aqt
from anki.consts import *
from anki.lang import _, ngettext
from anki.sound import clearAudioQueue
from anki.utils import fmtTimeSpan, ids2str
from aqt.deckcolumns import *
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
            deck = self.mw.col.decks.get(arg)
        else:
            cmd = url
        if cmd == "open":
            deck._selDeck()
        elif cmd == "opts":
            deck._showOptions()
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
            deck._dragDeckOnto(arg2)
        elif cmd == "collapse":
            deck._collapse()
        return False

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

    def _renderDeckTree(self, deck, depth=0, columns=None):
        """Html used to show the deck tree.

        keyword arguments
        depth -- the number of ancestors, excluding itself
        decks -- A list of decks, to render, with the same parent. See top of this file for detail"""
        if columns is None:
            columns = self._defaultColumns()
        buf = "".join(column.topRow() for column in columns)
        buf = f"""
  <tr>{buf}
  </tr>"""
        buf += self._topLevelDragRow(columns)
        buf += self.mw.col.decks.topLevel._renderDeckTree(columns)
        buf += self._topLevelDragRow(columns)
        return buf

    def _defaultColumns(self):
        return [
            DeckName(),
            Number("Due", "due", colDue),
            Number("New", "new", colNew),
            Gear(),
        ]

    @staticmethod
    def _topLevelDragRow(columns):
        return f"""
  <tr class='top-level-drag-row'>
    <td colspan='{len(columns)}'>
      &nbsp;
    </td>
  </tr>"""

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
                shortcut_ = _("Shortcut key: %s") % shortcut(shortcut_)
            buf += """<button title='%s' onclick='pycmd(\"%s\");'>%s</button>""" % (shortcut_, cmd, text)
        self.bottom.draw(buf)
        self.bottom.web.onBridgeCmd = self._linkHandler

    def _onShared(self):
        openLink(aqt.appShared+"decks/")
