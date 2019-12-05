"""  -*- coding: utf-8 -*-
Copyright: Arthur Milchior <arthur@milchior.fr>,
Based on Damien Elmes <anki@ichi2.net>'s anki's code
License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
Add-on number 46741504
Feel free to contribute on https://github.com/Arthur-Milchior/anki-empty-first-field.
"""

import cgi
import json
import os
import re
import traceback
import unicodedata
import zipfile

import anki.importing as importing
import aqt.deckchooser
import aqt.forms
import aqt.modelchooser
from anki.consts import NEW_CARDS_RANDOM
from anki.importing.noteimp import NoteImporter
from anki.lang import _, ngettext
from anki.utils import *
from aqt.addcards import AddCards
from aqt.importing import ChangeMap
from aqt.qt import *
from aqt.utils import (askUser, getFile, getOnlyText, openHelp, showText,
                       showWarning, tooltip)


def myAddNote(self, note):
        note.model()['did'] = self.deckChooser.selectedId()
        ret = note.dupeOrEmpty()
        if ret == 1:
            tooltip(_(
                "The first field is empty."))
        if '{{cloze:' in note.model()['tmpls'][0]['qfmt']:
            if not self.mw.col.models._availClozeOrds(
                    note.model(), note.joinedFields(), False):
                if not askUser(_("You have a cloze deletion note type "
                "but have not made any cloze deletions. Proceed?")):
                    return
        cards = self.mw.col.addNote(note)
        if not cards:
            showWarning(_("""\
The input you have provided would make an empty \
question on all cards."""), help="AddItems")
            return
        self.addHistory(note)
        self.mw.requireReset()
        return note

AddCards.addNote = myAddNote


##############
#Import
##########

def mappingOk(self):
    return True
NoteImporter.mappingOk = mappingOk

def importNotes(self, notes):
        "Convert each card into a note, apply attributes and add to col."
        assert self.mappingOk()
        # note whether tags are mapped
        self._tagsMapped = False
        for f in self.mapping:
            if f == "_tags":
                self._tagsMapped = True
        # gather checks for duplicate comparison
        csums = {}
        for csum, id in self.col.db.execute(
            "select csum, id from notes where mid = ?", self.model['id']):
            if csum in csums:
                csums[csum].append(id)
            else:
                csums[csum] = [id]
        firsts = {}#mapping sending first field of added note to true
        fld0name = self.model['flds'][0]['name']
        fld0idx = self.mapping.index(fld0name) if fld0name in self.mapping else None
        self._fmap = self.col.models.fieldMap(self.model)
        self._nextID = timestampID(self.col.db, "notes")
        # loop through the notes
        updates = []
        updateLog = []
        updateLogTxt = _("First field matched: %s")
        dupeLogTxt = _("Added duplicate with first field: %s")
        new = []
        self._ids = []
        self._cards = []
        self._emptyNotes = False
        dupeCount = 0
        dupes = []#List of first field seen, present in the db, and added anyway
        for n in notes:
            for c in range(len(n.fields)):
                if not self.allowHTML:
                    n.fields[c] = cgi.escape(n.fields[c])
                n.fields[c] = n.fields[c].strip()
                if not self.allowHTML:
                    n.fields[c] = n.fields[c].replace("\n", "<br>")
                n.fields[c] = unicodedata.normalize("NFC", n.fields[c])
            n.tags = [unicodedata.normalize("NFC", t) for t in n.tags]
            ###########start test fld0
            found = False #Whether a note with a similar first field was found
            if fld0idx:#Don't test for duplicate if there is no first field
               fld0 = n.fields[fld0idx]
               csum = fieldChecksum(fld0)
               # first field must exist
               if not fld0:
                   self.log.append(_("Empty first field: %s") %
                                   " ".join(n.fields))
                   continue
               # earlier in import?
               if fld0 in firsts and self.importMode != 2:
                   # duplicates in source file; log and ignore
                   self.log.append(_("Appeared twice in file: %s") %
                                   fld0)
                   continue
               firsts[fld0] = True
               if csum in csums:
                   # csum is not a guarantee; have to check
                   for id in csums[csum]:
                       flds = self.col.db.scalar(
                           "select flds from notes where id = ?", id)
                       sflds = splitFields(flds)
                       if fld0 == sflds[0]:
                           # duplicate
                           found = True
                           if self.importMode == 0:
                               data = self.updateData(n, id, sflds)
                               if data:
                                   updates.append(data)
                                   updateLog.append(updateLogTxt % fld0)
                                   dupeCount += 1
                                   found = True
                           elif self.importMode == 1:
                               dupeCount += 1
                           elif self.importMode == 2:
                               # allow duplicates in this case
                               if fld0 not in dupes:
                                   # only show message once, no matter how many
                                   # duplicates are in the collection already
                                   updateLog.append(dupeLogTxt % fld0)
                                   dupes.append(fld0)
                               found = False
            # newly add
            if not found:
                data = self.newData(n)
                if data:
                    new.append(data)
                    # note that we've seen this note once already
                    if fld0idx:firsts[fld0] = True
        self.addNew(new)
        self.addUpdates(updates)
        # make sure to update sflds, etc
        self.col.updateFieldCache(self._ids)
        # generate cards
        if self.col.genCards(self._ids):
            self.log.insert(0, _(
                "Empty cards found. Please run Tools>Empty Cards."))
        # apply scheduling updates
        self.updateCards()
        # we randomize or order here, to ensure that siblings
        # have the same due#
        did = self.col.decks.selected()
        conf = self.col.decks.confForDid(did)
        # in order due?
        if conf['new']['order'] == NEW_CARDS_RANDOM:
            self.col.sched.randomizeCards(did)
        else:
            self.col.sched.orderCards(did)

        part1 = ngettext("%d note added", "%d notes added", len(new)) % len(new)
        part2 = ngettext("%d note updated", "%d notes updated",
                         self.updateCount) % self.updateCount
        if self.importMode == 0:
            unchanged = dupeCount - self.updateCount
        elif self.importMode == 1:
            unchanged = dupeCount
        else:
            unchanged = 0
        part3 = ngettext("%d note unchanged", "%d notes unchanged",
                         unchanged) % unchanged
        self.log.append("%s, %s, %s." % (part1, part2, part3))
        self.log.extend(updateLog)
        if self._emptyNotes:
            self.log.append(_("""\
One or more notes were not imported, because they didn't generate any cards. \
This can happen when you have empty fields or when you have not mapped the \
content in the text file to the correct fields."""))
        self.total = len(self._ids)


NoteImporter.importNotes=importNotes


def changeMapInit(self, mw, model, current):
    QDialog.__init__(self, mw, Qt.Window)
    self.mw = mw
    self.model = model
    self.frm = aqt.forms.changemap.Ui_ChangeMap()
    self.frm.setupUi(self)
    n = 0
    setCurrent = False
    for field in self.model['flds']:
        self.frm.fields.addItem(field['name'])
        if current == field['name']:
            setCurrent = True
            self.frm.fields.setCurrentRow(n)
        n += 1
    self.frm.fields.addItem(QListWidgetItem(_("Tags")))
    self.frm.fields.addItem(QListWidgetItem(_("Ignore field")))
    if not setCurrent:
        if current == "_tags":
            self.frm.fields.setCurrentRow(n)
        else:
            self.frm.fields.setCurrentRow(n+1)
    self.field = None

ChangeMap.__init__= changeMapInit
