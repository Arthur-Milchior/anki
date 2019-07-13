# -*- coding: utf-8 -*-
# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

from anki.utils import (fieldChecksum, guid64, intTime, joinFields,
                        splitFields, stripHTMLMedia, timestampID)


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
    def __init__(self, col, model=None, id=None):
        """A note.

        Exactly one of model and id should be set. Not both.

        keyword arguments:
        id -- a note id. In this case, current note is the note with this id
        model -- A model object. In which case the note the note use this model.

        """
        assert not (model and id)
        self.col = col
        if id:
            self.id = id
            self.load()
        else:
            self.id = timestampID(col.db, "notes")
            self.guid = guid64()
            self._model = model
            self.mid = model['id']
            self.tags = []
            self.fields = [""] * len(self._model['flds'])
            self.flags = 0
            self.data = ""
            self._fmap = self.col.models.fieldMap(self._model)
            self.scm = self.col.scm

    def load(self):
        """Given a note knowing its collection and its id, choosing this
        card from the database."""
        (self.guid,
         self.mid,
         self.mod,
         self.usn,
         self.tags,
         self.fields,
         self.flags,
         self.data) = self.col.db.first("""
select guid, mid, mod, usn, tags, flds, flags, data
from notes where id = ?""", self.id)
        self.fields = splitFields(self.fields)
        self.tags = self.col.tags.split(self.tags)
        self._model = self.col.models.get(self.mid)
        self._fmap = self.col.models.fieldMap(self._model)
        self.scm = self.col.scm

    def flush(self, mod=None):
        """If fields or tags have changed, write changes to disk.

        If there exists a note with same id, tags and fields, and mod is not set, do nothing.
        Change the mod to given argument or current time
        Change the USNk
        If the note is not new, according to _preFlush, generate the cards
        Add its tag to the collection
        Add the note in the db

        Keyword arguments:
        mod -- A modification timestamp"""
        assert self.scm == self.col.scm
        self._preFlush()
        sfld = stripHTMLMedia(self.fields[self.col.models.sortIdx(self._model)])
        tags = self.stringTags()
        fields = self.joinedFields()
        if not mod and self.col.db.scalar(
            "select 1 from notes where id = ? and tags = ? and flds = ? limit 1",
            self.id, tags, fields):
            return
        csum = fieldChecksum(self.fields[0])
        self.mod = mod if mod else intTime()
        self.usn = self.col.usn()
        res = self.col.db.execute("""
insert or replace into notes values (?,?,?,?,?,?,?,?,?,?,?)""",
                            self.id, self.guid, self.mid,
                            self.mod, self.usn, tags,
                            fields, sfld, csum, self.flags,
                            self.data)
        self.col.tags.register(self.tags)
        self._postFlush()

    def joinedFields(self):
        """The list of fields, separated by \x1f (\\x1f)."""
        return joinFields(self.fields)

    def cards(self):
        """The list of cards objects associated to this note."""
        return [self.col.getCard(id) for id in self.col.db.list(
            "select id from cards where nid = ? order by ord", self.id)]

    def model(self):
        """The model object of this card."""
        return self._model

    # Dict interface
    ##################################################

    def keys(self):
        """The list of field names of this note."""
        return list(self._fmap.keys())

    def values(self):
        """The list of value of this note's fields."""
        return self.fields

    def items(self):
        """The list of (name, value), for each field of the note."""
        return [(fldType['name'], self.fields[ord])
                for ord, fldType in sorted(self._fmap.values())]

    def _fieldOrd(self, key):
        """The order of the key in the note."""
        try:
            return self._fmap[key][0]
        except:
            raise KeyError(key)

    def __getitem__(self, key):
        """The value of the field key."""
        return self.fields[self._fieldOrd(key)]

    def __setitem__(self, key, value):
        """Set the value of the field key to value."""
        self.fields[self._fieldOrd(key)] = value

    def __contains__(self, key):
        """Whether key is a field of this note."""
        return key in list(self._fmap.keys())

    # Tags
    ##################################################

    def hasTag(self, tag):
        """Whether tag is a tag of this note."""
        return self.col.tags.inList(tag, self.tags)

    def stringTags(self):
        """A string containing the tags, canonified, separated with white
space, with an initial and a final white space."""
        return self.col.tags.join(self.col.tags.canonify(self.tags))

    def setTagsFromStr(self, str):
        """Set the list of tags of this note using the str."""
        self.tags = self.col.tags.split(str)

    def delTag(self, tag):
        """Remove every occurence of tag in this note's tag. Case
        insensitive."""
        rems = []
        for tag in self.tags:
            if tag.lower() == tag.lower():
                rems.append(tag)
        for rem in rems:
            self.tags.remove(rem)

    def addTag(self, tag):
        """Add tag to the list of note's tag.

        duplicates will be stripped on save.
        """
        self.tags.append(tag)

    # Unique/duplicate check
    ##################################################

    def dupeOrEmpty(self):
        "1 if first is empty; 2 if first is a duplicate, False otherwise."
        val = self.fields[0]
        if not val.strip():
            return 1
        csum = fieldChecksum(val)
        # find any matching csums and compare
        for flds in self.col.db.list(
            "select flds from notes where csum = ? and id != ? and mid = ?",
            csum, self.id or 0, self.mid):
            if stripHTMLMedia(
                splitFields(flds)[0]) == stripHTMLMedia(self.fields[0]):
                return 2
        return False

    # Flushing cloze notes
    ##################################################

    def _preFlush(self):
        """Set newlyAdded to: whether at least one card of this note belongs
        in the db.

        """
        # have we been added yet?
        self.newlyAdded = not self.col.db.scalar(
            "select 1 from cards where nid = ? limit 1", self.id)

    def _postFlush(self):
        """Generate cards for non-empty template of this note.

        Not executed if this note is newlyAdded."""
        if not self.newlyAdded:
            rem = self.col.genCards([self.id])
            # popping up a dialog while editing is confusing; instead we can
            # document that the user should open the templates window to
            # garbage collect empty cards
            #self.col.remEmptyCards(ids)
