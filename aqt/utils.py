# Copyright: Ankitects Pty Ltd and contributors
# -*- coding: utf-8 -*-
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

import os
import re
import subprocess
import sys

import aqt
from anki.lang import _
from anki.sound import stripSounds
from anki.utils import (invalidFilename, isMac, isWin, noBundledLibs,
                        versionWithBuild)
from aqt.qt import *


def openHelp(section):
    link = aqt.appHelpSite
    if section:
        link += "#%s" % section
    openLink(link)

def openLink(link):
    tooltip(_("Loading..."), period=1000)
    with noBundledLibs():
        QDesktopServices.openUrl(QUrl(link))

def showWarning(text, parent=None, help="", title="Anki", textFormat=None):
    "Show a small warning with an OK button."
    return showInfo(text, parent, help, "warning", title=title, textFormat=textFormat)

def showCritical(text, parent=None, help="", title="Anki", textFormat=None):
    "Show a small critical error with an OK button."
    return showInfo(text, parent, help, "critical", title=title, textFormat=textFormat)

def showInfo(text, parent=False, help="", type="info", title="Anki", textFormat=None):
    "Show a small info window with an OK button."
    if parent is False:
        parent = aqt.mw.app.activeWindow() or aqt.mw
    if type == "warning":
        icon = QMessageBox.Warning
    elif type == "critical":
        icon = QMessageBox.Critical
    else:
        icon = QMessageBox.Information
    mb = QMessageBox(parent)
    if textFormat == "plain":
        mb.setTextFormat(Qt.PlainText)
    elif textFormat == "rich":
        mb.setTextFormat(Qt.RichText)
    elif textFormat is not None:
        raise Exception("unexpected textFormat type")
    mb.setText(text)
    mb.setIcon(icon)
    mb.setWindowTitle(title)
    okButton = mb.addButton(QMessageBox.Ok)
    okButton.setDefault(True)
    if help:
        okButton = mb.addButton(QMessageBox.Help)
        okButton.clicked.connect(lambda: openHelp(help))
        okButton.setAutoDefault(False)
    return mb.exec_()

def showText(txt, parent=None, type="text", run=True, geomKey=None, \
        minWidth=500, minHeight=400, title="Anki", copyBtn=False):
    if not parent:
        parent = aqt.mw.app.activeWindow() or aqt.mw
    diag = QDialog(parent)
    diag.setWindowTitle(title)
    layout = QVBoxLayout(diag)
    diag.setLayout(layout)
    text = QTextBrowser()
    text.setOpenExternalLinks(True)
    if type == "text":
        text.setPlainText(txt)
    else:
        text.setHtml(txt)
    layout.addWidget(text)
    box = QDialogButtonBox(QDialogButtonBox.Close)
    layout.addWidget(box)
    if copyBtn:
        def onCopy():
            QApplication.clipboard().setText(text.toPlainText())
        btn = QPushButton(_("Copy to Clipboard"))
        btn.clicked.connect(onCopy)
        box.addButton(btn, QDialogButtonBox.ActionRole)
    def onReject():
        if geomKey:
            saveGeom(diag, geomKey)
        QDialog.reject(diag)
    box.rejected.connect(onReject)
    def onFinish():
        if geomKey:
            saveGeom(diag, geomKey)
    box.accepted.connect(onFinish)
    diag.setMinimumHeight(minHeight)
    diag.setMinimumWidth(minWidth)
    if geomKey:
        restoreGeom(diag, geomKey)
    if run:
        diag.exec_()
    else:
        return diag, box

def askUser(text, parent=None, help="", defaultno=False, msgfunc=None, \
        title="Anki"):
    """Show a yes/no question. Return true if yes.

    Text -- the text displayed to the user
    parent -- Add this window as parent to the question
    help -- An help message, occuring if the user click on the help button
    defaultno -- whether the default answer is no
    msgfunc -- The kind of QMessageBox. By default, a question
    title -- title of the question window
    """
    if not parent:
        parent = aqt.mw.app.activeWindow()
    if not msgfunc:
        msgfunc = QMessageBox.question
    sb = QMessageBox.Yes | QMessageBox.No
    if help:
        sb |= QMessageBox.Help
    while 1:
        if defaultno:
            default = QMessageBox.No
        else:
            default = QMessageBox.Yes
        returnValue = msgfunc(parent, title, text, sb, default)
        if returnValue == QMessageBox.Help:

            openHelp(help)
        else:
            break
    return returnValue == QMessageBox.Yes

class ButtonedDialog(QMessageBox):

    def __init__(self, text, buttons, parent=None, help="", title="Anki"):
        """
        text -- Question to explain the user what they can answer
        buttons -- A list of message to show on each buttons
        parent -- The window from which this is opens
        help -- A message to show if user click on «help»
        title -- Title of the window
        """
        QMessageBox.__init__(self, parent)
        self.setWindowTitle(title)
        self.help = help
        self.setIcon(QMessageBox.Warning)
        self.setText(text)
        # layout = QVBoxLayout()
        # layout.addWidget(QLabel(text))
        # box = QDialogButtonBox()
        # layout.addWidget(box)
        self.buttons = [self.addButton(button, QMessageBox.AcceptRole) for button in buttons]
        if help:
            self.addButton(_("Help"), QMessageBox.HelpRole)
            buttons.append(_("Help"))
        #self.setLayout(layout)

    def run(self):
        self.exec_()
        but = self.clickedButton().text()
        if but == "Help":
            # FIXME stop dialog closing?
            openHelp(self.help)
        txt = self.clickedButton().text()
        # work around KDE 'helpfully' adding accelerators to button text of Qt apps
        return txt.replace("&", "")

    def setDefault(self, idx):
        self.setDefaultButton(self.buttons[idx])

def askUserDialog(text, buttons, parent=None, help="", title="Anki"):
    """
    Return a window asking the user to click on one of the buttons of Buttons.
    You should use .run to open it, and it returns the text of the button pressed or None.

    text -- Question to explain the user what they can answer
    buttons -- A list of message to show on each buttons
    parent -- The window from which this is opens
    help -- A message to show if user click on «help»
    title -- Title of the window
    """
    if not parent:
        parent = aqt.mw
    diag = ButtonedDialog(text, buttons, parent, help, title=title)
    return diag

class GetTextDialog(QDialog):

    def __init__(self, parent, question, help=None, edit=None, default="", \
                 title="Anki", minWidth=400):
        QDialog.__init__(self, parent)
        self.setWindowTitle(title)
        self.question = question
        self.help = help
        self.qlabel = QLabel(question)
        self.setMinimumWidth(minWidth)
        layout = QVBoxLayout()
        layout.addWidget(self.qlabel)
        if not edit:
            edit = QLineEdit()
        self.edit = edit
        if default:
            self.edit.setText(default)
            self.edit.selectAll()
        layout.addWidget(self.edit)
        buts = QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        if help:
            buts |= QDialogButtonBox.Help
        button = QDialogButtonBox(buts)
        layout.addWidget(button)
        self.setLayout(layout)
        button.button(QDialogButtonBox.Ok).clicked.connect(self.accept)
        button.button(QDialogButtonBox.Cancel).clicked.connect(self.reject)
        if help:
            button.button(QDialogButtonBox.Help).clicked.connect(self.helpRequested)

    def accept(self):
        return QDialog.accept(self)

    def reject(self):
        return QDialog.reject(self)

    def helpRequested(self):
        openHelp(self.help)

def getText(prompt, parent=None, help=None, edit=None, default="",
            title="Anki", geomKey=None, **kwargs):
    """
    A pair, with:
    * a text, entered by the user (or empty string)
    * value returned by the window. It's falsy if the window was closed and not validated.

    text -- Text to explain the user what they can answer
    parent -- The window from which this is opens. By default, aqt.mw
    help -- A message to show if user click on «help»
    edit -- Which editor to use. By default QLineEdit. No other is used in anki's code.
    default -- Default value of the text
    title -- Title of the window
    """
    if not parent:
        parent = aqt.mw.app.activeWindow() or aqt.mw
    dialog = GetTextDialog(parent, prompt, help=help, edit=edit,
                      default=default, title=title, **kwargs)
    dialog.setWindowModality(Qt.WindowModal)
    if geomKey:
        restoreGeom(dialog, geomKey)
    ret = dialog.exec_()
    if geomKey and ret:
        saveGeom(dialog, geomKey)
    return (str(dialog.edit.text()), ret)

def getOnlyText(*args, **kwargs):
    """A text asked to the user, or the empty string."""
    (text, returnValue) = getText(*args, **kwargs)
    if returnValue:
        return text
    else:
        return ""

# fixme: these utilities could be combined into a single base class
def chooseList(prompt, choices, startrow=0, parent=None):
    if not parent:
        parent = aqt.mw.app.activeWindow()
    dialog = QDialog(parent)
    dialog.setWindowModality(Qt.WindowModal)
    layout = QVBoxLayout()
    dialog.setLayout(layout)
    label = QLabel(prompt)
    layout.addWidget(label)
    widget = QListWidget()
    widget.addItems(choices)
    widget.setCurrentRow(startrow)
    layout.addWidget(widget)
    bb = QDialogButtonBox(QDialogButtonBox.Ok)
    bb.accepted.connect(dialog.accept)
    layout.addWidget(bb)
    dialog.exec_()
    return widget.currentRow()

def getTag(parent, deck, question, tags="user", **kwargs):
    from aqt.tagedit import TagEdit
    te = TagEdit(parent)
    te.setCol(deck)
    ret = getText(question, parent, edit=te,
                  geomKey='getTag', **kwargs)
    te.hideCompleter()
    return ret

# File handling
######################################################################

def getFile(parent, title, cb, filter="*.*", dir=None, key=None, multi=False):
    "Ask the user for a file."
    assert not dir or not key
    if not dir:
        dirkey = key+"Directory"
        dir = aqt.mw.pm.profile.get(dirkey, "")
    else:
        dirkey = None
    dialog = QFileDialog(parent)
    mode = QFileDialog.ExistingFiles if multi else QFileDialog.ExistingFile
    dialog.setFileMode(mode)
    if os.path.exists(dir):
        dialog.setDirectory(dir)
    dialog.setWindowTitle(title)
    dialog.setNameFilter(filter)
    ret = []
    def accept():
        files = list(dialog.selectedFiles())
        if dirkey:
            dir = os.path.dirname(files[0])
            aqt.mw.pm.profile[dirkey] = dir
        result = files if multi else files[0]
        if cb:
            cb(result)
        ret.append(result)
    dialog.accepted.connect(accept)
    if key:
        restoreState(dialog, key)
    dialog.exec_()
    if key:
        saveState(dialog, key)
    return ret and ret[0]

def getSaveFile(parent, title, dir_description, key, ext, fname=None):
    """Ask the user for a file to save. Use DIR_DESCRIPTION as config
    variable. The file dialog will default to open with FNAME."""
    config_key = dir_description + 'Directory'

    defaultPath = QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation)
    base = aqt.mw.pm.profile.get(config_key, defaultPath)
    path = os.path.join(base, fname)
    file = QFileDialog.getSaveFileName(
        parent, title, path, "{0} (*{1})".format(key, ext),
        options=QFileDialog.DontConfirmOverwrite)[0]
    if file:
        # add extension
        if not file.lower().endswith(ext):
            file += ext
        # save new default
        dir = os.path.dirname(file)
        aqt.mw.pm.profile[config_key] = dir
        # check if it exists
        if os.path.exists(file):
            if not askUser(
                _("This file exists. Are you sure you want to overwrite it?"),
                parent):
                return None
    return file

def saveGeom(widget, key):
    """Associate to the key the geometry of the widget"""
    key += "Geom"
    if isMac and widget.windowState() & Qt.WindowFullScreen:
        geom = None
    else:
        geom = widget.saveGeometry()
    aqt.mw.pm.profile[key] = geom

def restoreGeom(widget, key, offset=None, adjustSize=False):
    """Gets from the collection profil the geometry associated to the widget named key.

    keywords parameter:
    offset -- whether a mac window must be resized, assuming qtminor >6 ???
    adjustSize -- Whether to call widget.adjustSize if the key does not belongs in the database """
    key += "Geom"
    if aqt.mw.pm.profile.get(key):
        widget.restoreGeometry(aqt.mw.pm.profile[key])
        if isMac and offset:
            if qtminor > 6:
                # bug in osx toolkit
                size = widget.size()
                widget.resize(size.width(), size.height()+offset*2)
        ensureWidgetInScreenBoundaries(widget)
    else:
        if adjustSize:
            widget.adjustSize()

def ensureWidgetInScreenBoundaries(widget):
    handle = widget.window().windowHandle()
    if not handle:
        # window has not yet been shown, retry later
        aqt.mw.progress.timer(50, lambda: ensureWidgetInScreenBoundaries(widget), False)
        return

    # ensure widget is smaller than screen bounds
    geom = handle.screen().availableGeometry()
    wsize = widget.size()
    cappedWidth = min(geom.width(), wsize.width())
    cappedHeight = min(geom.height(), wsize.height())
    if cappedWidth > wsize.width() or cappedHeight > wsize.height():
        widget.resize(QSize(cappedWidth, cappedHeight))

    # ensure widget is inside top left
    wpos = widget.pos()
    x = max(geom.x(), wpos.x())
    y = max(geom.y(), wpos.y())
    # and bottom right
    x = min(x, geom.width()+geom.x()-cappedWidth)
    y = min(y, geom.height()+geom.y()-cappedHeight)
    if x != wpos.x() or y != wpos.y():
        widget.move(x, y)

def saveState(widget, key):
    key += "State"
    aqt.mw.pm.profile[key] = widget.saveState()

def restoreState(widget, key):
    key += "State"
    if aqt.mw.pm.profile.get(key):
        widget.restoreState(aqt.mw.pm.profile[key])

def saveSplitter(widget, key):
    key += "Splitter"
    aqt.mw.pm.profile[key] = widget.saveState()

def restoreSplitter(widget, key):
    key += "Splitter"
    if aqt.mw.pm.profile.get(key):
        widget.restoreState(aqt.mw.pm.profile[key])

def saveHeader(widget, key):
    key += "Header"
    aqt.mw.pm.profile[key] = widget.saveState()

def restoreHeader(widget, key):
    key += "Header"
    if aqt.mw.pm.profile.get(key):
        widget.restoreState(aqt.mw.pm.profile[key])

def mungeQA(col, txt):
    """txt, without its sound, and Replace local image url by replacing
        special character by the escape %xx

    """
    txt = col.media.escapeImages(txt)
    txt = stripSounds(txt)
    return txt

def openFolder(path):
    if isWin:
        subprocess.Popen(["explorer", "file://"+path])
    else:
        with noBundledLibs():
            QDesktopServices.openUrl(QUrl("file://" + path))

def shortcut(key):
    """On mac: ctrl is replaced by command. Otherwise identity"""
    if isMac:
        return re.sub("(?i)ctrl", "Command", key)
    return key

def maybeHideClose(bbox):
    """On mac only, remove the bbox's close buton."""
    if isMac:
        button = bbox.button(QDialogButtonBox.Close)
        if button:
            bbox.removeButton(button)

def addCloseShortcut(widg):
    if not isMac:
        return
    widg._closeShortcut = QShortcut(QKeySequence("Ctrl+W"), widg)
    widg._closeShortcut.activated.connect(widg.reject)

def downArrow():
    if isWin:
        return "▼"
    # windows 10 is lacking the smaller arrow on English installs
    return "▾"

# Tooltips
######################################################################

_tooltipTimer = None
_tooltipLabel = None

def tooltip(msg, period=3000, parent=None):
    """Show a small yellow box for period milliseconds, containing the
text msg."""
    global _tooltipTimer, _tooltipLabel
    class CustomLabel(QLabel):
        silentlyClose = True
        def mousePressEvent(self, evt):
            evt.accept()
            self.hide()
    closeTooltip()
    aw = parent or aqt.mw.app.activeWindow() or aqt.mw
    lab = CustomLabel("""\
<table cellpadding=10>
<tr>
<td>%s</td>
</tr>
</table>""" % msg, aw)
    lab.setFrameStyle(QFrame.Panel)
    lab.setLineWidth(2)
    lab.setWindowFlags(Qt.ToolTip)
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor("#feffc4"))
    palette.setColor(QPalette.WindowText, QColor("#000000"))
    lab.setPalette(palette)
    lab.move(
        aw.mapToGlobal(QPoint(0, -100 + aw.height())))
    lab.show()
    _tooltipTimer = aqt.mw.progress.timer(
        period, closeTooltip, False, requiresCollection=False)
    _tooltipLabel = lab

def closeTooltip():
    global _tooltipLabel, _tooltipTimer
    if _tooltipLabel:
        try:
            _tooltipLabel.deleteLater()
        except:
            # already deleted as parent window closed
            pass
        _tooltipLabel = None
    if _tooltipTimer:
        _tooltipTimer.stop()
        _tooltipTimer = None

# true if invalid; print warning
def checkInvalidFilename(str, dirsep=True):
    bad = invalidFilename(str, dirsep)
    if bad:
        showWarning(_("The following character can not be used: %s") %
                    bad)
        return True
    return False

# Menus
######################################################################

class MenuList:
    def __init__(self):
        self.children = []

    def addItem(self, title, func):
        item = MenuItem(title, func)
        self.children.append(item)
        return item

    def addSeparator(self):
        self.children.append(None)

    def addMenu(self, title):
        submenu = SubMenu(title)
        self.children.append(submenu)
        return submenu

    def addChild(self, child):
        self.children.append(child)

    def renderTo(self, qmenu):
        for child in self.children:
            if child is None:
                qmenu.addSeparator()
            elif isinstance(child, QAction):
                qmenu.addAction(child)
            else:
                child.renderTo(qmenu)

    def popupOver(self, widget):
        qmenu = QMenu()
        self.renderTo(qmenu)
        qmenu.exec_(widget.mapToGlobal(QPoint(0,0)))

    # Chunking
    ######################################################################

    chunkSize = 30

    def chunked(self):
        if len(self.children) <= self.chunkSize:
            return self

        newList = MenuList()
        oldItems = self.children[:]
        while oldItems:
            chunk = oldItems[:self.chunkSize]
            del oldItems[:self.chunkSize]
            label = self._chunkLabel(chunk)
            menu = newList.addMenu(label)
            menu.children = chunk
        return newList

    def _chunkLabel(self, items):
        start = items[0].title
        end = items[-1].title
        prefix = os.path.commonprefix([start.upper(), end.upper()])
        length = len(prefix)+1
        return "{}-{}".format(start[:length].upper(), end[:length].upper())

class SubMenu(MenuList):
    def __init__(self, title):
        super().__init__()
        self.title = title

    def renderTo(self, menu):
        submenu = menu.addMenu(self.title)
        super().renderTo(submenu)

class MenuItem:
    def __init__(self, title, func):
        self.title = title
        self.func = func

    def renderTo(self, qmenu):
        action = qmenu.addAction(self.title)
        action.triggered.connect(self.func)

def qtMenuShortcutWorkaround(qmenu):
    if qtminor < 10:
        return
    for act in qmenu.actions():
        act.setShortcutVisibleInContextMenu(True)

######################################################################

def supportText():
    import platform
    from aqt import mw

    if isWin:
        platname = "Windows " + platform.win32_ver()[0]
    elif isMac:
        platname = "Mac " + platform.mac_ver()[0]
    else:
        platname = "Linux"

    def schedVer():
        try:
            return mw.col.schedVer()
        except:
            return "?"

    return """\
Anki {} Python {} Qt {} PyQt {}
Platform: {}
Flags: frz={} ao={} sv={}
""".format(versionWithBuild(), platform.python_version(),
           QT_VERSION_STR, PYQT_VERSION_STR, platname,
           getattr(sys, "frozen", False),
           mw.addonManager.dirty, schedVer())

######################################################################

# adapted from version detection in qutebrowser
def opengl_vendor():
    old_context = QOpenGLContext.currentContext()
    old_surface = None if old_context is None else old_context.surface()

    surface = QOffscreenSurface()
    surface.create()

    ctx = QOpenGLContext()
    ok = ctx.create()
    if not ok:
        return None

    ok = ctx.makeCurrent(surface)
    if not ok:
        return None

    try:
        if ctx.isOpenGLES():
            # Can't use versionFunctions there
            return None

        vp = QOpenGLVersionProfile()
        vp.setVersion(2, 0)

        try:
            vf = ctx.versionFunctions(vp)
        except ImportError as e:
            return None

        if vf is None:
            return None

        return vf.glGetString(vf.GL_VENDOR)
    finally:
        ctx.doneCurrent()
        if old_context and old_surface:
            old_context.makeCurrent(old_surface)

def gfxDriverIsBroken():
    driver = opengl_vendor()
    return driver == "nouveau"

def flushNote(note):
    """Flush note. Tooltip if there is an error message."""
    msg = note.flush()
    if msg:
        tooltip(msg)
