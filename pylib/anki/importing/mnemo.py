# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

import re
import time

from anki.db import DB
from anki.importing.noteimp import ForeignCard, ForeignNote, NoteImporter
from anki.lang import _, ngettext
from anki.stdmodels import addBasicModel, addClozeModel


class MnemosyneImporter(NoteImporter):

    needMapper = False
    update = False
    allowHTML = True

    def run(self):
        db = DB(self.file)
        ver = db.scalar("select value from global_variables where key='version'")
        if not ver.startswith("Mnemosyne SQL 1") and ver not in ("2", "3"):
            self.log.append(_("File version unknown, trying import anyway."))
        # gather facts into temp objects
        curid = None
        notes = {}
        note = None
        for _id, id, k, v in db.execute(
            """
select _id, id, key, value from facts fact, data_for_fact d where
fact._id=d._fact_id"""
        ):
            if id != curid:
                if note:
                    # pylint: disable=unsubscriptable-object
                    notes[note["_id"]] = note
                note = {"_id": _id}
                curid = id
            assert note
            note[k] = v
        if note:
            notes[note["_id"]] = note
        # gather cards
        front = []
        frontback = []
        vocabulary = []
        cloze = {}
        for (
            _fact_id,
            fact_view_id,
            rawTags,
            next,
            prev,
            easiness,
            acq_reps_plus_ret_reps,
            lapses,
            card_type_id,
        ) in db.execute(
            """
select _fact_id, fact_view_id, tags, next_rep, last_rep, easiness,
acq_reps+ret_reps, lapses, card_type_id from cards"""
        ):
            # categorize note
            note = notes[_fact_id]
            if fact_view_id.endswith(".1"):
                if fact_view_id.startswith("1.") or fact_view_id.startswith("1::"):
                    front.append(note)
                elif fact_view_id.startswith("2.") or fact_view_id.startswith("2::"):
                    frontback.append(note)
                elif fact_view_id.startswith("3.") or fact_view_id.startswith("3::"):
                    vocabulary.append(note)
                elif fact_view_id.startswith("5.1"):
                    cloze[_fact_id] = note
            # check for None to fix issue where import can error out
            if rawTags is None:
                rawTags = ""
            # merge tags into note
            tags = rawTags.replace(", ", "\x1f").replace(" ", "_")
            tags = tags.replace("\x1f", " ")
            if "tags" not in note:
                note["tags"] = []
            note["tags"] += self.col.tags.split(tags)
            # if it's a new card we can go with the defaults
            if next == -1:
                continue
            # add the card
            card = ForeignCard()
            card.factor = int(easiness * 1000)
            card.reps = acq_reps_plus_ret_reps
            card.lapses = lapses
            # ivl is inferred in mnemosyne
            card.ivl = max(1, (next - prev) // 86400)
            # work out how long we've got left
            rem = int((next - time.time()) / 86400)
            card.due = self.col.sched.today + rem
            # get ord
            match = re.search(r".(\d+)$", fact_view_id)
            assert match
            ord = int(match.group(1)) - 1
            if "cards" not in note:
                note["cards"] = {}
            note["cards"][ord] = card
        self._addFronts(front)
        total = self.total
        self._addFrontBacks(frontback)
        total += self.total
        self._addVocabulary(vocabulary)
        self.total += total
        self._addCloze(cloze)
        self.total += total
        self.log.append(
            ngettext("%d note imported.", "%d notes imported.", self.total) % self.total
        )

    def fields(self):
        return self._fields

    def _mungeField(self, fld):
        # \n -> br
        fld = re.sub("\r?\n", "<br>", fld)
        # latex differences
        fld = re.sub(r"(?i)<(/?(\$|\$\$|latex))>", "[\\1]", fld)
        # audio differences
        fld = re.sub('<audio src="(.+?)">(</audio>)?', "[sound:\\1]", fld)
        return fld

    def _addFronts(self, notes, model=None, fields=("f", "b")):
        data = []
        for orig in notes:
            # create a foreign note object
            note = ForeignNote()
            note.fields = []
            for fieldType in fields:
                fld = self._mungeField(orig.get(fieldType, ""))
                note.fields.append(fld)
            note.tags = orig["tags"]
            note.cards = orig.get("cards", {})
            data.append(note)
        # add a basic model
        if not model:
            model = addBasicModel(self.col)
            model["name"] = "Mnemosyne-FrontOnly"
        mm = self.col.models
        mm.save(model)
        mm.setCurrent(model)
        self.model = model
        self._fields = len(model["flds"])
        self.initMapping()
        # import
        self.importNotes(data)

    def _addFrontBacks(self, notes):
        model = addBasicModel(self.col)
        model["name"] = "Mnemosyne-FrontBack"
        mm = self.col.models
        template = mm.newTemplate("Back")
        template["qfmt"] = "{{Back}}"
        template["afmt"] = template["qfmt"] + "\n\n<hr id=answer>\n\n{{Front}}"  # type: ignore
        mm.addTemplate(model, template)
        self._addFronts(notes, model)

    def _addVocabulary(self, notes):
        mm = self.col.models
        model = mm.new("Mnemosyne-Vocabulary")
        for fieldName in "Expression", "Pronunciation", "Meaning", "Notes":
            fm = mm.newField(fieldName)
            mm.addField(model, fm)
        template = mm.newTemplate("Recognition")
        template["qfmt"] = "{{Expression}}"
        template["afmt"] = (
            template["qfmt"]
            + """\n\n<hr id=answer>\n\n\
{{Pronunciation}}<br>\n{{Meaning}}<br>\n{{Notes}}"""  # type: ignore
        )
        mm.addTemplate(model, template)
        template = mm.newTemplate("Production")
        template["qfmt"] = "{{Meaning}}"
        template["afmt"] = (
            template["qfmt"]
            + """\n\n<hr id=answer>\n\n\
{{Expression}}<br>\n{{Pronunciation}}<br>\n{{Notes}}"""  # type: ignore
        )
        mm.addTemplate(model, template)
        mm.add(model)
        self._addFronts(notes, model, fields=("f", "p_1", "m_1", "n"))

    def _addCloze(self, notes):
        data = []
        notes = list(notes.values())
        for orig in notes:
            # create a foreign note object
            note = ForeignNote()
            note.fields = []
            fld = orig.get("text", "")
            fld = re.sub("\r?\n", "<br>", fld)
            state = 1

            def repl(match):
                # pylint: disable=cell-var-from-loop
                # replace [...] with cloze refs
                res = "{{c%d::%s}}" % (state, match.group(1))
                state += 1
                return res

            fld = re.sub(r"\[(.+?)\]", repl, fld)
            fld = self._mungeField(fld)
            note.fields.append(fld)
            note.fields.append("")  # extra
            note.tags = orig["tags"]
            note.cards = orig.get("cards", {})
            data.append(note)
        # add cloze model
        model = addClozeModel(self.col)
        model["name"] = "Mnemosyne-Cloze"
        mm = self.col.models
        mm.save(model)
        mm.setCurrent(model)
        self.model = model
        self._fields = len(model["flds"])
        self.initMapping()
        self.importNotes(data)
