# -*- coding: utf-8 -*-
# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

import json
import os
import re
import shutil
import unicodedata
import zipfile

from anki import Collection
from anki.hooks import runHook
from anki.lang import _
from anki.utils import ids2str, namedtmp, splitFields, stripHTML


class Exporter:
    """An abstract class. Inherited by class actually doing some kind of export.

    count -- the number of cards to export.
    """
    includeHTML = None

    def __init__(self, col, did=None):
        #Currently, did is never set during initialisation.
        self.col = col
        self.did = did

    def doExport(self, path):
        raise Exception("not implemented")

    def exportInto(self, path):
        """Export into path.

        This is the method called from the GUI to actually export things.

        Keyword arguments:
        path -- a path of file in which to export"""
        self._escapeCount = 0# not used ANYWHERE in the code as of 25 november 2018
        file = open(path, "wb")
        self.doExport(file)
        file.close()

    def processText(self, text):
        """remove HTML if not includeHTML, add quote if required, replace tab
        by eight spaces, newline by a line, and escape quote."""

        if self.includeHTML is False:
            text = self.stripHTML(text)

        text = self.escapeText(text)

        return text

    def escapeText(self, text):
        "Escape newlines, tabs, CSS and quotechar."
        # fixme: we should probably quote fields with newlines
        # instead of converting them to spaces
        text = text.replace("\n", " ")
        text = text.replace("\t", " " * 8)
        text = re.sub("(?i)<style>.*?</style>", "", text)
        text = re.sub(r"\[\[type:[^]]+\]\]", "", text)
        if "\"" in text:
            text = "\"" + text.replace("\"", "\"\"") + "\""
        return text

    def stripHTML(self, text):
        # very basic conversion to text
        text = re.sub(r"(?i)<(br ?/?|div|p)>", " ", text)
        text = re.sub(r"\[sound:[^]]+\]", "", text)
        text = stripHTML(text)
        text = re.sub(r"[ \n\t]+", " ", text)
        text = text.strip()
        return text

    def cardIds(self):
        """card ids of cards in deck self.did if it is set, all ids otherwise."""
        if not self.did:
            cids = self.col.db.list("select id from cards")
        else:
            cids = self.col.decks.cids(self.did, children=True)
        self.count = len(cids)
        return cids

# Cards as TSV
######################################################################

class TextCardExporter(Exporter):

    key = _("Cards in Plain Text")
    ext = ".txt"
    includeHTML = True

    def __init__(self, col):
        Exporter.__init__(self, col)

    def doExport(self, file):
        ids = sorted(self.cardIds())
        strids = ids2str(ids)
        def esc(cardContent):
            # strip off the repeated question in answer if exists
            cardContent = re.sub("(?si)^.*<hr id=answer>\n*", "", cardContent)
            return self.processText(cardContent)
        out = ""
        for cid in ids:
            card = self.col.getCard(cid)
            out += esc(card.q())
            out += "\t" + esc(card.a()) + "\n"
        file.write(out.encode("utf-8"))

# Notes as TSV
######################################################################

class TextNoteExporter(Exporter):

    key = _("Notes in Plain Text")
    ext = ".txt"
    includeTags = True
    includeHTML = True

    def __init__(self, col):
        Exporter.__init__(self, col)
        self.includeID = False

    def doExport(self, file):
        cardIds = self.cardIds()
        data = []
        for id, flds, tags in self.col.db.execute("""
select guid, flds, tags from notes
where id in
(select nid from cards
where cards.id in %s)""" % ids2str(cardIds)):
            row = []
            # note id
            if self.includeID:
                row.append(str(id))
            # fields
            row.extend([self.processText(fieldContent) for fieldContent in splitFields(flds)])
            # tags
            if self.includeTags:
                row.append(tags.strip())
            data.append("\t".join(row))
        self.count = len(data)
        out = "\n".join(data)
        file.write(out.encode("utf-8"))

# Anki decks
######################################################################
# media files are stored in self.mediaFiles, but not exported.

class AnkiExporter(Exporter):

    key = _("Anki 2.0 Deck")
    ext = ".anki2"
    includeSched = False
    includeMedia = True

    def __init__(self, col):
        Exporter.__init__(self, col)

    def exportInto(self, path):
        # sched info+v2 scheduler not compatible w/ older clients
        self._v2sched = self.col.schedVer() != 1 and self.includeSched

        # create a new collection at the target
        try:
            os.unlink(path)
        except (IOError, OSError):
            pass
        self.dst = Collection(path)
        self.src = self.col
        # find cards
        cids = self.cardIds()
        # copy cards, noting used nids
        nids = {}
        data = []
        for row in self.src.db.execute(
            "select * from cards where id in "+ids2str(cids)):
            nids[row[1]] = True
            data.append(row)
            # clear flags
            row = list(row)
            row[-2] = 0
        self.dst.db.executemany(
            "insert into cards values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            data)
        # notes
        strnids = ids2str(list(nids.keys()))
        notedata = []
        for row in self.src.db.all(
            "select * from notes where id in "+strnids):
            # remove system tags if not exporting scheduling info
            if not self.includeSched:
                row = list(row)
                row[5] = self.removeSystemTags(row[5])
            notedata.append(row)
        self.dst.db.executemany(
            "insert into notes values (?,?,?,?,?,?,?,?,?,?,?)",
            notedata)
        # models used by the notes
        mids = self.dst.db.list("select distinct mid from notes where id in "+
                                strnids)
        # card history and revlog
        if self.includeSched:
            data = self.src.db.all(
                "select * from revlog where cid in "+ids2str(cids))
            self.dst.db.executemany(
                "insert into revlog values (?,?,?,?,?,?,?,?,?)",
                data)
        else:
            # need to reset card state
            self.dst.sched.resetCards(cids)
        # models - start with zero
        self.dst.models.models = {}
        for srcModel in self.src.models.all():
            if int(srcModel['id']) in mids:
                self.dst.models.update(srcModel)
        # decks
        if not self.did:
            dids = []
        else:
            dids = self.src.decks.childDids(self.did, includeSelf=True)
        dconfs = {}
        for deck in self.src.decks.all():
            if str(deck['id']) == "1":
                continue
            if dids and deck['id'] not in dids:
                continue
            if not deck['dyn'] and deck['conf'] != 1:
                if self.includeSched:
                    dconfs[deck['conf']] = True
            if not self.includeSched:
                # scheduling not included, so reset deck settings to default
                deck = dict(deck)
                deck['conf'] = 1
            self.dst.decks.update(deck)
        # copy used deck confs
        for dc in self.src.decks.allConf():
            if dc['id'] in dconfs:
                self.dst.decks.updateConf(dc)
        # find used media
        media = {}
        self.mediaDir = self.src.media.dir()
        if self.includeMedia:
            for row in notedata:
                flds = row[6]
                mid = row[2]
                for file in self.src.media.filesInStr(mid, flds):
                    # skip files in subdirs
                    if file != os.path.basename(file):
                        continue
                    media[file] = True
            if self.mediaDir:
                for fname in os.listdir(self.mediaDir):
                    path = os.path.join(self.mediaDir, fname)
                    if os.path.isdir(path):
                        continue
                    if fname.startswith("_"):
                        # Scan all models in mids for reference to fname
                        for srcModel in self.src.models.all():
                            if int(srcModel['id']) in mids:
                                if self._modelHasMedia(srcModel, fname):
                                    media[fname] = True
                                    break
        self.mediaFiles = list(media.keys())
        self.dst.crt = self.src.crt
        # todo: tags?
        self.count = self.dst.cardCount()
        self.dst.setMod()
        self.postExport()
        self.dst.close()

    def postExport(self):
        # overwrite to apply customizations to the deck before it's closed,
        # such as update the deck description
        pass

    def removeSystemTags(self, tags):
        return self.src.tags.remFromStr("marked leech", tags)

    def _modelHasMedia(self, srcModel, fname):
        # First check the styling
        if fname in srcModel["css"]:
            return True
        # If no reference to fname then check the templates as well
        for template in srcModel["tmpls"]:
            if fname in template["qfmt"] or fname in template["afmt"]:
                return True
        return False

# Packaged Anki decks
######################################################################

class AnkiPackageExporter(AnkiExporter):

    key = _("Anki Deck Package")
    ext = ".apkg"

    def __init__(self, col):
        AnkiExporter.__init__(self, col)

    def exportInto(self, path):
        # open a zip file
        zip = zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED, allowZip64=True)
        media = self.doExport(zip, path)
        # media map
        zip.writestr("media", json.dumps(media))
        zip.close()

    def doExport(self, zip, path):
        # export into the anki2 file
        colfile = path.replace(".apkg", ".anki2")
        AnkiExporter.exportInto(self, colfile)
        if not self._v2sched:
            zip.write(colfile, "collection.anki2")
        else:
            # fixme: remove in the future
            raise Exception("Please switch to the normal scheduler before exporting a single deck with scheduling information.")

            # prevent older clients from accessing
            # pylint: disable=unreachable
            self._addDummyCollection(zip)
            zip.write(colfile, "collection.anki21")

        # and media
        self.prepareMedia()
        media = self._exportMedia(zip, self.mediaFiles, self.mediaDir)
        # tidy up intermediate files
        os.unlink(colfile)
        oldPath = path.replace(".apkg", ".media.db2")
        if os.path.exists(oldPath):
            os.unlink(oldPath)
        os.chdir(self.mediaDir)
        shutil.rmtree(path.replace(".apkg", ".media"))
        return media

    def _exportMedia(self, zip, files, fdir):
        media = {}
        for index, file in enumerate(files):
            cStr = str(index)
            mpath = os.path.join(fdir, file)
            if os.path.isdir(mpath):
                continue
            if os.path.exists(mpath):
                if re.search(r'\.svg$', file, re.IGNORECASE):
                    zip.write(mpath, cStr, zipfile.ZIP_DEFLATED)
                else:
                    zip.write(mpath, cStr, zipfile.ZIP_STORED)
                media[cStr] = unicodedata.normalize("NFC", file)
                runHook("exportedMediaFiles", index)

        return media

    def prepareMedia(self):
        # chance to move each file in self.mediaFiles into place before media
        # is zipped up
        pass

    # create a dummy collection to ensure older clients don't try to read
    # data they don't understand
    def _addDummyCollection(self, zip):
        path = namedtmp("dummy.anki2")
        col = Collection(path)
        note = col.newNote()
        note[_('Front')] = "This file requires a newer version of Anki."
        col.addNote(note)
        col.save()
        col.close()

        zip.write(path, "collection.anki2")
        os.unlink(path)

# Collection package
######################################################################

class AnkiCollectionPackageExporter(AnkiPackageExporter):

    key = _("Anki Collection Package")
    ext = ".colpkg"
    verbatim = True
    includeSched = None

    def __init__(self, col):
        AnkiPackageExporter.__init__(self, col)

    def doExport(self, zip, path):
        # close our deck & write it into the zip file, and reopen
        self.count = self.col.cardCount()
        v2 = self.col.schedVer() != 1
        self.col.close()
        if not v2:
            zip.write(self.col.path, "collection.anki2")
        else:
            self._addDummyCollection(zip)
            zip.write(self.col.path, "collection.anki21")
        self.col.reopen()
        # copy all media
        if not self.includeMedia:
            return {}
        mdir = self.col.media.dir()
        return self._exportMedia(zip, os.listdir(mdir), mdir)

# Export modules
##########################################################################

def exporters():
    """A list of pairs (description of an exporter class, the class)"""
    def id(obj):
        return ("%s (*%s)" % (obj.key, obj.ext), obj)
    exps = [
        id(AnkiCollectionPackageExporter),
        id(AnkiPackageExporter),
        id(TextNoteExporter),
        id(TextCardExporter),
    ]
    runHook("exportersList", exps)
    return exps
