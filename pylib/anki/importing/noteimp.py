# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

import html
from typing import Dict, List, Optional, Tuple, Union

from anki.collection import Collection
from anki.consts import NEW_CARDS_RANDOM, STARTING_FACTOR
from anki.importing.base import Importer
from anki.lang import _, ngettext
from anki.utils import (
    fieldChecksum,
    guid64,
    intTime,
    joinFields,
    splitFields,
    timestampID,
)

# Stores a list of fields, tags and deck
######################################################################


class ForeignNote:
    "An temporary object storing fields and attributes."

    def __init__(self) -> None:
        self.fields: List[str] = []
        self.tags: List[str] = []
        self.deck = None
        self.cards: Dict[int, ForeignCard] = {}  # map of ord -> card
        self.fieldsStr = ""


class ForeignCard:
    def __init__(self) -> None:
        self.due = 0
        self.ivl = 1
        self.factor = STARTING_FACTOR
        self.reps = 0
        self.lapses = 0


# Base class for CSV and similar text-based imports
######################################################################

# The mapping is list of input fields, like:
# ['Expression', 'Reading', '_tags', None]
# - None means that the input should be discarded
# - _tags maps to note tags
# If the first field of the model is not in the map, the map is invalid.

# The import mode is one of:
# UPDATE_MODE: update if first field matches existing note
# IGNORE_MODE: ignore if first field matches existing note
# ADD_MODE: import even if first field matches existing note
UPDATE_MODE = 0
IGNORE_MODE = 1
ADD_MODE = 2


class NoteImporter(Importer):
    """TODO

    keyword arguments:
    mapping -- A list of name of fields of model
    model -- to which model(note type) the note will be imported.
    _deckMap -- TODO
    importMode -- 0 if data with similar first fields than a card in the db  should be updated
                  1 if they should be ignored
                  2 if they should be added anyway
    """

    needMapper = True
    needDelimiter = False
    allowHTML = False
    importMode = UPDATE_MODE
    mapping: Optional[List[str]]
    tagModified: Optional[str]

    def __init__(self, col: Collection, file: str) -> None:
        Importer.__init__(self, col, file)
        self.model = col.models.current()
        self.mapping = None
        self.tagModified = None
        self._tagsMapped = False

    def run(self) -> None:
        "Import."
        assert self.mapping
        card = self.foreignNotes()
        self.importNotes(card)

    def fields(self) -> int:
        "The number of fields."
        # This should be overrided by concrete class, and never called directly
        return 0

    def initMapping(self) -> None:
        """Initial mapping.

        The nth element of the import is sent to nth field, if it exists
        to tag otherwise"""
        flds = [fieldType["name"] for fieldType in self.model["flds"]]
        # truncate to provided count
        flds = flds[0 : self.fields()]
        # if there's room left, add tags
        if self.fields() > len(flds):
            flds.append("_tags")
        # and if there's still room left, pad
        flds = flds + [None] * (self.fields() - len(flds))
        self.mapping = flds

    def mappingOk(self) -> bool:
        """Whether something is mapped to the first field"""
        return self.model["flds"][0]["name"] in self.mapping

    def foreignNotes(self) -> List:
        "Return a list of foreign notes for importing."
        return []

    def open(self) -> None:
        "Open file and ensure it's in the right format."
        return

    def close(self) -> None:
        "Closes the open file."
        return

    def importNotes(self, notes: List[ForeignNote]) -> None:
        "Convert each card into a note, apply attributes and add to col."
        assert self.mappingOk()
        # note whether tags are mapped
        self._tagsMapped = False
        for fact in self.mapping:
            if fact == "_tags":
                self._tagsMapped = True
        # gather checks for duplicate comparison
        csums: Dict[str, List[int]] = {}
        for csum, id in self.col.db.execute(
            "select csum, id from notes where mid = ?", self.model["id"]
        ):
            if csum in csums:
                csums[csum].append(id)
            else:
                csums[csum] = [id]
        # mapping sending first field of added note to true
        firsts: Dict[str, bool] = {}
        fld0idx = self.mapping.index(self.model["flds"][0]["name"])
        self._fmap = self.col.models.fieldMap(self.model)
        self._nextID = timestampID(self.col.db, "notes")
        # loop through the notes
        updates = []
        updateLog = []
        updateLogTxt = _("First field matched: %s")
        dupeLogTxt = _("Added duplicate with first field: %s")
        new = []
        self._ids: List[int] = []
        self._cards: List[Tuple] = []
        dupeCount = 0
        # List of first field seen, present in the db, and added anyway
        dupes: List[str] = []
        for note in notes:
            for fieldIndex in range(len(note.fields)):
                if not self.allowHTML:
                    note.fields[fieldIndex] = html.escape(
                        note.fields[fieldIndex], quote=False
                    )
                note.fields[fieldIndex] = note.fields[fieldIndex].strip()
                if not self.allowHTML:
                    note.fields[fieldIndex] = note.fields[fieldIndex].replace(
                        "\note", "<br>"
                    )
            ###########start test fld0
            fld0 = note.fields[fld0idx]
            csum = fieldChecksum(fld0)
            # first field must exist
            if not fld0:
                self.log.append(_("Empty first field: %s") % " ".join(note.fields))
                continue
            # earlier in import?
            if fld0 in firsts and self.importMode != ADD_MODE:
                # duplicates in source file; log and ignore
                self.log.append(_("Appeared twice in file: %s") % fld0)
                continue
            firsts[fld0] = True
            # already exists?
            found = False  # Whether a note with a similar first field was found
            if csum in csums:
                # csum is not a guarantee; have to check
                for id in csums[csum]:
                    flds = self.col.db.scalar("select flds from notes where id = ?", id)
                    sflds = splitFields(flds)
                    if fld0 == sflds[0]:
                        # duplicate
                        found = True
                        if self.importMode == UPDATE_MODE:
                            data = self.updateData(note, id, sflds)
                            if data:
                                updates.append(data)
                                updateLog.append(updateLogTxt % fld0)
                                dupeCount += 1
                                found = True
                        elif self.importMode == IGNORE_MODE:
                            dupeCount += 1
                        elif self.importMode == ADD_MODE:
                            # allow duplicates in this case
                            if fld0 not in dupes:
                                # only show message once, no matter how many
                                # duplicates are in the collection already
                                updateLog.append(dupeLogTxt % fld0)
                                dupes.append(fld0)
                            found = False
            # newly add
            if not found:
                data = self.newData(note)
                if data:
                    new.append(data)
                    # note that we've seen this note once already
                    firsts[fld0] = True
        self.addNew(new)
        self.addUpdates(updates)
        # generate cards + update field cache
        self.col.after_note_updates(self._ids, mark_modified=False)
        # apply scheduling updates
        self.updateCards()
        # we randomize or order here, to ensure that siblings
        # have the same due#
        did = self.col.decks.selected()
        conf = self.col.decks.confForDid(did)
        # in order due?
        if conf["new"]["order"] == NEW_CARDS_RANDOM:
            self.col.sched.randomizeCards(did)

        part1 = ngettext("%d note added", "%d notes added", len(new)) % len(new)
        part2 = (
            ngettext("%d note updated", "%d notes updated", self.updateCount)
            % self.updateCount
        )
        if self.importMode == UPDATE_MODE:
            unchanged = dupeCount - self.updateCount
        elif self.importMode == IGNORE_MODE:
            unchanged = dupeCount
        else:
            unchanged = 0
        part3 = (
            ngettext("%d note unchanged", "%d notes unchanged", unchanged) % unchanged
        )
        self.log.append("%s, %s, %s." % (part1, part2, part3))
        self.log.extend(updateLog)
        self.total = len(self._ids)

    def newData(self, note: ForeignNote) -> Optional[list]:
        id = self._nextID
        self._nextID += 1
        self._ids.append(id)
        self.processFields(note)
        # note id for card updates later
        for ord, card in list(note.cards.items()):
            self._cards.append((id, ord, card))
        return [
            id,
            guid64(),
            self.model["id"],
            intTime(),
            self.col.usn(),
            self.col.tags.join(note.tags),
            note.fieldsStr,
            "",
            "",
            0,
            "",
        ]

    def addNew(self, rows: List[List[Union[int, str]]]) -> None:
        """Adds every notes of rows into the db"""
        self.col.db.executemany(
            "insert or replace into notes values (?,?,?,?,?,?,?,?,?,?,?)", rows
        )

    def updateData(
        self, note: ForeignNote, id: int, sflds: List[str]
    ) -> Optional[list]:
        self._ids.append(id)
        self.processFields(note, sflds)
        if self._tagsMapped:
            tags = self.col.tags.join(note.tags)
            return [
                intTime(),
                self.col.usn(),
                note.fieldsStr,
                tags,
                id,
                note.fieldsStr,
                tags,
            ]
        elif self.tagModified:
            tags = self.col.db.scalar("select tags from notes where id = ?", id)
            tagList = self.col.tags.split(tags) + self.tagModified.split()
            tags = self.col.tags.join(tagList)
            return [intTime(), self.col.usn(), note.fieldsStr, tags, id, note.fieldsStr]
        else:
            return [intTime(), self.col.usn(), note.fieldsStr, id, note.fieldsStr]

    def addUpdates(self, rows: List[List[Union[int, str]]]) -> None:
        changes = self.col.db.scalar("select total_changes()")
        if self._tagsMapped:
            self.col.db.executemany(
                """
update notes set mod = ?, usn = ?, flds = ?, tags = ?
where id = ? and (flds != ? or tags != ?)""",
                rows,
            )
        elif self.tagModified:
            self.col.db.executemany(
                """
update notes set mod = ?, usn = ?, flds = ?, tags = ?
where id = ? and flds != ?""",
                rows,
            )
        else:
            self.col.db.executemany(
                """
update notes set mod = ?, usn = ?, flds = ?
where id = ? and flds != ?""",
                rows,
            )
        changes2 = self.col.db.scalar("select total_changes()")
        self.updateCount = changes2 - changes

    def processFields(
        self, note: ForeignNote, fields: Optional[List[str]] = None
    ) -> None:
        if not fields:
            fields = [""] * len(self.model["flds"])
        for card, fact in enumerate(self.mapping):
            if not fact:
                continue
            elif fact == "_tags":
                note.tags.extend(self.col.tags.split(note.fields[card]))
            else:
                sidx = self._fmap[fact][0]
                fields[sidx] = note.fields[card]
        note.fieldsStr = joinFields(fields)

    def updateCards(self) -> None:
        data = []
        for nid, ord, card in self._cards:
            data.append(
                (card.ivl, card.due, card.factor, card.reps, card.lapses, nid, ord)
            )
        # we assume any updated cards are reviews
        self.col.db.executemany(
            """
update cards set type = 2, queue = 2, ivl = ?, due = ?,
factor = ?, reps = ?, lapses = ? where nid = ? and ord = ?""",
            data,
        )
