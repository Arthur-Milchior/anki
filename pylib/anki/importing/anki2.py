# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

import os
import unicodedata
from typing import Any, Dict, List, Optional, Tuple

from anki.collection import Collection
from anki.consts import *
from anki.decks import DeckManager
from anki.importing.base import Importer
from anki.lang import _
from anki.utils import intTime, joinFields, splitFields

GUID = 1
MID = 2
MOD = 3


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
    deckPrefix: Optional[str] = None
    allowUpdate = True
    src: Collection
    dst: Collection

    def __init__(self, col: Collection, file: str) -> None:
        super().__init__(col, file)

        # set later, defined here for typechecking
        self._decks: Dict[int, int] = {}
        self.mustResetLearning = False

    def run(self, media: None = None) -> None:
        self._prepareFiles()
        if media is not None:
            # Anki1 importer has provided us with a custom media folder
            self.src.media._dir = media
        try:
            self._import()
        finally:
            self.src.close(save=False, downgrade=False)

    def _prepareFiles(self) -> None:
        importingV2 = self.file.endswith(".anki21")
        self.mustResetLearning = False

        self.dst = self.col
        self.src = Collection(self.file)

        if not importingV2 and self.col.schedVer() != 1:
            # any scheduling included?
            if self.src.db.scalar("select 1 from cards where queue != 0 limit 1"):
                self.mustResetLearning = True

    def _import(self) -> None:
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
        self.dst.optimize()

    # Notes
    ######################################################################

    def _logNoteRow(self, action: str, noteRow: List[str]) -> None:
        self.log.append("[%s] %s" % (action, noteRow[6].replace("\x1f", ", ")))

    def _importNotes(self) -> None:
        # build guid -> (id,mod,mid) hash & map of existing note ids
        self._notes: Dict[str, Tuple[int, int, int]] = {}
        existing = {}
        for id, guid, mod, mid in self.dst.db.execute(
            "select id, guid, mod, mid from notes"
        ):
            self._notes[guid] = (id, mod, mid)
            existing[id] = True
        # we may need to rewrite the guid if the model schemas don't match,
        # so we need to keep track of the changes for the card import stage
        self._changedGuids: Dict[str, bool] = {}
        # we ignore updates to changed schemas. we need to note the ignored
        # guids, so we avoid importing invalid cards
        self._ignoredGuids: Dict[str, bool] = {}
        # iterate over source collection
        add = []
        update = []
        dirty = []
        usn = self.dst.usn()
        dupesIdentical = []
        dupesIgnored = []
        total = 0
        for note in self.src.db.execute("select * from notes"):
            total += 1
            # turn the db result into a mutable list
            note = list(note)
            shouldAdd = self._uniquifyNote(note)
            if shouldAdd:
                # ensure id is unique
                while note[0] in existing:
                    note[0] += 999
                existing[note[0]] = True
                # bump usn
                note[4] = usn
                # update media references in case of dupes
                note[6] = self._mungeMedia(note[MID], note[6])
                add.append(note)
                dirty.append(note[0])
                # note we have the added the guid
                self._notes[note[GUID]] = (note[0], note[3], note[MID])
            else:
                # a duplicate or changed schema - safe to update?
                if self.allowUpdate:
                    oldNid, oldMod, oldMid = self._notes[note[GUID]]
                    # will update if incoming note more recent
                    if oldMod < note[MOD]:
                        # safe if note types identical
                        if oldMid == note[MID]:
                            # incoming note should use existing id
                            note[0] = oldNid
                            note[4] = usn
                            note[6] = self._mungeMedia(note[MID], note[6])
                            update.append(note)
                            dirty.append(note[0])
                        else:
                            dupesIgnored.append(note)
                            self._ignoredGuids[note[GUID]] = True
                    else:
                        dupesIdentical.append(note)

        self.log.append(_("Notes found in file: %d") % total)

        if dupesIgnored:
            self.log.append(
                _("Notes that could not be imported as note type has changed: %d")
                % len(dupesIgnored)
            )
        if update:
            self.log.append(
                _("Notes updated, as file had newer version: %d") % len(update)
            )
        if add:
            self.log.append(_("Notes added from file: %d") % len(add))
        if dupesIdentical:
            self.log.append(
                _("Notes skipped, as they're already in your collection: %d")
                % len(dupesIdentical)
            )

        self.log.append("")

        if dupesIgnored:
            for dupeIgnored in dupesIgnored:
                self._logNoteRow(_("Skipped"), dupeIgnored)
        if update:
            for update_ in update:
                self._logNoteRow(_("Updated"), update_)
        if add:
            for add_ in add:
                self._logNoteRow(_("Added"), add_)
        if dupesIdentical:
            for dupeIdentical in dupesIdentical:
                self._logNoteRow(_("Identical"), dupeIdentical)

        # export info for calling code
        self.dupes = len(dupesIdentical)
        self.added = len(add)
        self.updated = len(update)
        # add to col
        self.dst.db.executemany(
            "insert or replace into notes values (?,?,?,?,?,?,?,?,?,?,?)", add
        )
        self.dst.db.executemany(
            "insert or replace into notes values (?,?,?,?,?,?,?,?,?,?,?)", update
        )
        self.dst.updateFieldCache(dirty)

    # determine if note is a duplicate, and adjust mid and/or guid as required
    # returns true if note should be added
    def _uniquifyNote(self, note: List[Any]) -> bool:
        origGuid = note[GUID]
        srcMid = note[MID]
        dstMid = self._mid(srcMid)
        # duplicate schemas?
        if srcMid == dstMid:
            return origGuid not in self._notes
        # differing schemas and note doesn't exist?
        note[MID] = dstMid
        if origGuid not in self._notes:
            return True
        # schema changed; don't import
        self._ignoredGuids[origGuid] = True
        return False

    # Models
    ######################################################################
    # Models in the two decks may share an ID but not a schema, so we need to
    # compare the field & template signature rather than just rely on ID. If
    # the schemas don't match, we increment the mid and try again, creating a
    # new model if necessary.

    def _prepareModels(self) -> None:
        "Prepare index of schema hashes."
        self._modelMap: Dict[int, int] = {}

    def _mid(self, srcMid: int) -> Any:
        """Return local id for remote MID.

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
        srcScm = self.src.models.scmhash(srcModel)
        while True:
            # missing from target col?
            if not self.dst.models.have(mid):
                # copy it over
                model = srcModel.copy()
                model["id"] = mid
                model["usn"] = self.col.usn()
                self.dst.models.update(model)
                break
            # there's an existing model; do the schemas match?
            dstModel = self.dst.models.get(mid)
            dstScm = self.dst.models.scmhash(dstModel)
            if srcScm == dstScm:
                # copy styling changes over if newer
                if srcModel["mod"] > dstModel["mod"]:
                    model = srcModel.copy()
                    model["id"] = mid
                    model["usn"] = self.col.usn()
                    self.dst.models.update(model)
                break
            # as they don't match, try next id
            mid += 1
        # save map and return new mid
        self._modelMap[srcMid] = mid
        return mid

    # Decks
    ######################################################################

    def _did(self, did: int) -> Any:
        "Given did in src col, return local id."
        # already converted?
        if did in self._decks:
            return self._decks[did]
        # get the name in src
        importedDeck = self.src.decks.get(did)
        name = importedDeck["name"]
        # if there's a prefix, replace the top level deck
        if self.deckPrefix:
            tmpname = "::".join(DeckManager.path(name)[1:])
            name = self.deckPrefix
            if tmpname:
                name += "::" + tmpname
        # manually create any parents so we can pull in descriptions
        head = ""
        for parentPiece in DeckManager.immediate_parent_path(name):
            if head:
                head += "::"
            head += parentPiece
            idInSrc = self.src.decks.id(head)
            self._did(idInSrc)
        # if target is a filtered deck, we'll need a new deck name
        localDeck = self.dst.decks.byName(name)
        if localDeck and localDeck["dyn"]:
            name = "%s %d" % (name, intTime())
        # create in local
        newid = self.dst.decks.id(name)
        # pull conf over
        if "conf" in importedDeck and importedDeck["conf"] != 1:
            conf = self.src.decks.get_config(importedDeck["conf"])
            self.dst.decks.save(conf)
            self.dst.decks.update_config(conf)
            g2 = self.dst.decks.get(newid)
            g2["conf"] = importedDeck["conf"]
            self.dst.decks.save(g2)
        # save desc
        localDeck = self.dst.decks.get(newid)
        localDeck["desc"] = importedDeck["desc"]
        self.dst.decks.save(localDeck)
        # add to localDeck map and return
        self._decks[did] = newid
        return newid

    # Cards
    ######################################################################

    def _importCards(self) -> None:
        if self.mustResetLearning:
            self.src.modSchema(check=False)
            self.src.changeSchedulerVer(2)
        # build map of (guid, ord) -> cid and used id cache
        self._cards: Dict[Tuple[str, int], int] = {}
        existing = {}
        for guid, ord, cid in self.dst.db.execute(
            "select note.guid, card.ord, card.id from cards card, notes note "
            "where card.nid = note.id"
        ):
            existing[cid] = True
            self._cards[(guid, ord)] = cid
        # loop through src
        cards = []
        revlog = []
        cnt = 0
        usn = self.dst.usn()
        aheadBy = self.src.sched.today - self.dst.sched.today
        for (
            guid,
            note_mid,
            scid,
            nid,
            did,
            ord,
            old_mod,
            old_usn,
            type,
            queue,
            due,
            ivl,
            factor,
            reps,
            lapses,
            left,
            odue,
            odid,
            flags,
            data,
        ) in self.src.db.execute(
            "select note.guid, note.mid, card.* from cards card, notes note "
            "where card.nid = note.id"
        ):
            if guid in self._changedGuids:
                guid = self._changedGuids[guid]
            if guid in self._ignoredGuids:
                continue
            # does the card's note exist in dst col?
            if guid not in self._notes:
                continue
            # does the card already exist in the dst col?
            if (guid, ord) in self._cards:
                # fixme: in future, could update if newer mod time
                continue
            # doesn't exist. strip off note info, and save src id for later
            # ensure the card id is unique
            while scid in existing:
                scid += 999
            existing[scid] = True
            # update cid, nid, etc
            nid = self._notes[guid][0]
            did = self._did(did)
            mod = intTime()
            # review cards have a due date relative to collection
            if (
                queue in (QUEUE_TYPE_REV, QUEUE_TYPE_DAY_LEARN_RELEARN)
                or type == CARD_TYPE_REV
            ):
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
                if type == CARD_TYPE_LRN:  # type
                    queue = QUEUE_TYPE_NEW
                else:
                    queue = type
                # type
                if type == CARD_TYPE_LRN:
                    type = CARD_TYPE_NEW
            cards.append(
                (
                    scid,
                    nid,
                    did,
                    ord,
                    old_mod,
                    old_usn,
                    type,
                    queue,
                    due,
                    ivl,
                    factor,
                    reps,
                    lapses,
                    left,
                    odue,
                    odid,
                    flags,
                    data,
                )
            )
            # we need to import revlog, rewriting card ids and bumping usn
            for rev in self.src.db.execute("select * from revlog where cid = ?", scid):
                rev = list(rev)
                rev[1] = scid
                rev[2] = self.dst.usn()
                revlog.append(rev)
            cnt += 1
        # apply
        self.dst.db.executemany(
            """
insert or ignore into cards values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            cards,
        )
        self.dst.db.executemany(
            """
insert or ignore into revlog values (?,?,?,?,?,?,?,?,?)""",
            revlog,
        )

    # Media
    ######################################################################

    # note: this func only applies to imports of .anki2. for .apkg files, the
    # apkg importer does the copying
    def _importStaticMedia(self) -> None:
        # Import any '_foo' prefixed media files regardless of whether
        # they're used on notes or not
        dir = self.src.media.dir()
        if not os.path.exists(dir):
            return
        for fname in os.listdir(dir):
            if fname.startswith("_") and not self.dst.media.have(fname):
                self._writeDstMedia(fname, self._srcMediaData(fname))

    def _mediaData(self, fname: str, dir: Optional[str] = None) -> bytes:
        if not dir:
            dir = self.src.media.dir()
        path = os.path.join(dir, fname)
        try:
            with open(path, "rb") as file_object:
                return file_object.read()
        except (IOError, OSError):
            return b""

    def _srcMediaData(self, fname: str) -> bytes:
        "Data for FNAME in src collection."
        return self._mediaData(fname, self.src.media.dir())

    def _dstMediaData(self, fname: str) -> bytes:
        "Data for FNAME in dst collection."
        return self._mediaData(fname, self.dst.media.dir())

    def _writeDstMedia(self, fname: str, data: bytes) -> None:
        path = os.path.join(self.dst.media.dir(), unicodedata.normalize("NFC", fname))
        try:
            with open(path, "wb") as file_object:
                file_object.write(data)
        except (OSError, IOError):
            # the user likely used subdirectories
            pass

    def _mungeMedia(self, mid: int, fieldsStr: str) -> str:
        fields = splitFields(fieldsStr)

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

    def _postImport(self) -> None:
        for did in list(self._decks.values()):
            self.col.sched.maybeRandomizeDeck(did)
        # make sure new position is correct
        self.dst.conf["nextPos"] = (
            self.dst.db.scalar("select max(due)+1 from cards where type = 0") or 0
        )
        self.dst.save()
