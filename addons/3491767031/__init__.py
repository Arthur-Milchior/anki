# -*- coding: utf-8 -*-
# Version: 2.5
# See github page to report issues or to contribute:
# https://github.com/hssm/anki-addons

import aqt.editor
from anki.hooks import wrap
from aqt import *
from aqt.editor import Editor

# A sensible maximum number of columns we are able to set
MAX_COLUMNS = 18

# Settings key to remember column count
CONF_KEY_COLUMN_COUNT = 'multi_column_count'

# Flag to enable hack to make Frozen Fields look normal
ffFix = False

aqt.editor._html += """
<script>
var columnCount = 1;
singleColspan = columnCount;
singleLine = [];

function setColumnCount(n) {
    columnCount = n;
}

function setSingleLine(field) {
    singleLine.push(field);
}

var ffFix = false; // Frozen Fields fix
function setFFFix(use) {
  ffFix = use;
}

// Event triggered when #fields is modified.
function makeColumns(event) {

    // If the inserted object is not at the top level of the "fields" object,
    // ignore it. We're assuming that anything added to the "fields" table is
    // the entirety of the content of the table itself.
    if ($(event.target).parent()[0].id !== "fields") {
        return;
    }

    // In the original, there is a row for each field's name followed by a row
    // with that field's edit box. I.e.:
    // <tr><td>...Field name...</td></tr>
    // <tr><td>...Edit box...</td></tr>
    // We copy each row into its own group's array and then
    // write out the table again using our own ordering.

    singleLine = []
    pycmd("mceTrigger"); // Inject global variables for us to use from python.
}

// Because of the asynchronous nature of the bridge calls, we split this method
// into two parts, the latter of which is called from python once the variable
// injection has completed.

function makeColumns2() {
    singleColspan = columnCount;

    // Hack to make Frozen Fields look right.
    if (ffFix) {
        // Apply fixed width to first <td>, which is a Frozen Fields cell,
        // or it will take up too much space.
        $("#fields td:first-child").each(function (){
            $(this).attr("width", "28px");
        });
        singleColspan = (columnCount*2)-1;
    }
    
    s = '<style>';
    s += '.mceTable { table-layout: fixed; height: 1%%; width: 100%%;}';
    s += '.mceTable td .field { height: 100%%; }';
    s += '</style>';
    $('html > head').append(s);
    
    var fNames = [];
    var fEdit = [];
    
    // Create our two lists and tag those that need their own row.
    var rows = $('#fields tr');
    for(var i=0; i<rows.length;){
        fldName = $('.fname', rows[i])[0].innerHTML;
        if (singleLine.indexOf(fldName) >= 0) {
            $(rows[i]).addClass("mceSingle");
            $(rows[i+1]).addClass("mceSingle");
        }
        fNames.push(rows[i]);
        fEdit.push(rows[i+1]);
        i += 2;
    }

    txt = "";
    txt += "<tr>";
    // Pre-populate empty cells to influence column size
    for (var i = 0; i < columnCount; i++) {
        if (ffFix) {
            txt += "<td width=28px></td>";
        }
        txt += "<td></td>";
    }
    txt += "</tr>";

    for (var i = 0; i < fNames.length;) {
        // Lookahead for single-line fields
        target = columnCount;
        for (var j = 0; j < target && i+j < fNames.length; j++) {
            nTd = fNames[i+j];
            eTd = fEdit[i+j];
    
            if ($(nTd).hasClass("mceSingle")) {
                $('.fname', nTd).attr("colspan", singleColspan);
                $('td[width^=100]', eTd).attr("colspan", singleColspan); // hacky selector. need a class
                txt += "<tr class='mceRow mceNameRow'>" + nTd.innerHTML + "</tr>";
                txt += "<tr class='mceRow mceEditRow'>" + eTd.innerHTML + "</tr>";
                fNames[i+j] = "skipme";
                fEdit[i+j] = "skipme";
                target++;
            }
        }
        
        nTxt = "<tr class='mceRow mceNameRow'>";
        eTxt = "<tr class='mceRow mceEditRow'>";
        target = columnCount;
        for (var j = 0; j < target && i+j < fNames.length; j++) {
            var nTd = fNames[i+j];
            var eTd = fEdit[i+j];
            if (nTd === "skipme") {
                target++;
                continue;
            }
            nTxt += nTd.innerHTML;
            eTxt += eTd.innerHTML;
        }
        nTxt += "</tr>";
        eTxt += "</tr>";
        i += target;
        txt += nTxt + eTxt;
    }
    
    // Unbind then rebind to avoid infinite loop
    $('#fields').unbind('DOMNodeInserted')
    $("#fields").html("<table class='mceTable'>" + txt + "</table>");
    $('#fields').bind('DOMNodeInserted', makeColumns);
}

// Attach event to restructure the table after it is populated
$('#fields').bind('DOMNodeInserted', makeColumns);
</script>
"""

def getKeyForContext(self):
    """Get a key that takes into account the parent window type and
    the note type.
    
    This allows us to have a different key for different contexts,
    since we may want different column counts in the browser vs
    note adder, or for different note types.
    """
    return "%s-%s-%s" % (CONF_KEY_COLUMN_COUNT,
                     self.parentWindow.__class__.__name__,
                     self.note.mid)


def onColumnCountChanged(self, count):
    "Save column count to settings and re-draw with new count."
    mw.pm.profile[getKeyForContext(self)] = count
    self.loadNote()


def myEditorInit(self, mw, widget, parentWindow, addMode=False):
    self.ccSpin = QSpinBox(self.widget)
    b = QPushButton(u"▾")
    b.clicked.connect(lambda: onConfigClick(self))
    b.setFixedHeight(self.tags.height())
    b.setFixedWidth(25)
    b.setAutoDefault(False)
    hbox = QHBoxLayout()
    hbox.setSpacing(0)
    label = QLabel("Columns:", self.widget)
    hbox.addWidget(label)
    hbox.addWidget(self.ccSpin)
    hbox.addWidget(b)
    
    self.ccSpin.setMinimum(1)
    self.ccSpin.setMaximum(MAX_COLUMNS)
    self.ccSpin.valueChanged.connect(lambda value: onColumnCountChanged(self, value))

    # We will place the column count editor next to the tags widget.
    pLayout = self.tags.parentWidget().layout()
    # Get the indices of the tags widget
    (rIdx, cIdx, r, c) = pLayout.getItemPosition(pLayout.indexOf(self.tags))
    # Place ours on the same row, to its right.
    pLayout.addLayout(hbox, rIdx, cIdx+1)
        
    # If the user has the Frozen Fields add-on installed, tweak the
    # layout a bit to make it look right.
    global ffFix
    try:
        __import__("Frozen Fields")
        ffFix = True
    except:
        pass


def myOnBridgeCmd(self, cmd):
    """
    Called from JavaScript to inject some values before it needs
    them.
    """
    if cmd == "mceTrigger":
        count = mw.pm.profile.get(getKeyForContext(self), 1)
        self.web.eval("setColumnCount(%d);" % count)
        self.ccSpin.blockSignals(True)
        self.ccSpin.setValue(count)
        self.ccSpin.blockSignals(False)
        for fld, val in self.note.items():
            if mw.pm.profile.get(getKeyForContext(self)+fld, False):
                self.web.eval("setSingleLine('%s');" % fld)
        if ffFix:
            self.web.eval("setFFFix(true)")
        self.web.eval("makeColumns2()")


def onConfigClick(self):
    m = QMenu(self.mw)
    def addCheckableAction(menu, key, text):
        a = menu.addAction(text)
        a.setCheckable(True)
        a.setChecked(mw.pm.profile.get(key, False))
        a.toggled.connect(lambda b, k=key: onCheck(self, k))

    # Descriptive title thing
    a = QAction(u"―Single Row―", m)
    a.setEnabled(False)
    m.addAction(a)
    
    for fld, val in self.note.items():
        key = getKeyForContext(self) + fld
        addCheckableAction(m, key, fld)

    m.exec_(QCursor.pos())


def onCheck(self, key):
    mw.pm.profile[key] = not mw.pm.profile.get(key)
    self.loadNote()


Editor.__init__ = wrap(Editor.__init__, myEditorInit)
Editor.onBridgeCmd = wrap(Editor.onBridgeCmd, myOnBridgeCmd, 'before')
