# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

from __future__ import annotations

import copy
import pprint
import time
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import anki  # pylint: disable=unused-import
import anki.backend_pb2 as pb
from anki.consts import *
from anki.lang import _
from anki.rsbackend import NotFoundError, StockNoteType, from_json_bytes, to_json_bytes
from anki.utils import checksum, ids2str, intTime, joinFields, splitFields

# types
NoteType = Dict[str, Any]
Field = Dict[str, Any]
Template = Dict[str, Union[str, int, None]]
"""This module deals with models, known as note type in Anki's documentation.

A model is composed of:
css -- CSS, shared for all templates of the model
did -- Long specifying the id of the deck that cards are added to by
default
flds -- JSONArray containing object for each field in the model. See flds
id -- model ID, matches notes.mid
latexPost -- String added to end of LaTeX expressions (usually \\end{document}),
latexPre -- preamble for LaTeX expressions,
mod -- modification time in milliseconds,
name -- the name of the model,
req -- Array of arrays describing which fields are required. See req
sortf -- Integer specifying which field is used for sorting in the
browser,
tags -- Anki saves the tags of the last added note to the current
model, use an empty array [],
tmpls -- The list of templates. See below
      -- In db:JSONArray containing object of CardTemplate for each card in
model.
type -- Integer specifying what type of model. 0 for standard, 1 for
cloze,
usn -- Update sequence number: used in same way as other usn vales in
db,
vers -- Legacy version number (unused), use an empty array []
changed -- Whether the Model has been changed and should be written in
the database.

A field object (flds) is an array composed of:
font -- "display font",
media -- "array of media. appears to be unused",
name -- "field name",
ord -- "ordinal of the field - goes from 0 to num fields -1",
rtl -- "boolean, right-to-left script",
size -- "font size",
sticky -- "sticky fields retain the value that was last added
when adding new notes"

req' fields are:
"the 'ord' value of the template object from the 'tmpls' array you are setting the required fields of",
'? string, "all" or "any"',
["? another array of 'ord' values from field object you
want to require from the 'flds' array"]

tmpls (a template): a dict with
afmt -- "answer template string",
bafmt -- "browser answer format:
used for displaying answer in browser",
bqfmt -- "browser question format:
used for displaying question in browser",
did -- "deck override (null by default)",
name -- "template name",
ord -- "template number, see flds",
qfmt -- "question format string"
"""


class ModelsDictProxy:
    def __init__(self, col: anki.collection.Collection):
        self._col = col.weakref()

    def _warn(self):
        print("add-on should use methods on col.models, not col.models.models dict")

    def __getitem__(self, item):
        self._warn()
        return self._col.models.get(int(item))

    def __setitem__(self, key, val):
        self._warn()
        self._col.models.save(val)

    def __len__(self):
        self._warn()
        return len(self._col.models.all_names_and_ids())

    def keys(self):
        self._warn()
        return [str(nt.id) for nt in self._col.models.all_names_and_ids()]

    def values(self):
        self._warn()
        return self._col.models.all()

    def items(self):
        self._warn()
        return [(str(nt["id"]), nt) for nt in self._col.models.all()]

    def __contains__(self, item):
        self._warn()
        self._col.models.have(item)


class ModelManager:
    """This object is usually denoted mm as a variable. Or .models in
    collection."""

    # Saving/loading registry
    #############################################################

    def __init__(self, col: anki.collection.Collection) -> None:
        self.col = col.weakref()
        self.models = ModelsDictProxy(col)
        # do not access this directly!
        self._cache = {}

    def __repr__(self) -> str:
        d = dict(self.__dict__)
        del d["col"]
        return f"{super().__repr__()} {pprint.pformat(d, width=300)}"

    def save(
        self,
        model: NoteType = None,
        # no longer used
        templates: bool = False,
        updateReqs: bool = True,
    ) -> None:
        """
        * Mark model modified if provided.
        * Schedule registry flush.
        * Calls hook newModel

        Keyword arguments:
        model -- A Model
        templates -- whether to check for cards not generated in this model
        """
        if not model:
            print("col.models.save() should be passed the changed notetype")
            return

        self.update(model, preserve_usn=False)

    # legacy
    def flush(self) -> None:
        pass

    # Caching
    #############################################################
    # A lot of existing code expects to be able to quickly and
    # frequently obtain access to an entire notetype, so we currently
    # need to cache responses from the backend. Please do not
    # access the cache directly!

    _cache: Dict[int, NoteType] = {}

    def _update_cache(self, nt: NoteType) -> None:
        self._cache[nt["id"]] = nt

    def _remove_from_cache(self, ntid: int) -> None:
        if ntid in self._cache:
            del self._cache[ntid]

    def _get_cached(self, ntid: int) -> Optional[NoteType]:
        return self._cache.get(ntid)

    def _clear_cache(self):
        self._cache = {}

    # Listing note types
    #############################################################

    def all_names_and_ids(self) -> Sequence[pb.NoteTypeNameID]:
        return self.col.backend.get_notetype_names()

    def all_use_counts(self) -> Sequence[pb.NoteTypeNameIDUseCount]:
        return self.col.backend.get_notetype_names_and_counts()

    # legacy

    def allNames(self) -> List[str]:
        "Get all model names."
        return [n.name for n in self.all_names_and_ids()]

    def ids(self) -> List[int]:
        """The list of id of models"""
        return [n.id for n in self.all_names_and_ids()]

    # only used by importing code
    def have(self, id: int) -> bool:
        """Whether there exists a model whose id is did."""
        if isinstance(id, str):
            id = int(id)
        return any(True for e in self.all_names_and_ids() if e.id == id)

    # Current note type
    #############################################################

    def current(self, forDeck: bool = True) -> Any:
        """Get current model.

        This mode is first considered using the current deck's mid, if
        forDeck is true(default).

        Otherwise, the curModel configuration value is used.

        Otherwise, the first model is used.

        Keyword arguments:
        forDeck -- Whether ther model of the deck should be considered; assuming it exists."""
        model = self.get(self.col.decks.current().get("mid"))
        if not forDeck or not model:
            model = self.get(self.col.conf["curModel"])
        if model:
            return model
        return self.get(self.all_names_and_ids()[0].id)

    def setCurrent(self, model: NoteType) -> None:
        """Change curModel value and marks the collection as modified."""
        self.col.conf["curModel"] = model["id"]
        self.col.setMod()

    # Retrieving and creating models
    #############################################################

    def id_for_name(self, name: str) -> Optional[int]:
        try:
            return self.col.backend.get_notetype_id_by_name(name)
        except NotFoundError:
            return None

    def get(self, id: int) -> Optional[NoteType]:
        "Get model with ID, or None."
        # deal with various legacy input types
        if id is None:
            return None
        elif isinstance(id, str):
            id = int(id)

        nt = self._get_cached(id)
        if not nt:
            try:
                nt = from_json_bytes(self.col.backend.get_notetype_legacy(id))
                self._update_cache(nt)
            except NotFoundError:
                return None
        return nt

    def all(self) -> List[NoteType]:
        "Get all models."
        return [self.get(nt.id) for nt in self.all_names_and_ids()]

    def byName(self, name: str) -> Optional[NoteType]:
        """Get model whose name is name.

        keyword arguments
        name -- the name of the wanted model."""
        id = self.id_for_name(name)
        if id:
            return self.get(id)
        else:
            return None

    def new(self, name: str) -> NoteType:
        "Create a new model, and return it."
        # caller should call save() after modifying
        nt = from_json_bytes(
            self.col.backend.get_stock_notetype_legacy(
                StockNoteType.STOCK_NOTE_TYPE_BASIC
            )
        )
        nt["flds"] = []
        nt["tmpls"] = []
        nt["name"] = name
        return nt

    def rem(self, model: NoteType) -> None:
        "Delete model, and all its cards/notes."
        self.remove(model["id"])

    def remove_all_notetypes(self):
        for nt in self.all_names_and_ids():
            self._remove_from_cache(nt.id)
            self.col.backend.remove_notetype(nt.id)

    def remove(self, id: int) -> None:
        "Modifies schema."
        self._remove_from_cache(id)
        self.col.backend.remove_notetype(id)

    def add(self, model: NoteType) -> None:
        """Add a new model model in the database of models"""
        self.save(model)

    def ensureNameUnique(self, model: NoteType) -> None:
        """Transform the name of model into a new name.

        If a model with this name but a distinct id exists in the
        manager, the name of this object is appended by - and by a
        5 random digits generated using the current time.
        Keyword arguments
        model -- a model object"""
        existing_id = self.id_for_name(model["name"])
        if existing_id is not None and existing_id != model["id"]:
            model["name"] += "-" + checksum(str(time.time()))[:5]

    def update(self, model: NoteType, preserve_usn=True) -> None:
        "Add or update an existing model. Use .save() instead."
        self._remove_from_cache(model["id"])
        self.ensureNameUnique(model)
        model["id"] = self.col.backend.add_or_update_notetype(
            json=to_json_bytes(model), preserve_usn_and_mtime=preserve_usn
        )
        self.setCurrent(model)
        self._mutate_after_write(model)

    def _mutate_after_write(self, nt: NoteType) -> None:
        # existing code expects the note type to be mutated to reflect
        # the changes made when adding, such as ordinal assignment :-(
        updated = self.get(nt["id"])
        nt.update(updated)

    # Tools
    ##################################################

    def nids(self, ntid: int) -> Any:
        """The ids of notes whose model is model.

        Keyword arguments
        model -- a model object."""
        if isinstance(ntid, dict):
            # legacy callers passed in note type
            ntid = ntid["id"]
        return self.col.db.list("select id from notes where mid = ?", ntid)

    def useCount(self, model: NoteType) -> Any:
        """Number of note using the model model.

        Keyword arguments
        model -- a model object."""
        return self.col.db.scalar(
            "select count() from notes where mid = ?", model["id"]
        )

    # Copying
    ##################################################

    def copy(self, model: NoteType) -> Any:
        "Copy, save and return."
        m2 = copy.deepcopy(model)
        m2["name"] = _("%s copy") % m2["name"]
        m2["id"] = 0
        self.add(m2)
        return m2

    # Fields
    ##################################################

    def fieldMap(self, model: NoteType) -> Dict[str, Tuple[int, Field]]:
        """Mapping of (field name) -> (ord, field object).

        keyword arguments:
        model : a model
        """
        return dict(
            (fieldType["name"], (fieldType["ord"], fieldType))
            for fieldType in model["flds"]
        )

    def fieldNames(self, model: NoteType) -> List[str]:
        """The list of names of fields of this model."""
        return [fieldType["name"] for fieldType in model["flds"]]

    def sortIdx(self, model: NoteType) -> Any:
        """The index of the field used for sorting."""
        return model["sortf"]

    # Adding & changing fields
    ##################################################

    def new_field(self, name: str) -> Field:
        """A new field, similar to the default one, whose name is name."""
        assert isinstance(name, str)
        nt = from_json_bytes(
            self.col.backend.get_stock_notetype_legacy(
                StockNoteType.STOCK_NOTE_TYPE_BASIC
            )
        )
        field = nt["flds"][0]
        field["name"] = name
        field["ord"] = None
        return field

    def add_field(self, model: NoteType, field: Field) -> None:
        "Modifies schema."
        model["flds"].append(field)

    def remove_field(self, model: NoteType, field: Field) -> None:
        "Modifies schema."
        model["flds"].remove(field)

    def reposition_field(self, model: NoteType, field: Field, idx: int) -> None:
        "Modifies schema."
        oldidx = model["flds"].index(field)
        if oldidx == idx:
            return

        model["flds"].remove(field)
        model["flds"].insert(idx, field)

    def rename_field(self, m: NoteType, field: Field, new_name: str) -> None:
        assert field in m["flds"]
        field["name"] = new_name

    def set_sort_index(self, nt: NoteType, newIdx: int) -> None:
        "Modifies schema."
        assert 0 <= newIdx < len(nt["flds"])
        nt["sortf"] = newIdx

    # legacy

    newField = new_field

    def addField(self, m: NoteType, field: Field) -> None:
        """Append the field field as last element of the model model.

        todo

        Keyword arguments
        model -- a model
        field -- a field object
        """
        self.add_field(m, field)
        if m["id"]:
            self.save(m)

    def remField(self, model: NoteType, field: Field) -> None:
        """Remove a field from a model.
        Also remove it from each note of this model
        Move the position of the sortfield. Update the position of each field.

        Modify the template

        model -- the model
        field -- the field object"""
        self.remove_field(model, field)
        self.save(model)

    def moveField(self, model: NoteType, field: Field, idx: int) -> None:
        """Move the field to position idx

        idx -- new position, integer
        field -- a field object
        """
        self.reposition_field(model, field, idx)
        self.save(model)

    def renameField(self, model: NoteType, field: Field, newName: str) -> None:
        """Rename the field. In each template, find the mustache related to
        this field and change them.

        model -- the model dictionnary
        field -- the field dictionnary
        newName -- either a name. Or None if the field is deleted.

        """
        self.rename_field(model, field, newName)
        self.save(model)

    # Adding & changing templates
    ##################################################

    def new_template(self, name: str) -> Template:
        """A new template, whose content is the one of
        defaultTemplate, and name is name.

        It's used in order to import mnemosyn, and create the standard
        model during anki's first initialization. It's not used in day to day anki.
        """
        nt = from_json_bytes(
            self.col.backend.get_stock_notetype_legacy(
                StockNoteType.STOCK_NOTE_TYPE_BASIC
            )
        )
        template = nt["tmpls"][0]
        template["name"] = name
        template["qfmt"] = ""
        template["afmt"] = ""
        template["ord"] = None
        return template

    def add_template(self, model: NoteType, template: Template) -> None:
        """Add a new template in model, as last element. This template is a copy
        of the input template

        Note: should col.genCards() afterwards."""
        model["tmpls"].append(template)

    def remove_template(self, model: NoteType, template: Template) -> None:
        """Remove the input template from the model model.

        Return False if removing template would leave orphan
        notes. Otherwise True
        """

        assert len(model["tmpls"]) > 1
        model["tmpls"].remove(template)

    def reposition_template(
        self, model: NoteType, template: Template, newIdx: int
    ) -> None:
        "Modifies schema."
        oldidx = model["tmpls"].index(template)
        if oldidx == newIdx:
            return

        model["tmpls"].remove(template)
        model["tmpls"].insert(newIdx, template)

    # legacy

    newTemplate = new_template

    def addTemplate(self, model: NoteType, template: Template) -> None:
        self.add_template(model, template)
        if model["id"]:
            self.save(model)

    def remTemplate(self, model: NoteType, template: Template) -> None:
        self.remove_template(model, template)
        self.save(model)

    def moveTemplate(self, model: NoteType, template: Template, newIdx: int) -> None:
        """Move input template to position idx in model.

        Move also every other template to make this consistent.

        Comment again after that TODODODO
        """
        self.reposition_template(model, template, newIdx)
        self.save(model)

    def template_use_count(self, ntid: int, ord: int) -> int:
        return self.col.db.scalar(
            """
select count() from cards, notes where cards.nid = notes.id
and notes.mid = ? and cards.ord = ?""",
            ntid,
            ord,
        )

    # Model changing
    ##########################################################################
    # - maps are ord->ord, and there should not be duplicate targets
    # - newModel should be self if model is not changing

    def change(
        self, model: NoteType, nids: List[int], newModel: NoteType, fmap: Any, cmap: Any
    ) -> None:
        """Change the model of the nodes in nids to newModel

        currently, fmap and cmap are null only for tests.

        keyword arguments
        model -- the previous model of the notes
        nids -- a list of id of notes whose model is model
        newModel -- the model to which the cards must be converted
        fmap -- the dictionnary sending to each fields'ord of the old model a field'ord of the new model
        cmap -- the dictionnary sending to each card type's ord of the old model a card type's ord of the new model
        """
        self.col.modSchema(check=True)
        assert newModel["id"] == model["id"] or (fmap and cmap)
        if fmap:
            self._changeNotes(nids, newModel, fmap)
        if cmap:
            self._changeCards(nids, model, newModel, cmap)
        self.col.after_note_updates(nids, mark_modified=True)

    def _changeNotes(
        self, nids: List[int], newModel: NoteType, map: Dict[int, Union[None, int]]
    ) -> None:
        """Change the note whose ids are nid to the model newModel, reorder
        fields according to map. Write the change in the database

        Note that if a field is mapped to nothing, it is lost

        keyword arguments:
        nids -- the list of id of notes to change
        newmodel -- the model of destination of the note
        map -- the dictionnary sending to each fields'ord of the old model a field'ord of the new model
        """
        noteData = []
        # The list of dictionnaries, containing the information relating to the new cards
        nfields = len(newModel["flds"])
        for (nid, flds) in self.col.db.execute(
            "select id, flds from notes where id in " + ids2str(nids)
        ):
            newflds = {}
            flds = splitFields(flds)
            for old, new in list(map.items()):
                newflds[new] = flds[old]
            flds = []
            for index in range(nfields):
                flds.append(newflds.get(index, ""))
            flds = joinFields(flds)
            noteData.append((flds, newModel["id"], intTime(), self.col.usn(), nid,))
        self.col.db.executemany(
            "update notes set flds=?,mid=?,mod=?,usn=? where id = ?", noteData
        )

    def _changeCards(
        self,
        nids: List[int],
        oldModel: NoteType,
        newModel: NoteType,
        map: Dict[int, Union[None, int]],
    ) -> None:
        """Change the note whose ids are nid to the model newModel, reorder
        fields according to map. Write the change in the database

        Remove the cards mapped to nothing

        If the source is a cloze, it is (currently?) mapped to the
        card of same order in newModel, independtly of map.

        keyword arguments:
        nids -- the list of id of notes to change
        oldModel -- the soruce model of the notes
        newmodel -- the model of destination of the notes
        map -- the dictionnary sending to each card 'ord of the old model a card'ord of the new model or to None
        """
        cardData = []
        deleted = []
        for (cid, ord) in self.col.db.execute(
            "select id, ord from cards where nid in " + ids2str(nids)
        ):
            # if the src model is a cloze, we ignore the map, as the gui
            # doesn't currently support mapping them
            if oldModel["type"] == MODEL_CLOZE:
                new = ord
                if newModel["type"] != MODEL_CLOZE:
                    # if we're mapping to a regular note, we need to check if
                    # the destination ord is valid
                    if len(newModel["tmpls"]) <= ord:
                        new = None
            else:
                # mapping from a regular note, so the map should be valid
                new = map[ord]
            if new is not None:
                cardData.append((new, self.col.usn(), intTime(), cid))
            else:
                deleted.append(cid)
        self.col.db.executemany(
            "update cards set ord=?,usn=?,mod=? where id=?", cardData
        )
        self.col.remove_cards_and_orphaned_notes(deleted)

    # Schema hash
    ##########################################################################

    def scmhash(self, model: NoteType) -> str:
        """Return a hash of the schema, to see if models are
        compatible. Consider only name of fields and of card type, and
        not the card type itself.

        """
        scm = ""
        for fieldType in model["flds"]:
            scm += fieldType["name"]
        for template in model["tmpls"]:
            scm += template["name"]
        return checksum(scm)

    # Cloze
    ##########################################################################

    def _availClozeOrds(
        self, model: NoteType, flds: str, allowEmpty: bool = True
    ) -> List:
        """The list of fields F which are used in some {{cloze:F}} in a template

        keyword arguments:
        model: a model
        flds: a list of fields as in the database
        allowEmpty: allows to treat a note without cloze field as a note with a cloze number 1
        """
        print("_availClozeOrds() is deprecated; use note.cloze_numbers_in_fields()")
        note = anki.rsbackend.BackendNote(fields=[flds])
        return list(self.col.backend.cloze_numbers_in_note(note))
