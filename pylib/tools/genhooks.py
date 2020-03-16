# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""
Generate code for hook handling, and insert it into anki/hooks.py.

To add a new hook:
- update the hooks list below
- run 'make develop'
- send a pull request that includes the changes to this file and hooks.py
"""

import os
from hookslib import Hook, update_file

# Hook/filter list
######################################################################

hooks = [
    Hook(name="card_did_leech", args=["card: Card"], legacy_hook="leech"),
    Hook(name="card_odue_was_invalid"),
    Hook(name="schema_will_change", args=["proceed: bool"], return_type="bool"),
    Hook(
        name="notes_will_be_deleted",
        args=["col: anki.storage._Collection", "ids: List[int]"],
        legacy_hook="remNotes",
    ),
    Hook(
        name="deck_added",
        args=["deck: Dict[str, Any]"],
        legacy_hook="newDeck",
        legacy_no_args=True,
    ),
    Hook(name="media_files_did_export", args=["count: int"]),
    Hook(
        name="exporters_list_created",
        args=["exporters: List[Tuple[str, Any]]"],
        legacy_hook="exportersList",
    ),
    Hook(
        name="search_terms_prepared",
        args=["searches: Dict[str, Callable]"],
        legacy_hook="search",
    ),
    Hook(
        name="note_type_added",
        args=["notetype: Dict[str, Any]"],
        legacy_hook="newModel",
        legacy_no_args=True,
    ),
    Hook(name="sync_stage_did_change", args=["stage: str"], legacy_hook="sync"),
    Hook(name="sync_progress_did_change", args=["msg: str"], legacy_hook="syncMsg"),
    Hook(
        name="bg_thread_progress_callback",
        args=["proceed: bool", "progress: anki.rsbackend.Progress"],
        return_type="bool",
        doc="Warning: this is called on a background thread.",
    ),
    Hook(
        name="tag_added", args=["tag: str"], legacy_hook="newTag", legacy_no_args=True,
    ),
    Hook(
        name="field_filter",
        args=[
            "field_text: str",
            "field_name: str",
            "filter_name: str",
            "ctx: anki.template.TemplateRenderContext",
        ],
        return_type="str",
        doc="""Allows you to define custom {{filters:..}}
        
        Your add-on can check filter_name to decide whether it should modify
        field_text or not before returning it.""",
    ),
    Hook(
        name="note_will_flush",
        args=["note: Note"],
        doc="Allow to change a note before it is added/updated in the database.",
    ),
    Hook(
        name="card_will_flush",
        args=["card: Card"],
        doc="Allow to change a card before it is added/updated in the database.",
    ),
    Hook(
        name="card_did_render",
        args=[
            "output: anki.template.TemplateRenderOutput",
            "ctx: anki.template.TemplateRenderContext",
        ],
        doc="Can modify the resulting text after rendering completes.",
    ),
    Hook(
        name="schedv2_did_answer_review_card",
        args=["card: anki.cards.Card", "ease: int", "early: bool"],
    ),
    Hook(
        name="scheduler_new_limit_for_single_deck",
        args=["count: int", "deck: Dict[str, Any]"],
        return_type="int",
        doc="""Allows changing the number of new card for this deck (without
        considering descendants).""",
    ),
    Hook(
        name="scheduler_review_limit_for_single_deck",
        args=["count: int", "deck: Dict[str, Any]"],
        return_type="int",
        doc="""Allows changing the number of rev card for this deck (without
        considering descendants).""",
    ),
    # Importing
    ###################
    Hook(
        name="importer_does_it_update_note",
        args=["importing: bool", "note: List[Any]", "old_note: Tuple[int, int, int]"],
        return_type="bool",
        doc="""Decides whether a note from the collection should be updated to the
        imported deck value. It assumes that the note is present in
        both collection and imported deck.

        By default, a note is updated iff its last modification date
        is more recent in the imported deck than in the current
        collection.

        The note is the list of values taken from the collection
        database.  The old_note is an in Anki2Importer._notes.  """,
    ),
    Hook(
        name="importer_does_it_update_note_type",
        args=[
            "importing: bool",
            "srcModel: anki.models.NoteType",
            "dstModel: anki.models.NoteType",
        ],
        return_type="bool",
        doc="""Decides whether a note type should be replaced when importing a
        collection. By default, a note type is replaced iff its last
        modification date is more recent in the imported deck than in
        the current collection. It is assumed that the schemas are the
        same, otherwise update is technically impossible anyway.""",
    ),
    Hook(
        name="importer_change_update",
        args=["update: List[Any]", "importer: anki.importing.anki2.Anki2Importer"],
        doc="""Change the notes before updating them.""",
    ),
    Hook(
        name="importing_change_deck_description",
        args=["update: bool", "newid: int", "imported_deck: Dict[str, Any]"],
        return_type="bool",
        doc="""Whether to update the description of a deck.""",
    ),
]

if __name__ == "__main__":
    path = os.path.join(os.path.dirname(__file__), "..", "anki", "hooks.py")
    update_file(path, hooks)
