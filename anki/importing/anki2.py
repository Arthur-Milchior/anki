# -*- coding: utf-8 -*-
# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

import os
import unicodedata

from anki import Collection
from anki.consts import *
from anki.importing.base import Importer
from anki.lang import _
from anki.models import Model
from anki.utils import intTime, joinFields, splitFields


class Anki2Importer(Importer):

    """
    _modelMap -- associating model id from source to id of model in current collection
    src -- the Collection imported
    dst -- the collection in which we import. Normally the collection loaded in the main window.
    _notes -- guid -> (id,mod,mid) acording to destination
    _changedGuids -- seems to be always empty
    _ignoredGuids -- sends to True the GUID which won't be imported.
    allowUpdate -- whether an update is
    dupes -- Number of cards which have been ignored: note with same guid is already in src or dst collection, and update allowed but imported mod time of the model of the imported note is older or equal to the mod time of the other note with same guid.
    add -- the number of cards added
    updated -- the number of card updated
    """

    needMapper = False
    deckPrefix = None
    allowUpdate = True

    def run(self, media=None):
        self._prepareFiles()
        if media is not None:
            # Anki1 importer has provided us with a custom media folder
            self.src.media._dir = media
        try:
            self._import()
        finally:
            self.src.close(save=False)

    def _prepareFiles(self):
        importingV2 = self.file.endswith(".anki21")
        if importingV2 and self.col.schedVer() == 1:
            raise Exception("V2 scheduler must be enabled to import this file.")

        self.dst = self.col
        self.src = Collection(self.file)

        if not importingV2 and self.col.schedVer() != 1:
            # if v2 scheduler enabled, can't import v1 decks that include scheduling
            if self.src.db.scalar("select 1 from cards where queue != 0 limit 1"):
                self.src.close(save=False)
                raise Exception("V2 scheduler can not import V1 decks with scheduling included.")

    def _import(self):
        self._decks = {}
        if self.deckPrefix:
            id = self.dst.decks.id(self.deckPrefix)
            self.dst.decks.select(id)
        self._prepareTS()
        self._prepareModels()
        self._importNotes()
        self._importCards()
        self._importStaticMedia()
        self._postImport()
        self.dst.db.setAutocommit(True)
        self.dst.db.execute("vacuum")
        self.dst.db.execute("analyze")
        self.dst.db.setAutocommit(False)

    # Notes
    ######################################################################

    def _logNoteRow(self, action, noteRow):
        self.log.append("[%s] %s" % (
            action,
            noteRow[6].replace("\x1f", ", ")
        ))

    def _importNotes(self):
        # build guid -> (id,mod,mid) hash & map of existing note ids
        self._notes = {}
        existing = {}
        for id, guid, mod, mid in self.dst.db.execute(
            "select id, guid, mod, mid from notes"):
            self._notes[guid] = (id, mod, mid)
            existing[id] = True
        # we may need to rewrite the guid if the model schemas don't match,
        # so we need to keep track of the changes for the card import stage
        self._changedGuids = {}
        # we ignore updates to changed schemas. we need to note the ignored
        # guids, so we avoid importing invalid cards
        self._ignoredGuids = {}
        # iterate over source collection
        add = []
        update = []
        dirty = []
        usn = self.dst.usn()
        dupesIdentical = []
        dupesIgnored = []
        total = 0
        for note in self.src.db.execute(
            "select * from notes"):
            total += 1
            # turn the db result into a mutable list
            nid, guid, mid, mod, usn_, tags, flds, sfld, csum, flags, data = note
            shouldAdd, mid = self._uniquifyNote(guid, mid)
            if shouldAdd:
                # ensure id is unique
                while nid in existing:
                    nid += 999
                existing[nid] = True
                # bump usn
                usn_ = usn
                # update media references in case of dupes
                flds = self._mungeMedia(mid, flds)
                note = nid, guid, mid, mod, usn_, tags, flds, sfld, csum, flags, data
                add.append(note)
                dirty.append(nid)
                # note we have added the guid
                self._notes[guid] = (nid, mod, mid)
            else:
                # a duplicate or changed schema - safe to update?
                if self.allowUpdate:
                    oldNid, oldMod, oldMid = self._notes[guid]
                    # will update if incoming note more recent
                    if oldMod < mod:
                        # safe if note types identical
                        if oldMid == mid:
                            # incoming note should use existing id
                            nid = oldNid
                            usn_ = usn
                            flds = self._mungeMedia(mid, flds)
                            note = nid, guid, mid, mod, usn_, tags, flds, sfld, csum, flags, data
                            update.append(note)
                            dirty.append(nid)
                        else:
                            note = nid, guid, mid, mod, usn_, tags, flds, sfld, csum, flags, data
                            dupesIgnored.append(note)
                            self._ignoredGuids[guid] = True
                    else:
                        note = nid, guid, mid, mod, usn_, tags, flds, sfld, csum, flags, data
                        dupesIdentical.append(note)

        self.log.append(_("Notes found in file: %d") % total)

        if dupesIgnored:
            self.log.append(
                _("Notes that could not be imported as note type has changed: %d") %
                len(dupesIgnored))
        if update:
            self.log.append(
                _("Notes updated, as file had newer version: %d") %
                len(update))
        if add:
            self.log.append(
                _("Notes added from file: %d") %
                len(add))
        if dupesIdentical:
            self.log.append(
                _("Notes skipped, as they're already in your collection: %d") %
                len(dupesIdentical))

        self.log.append("")

        if dupesIgnored:
            for row in dupesIgnored:
                self._logNoteRow(_("Skipped"), row)
        if update:
            for row in update:
                self._logNoteRow(_("Updated"), row)
        if add:
            for row in add:
                self._logNoteRow(_("Added"), row)
        if dupesIdentical:
            for row in dupesIdentical:
                self._logNoteRow(_("Identical"), row)

        # export info for calling code
        self.dupes = len(dupesIdentical)
        self.added = len(add)
        self.updated = len(update)
        # add to col
        self.dst.db.executemany(
            "insert or replace into notes values (?,?,?,?,?,?,?,?,?,?,?)",
            add)
        self.dst.db.executemany(
            "insert or replace into notes values (?,?,?,?,?,?,?,?,?,?,?)",
            update)
        self.dst.updateFieldCache(dirty)
        self.dst.tags.registerNotes(dirty)

    # determine if note is a duplicate, and adjust mid and/or guid as required
    # returns true if note should be added
    def _uniquifyNote(self, origGuid, srcMid):
        dstMid = self._mid(srcMid)
        # duplicate schemas?
        if srcMid == dstMid:
            return (origGuid not in self._notes, srcMid)
        # differing schemas and note doesn't exist?
        if origGuid not in self._notes:
            return True, dstMid
        # schema changed; don't import
        self._ignoredGuids[origGuid] = True
        return False, dstMid

    # Models
    ######################################################################
    # Models in the two decks may share an ID but not a schema, so we need to
    # compare the field & template signature rather than just rely on ID. If
    # the schemas don't match, we increment the mid and try again, creating a
    # new model if necessary.

    def _prepareModels(self):
        "Prepare index of schema hashes."
        self._modelMap = {}

    def _mid(self, srcMid):
        """Return local id for remote mid.

        Two models are assumed to be compatible if they have the same
        names of fields and of card type. If imported model is
        compatible with local model of the same id, then both models
        are "merged". I.e. the lastly changed model is used.

        Otherwise the model of imported note is imported in the
        collection.

        """
        # already processed this mid?
        if srcMid in self._modelMap:
            return self._modelMap[srcMid]
        mid = srcMid
        srcModel = self.src.models.get(srcMid)
        srcScm = srcModel.scmhash()
        while True:
            # missing from target col?
            if not self.dst.models.have(mid):
                # copy it over
                dstModel = Model(self.dst.models, srcModel.copy())
                dstModel.setId(mid)
                dstModel['usn'] = self.col.usn()
                self.dst.models.update(dstModel)
                break
            # there's an existing model; do the schemas match?
            dstModel = self.dst.models.get(mid)
            dstScm = dstModel.scmhash()
            if srcScm == dstScm:
                # copy styling changes over if newer
                if srcModel['mod'] > dstModel['mod']:
                    dstModel = Model(self.dst.models, srcModel.copy())
                    dstModel.setId(mid)
                    dstModel['usn'] = self.col.usn()
                    self.dst.models.update(dstModel)
                break
            # as they don't match, try next id
            mid += 1
        # save map and return new mid
        self._modelMap[srcMid] = mid
        return mid

    # Decks
    ######################################################################

    def _did(self, did):
        "Given did in src col, return local id."
        # already converted?
        if did in self._decks:
            return self._decks[did]
        # get the name in src
        importedDeck = self.src.decks.get(did)
        name = importedDeck.getName()
        # if there's a prefix, replace the top level deck
        if self.deckPrefix:
            if "::" in name:
                tmpname = name.split("::", 1)[1]
            else:
                tmpname = ""
            name = self.deckPrefix
            if tmpname:
                name += "::" + tmpname
        # manually create any parents so we can pull in descriptions
        head = ""
        for parentPiece in name.split("::")[:-1]:
            if head:
                head += "::"
            head += parentPiece
            idInSrc = self.src.decks.id(head)
            self._did(idInSrc)
        # if target is a filtered deck, we'll need a new deck name
        localDeck = self.dst.decks.byName(name)
        if localDeck and localDeck.isDyn():
            name = "%s %d" % (name, intTime())
        # create in local
        newid = self.dst.decks.id(name)
        # pull conf over
        if 'conf' in importedDeck and importedDeck['conf'] != 1:
            conf = self.src.decks.getConf(importedDeck['conf'])
            self.dst.decks.save(conf)
            self.dst.decks.updateConf(conf)
            localDeck = self.dst.decks.get(newid)
            localDeck['conf'] = importedDeck.getConfId()
            self.dst.decks.save(localDeck)
        # save desc
        localDeck = self.dst.decks.get(newid)
        localDeck['desc'] = importedDeck['desc']
        self.dst.decks.save(localDeck)
        # add to deck map and return
        self._decks[did] = newid
        return newid

    # Cards
    ######################################################################

    def _importCards(self):
        # build map of (guid, ord) -> cid and used id cache
        self._cards = {}
        existing = {}
        for guid, ord, cid in self.dst.db.execute(
            "select note.guid, card.ord, card.id from cards card, notes note "
            "where card.nid = note.id"):
            existing[cid] = True
            self._cards[(guid, ord)] = cid
        # loop through src
        cards = []
        revlog = []
        cnt = 0
        usn = self.dst.usn()
        aheadBy = self.src.sched.today - self.dst.sched.today
        for card in self.src.db.execute(
            "select note.guid, note.mid, card.* from cards card, notes note "
            "where card.nid = note.id"):
            guid, mid, cid, nid, did, ord, mod, usn_, type, queue, due, ivl, factor, reps, lapses, left, odue, odid, flags, data = card
            scid = cid
            if guid in self._changedGuids:
                guid = self._changedGuids[guid]
            if guid in self._ignoredGuids:
                continue
            # does the card's note exist in dst col?
            if guid not in self._notes:
                continue
            dnid = self._notes[guid]
            # does the card already exist in the dst col?
            if (guid, ord) in self._cards:
                # fixme: in future, could update if newer mod time
                continue
            # doesn't exist. strip off note info, and save src id for later
            # ensure the card id is unique
            while cid in existing:
                cid += 999
            existing[cid] = True
            # update cid, nid, etc
            nid = self._notes[guid][0]
            did = self._did(did)
            mod = intTime()
            # review cards have a due date relative to collection
            if queue in (CARD_DUE, CARD_FILTERED) or type == QUEUE_REV:
                due -= aheadBy
            # odue needs updating too
            if odue:
                odue -= aheadBy
            # if odid true, convert card from filtered to normal
            if odid:
                # odid
                odid = 0
                # odue
                due = odue
                odue = 0
                # queue
                if type == QUEUE_LRN: # type
                    queue = CARD_NEW
                else:
                    queue = type
                # type
                if type == QUEUE_LRN:
                    type = QUEUE_NEW
                if type == 1:
                    type = 0
            card = (cid, nid, did, ord, mod, usn, type, queue, due, ivl, factor, reps, lapses, left, odue, odid, flags, data)
            cards.append(card)
            # we need to import revlog, rewriting card ids and bumping usn
            for rid, cid_, usn_, ease, ivl, lastIvl, factor, time, type in self.src.db.execute(
                "select * from revlog where cid = ?", scid):
                rev = (rid, cid, usn, ease, ivl, lastIvl, factor, time, type)
                revlog.append(rev)
            cnt += 1
        # apply
        self.dst.db.executemany("""
insert or ignore into cards values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", cards)
        self.dst.db.executemany("""
insert or ignore into revlog values (?,?,?,?,?,?,?,?,?)""", revlog)

    # Media
    ######################################################################

    # note: this func only applies to imports of .anki2. for .apkg files, the
    # apkg importer does the copying
    def _importStaticMedia(self):
        # Import any '_foo' prefixed media files regardless of whether
        # they're used on notes or not
        dir = self.src.media.dir()
        if not os.path.exists(dir):
            return
        for fname in os.listdir(dir):
            if fname.startswith("_") and not self.dst.media.have(fname):
                self._writeDstMedia(fname, self._srcMediaData(fname))

    def _mediaData(self, fname, dir=None):
        if not dir:
            dir = self.src.media.dir()
        path = os.path.join(dir, fname)
        try:
            with open(path, "rb") as file:
                return file.read()
        except (IOError, OSError):
            return

    def _srcMediaData(self, fname):
        "Data for FNAME in src collection."
        return self._mediaData(fname, self.src.media.dir())

    def _dstMediaData(self, fname):
        "Data for FNAME in dst collection."
        return self._mediaData(fname, self.dst.media.dir())

    def _writeDstMedia(self, fname, data):
        path = os.path.join(self.dst.media.dir(),
                            unicodedata.normalize("NFC", fname))
        try:
            with open(path, "wb") as file:
                file.write(data)
        except (OSError, IOError):
            # the user likely used subdirectories
            pass

    def _mungeMedia(self, mid, fields):
        fields = splitFields(fields)
        def repl(match):
            fname = match.group("fname")
            srcData = self._srcMediaData(fname)
            dstData = self._dstMediaData(fname)
            if not srcData:
                # file was not in source, ignore
                return match.group(0)
            # if model-local file exists from a previous import, use that
            name, ext = os.path.splitext(fname)
            lname = "%s_%s%s" % (name, mid, ext)
            if self.dst.media.have(lname):
                return match.group(0).replace(fname, lname)
            # if missing or the same, pass unmodified
            elif not dstData or srcData == dstData:
                # need to copy?
                if not dstData:
                    self._writeDstMedia(fname, srcData)
                return match.group(0)
            # exists but does not match, so we need to dedupe
            self._writeDstMedia(lname, srcData)
            return match.group(0).replace(fname, lname)
        for i in range(len(fields)):
            fields[i] = self.dst.media.transformNames(fields[i], repl)
        return joinFields(fields)

    # Post-import cleanup
    ######################################################################

    def _postImport(self):
        for did in list(self._decks.values()):
            self.col.sched.maybeRandomizeDeck(did)
        # make sure new position is correct
        self.dst.conf['nextPos'] = self.dst.db.scalar(
            "select max(due)+1 from cards where type = 0") or 0
        self.dst.save()
