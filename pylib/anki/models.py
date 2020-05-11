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
        "Save changes made to provided note type."
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
        return [n.name for n in self.all_names_and_ids()]

    def ids(self) -> List[int]:
        return [n.id for n in self.all_names_and_ids()]

    # only used by importing code
    def have(self, id: int) -> bool:
        if isinstance(id, str):
            id = int(id)
        return any(True for e in self.all_names_and_ids() if e.id == id)

    # Current note type
    #############################################################

    def current(self, forDeck: bool = True) -> Any:
        "Get current model."
        model = self.get(self.col.decks.current().get("mid"))
        if not forDeck or not model:
            model = self.get(self.col.conf["curModel"])
        if model:
            return model
        return self.get(self.all_names_and_ids()[0].id)

    def setCurrent(self, model: NoteType) -> None:
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
        "Get model with NAME."
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
        self.save(model)

    def ensureNameUnique(self, model: NoteType) -> None:
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
        "Note ids for MODEL."
        if isinstance(ntid, dict):
            # legacy callers passed in note type
            ntid = ntid["id"]
        return self.col.db.list("select id from notes where mid = ?", ntid)

    def useCount(self, model: NoteType) -> Any:
        "Number of note using MODEL."
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
        "Mapping of field name -> (ord, field)."
        return dict((f["name"], (f["ord"], f)) for f in model["flds"])

    def fieldNames(self, model: NoteType) -> List[str]:
        return [f["name"] for f in model["flds"]]

    def sortIdx(self, model: NoteType) -> Any:
        return model["sortf"]

    # Adding & changing fields
    ##################################################

    def new_field(self, name: str) -> Field:
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

    def set_sort_index(self, nt: NoteType, idx: int) -> None:
        "Modifies schema."
        assert 0 <= idx < len(nt["flds"])
        nt["sortf"] = idx

    # legacy

    newField = new_field

    def addField(self, m: NoteType, field: Field) -> None:
        self.add_field(m, field)
        if m["id"]:
            self.save(m)

    def remField(self, model: NoteType, field: Field) -> None:
        self.remove_field(model, field)
        self.save(model)

    def moveField(self, model: NoteType, field: Field, idx: int) -> None:
        self.reposition_field(model, field, idx)
        self.save(model)

    def renameField(self, model: NoteType, field: Field, newName: str) -> None:
        self.rename_field(model, field, newName)
        self.save(model)

    # Adding & changing templates
    ##################################################

    def new_template(self, name: str) -> Template:
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
        "Modifies schema."
        model["tmpls"].append(template)

    def remove_template(self, model: NoteType, template: Template) -> None:
        "Modifies schema."
        assert len(model["tmpls"]) > 1
        model["tmpls"].remove(template)

    def reposition_template(
        self, model: NoteType, template: Template, idx: int
    ) -> None:
        "Modifies schema."
        oldidx = model["tmpls"].index(template)
        if oldidx == idx:
            return

        model["tmpls"].remove(template)
        model["tmpls"].insert(idx, template)

    # legacy

    newTemplate = new_template

    def addTemplate(self, model: NoteType, template: Template) -> None:
        self.add_template(model, template)
        if model["id"]:
            self.save(model)

    def remTemplate(self, model: NoteType, template: Template) -> None:
        self.remove_template(model, template)
        self.save(model)

    def moveTemplate(self, model: NoteType, template: Template, idx: int) -> None:
        self.reposition_template(model, template, idx)
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
        d = []
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
            d.append((flds, newModel["id"], intTime(), self.col.usn(), nid,))
        self.col.db.executemany(
            "update notes set flds=?,mid=?,mod=?,usn=? where id = ?", d
        )

    def _changeCards(
        self,
        nids: List[int],
        oldModel: NoteType,
        newModel: NoteType,
        map: Dict[int, Union[None, int]],
    ) -> None:
        d = []
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
                d.append((new, self.col.usn(), intTime(), cid))
            else:
                deleted.append(cid)
        self.col.db.executemany("update cards set ord=?,usn=?,mod=? where id=?", d)
        self.col.remove_cards_and_orphaned_notes(deleted)

    # Schema hash
    ##########################################################################

    def scmhash(self, model: NoteType) -> str:
        "Return a hash of the schema, to see if models are compatible."
        s = ""
        for f in model["flds"]:
            s += f["name"]
        for t in model["tmpls"]:
            s += t["name"]
        return checksum(s)

    # Cloze
    ##########################################################################

    def _availClozeOrds(
        self, model: NoteType, flds: str, allowEmpty: bool = True
    ) -> List:
        print("_availClozeOrds() is deprecated; use note.cloze_numbers_in_fields()")
        note = anki.rsbackend.BackendNote(fields=[flds])
        return list(self.col.backend.cloze_numbers_in_note(note))
