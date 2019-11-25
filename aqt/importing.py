# coding=utf-8
# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

import json
import os
import re
import shutil
import traceback
import unicodedata
import zipfile

import anki.importing as importing
import aqt.deckchooser
import aqt.forms
import aqt.modelchooser
from anki.hooks import addHook, remHook
from anki.lang import _, ngettext
from aqt.qt import *
from aqt.utils import (askUser, getFile, getOnlyText, openHelp, showInfo,
                       showText, showWarning, tooltip)


class ChangeMap(QDialog):
    def __init__(self, mw, model, current):
        QDialog.__init__(self, mw, Qt.Window)
        self.mw = mw
        self.model = model
        self.frm = aqt.forms.changemap.Ui_ChangeMap()
        self.frm.setupUi(self)
        count = 0
        setCurrent = False
        for field in self.model['flds']:
            item = QListWidgetItem(_("Map to %s") % field.getName())
            self.frm.fields.addItem(item)
            if current == field.getName():
                setCurrent = True
                self.frm.fields.setCurrentRow(count)
            count += 1
        self.frm.fields.addItem(QListWidgetItem(_("Map to Tags")))
        self.frm.fields.addItem(QListWidgetItem(_("Ignore field")))
        if not setCurrent:
            if current == "_tags":
                self.frm.fields.setCurrentRow(count)
            else:
                self.frm.fields.setCurrentRow(count+1)
        self.field = None

    def getField(self):
        self.exec_()
        return self.field

    def accept(self):
        row = self.frm.fields.currentRow()
        if row < len(self.model['flds']):
            self.field = self.model['flds'][row].getName()
        elif row == self.frm.fields.count() - 2:
            self.field = "_tags"
        else:
            self.field = None
        QDialog.accept(self)

    def reject(self):
        self.accept()

class ImportDialog(QDialog):

    def __init__(self, mw, importer):
        QDialog.__init__(self, mw, Qt.Window)
        self.mw = mw
        self.importer = importer
        self.frm = aqt.forms.importing.Ui_ImportDialog()
        self.frm.setupUi(self)
        self.frm.buttonBox.button(QDialogButtonBox.Help).clicked.connect(
            self.helpRequested)
        self.setupMappingFrame()
        self.setupOptions()
        self.modelChanged()
        self.frm.autoDetect.setVisible(self.importer.needDelimiter)
        addHook("currentModelChanged", self.modelChanged)
        self.frm.autoDetect.clicked.connect(self.onDelimiter)
        self.updateDelimiterButtonText()
        self.frm.allowHTML.setChecked(self.mw.pm.profile.get('allowHTML', True))
        self.frm.importMode.setCurrentIndex(self.mw.pm.profile.get('importMode', 1))
        # import button
        importButton = QPushButton(_("Import"))
        self.frm.buttonBox.addButton(importButton, QDialogButtonBox.AcceptRole)
        self.exec_()

    def setupOptions(self):
        self.model = self.mw.col.models.current()
        self.modelChooser = aqt.modelchooser.ModelChooser(
            self.mw, self.frm.modelArea, label=False)
        self.deck = aqt.deckchooser.DeckChooser(
            self.mw, self.frm.deckArea, label=False)

    def modelChanged(self):
        self.importer.model = self.mw.col.models.current()
        self.importer.initMapping()
        self.showMapping()
        if self.mw.col.conf.get("addToCur", True):
            did = self.mw.col.conf['curDeck']
            if self.mw.col.decks.isDyn(did):
                did = 1
        else:
            did = self.importer.model['did']
        #self.deck.setText(self.mw.col.decks.name(did))

    def onDelimiter(self):
        str = getOnlyText(_("""\
By default, Anki will detect the character between fields, such as
a tab, comma, and so on. If Anki is detecting the character incorrectly,
you can enter it here. Use \\t to represent tab."""),
                self, help="importing") or "\t"
        str = str.replace("\\t", "\t")
        if len(str) > 1:
            showWarning(_(
                "Multi-character separators are not supported. "
                "Please enter one character only."))
            return
        self.hideMapping()
        def updateDelim():
            self.importer.delimiter = str
            self.importer.updateDelimiter()
        self.showMapping(hook=updateDelim)
        self.updateDelimiterButtonText()

    def updateDelimiterButtonText(self):
        if not self.importer.needDelimiter:
            return
        if self.importer.delimiter:
            delimiter = self.importer.delimiter
        else:
            delimiter = self.importer.dialect.delimiter
        if delimiter == "\t":
            delimiter = _("Tab")
        elif delimiter == ",":
            delimiter = _("Comma")
        elif delimiter == " ":
            delimiter = _("Space")
        elif delimiter == ";":
            delimiter = _("Semicolon")
        elif delimiter == ":":
            delimiter = _("Colon")
        else:
            delimiter = repr(delimiter)
        txt = _("Fields separated by: %s") % delimiter
        self.frm.autoDetect.setText(txt)

    def accept(self):
        self.importer.mapping = self.mapping
        if not self.importer.mappingOk():
            showWarning(
                _("The first field of the note type must be mapped."))
            return
        self.importer.importMode = self.frm.importMode.currentIndex()
        self.mw.pm.profile['importMode'] = self.importer.importMode
        self.importer.allowHTML = self.frm.allowHTML.isChecked()
        self.mw.pm.profile['allowHTML'] = self.importer.allowHTML
        did = self.deck.selectedId()
        if did != self.importer.model['did']:
            self.importer.model['did'] = did
            self.importer.model.save()
        self.mw.col.decks.select(did)
        self.mw.progress.start(immediate=True)
        self.mw.checkpoint(_("Import"))
        try:
            self.importer.run()
        except UnicodeDecodeError:
            showUnicodeWarning()
            return
        except Exception as e:
            msg = _("Import failed.\n")
            err = repr(str(e))
            if "1-character string" in err:
                msg += err
            elif "invalidTempFolder" in err:
                msg += self.mw.errorHandler.tempFolderMsg()
            else:
                msg += str(traceback.format_exc(), "ascii", "replace")
            showText(msg)
            return
        finally:
            self.mw.progress.finish()
        txt = _("Importing complete.") + "\n"
        if self.importer.log:
            txt += "\n".join(self.importer.log)
        self.close()
        showText(txt)
        self.mw.reset()

    def setupMappingFrame(self):
        # qt seems to have a bug with adding/removing from a grid, so we add
        # to a separate object and add/remove that instead
        self.frame = QFrame(self.frm.mappingArea)
        self.frm.mappingArea.setWidget(self.frame)
        self.mapbox = QVBoxLayout(self.frame)
        self.mapbox.setContentsMargins(0,0,0,0)
        self.mapwidget = None

    def hideMapping(self):
        self.frm.mappingGroup.hide()

    def showMapping(self, keepMapping=False, hook=None):
        if hook:
            hook()
        if not keepMapping:
            self.mapping = self.importer.mapping
        self.frm.mappingGroup.show()
        assert self.importer.fields()
        # set up the mapping grid
        if self.mapwidget:
            self.mapbox.removeWidget(self.mapwidget)
            self.mapwidget.deleteLater()
        self.mapwidget = QWidget()
        self.mapbox.addWidget(self.mapwidget)
        self.grid = QGridLayout(self.mapwidget)
        self.mapwidget.setLayout(self.grid)
        self.grid.setContentsMargins(3,3,3,3)
        self.grid.setSpacing(6)
        fields = self.importer.fields()
        for num in range(len(self.mapping)):
            text = _("Field <b>%d</b> of file is:") % (num + 1)
            self.grid.addWidget(QLabel(text), num, 0)
            if self.mapping[num] == "_tags":
                text = _("mapped to <b>Tags</b>")
            elif self.mapping[num]:
                text = _("mapped to <b>%s</b>") % self.mapping[num]
            else:
                text = _("<ignored>")
            self.grid.addWidget(QLabel(text), num, 1)
            button = QPushButton(_("Change"))
            self.grid.addWidget(button, num, 2)
            button.clicked.connect(lambda _, s=self,num=num: s.changeMappingNum(num))

    def changeMappingNum(self, num):
        fieldName = ChangeMap(self.mw, self.importer.model, self.mapping[num]).getField()
        try:
            # make sure we don't have it twice
            index = self.mapping.index(fieldName)
            self.mapping[index] = None
        except ValueError:
            pass
        self.mapping[num] = fieldName
        if getattr(self.importer, "delimiter", False):
            self.savedDelimiter = self.importer.delimiter
            def updateDelim():
                self.importer.delimiter = self.savedDelimiter
            self.showMapping(hook=updateDelim, keepMapping=True)
        else:
            self.showMapping(keepMapping=True)

    def reject(self):
        self.modelChooser.cleanup()
        self.deck.cleanup()
        remHook("currentModelChanged", self.modelChanged)
        QDialog.reject(self)

    def helpRequested(self):
        openHelp("importing")


def showUnicodeWarning():
    """Shorthand to show a standard warning."""
    showWarning(_(
        "Selected file was not in UTF-8 format. Please see the "
        "importing section of the manual."))


def onImport(mw):
    filt = ";;".join([importerName for (importerName, importer) in importing.Importers])
    file = getFile(mw, _("Import"), None, key="import",
                   filter=filt)
    if not file:
        return
    file = str(file)

    head, ext = os.path.splitext(file)
    ext = ext.lower()
    if ext == ".anki":
        showInfo(_(".anki files are from a very old version of Anki. You can import them with Anki 2.0, available on the Anki website."))
        return
    elif ext == ".anki2":
        showInfo(_(".anki2 files are not directly importable - please import the .apkg or .zip file you have received instead."))
        return

    importFile(mw, file)

def importFile(mw, file):
    importerClass = None
    done = False
    for importer in importing.Importers:
        if done:
            break
        for mext in re.findall(r"[( ]?\*\.(.+?)[) ]", importer[0]):
            if file.endswith("." + mext):
                importerClass = importer[1]
                done = True
                break
    if not importerClass:
        # if no matches, assume TSV
        importerClass = importing.Importers[0][1]
    importer = importerClass(mw.col, file)
    # need to show import dialog?
    if importer.needMapper:
        # make sure we can load the file first
        mw.progress.start(immediate=True)
        try:
            importer.open()
        except UnicodeDecodeError:
            showUnicodeWarning()
            return
        except Exception as e:
            msg = repr(str(e))
            if msg == "'unknownFormat'":
                showWarning(_("Unknown file format."))
            else:
                msg = _("Import failed. Debugging info:\n")
                msg += str(traceback.format_exc())
                showText(msg)
            return
        finally:
            mw.progress.finish()
        diag = ImportDialog(mw, importer)
    else:
        # if it's an apkg/zip, first test it's a valid file
        if importer.__class__.__name__ == "AnkiPackageImporter":
            try:
                zip = zipfile.ZipFile(importer.file)
                zip.getinfo("collection.anki2")
            except:
                showWarning(invalidZipMsg())
                return
            # we need to ask whether to import/replace
            if not setupApkgImport(mw, importer):
                return
        mw.progress.start(immediate=True)
        try:
            try:
                importer.run()
            finally:
                mw.progress.finish()
        except zipfile.BadZipfile:
            showWarning(invalidZipMsg())
        except Exception as e:
            err = repr(str(e))
            if "invalidFile" in err:
                msg = _("""\
Invalid file. Please restore from backup.""")
                showWarning(msg)
            elif "invalidTempFolder" in err:
                showWarning(mw.errorHandler.tempFolderMsg())
            elif "readonly" in err:
                showWarning(_("""\
Unable to import from a read-only file."""))
            else:
                msg = _("Import failed.\n")
                msg += str(traceback.format_exc())
                showText(msg)
        else:
            log = "\n".join(importer.log)
            if "\n" not in log:
                tooltip(log)
            else:
                showText(log)
        mw.reset()

def invalidZipMsg():
    return _("""\
This file does not appear to be a valid .apkg file. If you're getting this \
error from a file downloaded from AnkiWeb, chances are that your download \
failed. Please try again, and if the problem persists, please try again \
with a different browser.""")

def setupApkgImport(mw, importer):
    base = os.path.basename(importer.file).lower()
    full = ((base == "collection.apkg") or
            re.match("backup-.*\\.apkg", base) or
            base.endswith(".colpkg"))
    if not full:
        # adding
        return True
    if not mw.restoringBackup and not askUser(_("""\
This will delete your existing collection and replace it with the data in \
the file you're importing. Are you sure?"""), msgfunc=QMessageBox.warning,
                                              defaultno=True):
        return False

    replaceWithApkg(mw, importer.file, mw.restoringBackup)

def replaceWithApkg(mw, file, backup):
    mw.unloadCollection(lambda: _replaceWithApkg(mw, file, backup))

def _replaceWithApkg(mw, file, backup):
    mw.progress.start(immediate=True)

    zip = zipfile.ZipFile(file)

    # v2 scheduler?
    colname = "collection.anki21"
    try:
        zip.getinfo(colname)
    except KeyError:
        colname = "collection.anki2"

    try:
        with zip.open(colname) as source, \
                open(mw.pm.collectionPath(), "wb") as target:
            shutil.copyfileobj(source, target)
    except:
        mw.progress.finish()
        showWarning(_("The provided file is not a valid .apkg file."))
        return
    # because users don't have a backup of media, it's safer to import new
    # data and rely on them running a media db check to get rid of any
    # unwanted media. in the future we might also want to deduplicate this
    # step
    mediaFolder = os.path.join(mw.pm.profileFolder(), "collection.media")
    for index, (cStr, file) in enumerate(
            json.loads(zip.read("media").decode("utf8")).items()):
        mw.progress.update(ngettext("Processed %d media file",
                                    "Processed %d media files", index) % index)
        size = zip.getinfo(cStr).file_size
        dest = os.path.join(mediaFolder, unicodedata.normalize("NFC", file))
        # if we have a matching file size
        if os.path.exists(dest) and size == os.stat(dest).st_size:
            continue
        data = zip.read(cStr)
        open(dest, "wb").write(data)
    zip.close()
    # reload
    if not mw.loadCollection():
        mw.progress.finish()
        return
    if backup:
        mw.col.modSchema(check=False)
    mw.progress.finish()
