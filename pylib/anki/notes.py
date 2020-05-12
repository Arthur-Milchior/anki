# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

from __future__ import annotations

import pprint
from typing import Any, List, Optional, Sequence, Tuple

import anki  # pylint: disable=unused-import
from anki import hooks
from anki.models import NoteType
from anki.rsbackend import BackendNote
from anki.utils import joinFields


class Note:
    """A note is composed of:

    id -- epoch seconds of when the note was created. A unique id
    guid -- globally unique id, almost certainly used for syncing
    mid -- model id
    mod -- modification timestamp, epoch seconds
    usn -- update sequence number: see readme.synchronization for more info
    tags -- List of tags.
         -- In the database, it is a space-separated string of tags.
         -- includes space at the beginning and end, for LIKE "% tag %" queries
    fields -- the list of values of the fields in this note.
          in the db, instead of fields, there is flds; which is the content of fields, in the order of the note type, concatenated using \x1f (\\x1f))
    sfld -- sort field: used for quick sorting and duplicate check
    csum -- field checksum used for duplicate check.
         --   integer representation of first 8 digits of sha1 hash of the first field
    flags-- unused
    data -- unused

    Not in the database:
    col -- its collection
    _model -- the model object
    _fmap -- Mapping of (field name) -> (ord, field object). See models.py for field objects
    scm -- schema mod time: time when "schema" was modified. As in the collection.
    newlyAdded -- used by flush, to see whether a note is new or not.
    """

    # not currently exposed
    flags = 0
    data = ""

    def __init__(
        self,
        col: anki.collection.Collection,
        model: Optional[NoteType] = None,
        id: Optional[int] = None,
    ) -> None:
        """A note.

        Exactly one of model and id should be set. Not both.

        keyword arguments:
        id -- a note id. In this case, current note is the note with this id
        model -- A model object. In which case the note the note use this model.

        """

        assert not (model and id)
        self.col = col.weakref()
        # self.newlyAdded = False

        if id:
            # existing note
            self.id = id
            self.load()
        else:
            # new note for provided notetype
            self._load_from_backend_note(self.col.backend.new_note(model["id"]))

    def load(self) -> None:
        """Given a note knowing its collection and its id, choosing this
        card from the database."""
        n = self.col.backend.get_note(self.id)
        assert n
        self._load_from_backend_note(n)

    def _load_from_backend_note(self, n: BackendNote) -> None:
        self.id = n.id
        self.guid = n.guid
        self.mid = n.ntid
        self.mod = n.mtime_secs
        self.usn = n.usn
        self.tags = list(n.tags)
        self.fields = list(n.fields)
        self._fmap = self.col.models.fieldMap(self.model())

    def to_backend_note(self) -> BackendNote:
        hooks.note_will_flush(self)
        return BackendNote(
            id=self.id,
            guid=self.guid,
            ntid=self.mid,
            mtime_secs=self.mod,
            usn=self.usn,
            tags=self.tags,
            fields=self.fields,
        )

    def flush(self) -> None:
        """If fields or tags have changed, write changes to disk.

        If there exists a note with same id, tags and fields, and mod is not set, do nothing.
        Change the mod to given argument or current time
        Change the USNk
        If the note is not new, according to _preFlush, generate the cards
        Add its tag to the collection
        Add the note in the db

        Keyword arguments:
        mod -- A modification timestamp"""
        assert self.id != 0
        self.col.backend.update_note(self.to_backend_note())

    def __repr__(self) -> str:
        d = dict(self.__dict__)
        del d["col"]
        return f"{super().__repr__()} {pprint.pformat(d, width=300)}"

    def joinedFields(self) -> str:
        """The list of fields, separated by \x1f (\\x1f)."""
        return joinFields(self.fields)

    def cards(self) -> List[anki.cards.Card]:
        """The list of cards objects associated to this note."""
        return [
            self.col.getCard(id)
            for id in self.col.db.list(
                "select id from cards where nid = ? order by ord", self.id
            )
        ]

    def model(self) -> Optional[NoteType]:
        """The model object of this card."""
        return self.col.models.get(self.mid)

    _model = property(model)

    def cloze_numbers_in_fields(self) -> Sequence[int]:
        return self.col.backend.cloze_numbers_in_note(self.to_backend_note())

    # Dict interface
    ##################################################

    def keys(self) -> List[str]:
        """The list of field names of this note."""
        return list(self._fmap.keys())

    def values(self) -> List[str]:
        """The list of value of this note's fields."""
        return self.fields

    def items(self) -> List[Tuple[Any, Any]]:
        """The list of (name, value), for each field of the note."""
        return [
            (fldType["name"], self.fields[ord])
            for ord, fldType in sorted(self._fmap.values())
        ]

    def _fieldOrd(self, key: str) -> Any:
        """The order of the key in the note."""
        try:
            return self._fmap[key][0]
        except:
            raise KeyError(key)

    def __getitem__(self, key: str) -> str:
        """The value of the field key."""
        return self.fields[self._fieldOrd(key)]

    def __setitem__(self, key: str, value: str) -> None:
        """Set the value of the field key to value."""
        self.fields[self._fieldOrd(key)] = value

    def __contains__(self, key) -> bool:
        """Whether key is a field of this note."""
        return key in self._fmap

    # Tags
    ##################################################

    def hasTag(self, tag: str) -> Any:
        """Whether tag is a tag of this note."""
        return self.col.tags.inList(tag, self.tags)

    def stringTags(self) -> Any:
        """A string containing the tags, canonified, separated with white
        space, with an initial and a final white space."""
        return self.col.tags.join(self.col.tags.canonify(self.tags))

    def setTagsFromStr(self, tags: str) -> None:
        """Set the list of tags of this note using the str."""
        self.tags = self.col.tags.split(tags)

    def delTag(self, tag: str) -> None:
        """Remove every occurence of tag in this note's tag. Case
        insensitive."""
        rems = []
        for tag in self.tags:
            if tag.lower() == tag.lower():
                rems.append(tag)
        for rem in rems:
            self.tags.remove(rem)

    def addTag(self, tag: str) -> None:
        # duplicates will be stripped on save
        """Add tag to the list of note's tag.

        duplicates will be stripped on save.
        """
        self.tags.append(tag)

    # Unique/duplicate check
    ##################################################

    def dupeOrEmpty(self) -> int:
        "1 if first is empty; 2 if first is a duplicate, 0 otherwise."
        return self.col.backend.note_is_duplicate_or_empty(self.to_backend_note()).state
