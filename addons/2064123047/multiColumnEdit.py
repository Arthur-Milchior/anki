import json
import os

from anki.hooks import runHook
from anki.lang import _
from aqt import editor
from aqt.editor import *
from aqt.editor import _html
from aqt.qt import *
from aqt.utils import shortcut

old_init = Editor.__init__

def __init__(self, *args, **kwargs):
    self.modelChanged = False
    self.model = None
    old_init(self, *args, **kwargs)
Editor.__init__ = __init__

old_setupTags = Editor.setupTags
def setupTags(self, *args, **kwargs):
        g = QGroupBox(self.widget)
        g.setFlat(True)
        tabLine = QHBoxLayout()
        tabLine.setSpacing(12)
        tabLine.setContentsMargins(6,6,6,6)

        self.setupActualTags(tabLine)
        self.setupNumberColum(tabLine)

        self.outerLayout.addWidget(g)
        g.setLayout(tabLine)
Editor.setupTags = setupTags

def setupActualTags(self, tabLine):
        import aqt.tagedit
        # tags
        tagLabel = QLabel(_("Tags"))
        tabLine.addWidget(tagLabel)
        self.tags = aqt.tagedit.TagEdit(self.widget)
        self.tags.lostFocus.connect(self.saveTags)
        self.tags.setToolTip(shortcut(_("Jump to tags with Ctrl+Shift+T")))
        tabLine.addWidget(self.tags)
Editor.setupActualTags = setupActualTags

def setupNumberColum(self, tabLine):
        label = QLabel("Columns:", self.widget)
        tabLine.addWidget(label)
        self.ccSpin = QSpinBox(self.widget)
        tabLine.addWidget(self.ccSpin)
        self.ccSpin.setMinimum(1)
        self.ccSpin.valueChanged.connect(lambda value: self.onColumnCountChanged(value))
Editor.setupNumberColum = setupNumberColum

oldOnBridgeCmd = Editor.onBridgeCmd
def onBridgeCmd(self, cmd):
    if cmd.startswith("toggleFroze"):
        fieldNumber = cmd.split(":", 1)[1]
        fieldNumber = int(fieldNumber)
        fieldObject = self.model['flds'][fieldNumber]
        self.modelChanged = True
        fieldObject["sticky"] = not fieldObject.get("sticky", False)
        self.loadNote()

    elif cmd.startswith("toggleLineAlone"):
        fieldNumber = cmd.split(":", 1)[1]
        fieldNumber = int(fieldNumber)
        fieldObject = self.model['flds'][fieldNumber]
        fieldObject["Line alone"] = not fieldObject.get("Line alone", False)
        self.modelChanged = True
        self.loadNote()
    else:
        oldOnBridgeCmd(self, cmd)
Editor.onBridgeCmd = onBridgeCmd

oldSetNote = Editor.setNote
def setNote(self, note, hide=True, focusTo=None):
    if note:
        self.model = note.model()
    else:
        self.model = None
    oldSetNote(self, note, hide=True, focusTo=None)
    if self.modelChanged:
        self.mw.col.models.save(self.model)
    self.modelChanged = False
    if self.note:
        self.ccSpin.setValue(self.model.get("number of columns", 1))
Editor.setNote = setNote

def loadNote(self, focusTo=None):
        """Todo

        focusTo -- Whether focus should be set to some field."""
        if not self.note:
            return

        # Triple, for each fields, with (field name, field
        # content modified so that it's image's url can be
        # used locally, and whether it is on its own line)
        data = []
        for ord, (fld, val) in enumerate(self.note.items()):
            val = self.mw.col.media.escapeImages(val)
            field = self.model["flds"][ord]
            lineAlone = field.get("Line alone", False)
            sticky = field.get("sticky", False)
            data.append((fld, val, lineAlone, sticky))
        self.widget.show()
        self.updateTags()

        def oncallback(arg):
            if not self.note:
                return
            self.setupForegroundButton()
            self.checkValid()
            if focusTo is not None:
                self.web.setFocus()
            runHook("loadNote", self)

        self.web.evalWithCallback("setFieldsMC(%s, %d, '%s', '%s'); setFonts(%s); focusField(%s); setNoteId(%s)" % (
            json.dumps(data),
            self.model.get("number of columns", 1),
            self.resourceToData(icon_path_frozen),
            self.resourceToData(icon_path_unfrozen),
            json.dumps(self.fonts()),
            json.dumps(focusTo),
            json.dumps(self.note.id)),
                                  oncallback)
Editor.loadNote = loadNote


def onColumnCountChanged(self, count):
        "Save column count to settings and re-draw with new count."
        self.model["number of columns"] = count
        self.modelChanged = True
        self.loadNote()
Editor.onColumnCountChanged = onColumnCountChanged

__location__ = os.path.realpath(
    os.path.join(os.getcwd(), os.path.dirname(__file__)))
js_file = os.path.join(__location__,"js.js")
user_files = os.path.join(__location__,"user_files")
css_file = os.path.join(user_files,"css.css")
icon_path = os.path.join(__location__,"icons")
icon_path_frozen = os.path.join(icon_path, "frozen.png")
icon_path_unfrozen = os.path.join(icon_path, "unfrozen.png")
with open(js_file,"r") as f:
    js= f.read()
with open(css_file,"r") as f:
    css= f.read()

js = f"""<script>{js}</script>"""
css = f"""<style>{css}</style>"""


def setupWeb(self):
        self.web = EditorWebView(self.widget, self)
        self.web.title = "editor"
        self.web.allowDrops = True
        self.web.onBridgeCmd = self.onBridgeCmd
        self.outerLayout.addWidget(self.web, 1)

        # List of buttons on top right of editor
        righttopbtns = list()
        righttopbtns.append(self._addButton('text_bold', 'bold', _("Bold text (Ctrl+B)"), id='bold'))
        righttopbtns.append(self._addButton('text_italic', 'italic', _("Italic text (Ctrl+I)"), id='italic'))
        righttopbtns.append(self._addButton('text_under', 'underline', _("Underline text (Ctrl+U)"), id='underline'))
        righttopbtns.append(self._addButton('text_super', 'super', _("Superscript (Ctrl++)"), id='superscript'))
        righttopbtns.append(self._addButton('text_sub', 'sub', _("Subscript (Ctrl+=)"), id='subscript'))
        righttopbtns.append(self._addButton('text_clear', 'clear', _("Remove formatting (Ctrl+R)")))
        # The color selection buttons do not use an icon so the HTML must be specified manually
        tip = _("Set foreground colour (F7)")
        righttopbtns.append('''<button tabindex=-1 class=linkb title="{}"
            type="button" onclick="pycmd('colour');return false;">
            <div id=forecolor style="display:inline-block; background: #000;border-radius: 5px;"
            class=topbut></div></button>'''.format(tip))
        tip = _("Change colour (F8)")
        righttopbtns.append('''<button tabindex=-1 class=linkb title="{}"
            type="button" onclick="pycmd('changeCol');return false;">
            <div style="display:inline-block; border-radius: 5px;"
            class="topbut rainbow"></div></button>'''.format(tip))
        righttopbtns.append(self._addButton('text_cloze', 'cloze', _("Cloze deletion (Ctrl+Shift+C)")))
        righttopbtns.append(self._addButton('paperclip', 'attach', _("Attach pictures/audio/video (F3)")))
        righttopbtns.append(self._addButton('media-record', 'record', _("Record audio (F5)")))
        righttopbtns.append(self._addButton('more', 'more'))
        righttopbtns = runFilter("setupEditorButtons", righttopbtns, self)

        # Fields... and Cards... button on top lefts, and
        lefttopbtns = """
                <button title='%(fldsTitle)s' onclick="pycmd('fields')">%(flds)s...</button>
                <button title='%(cardsTitle)s' onclick="pycmd('cards')">%(cards)s...</button>
        """%dict(flds=_("Fields"), cards=_("Cards"),
                   fldsTitle=_("Customize Fields"),
                   cardsTitle=shortcut(_("Customize Card Templates (Ctrl+L)")))
        topbuts= """
            <div id="topbutsleft" style="float:left;">
                %(lefttopbtns)s
            </div>
            <div id="topbutsright" style="float:right;">
                %(rightbts)s
            </div>
        """ % dict(lefttopbtns = lefttopbtns, rightbts="".join(righttopbtns))
        bgcol = self.mw.app.palette().window().color().name()
        # then load page
        html = _html % (
            bgcol, bgcol,
            topbuts,
            _("Show Duplicates"))
        self.web.stdHtml(html,
                         css=["editor.css"], # only difference, css and js file
                         js=["jquery.js", "editor.js"],
                         head=js+css)
Editor.setupWeb = setupWeb
