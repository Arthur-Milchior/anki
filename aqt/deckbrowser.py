# Copyright: Ankitects Pty Ltd and contributors
# -*- coding: utf-8 -*-
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

# Indentation level is:
# center 0
#   table 2
#     tr 4
#       td 6
#         th, td 8
#           content 10
# newline before the text, not after

# A node is composed of
#                  (name of the deck,
#                  its id,
#                  its number of due cards,
#                  number of reviews of cards in learning which will occur today,
#                  its number of new cards to see today,
#                  its list of children)
from aqt.qt import *
from aqt.utils import askUser, getOnlyText, openLink, showWarning, shortcut, \
    openHelp
from anki.utils import ids2str, fmtTimeSpan
from anki.consts import *
from anki.errors import DeckRenameError
import aqt
from anki.sound import clearAudioQueue
from anki.hooks import runHook
from copy import deepcopy
from anki.lang import _, ngettext

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
            self._dueTree = self.mw.col.sched.deckDueTree()
            self.__renderPage(None)
            return
        self.web.evalWithCallback("window.pageYOffset", self.__renderPage)

    def __renderPage(self, offset):
        tree = self._renderDeckTree(self._dueTree)
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
        """The message "Studied c cards in t time today". """
        cards, thetime = self.mw.col.db.first("""
select count(), sum(time)/1000 from revlog
where id > ?""", (self.mw.col.sched.dayCutoff-86400)*1000)
        cards = cards or 0
        thetime = thetime or 0
        msgp1 = ngettext("<!--studied-->%d card", "<!--studied-->%d cards", cards) % cards
        buf = _("Studied %(a)s %(b)s today.") % dict(a=msgp1,
                                                     b=fmtTimeSpan(thetime, unit=1, inTime=True))
        return buf

    def _countWarn(self):
        if (self.mw.col.decks.count() < 25 or
                self.mw.pm.profile.get("hideDeckLotsMsg")):
            return ""
        link = f"""<a href=# onclick=\"return pycmd('lots')\">{_("this page")}</a>"""
        hide = f"""
  <br>
  <small>
    <a href=# onclick='return pycmd(\"hidelots\")'>({_("hide")})</a>
  </small>"""
        message = _("You have a lot of decks. Please see %(a)s. %(b)s") % dict(
                    a=link,
                    b=hide)
        return (f"""
<br>
<div style='width:50%;border: 1px solid #000;padding:5px;'>{message}
</div>""")

    def _header(self):
        return f"""
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

    def _renderDeckTree(self, nodes, depth=0, nameMap=None):
        """Html used to show the deck browser. This part consider a list of siblings nodes, at some specified depth

        keyword arguments
        depth -- the number of ancestors, excluding itself
        nodes -- A list of nodes, to render, with the same parent. See top of this file for detail
        nameMap -- dictionnary, associating to a deck id its node(to avoid recomputing it)"""
        nameMap = nameMap or self.mw.col.decks.nameMap()#only compute the map on top level
        if not nodes:
            return ""
        rows = "".join(self._deckRow(node, depth, len(nodes), nameMap) for node in nodes)
        if depth == 0:
            return (self._header()
                    +self._topLevelDragRow()
                    +rows
                    +self._topLevelDragRow())
        else:
            return rows

    def _deckRow(self, node, depth, cnt, nameMap):
        """The HTML for a single deck (and its descendant)

        Keyword arguments:
        node -- see in the introduction of the file for a node description
        depth -- indentation argument (number of ancestors)
        cnt --  the number of sibling, counting itself
        nameMap -- dictionnary, associating to a deck id its node
        """
        name, did, rev, lrn, new, children = node
        # if the default deck is empty, not alone, and without child, hide it
        if (did == 1
            and cnt > 1
            and not children
            and not self.mw.col.db.scalar("select 1 from cards where did = 1 limit 1")):
                return ""
        deck = self.mw.col.decks.get(did)

        buf = self._singleDeckRow(depth, deck, did, name, rev, new, collapsed, bool(children))
        due = rev + lrn
        # children
        if not collapsed:
            buf += self._renderDeckTree(children, depth+1, nameMap=nameMap)
            # Equivalent to "".join(self._deckRow(node, depth+1, len(nodes), nameMap) for node in nodes)
            # but add-ons may want to modifiy _renderDeckTree, so we keep it
        return buf

    def _collapseLink(self, did, children, collapsed):
        """Html used to show + or - to collapse deck if required."""
        prefix = "+" if collapsed else "-"
        if children:
            return f"""
        <a class=collapse href=# onclick='return pycmd("collapse:{did}")'>
          {prefix}
        </a>"""
        else:
            return """
        <span class=collapse></span>"""

    def _deckName(self, depth, deck, did, name, collapsed, hasChildren):
        """Html for the deck name's cell"""
        collapse = self._collapseLink(did, hasChildren, collapsed)
        if deck['dyn']:
            extraclass = "filtered"
        else:
            extraclass = ""
        indent = "&nbsp;"*(6*depth)
        return f"""
      <td class=decktd colspan=5>
        {indent}{collapse}
        <a class="deck {extraclass}" href=# onclick="return pycmd('open:{did}')">
          {name}
        </a>
      </td>"""

    def nonzeroColour(self, cnt, colour):
        """Html cell used to show the number:
            "1000+" if greater than 1000
            in grey if it is 0
            in colour otherwise
            """
        if not cnt:
            colour = "#e0e0e0"
        if cnt >= 1000:
            cnt = "1000+"
        return f"""
      <td align=right>
        <font color='{colour}'>{cnt}</font>
      </td>"""

    def _option(self, did):
        """html cell, to show gear opening options"""
        return f"""
      <td align=center class=opts>
        <a onclick='return pycmd("opts:{did}");'>
          <img src='/_anki/imgs/gears.svg' class=gears>
        </a>
      </td>"""

    def _singleDeckRow(self, depth, deck, did, name, due, new, collapsed, hasChildren):
        klass = 'deck'
        if did == self.mw.col.conf['curDeck']:
            klass += ' current'
        return (f"""
    <tr class='{klass}' id='{did}'>"""
                +self._deckName(depth, deck, did, name, collapsed, hasChildren)
                +self.nonzeroColour(due, self.mw.col.conf.get("colors", defaultColors)["due"])
                +self.nonzeroColour(new, self.mw.col.conf.get("colors", defaultColors)["new"])
                +self._option(did)
                +"""
    </tr>""")

    def _topLevelDragRow(self):
        """An empty line. You can drag on it to put some deck at top level"""
        return """
    <tr class='top-level-drag-row'>
      <td colspan='6'>&nbsp;</td>
    </tr>"""

    # Options
    ##########################################################################

    def _showOptions(self, did):
        """Open a menu where mouse clicked (in QtPy, not in HTML) on the gear on a deck line

        did -- the deck' id from the deck line where it was clicked"""
        m = QMenu(self.mw)
        a = m.addAction(_("Rename"))
        a.triggered.connect(lambda b, did=did: self._rename(did))
        a = m.addAction(_("Options"))
        a.triggered.connect(lambda b, did=did: self._options(did))
        a = m.addAction(_("Export"))
        a.triggered.connect(lambda b, did=did: self._export(did))
        a = m.addAction(_("Delete"))
        a.triggered.connect(lambda b, did=did: self._delete(did))
        runHook("showDeckOptions", m, did)
        m.exec_(QCursor.pos())

    def _export(self, did):
        """State to export the deck did.

        Called from the gear on a deck line """
        self.mw.onExport(did=did)

    def _rename(self, did):
        """
        Open a window to rename deck whose id is did

        Called from the gear on a deck line"""
        self.mw.checkpoint(_("Rename Deck"))
        deck = self.mw.col.decks.get(did)
        oldName = deck['name']
        newName = getOnlyText(_("New deck name:"), default=oldName)
        newName = newName.replace('"', "")
        if not newName or newName == oldName:
            return
        try:
            self.mw.col.decks.rename(deck, newName)
        except DeckRenameError as e:
            return showWarning(e.description)
        self.show()

    def _options(self, did):
        """
        Open the deck configuration window for deck  whose id is did

        Called from the gear on a deck line"""
        # select the deck first, because the dyn deck conf assumes the deck
        # we're editing is the current one
        self.mw.col.decks.select(did)
        self.mw.onDeckConf()

    def _collapse(self, did):
        """
        State to hide/show the subdeck of deck whose id is did.

        Called from the +/- sign on a deck line"""
        self.mw.col.decks.collapse(did)
        self._renderPage(reuse=True)

    def _dragDeckOnto(self, draggedDeckDid, ontoDeckDid):
        """Ensure that draggedDeckDid becomes a subdeck of ontoDeckDid.

        If it is impossible, (because ontoDeckDid is a filtered deck),
        then show a warning. Update the window accordingly.

        """
        try:
            self.mw.col.decks.renameForDragAndDrop(draggedDeckDid, ontoDeckDid)
        except DeckRenameError as e:
            return showWarning(e.description)

        self.show()

    def _delete(self, did):
        """Delete the deck whose id is did (ask for confirmation first unless
        it is empty and not filtered)

        Called from the gear on a deck line
        Show a warning instead if did is default deck.

        """

        if str(did) == '1':
            return showWarning(_("The default deck can't be deleted."))
        self.mw.checkpoint(_("Delete Deck"))
        deck = self.mw.col.decks.get(did)
        if not deck['dyn']:
            dids = self.mw.col.decks.childDids(did, includeSelf=True)
            cnt = self.mw.col.db.scalar(
                "select count() from cards where did in {0} or "
                "odid in {0}".format(ids2str(dids)))
            if cnt:
                extra = ngettext(" It has %d card.", " It has %d cards.", cnt) % cnt
            else:
                extra = None
        if deck['dyn'] or not extra or askUser(
            (_("Are you sure you wish to delete %s?") % deck['name']) +
            extra):
            self.mw.progress.start(immediate=True)
            self.mw.col.decks.rem(did, True)
            self.mw.progress.finish()
            self.show()

    # Footer buttons
    ######################################################################

    """List of tuple (Shortcut, pycmd function, text to show) for the
    footer buttons."""
    drawLinks = [
            ["", "shared", _("Get Shared")],
            ["", "create", _("Create Deck")],
            ["Ctrl+I", "import", _("Import File")],  # Ctrl+I works from menu
    ]

    def _drawButtons(self):
        """Change the footer HTML to show those buttons"""
        buf = ""
        drawLinks = deepcopy(self.drawLinks)
        for b in drawLinks:
            if b[0]:
                b[0] = _("Shortcut key: %s") % shortcut(b[0])
            buf += """
<button title='%s' onclick='pycmd(\"%s\");'>%s</button>""" % tuple(b)
        self.bottom.draw(buf)
        self.bottom.web.onBridgeCmd = self._linkHandler

    def _onShared(self):
        openLink(aqt.appShared+"decks/")
