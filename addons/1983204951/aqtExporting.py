# -*- coding: utf-8 -*-
# Copyright: Arthur Milchior arthur@milchior.fr
# encoding: utf8
# License: GNU GPL, version 3 or later; http://www.gnu.org/copyleft/gpl.html
# Feel free to contribute to this code on https://github.com/Arthur-Milchior/anki-export-from-browser
# Add-on number 1983204951 https://ankiweb.net/shared/info/1983204951

import os
import re
import time

from PyQt5.QtWidgets import QAction

from anki import Collection
from anki.exporting import AnkiExporter, Exporter, exporters
from anki.hooks import addHook, remHook
from anki.lang import _, ngettext
from anki.utils import ids2str
from aqt import mw
from aqt.exporting import ExportDialog
from aqt.qt import QDialog, QDialogButtonBox, QKeySequence, QPushButton
from aqt.utils import (checkInvalidFilename, getSaveFile, showInfo,
                       showWarning, tooltip)


def debug(t):
    print(t)
    pass

#Change to ExportDialog
oldInit=ExportDialog.__init__
def __init__(self, mw, did=None, cids=None):
    self.cids = cids
    oldInit(self,mw,did=did)
ExportDialog.__init__=__init__

# oldExporterChanged = ExportDialog.exportChanged
# def exporterChanged(self, idx):
#     oldExporterChanged(self,idx)
# ExportDialog.exportChanged=exporterChanged


def setup(self, did):
        """
        keyword arguments:
        did -- if None, then export whole anki. If did, export this deck. If list of cids, expots those cids.
        """
        debug(f"Calling setup({did}), its cids is {self.cids}")
        self.exporters = exporters()
        # if a deck specified, start with .apkg type selected
        idx = 0
        if did or self.cids:
            for c, (k,e) in enumerate(self.exporters):
                if e.ext == ".apkg":
                    idx = c
                    break
        self.frm.format.insertItems(0, [e[0] for e in self.exporters])
        self.frm.format.setCurrentIndex(idx)
        self.frm.format.activated.connect(self.exporterChanged)
        self.exporterChanged(idx)
        # deck list
        self.decks = [_("All Decks")]
        if self.cids:
            bs=_("Browser's selection")
            debug(f"Adding {bs}")
            self.decks = self.decks+[bs]
        self.decks = self.decks + sorted(self.col.decks.allNames())
        self.frm.deck.addItems(self.decks)
        # save button
        b = QPushButton(_("Export..."))
        self.frm.buttonBox.addButton(b, QDialogButtonBox.AcceptRole)
        # set default option if accessed through deck button
        if did:
            name = self.mw.col.decks.get(did)['name']
            index = self.frm.deck.findText(name)
            self.frm.deck.setCurrentIndex(index)
        if self.cids:
            self.frm.deck.setCurrentIndex(1)
ExportDialog.setup=setup

def accept(self):
        debug(f"Calling accept()")
        self.exporter.includeSched = (
            self.frm.includeSched.isChecked())
        self.exporter.includeMedia = (
            self.frm.includeMedia.isChecked())
        self.exporter.includeTags = (
            self.frm.includeTags.isChecked())
        self.exporter.includeHTML = (
            self.frm.includeHTML.isChecked())
### Starting change
        if self.frm.deck.currentIndex() == 0:#position 0 means: all decks.
            self.exporter.did = None
            self.exporter.cids = None
        elif self.frm.deck.currentIndex() == 1 and self.cids is not None:#position 1 means: selected decks.
            self.exporter.did = None
            self.exporter.cids = self.cids
        else:
            self.exporter.cids = None
### ending change
            name = self.decks[self.frm.deck.currentIndex()]
            self.exporter.did = self.col.decks.id(name)
        if self.isVerbatim:
            name = time.strftime("-%Y-%m-%d@%H-%M-%S",
                                 time.localtime(time.time()))
            deck_name = _("collection")+name
        else:
            # Get deck name and remove invalid filename characters
            deck_name = self.decks[self.frm.deck.currentIndex()]
            deck_name = re.sub('[\\\\/?<>:*|"^]', '_', deck_name)

        if not self.isVerbatim and self.isApkg and self.exporter.includeSched and self.col.schedVer() == 2:
            showInfo("Please switch to the regular scheduler before exporting a single deck .apkg with scheduling.")
            return

        filename = '{0}{1}'.format(deck_name, self.exporter.ext)
        while 1:
            file = getSaveFile(self, _("Export"), "export",
                               self.exporter.key, self.exporter.ext,
                               fname=filename)
            if not file:
                return
            if checkInvalidFilename(os.path.basename(file), dirsep=False):
                continue
            break
        self.hide()
        if file:
            self.mw.progress.start(immediate=True)
            try:
                f = open(file, "wb")
                f.close()
            except (OSError, IOError) as e:
                showWarning(_("Couldn't save file: %s") % str(e))
            else:
                os.unlink(file)
                exportedMedia = lambda cnt: self.mw.progress.update(
                        label=ngettext("Exported %d media file",
                                       "Exported %d media files", cnt) % cnt
                        )
                addHook("exportedMediaFiles", exportedMedia)
                self.exporter.exportInto(file)
                remHook("exportedMediaFiles", exportedMedia)
                period = 3000
                if self.isVerbatim:
                    msg = _("Collection exported.")
                else:
                    if self.isTextNote:
                        msg = ngettext("%d note exported.", "%d notes exported.",
                                    self.exporter.count) % self.exporter.count
                    else:
                        msg = ngettext("%d card exported.", "%d cards exported.",
                                    self.exporter.count) % self.exporter.count
                tooltip(msg, period=period)
            finally:
                self.mw.progress.finish()
        QDialog.accept(self)
ExportDialog.accept = accept
