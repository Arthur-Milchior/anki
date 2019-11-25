# -*- coding: utf-8 -*-
# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

import copy
import datetime
import json
import os
import pprint
import random
import re
import stat
import time
import traceback

import anki.cards
import anki.find
import anki.latex  # sets up hook
import anki.notes
import anki.template
from anki.consts import *
from anki.decks import DeckManager
from anki.errors import AnkiError
from anki.hooks import runFilter, runHook
from anki.lang import _, ngettext
from anki.media import MediaManager
from anki.models import ModelManager
from anki.sound import stripSounds
from anki.tags import TagManager
from anki.utils import (devMode, fieldChecksum, ids2str, intTime, joinFields,
                        maxID, splitFields, stripHTMLMedia)

defaultConf = {
    # review options
    'activeDecks': [1],
    'curDeck': 1,
    'newSpread': NEW_CARDS_DISTRIBUTE,
    'collapseTime': 1200,
    'timeLim': 0,
    'estTimes': True,
    'dueCounts': True,
    # other config
    'curModel': None,
    'nextPos': 1,
    'sortType': "noteFld",
    'sortBackwards': False,
    'addToCur': True, # add new to currently selected deck?
    'dayLearnFirst': False,
}

# this is initialized by storage.Collection
class _Collection:
    """A collection is, basically, everything that composed an account in
    Anki.

    This object is usually denoted col

    _lastSave -- time of the last save. Initially time of creation.
    _undo -- An undo object. See below

    The collection is an object composed of:
    id -- arbitrary number since there is only one row
    crt -- timestamp of the creation date. It's correct up to the day. For V1 scheduler, the hour corresponds to starting a newday.
    mod -- last modified in milliseconds
    scm -- schema mod time: time when "schema" was modified.
        --  If server scm is different from the client scm a full-sync is required
    ver -- version
    dty -- dirty: unused, set to 0
    usn -- update sequence number: used for finding diffs when syncing.
        --   See usn in cards table for more details.
    ls -- "last sync time"
    conf -- json object containing configuration options that are synced
    """

    """
    In the db, not in col objects: json array of json objects containing the models (aka Note types)
    decks -- The deck manager
          -- in the db  it is a json array of json objects containing the deck
    dconf -- json array of json objects containing the deck options
    tags -- a cache of tags used in the collection (probably for autocomplete etc)
    """

    """
    conf -- ("conf" in the database.)
    "curDeck": "The id (as int) of the last deck selectionned (review, adding card, changing the deck of a card)",
    "activeDecks": "The list containing the current deck id and its descendent (as ints)",
    "newSpread": "In which order to view to review the cards. This can be selected in Preferences>Basic. Possible values are:
      0 -- NEW_CARDS_DISTRIBUTE (Mix new cards and reviews)
      1 -- NEW_CARDS_LAST (see new cards after review)
      2 -- NEW_CARDS_FIRST (See new card before review)",
    "collapseTime": "'Preferences>Basic>Learn ahead limit'*60.
    If there are no other card to review, then we can review cards in learning in advance if they are due in less than this number of seconds.",
    "timeLim": "'Preferences>Basic>Timebox time limit'*60. Each time this number of second elapse, anki tell you how many card you reviewed.",
    "estTimes": "'Preferences>Basic>Show next review time above answer buttons'. A Boolean."
    "dueCounts": "'Preferences>Basic>Show remaining card count during review'. A Boolean."
    "curModel": "Id (as string) of the last note type (a.k.a. model) used (i.e. either when creating a note, or changing the note type of a note).",
    "nextPos": "This is the highest value of a due value of a new card. It allows to decide the due number to give to the next note created. (This is useful to ensure that cards are seen in order in which they are added.",
    "sortType": "A string representing how the browser must be sorted. Its value should be one of the possible value of 'aqt.browsers.DataModel.activeCols' (or equivalently of 'activeCols'  but not any of ('question', 'answer', 'template', 'deck', 'note', 'noteTags')",
    "sortBackwards": "A Boolean stating whether the browser sorting must be in increasing or decreasing order",
    "addToCur": "A Boolean. True for 'When adding, default to current deck' in Preferences>Basic. False for 'Change deck depending on note type'.",
    "dayLearnFirst": "A Boolean. It corresponds to the option 'Show learning cards with larger steps before reviews'. But this option does not seems to appear in the preference box",
    "newBury": "A Boolean. Always set to true and not read anywhere in the code but at the place where it is set to True if it is not already true. Hence probably quite useful.",

    "lastUnburied":"The date of the last time the scheduler was initialized or reset. If it's not today, then buried notes must be unburied. This is not in the json until scheduler is used once.",
    "activeCols":"the list of name of columns to show in the browser. Possible values are listed in aqt.browser.Browser.setupColumns. They are:
    'question' -- the browser column'Question',
    'answer' -- the browser column'Answer',
    'template' -- the browser column'Card',
    'deck' -- the browser column'Deck',
    'noteFld' -- the browser column'Sort Field',
    'noteCrt' -- the browser column'Created',
    'noteMod' -- the browser column'Edited',
    'cardMod' -- the browser column'Changed',
    'cardDue' -- the browser column'Due',
    'cardIvl' -- the browser column'Interval',
    'cardEase' -- the browser column'Ease',
    'cardReps' -- the browser column'Reviews',
    'cardLapses' -- the browser column'Lapses',
    'noteTags' -- the browser column'Tags',
    'note' -- the browser column'Note',
    The default columns are: noteFld, template, cardDue and deck
    This is not in the json at creaton. It's added when the browser is open.
    "
    """

    """An undo object is of the form
    [type, undoName, data]
    Here, type is 1 for review, 2 for checkpoint.
    undoName is the name of the action to undo. Used in the edit menu,
    and in tooltip stating that undo was done.

    server -- Whether to pretend to be the server. Only set to true during anki.sync.Syncer.remove; i.e. while removing what the server says to remove. When set to true:
    * the usn returned by self.usn is self._usn, otherwise -1.
    * media manager does not connect nor close database connexion (I've no idea why)
    """
    def __init__(self, db, server=False, log=False):
        self._debugLog = log
        self.db = db
        self.path = db._path
        self._openLog()
        self.log(self.path, anki.version)
        self.server = server
        self._lastSave = time.time()
        self.clearUndo()
        self.media = MediaManager(self, server)
        self.models = ModelManager(self)
        self.decks = DeckManager(self)
        self.tags = TagManager(self)
        self.load()
        if not self.crt:
            dt = datetime.datetime.today()
            dt -= datetime.timedelta(hours=4)
            dt = datetime.datetime(dt.year, dt.month, dt.day)
            dt += datetime.timedelta(hours=4)
            self.crt = int(time.mktime(dt.timetuple()))
        self._loadScheduler()
        if not self.conf.get("newBury", False):
            self.conf['newBury'] = True
            self.setMod()

    def name(self):
        return os.path.splitext(os.path.basename(self.path))[0]

    # Scheduler
    ##########################################################################

    defaultSchedulerVersion = 1
    supportedSchedulerVersions = (1, 2)

    def schedVer(self):
        ver = self.conf.get("schedVer", self.defaultSchedulerVersion)
        if ver in self.supportedSchedulerVersions:
            return ver
        else:
            raise Exception("Unsupported scheduler version")

    def _loadScheduler(self):
        """Set self.sched to the chosen Scheduler"""
        ver = self.schedVer()
        if ver == 1:
            from anki.sched import Scheduler
        elif ver == 2:
            from anki.schedv2 import Scheduler

        self.sched = Scheduler(self)

    def changeSchedulerVer(self, ver):
        if ver == self.schedVer():
            return
        if ver not in self.supportedSchedulerVersions:
            raise Exception("Unsupported scheduler version")

        self.modSchema(check=True)
        self.clearUndo()

        from anki.schedv2 import Scheduler
        v2Sched = Scheduler(self)

        if ver == 1:
            v2Sched.moveToV1()
        else:
            v2Sched.moveToV2()

        self.conf['schedVer'] = ver
        self.setMod()

        self._loadScheduler()

    # DB-related
    ##########################################################################

    def load(self):
        (self.crt,
         self.mod,
         self.scm,
         self.dty, # no longer used
         self._usn,
         self.ls,
         self.conf,
         models,
         decks,
         dconf,
         tags) = self.db.first("""
select crt, mod, scm, dty, usn, ls,
conf, models, decks, dconf, tags from col""")
        self.conf = json.loads(self.conf)
        self.models.load(models)
        self.decks.load(decks, dconf)
        self.tags.load(tags)

    def setMod(self):
        """Mark DB modified.

DB operations and the deck/tag/model managers do this automatically, so this
is only necessary if you modify properties of this object or the conf dict."""
        self.db.mod = True

    def flush(self, mod=None):
        "Flush state to DB, updating mod time."
        self.mod = intTime(1000) if mod is None else mod
        self.db.execute(
            """update col set
crt=?, mod=?, scm=?, dty=?, usn=?, ls=?, conf=?""",
            self.crt, self.mod, self.scm, self.dty,
            self._usn, self.ls, json.dumps(self.conf))

    def save(self, name=None, mod=None):
        """
        Flush, commit DB, and take out another write lock.

        name --
        """
        # let the managers conditionally flush
        self.models.flush()
        self.decks.flush()
        self.tags.flush()
        # and flush deck + bump mod if db has been changed
        if self.db.mod:
            self.flush(mod=mod)
            self.db.commit()
            self.lock()
            self.db.mod = False
        self._markOp(name)
        self._lastSave = time.time()

    def autosave(self):
        "Save if 5 minutes has passed since last save. True if saved."
        if time.time() - self._lastSave > 300:
            self.save()
            return True

    def lock(self):
        """TODO. """
        mod = self.db.mod# make sure we don't accidentally bump mod time
        self.db.execute("update col set mod=mod")
        self.db.mod = mod

    def close(self, save=True):
        """Save or rollback collection's db according to save.
        Close collection's db, media's db and log.
        """
        if self.db:
            if save:
                self.save()
            else:
                self.db.rollback()
            if not self.server:
                self.db.setAutocommit(True)
                self.db.execute("pragma journal_mode = delete")
                self.db.setAutocommit(False)
            self.db.close()
            self.db = None
            self.media.close()
            self._closeLog()

    def reopen(self):
        "Reconnect to DB (after changing threads, etc)."
        import anki.db
        if not self.db:
            self.db = anki.db.DB(self.path)
            self.media.connect()
            self._openLog()

    def rollback(self):
        self.db.rollback()
        self.load()
        self.lock()

    def modSchema(self, check):
        """Mark schema modified.

        To be called before anything modifying the schema, so anki can
        check with the user if it's all right.

        Raise AnkiError("abortSchemaMod") if the change is
        rejected by the filter (e.g. if the user states to abort).

        Once the change is accepted, the filter is not run until a
        synchronization occurs.

        Change the scm value

        check -- whether to ask user whether they want it.

        """
        if not self.schemaChanged():
            if check and not runFilter("modSchema", True):
                #default hook is added in aqt/main setupHooks. It is function onSchemaMod from class AnkiQt aqt/main
                raise AnkiError("abortSchemaMod")
        self.scm = intTime(1000)
        self.setMod()

    def schemaChanged(self):
        "True if schema changed since last sync."
        return self.scm > self.ls

    def usn(self):
        """Return the synchronization number to use. Usually, -1, since
        no actions are synchronized. The exception being actions
        requested by synchronization itself, when self.server is
        true. In which case _usn number.

        """
        return self._usn if self.server else -1

    def beforeUpload(self):
        """Called before a full upload.

        * change usn -1 to 0 in notes, card and revlog, and all models, tags, decks, deck options.
        * empty graves.
        * Update usn
        * set modSchema to true (no nead for new upload)
        * update last sync time to current schema
        * Save or rollback collection's db according to save.
        * Close collection's db, media's db and log.
        """
        tbls = "notes", "cards", "revlog"
        for table in tbls:
            self.db.execute("update %s set usn=0 where usn=-1" % table)
        # we can save space by removing the log of deletions
        self.db.execute("delete from graves")
        self._usn += 1
        self.models.beforeUpload()
        self.tags.beforeUpload()
        self.decks.beforeUpload()
        self.modSchema(check=False)
        self.ls = self.scm
        # ensure db is compacted before upload
        self.db.setAutocommit(True)
        self.db.execute("vacuum")
        self.db.execute("analyze")
        self.close()

    # Object creation helpers
    ##########################################################################

    def getCard(self, id):
        """The card object whose id is id."""
        return anki.cards.Card(self, id)

    def getNote(self, id):
        """The note object whose id is id."""
        return anki.notes.Note(self, id=id)

    # Utils
    ##########################################################################

    def nextID(self, type, inc=True):
        """Get the id next{Type} in the collection's configuration. Increment this id.

        Use 1 instead if this id does not exists in the collection."""
        type = "next"+type.capitalize()
        id = self.conf.get(type, 1)
        if inc:
            self.conf[type] = id+1
        return id

    def reset(self):
        """See sched's reset documentation"""
        self.sched.reset()

    # Deletion logging
    ##########################################################################

    def _logRem(self, ids, type):
        self.db.executemany("insert into graves values (%d, ?, %d)" % (
            self.usn(), type), ([id] for id in ids))

    # Notes
    ##########################################################################

    def noteCount(self):
        return self.db.scalar("select count() from notes")

    def newNote(self, forDeck=True):
        "Return a new note with the current model."
        return anki.notes.Note(self, self.models.current(forDeck))

    def addNote(self, note):
        """Add a note to the collection unless it generates no card. Return
        number of new cards."""
        # check we have card models available, then save
        cms = self.findTemplates(note)
        if not cms:
            return 0
        note.flush()
        # deck conf governs which of these are used
        due = self.nextID("pos")
        # add cards
        ncards = 0
        for template in cms:
            self._newCard(note, template, due)
            ncards += 1
        return ncards

    def remNotes(self, ids):
        """Removes all cards associated to the notes whose id is in ids"""
        self.remCards(self.db.list("select id from cards where nid in "+
                                   ids2str(ids)))

    def _remNotes(self, ids):
        "Bulk delete notes by ID. Don't call this directly."
        if not ids:
            return
        strids = ids2str(ids)
        # we need to log these independently of cards, as one side may have
        # more card templates
        runHook("remNotes", self, ids)
        self._logRem(ids, REM_NOTE)
        self.db.execute("delete from notes where id in %s" % strids)

    # Card creation
    ##########################################################################

    def findTemplates(self, note):
        "Return templates generating contents from this note."
        model = note.model()
        avail = model.availOrds(joinFields(note.fields))
        return self._tmplsFromOrds(model, avail)

    def _tmplsFromOrds(self, model, avail):
        """Given a list of ordinals, returns a list of templates
        corresponding to those position/cloze"""
        ok = []
        if model['type'] == MODEL_STD:
            for template in model['tmpls']:
                if template['ord'] in avail:
                    ok.append(template)
        else:
            # cloze - generate temporary templates from first
            for ord in avail:
                template = copy.copy(model['tmpls'][0])
                template['ord'] = ord
                ok.append(template)
        return ok

    def genCards(self, nids):
        """Ids of cards which needs to be removed.

        Generate missing cards of a note with id in nids.
        """
        # build map of (nid,ord) so we don't create dupes
        snids = ids2str(nids)
        have = {}#Associated to each nid a dictionnary from card's order to card id.
        dids = {}#Associate to each nid the only deck id containing its cards. Or None if there are multiple decks
        dues = {}#Associate to each nid the due value of the last card seen.
        for id, nid, ord, did, due, odue, odid, type in self.db.execute(
            "select id, nid, ord, did, due, odue, odid, type from cards where nid in "+snids):
            # existing cards
            if nid not in have:
                have[nid] = {}
            have[nid][ord] = id
            # if in a filtered deck, add new cards to original deck
            if odid != 0:
                did = odid
            # and their dids
            if nid in dids:
                if dids[nid] and dids[nid] != did:
                    # cards are in two or more different decks; revert to
                    # model default
                    dids[nid] = None
            else:
                # first card or multiple cards in same deck
                dids[nid] = did
            # save due
            if odid != 0:
                due = odue
            if nid not in dues and type == 0:
                # Add due to new card only if it's the due of a new sibling
                dues[nid] = due
        # build cards for each note
        data = []#Tuples for cards to create. Each tuple is newCid, nid, did, ord, now, usn, due
        ts = maxID(self.db)
        now = intTime()
        rem = []#cards to remove
        usn = self.usn()
        for nid, mid, flds in self.db.execute(
            "select id, mid, flds from notes where id in "+snids):
            model = self.models.get(mid)
            avail = model.availOrds(flds)
            did = dids.get(nid) or model['did']
            due = dues.get(nid)
            # add any missing cards
            for template in self._tmplsFromOrds(model, avail):
                doHave = nid in have and template['ord'] in have[nid]
                if not doHave:
                    # check deck is not a cram deck
                    did = template['did'] or did
                    if self.decks.isDyn(did):
                        did = 1
                    # if the deck doesn'template exist, use default instead
                    did = self.decks.get(did).getId()
                    # use sibling due# if there is one, else use a new id
                    if due is None:
                        due = self.nextID("pos")
                    data.append((ts, nid, did, template['ord'],
                                 now, usn, due))
                    ts += 1
            # note any cards that need removing
            if nid in have:
                for ord, id in list(have[nid].items()):
                    if ord not in avail:
                        rem.append(id)
        # bulk update
        self.db.executemany("""
insert into cards values (?,?,?,?,?,?,0,0,?,0,0,0,0,0,0,0,0,"")""",
                            data)
        return rem

    def previewCards(self, note, type=0, did=None):
        """Returns a list of new cards, one by template. Those cards are not flushed, and their due is always 1.

        type 0 - when previewing in add dialog, only non-empty. Seems to be used only in tests.
        type 1 - when previewing edit, only existing. Seems to be used only in tests.
        type 2 - when previewing in models dialog (i.e. note type modifier), return the list of cards for every single template of the model.
        """
        #cms is the list of templates to consider
        if type == 0:
            cms = self.findTemplates(note)
        elif type == 1:
            cms = [card.template() for card in note.cards()]
        else:
            cms = note.model()['tmpls']
        if not cms:
            return []
        cards = []
        for template in cms:
            cards.append(self._newCard(note, template, 1, flush=False, did=did))
        return cards

    def _newCard(self, note, template, due, flush=True, did=None):
        """A new card object belonging to this collection.
        Its nid according to note,
        ord according to template
        did according to template, or to model, or default if otherwise deck is dynamic
        Cards is flushed or not according to flush parameter

        keyword arguments:
        note -- the note of this card
        template -- the template of this card
        due -- The due time of this card, assuming no random
        flush -- whether this card should be push in the db
        """
        card = anki.cards.Card(self)
        card.nid = note.id
        card.ord = template['ord']
        card.did = self.db.scalar("select did from cards where nid = ? and ord = ?", card.nid, card.ord)
        # Use template did (deck override) if valid, otherwise did in argument, otherwise model did
        if not card.did:
            if template['did'] and str(template['did']) in self.decks.decks:
                card.did = template['did']
            elif did:
                card.did = did
            else:
                card.did = note.model()['did']
        # if invalid did, use default instead
        deck = self.decks.get(card.did)
        if deck['dyn']:
            # must not be a filtered deck
            card.did = 1
        else:
            card.did = deck.getId()
        card.due = self._dueForDid(card.did, due)
        if flush:
            card.flush()
        return card

    def _dueForDid(self, did, due):
        """The due date of a card. Itself if not random mode. A random number
        depending only on the due date otherwise.

        keyword arguments
        did -- the deck id of the considered card
        due -- the due time of the considered card

        """
        conf = self.decks.confForDid(did)
        # in order due?
        if conf['new']['order'] == NEW_CARDS_DUE:
            return due
        else:
            # random mode; seed with note ts so all cards of this note get the
            # same random number
            rand = random.Random()
            rand.seed(due)
            return rand.randrange(1, max(due, 1000))

    # Cards
    ##########################################################################

    def isEmpty(self):
        """Is there no cards in this collection."""
        return not self.db.scalar("select 1 from cards limit 1")

    def cardCount(self):
        return self.db.scalar("select count() from cards")

    def remCards(self, ids, notes=True):
        """Bulk delete cards by ID.

        keyword arguments:
        notes -- whether note without cards should be deleted."""
        if not ids:
            return
        sids = ids2str(ids)
        nids = self.db.list("select nid from cards where id in "+sids)
        # remove cards
        self._logRem(ids, REM_CARD)
        self.db.execute("delete from cards where id in "+sids)
        # then notes
        if not notes:
            return
        nids = self.db.list("""
select id from notes where id in %s and id not in (select nid from cards)""" %
                     ids2str(nids))
        self._remNotes(nids)

    def emptyCids(self):
        """The card id of empty cards of the collection"""
        rem = []
        for model in self.models.all():
            rem += self.genCards(model.nids())
        return rem

    def emptyCardReport(self, cids):
        rep = ""
        for ords, cnt, flds in self.db.all("""
select group_concat(ord+1), count(), flds from cards card, notes note
where card.nid = note.id and card.id in %s group by nid""" % ids2str(cids)):
            rep += _("Empty card numbers: %(card)s\nFields: %(fieldsContent)s\n\n") % dict(
                card=ords, fieldsContent=flds.replace("\x1f", " / "))
        return rep

    # Field checksums and sorting fields
    ##########################################################################

    def _fieldData(self, snids):
        return self.db.execute(
            "select id, mid, flds from notes where id in "+snids)

    def updateFieldCache(self, nids):
        "Update field checksums and sort cache, after find&replace, changing model, etc."
        snids = ids2str(nids)
        notesUpdates = []
        for (nid, mid, flds) in self._fieldData(snids):
            fields = splitFields(flds)
            model = self.models.get(mid)
            if not model:
                # note points to invalid model
                continue
            notesUpdates.append((stripHTMLMedia(fields[self.models.sortIdx(model)]),
                      fieldChecksum(fields[0]),
                      nid))
        # apply, relying on calling code to bump usn+mod
        self.db.executemany("update notes set sfld=?, csum=? where id=?", notesUpdates)

    # Q/A generation
    ##########################################################################

    def renderQA(self, ids=None, type="card"):
        # gather metadata
        """TODO

        The list of renderQA for each cards whose type belongs to ids.

        Types may be card(default), note, model or all (in this case, ids is not used).
        It seems to be called nowhere
        """
        if type == "card":
            where = "and card.id in " + ids2str(ids)
        elif type == "note":
            where = "and note.id in " + ids2str(ids)
        elif type == "model":
            where = "and model.id in " + ids2str(ids)
        elif type == "all":
            where = ""
        else:
            raise Exception()
        return [self._renderQA(row)
                for row in self._qaData(where)]

    def _renderQA(self, data, qfmt=None, afmt=None):
        """Returns hash of id, question, answer.
        Keyword arguments:
        data -- [cid, nid, mid, did, ord, tags, flds] (see db
        documentation for more information about those values)
        This corresponds to the information you can obtain in templates, using {{Tags}}, {{Type}}, etc..
        qfmt -- question format string (as in template)
        afmt -- answer format string (as in template)
        Return a dictionnary associating the question, the answer and the card id
        """
        cid, nid, mid, did, ord, tags, flds, cardFlags = data
        # data is [cid, nid, mid, did, ord, tags, flds, cardFlags]
        # unpack fields and create dict

        model = self.models.get(mid)
        if model['type'] == MODEL_STD:
            template = model['tmpls'][ord]
        else:
            template = model['tmpls'][0]
        fields = self._extendedFields(flds, tags, ord, cardFlags, model, template, did)
        # render q & a
        d = dict()
        d['id'] = cid
        d['q'] = self._renderQuestion(data, fields, flds, ord, template, model, qfmt)
        d['a'] = self._renderAnswer(data, fields, ord, template, model, afmt)
        return d

    def _basicFields(self, flds, model):
        """A dict associating:
        for each field name it's content
        """
        fields = {}
        flist = splitFields(flds)#the list of fields
        for (name, (idx, conf)) in list(model.fieldMap().items()):#conf is not used
            fields[name] = flist[idx]
        return fields

    def _extendedFields(self, flds, tags, ord, cardFlags, model, template, did):
        """A dict associating:
        for each field name it's content
        Type: the name of the model,
        Deck, Subdeck: their name
        Card: the template name
        cn: 1 for n being the ord+1
        it'll be extended by renderQuestion to add FrontSide to it"""
        fields = self._basicFields(flds, model)
        fields['Tags'] = tags.strip()
        fields['Type'] = model.getName()
        fields['Deck'] = self.decks.name(did)
        fields['Subdeck'] = self.decks._basename(fields['Deck'])
        fields['CardFlag'] = self._flagNameFromCardFlags(cardFlags)
        fields['Card'] = template.getName()
        fields['c%d' % (ord+1)] = "1"
        return fields

    def _renderQuestion(self, data, fields, flds, ord, template, model, qfmt=None):
        """The question for this template, given those fields."""
        format = qfmt or template['qfmt']
        #Replace {{'foo'cloze: by {{'foo'cq-(ord+1), where 'foo' does not begins with "type:"
        format = re.sub("{{(?!type:)(.*?)cloze:", r"{{\1cq-%d:" % (ord+1), format)
        #Replace <%cloze: by <%%cq:(ord+1)
        format = format.replace("<%cloze:", "<%%cq:%d:" % (ord+1))
        question = self.__renderQA(fields, model, data, format, "q")
        fields['FrontSide'] = stripSounds(question)
        # empty cloze?
        if model['type'] == MODEL_CLOZE and not model._availClozeOrds(flds, False):
             question += ("<p>" + _(
                "Please edit this note and add some cloze deletions. (%s)") % (
                    "<a href=%s#cloze>%s</a>" % (HELP_SITE, _("help"))))
        return question

    def _renderAnswer(self, data, fields, ord, template, model, afmt=None):
        """The answer for this template, given those fields."""
        format = afmt or template['afmt']
        #Replace {{'foo'cloze: by {{'foo'ca-(ord+1)
        format = re.sub("{{(.*?)cloze:", r"{{\1ca-%d:" % (ord+1), format)
        #Replace <%cloze: by <%%ca:(ord+1)
        format = format.replace("<%cloze:", "<%%ca:%d:" % (ord+1))
        return self.__renderQA(fields, model, data, format, "a")

    def __renderQA(self, fields, model, data, format, type):
        """apply fields to format. Use munge hooks before and after"""
        fields = runFilter("mungeFields", fields, model, data, self)
        html = anki.template.render(format, fields)
        return runFilter(
            "mungeQA", html, type, fields, model, data, self)

    def _qaData(self, where=""):
        """The list of [cid, nid, mid, did, ord, tags, flds, cardFlags] for each pair cards satisfying where.

        Where should start with an and."""
        return self.db.execute("""
select card.id, note.id, note.mid, card.did, card.ord, note.tags, note.flds, card.flags
from cards card, notes note
where card.nid == note.id
%s""" % where)

    def _flagNameFromCardFlags(self, flags):
        flag = flags & 0b111
        if not flag:
            return ""
        return "flag%d" % flag

    # Finding cards
    ##########################################################################

    def findCards(self, *args, **kwargs):
        "Return a list of cards satisfying query, sorted by order. See finder.FindCards for more details."
        return anki.find.Finder(self).findCards(*args, **kwargs)

    def findNotesWithOneCard(self, *args, **kwargs):
        return anki.find.Finder(self).findNotesWithOneCard(*args, **kwargs)

    def findNotes(self, *args, **kwargs):
        "Return a list of notes ids for QUERY. See finder.findNotes for more details"
        return anki.find.Finder(self).findNotes(*args, **kwargs)

    def findReplace(self, *args, **kwargs):
        """Pairs (cid, nid), with nid unique satisfing this query."""
        return anki.find.findReplace(self, *args, **kwargs)

    def findDupes(self, *args, **kwargs):
        return anki.find.findDupes(self, *args, **kwargs)

    # Stats
    ##########################################################################

    def cardStats(self, card):
        from anki.stats import CardStats
        return CardStats(self, card).report()

    def stats(self):
        from anki.stats import CollectionStats
        return CollectionStats(self)

    # Timeboxing
    ##########################################################################

    def startTimebox(self):
        self._startTime = time.time()
        self._startReps = self.sched.reps

    def timeboxReached(self):
        "Return (elapsedTime, reps) if timebox reached, or False."
        if not self.conf['timeLim']:
            # timeboxing disabled
            return False
        elapsed = time.time() - self._startTime
        if elapsed > self.conf['timeLim']:
            return (self.conf['timeLim'], self.sched.reps - self._startReps)

    # Undo
    ##########################################################################
    # [type, undoName, data]
    # type 1 = review; type 2 = checkpoint

    def clearUndo(self):
        """Erase all undo information from the collection."""
        self._undo = None

    def undoName(self):
        """The name of the action which could potentially be undone.

        None if nothing can be undone. This let test whether something
        can be undone.
        """
        if not self._undo:
            return None
        return self._undo[1]

    def undo(self):
        """Undo the last operation.

        Assuming an undo object exists."""
        if self._undo[0] == 1:
            return self._undoReview()
        else:
            self._undoOp()

    def markReview(self, card):
        old = []
        if self._undo:
            if self._undo[0] == 1:
                old = self._undo[2]
            self.clearUndo()
        wasLeech = card.note().hasTag("leech") or False#The or is probably useless.
        self._undo = [1, _("Review"), old + [copy.copy(card)], wasLeech]

    def _undoReview(self):
        data = self._undo[2]
        wasLeech = self._undo[3]
        card = data.pop()
        if not data:
            self.clearUndo()
        # remove leech tag if it didn't have it before
        if not wasLeech and card.note().hasTag("leech"):
            card.note().delTag("leech")
            card.note().flush()
        # write old data
        card.flush()
        # and delete revlog entry
        last = self.db.scalar(
            "select id from revlog where cid = ? "
            "order by id desc limit 1", card.id)
        self.db.execute("delete from revlog where id = ?", last)
        # restore any siblings
        self.db.execute(
            "update cards set queue=type,mod=?,usn=? where queue=-2 and nid=?",
            intTime(), self.usn(), card.nid)
        # and finally, update daily counts
        index = 1 if card.queue == 3 else card.queue
        type = ("new", "lrn", "rev")[index]
        self.sched._updateStats(card, type, -1)
        self.sched.reps -= 1
        return card.id

    def _markOp(self, name):
        "Call via .save()"
        if name:
            self._undo = [2, name]
        else:
            # saving disables old checkpoint, but not review undo
            if self._undo and self._undo[0] == 2:
                self.clearUndo()

    def _undoOp(self):
        self.rollback()
        self.clearUndo()

    # DB maintenance
    ##########################################################################

    def basicCheck(self):
        """True if basic integrity is meet.

        Used before and after sync, or before a full upload.

        Tests:
        * whether each card belong to a note
        * each note has a model
        * each note has a card
        * each card's ord is valid according to the note model.
        """
        # cards without notes
        if self.db.scalar("""
select 1 from cards where nid not in (select id from notes) limit 1"""):
            return
        # notes without cards or models
        if self.db.scalar("""
select 1 from notes where id not in (select distinct nid from cards)
or mid not in %s limit 1""" % ids2str(self.models.ids())):
            return
        # invalid ords
        for model in self.models.all():
            # ignore clozes
            if model['type'] != MODEL_STD:
                continue
            if self.db.scalar("""
select 1 from cards where ord not in %s and nid in (
select id from notes where mid = ?) limit 1""" %
                               ids2str([template['ord'] for template in model['tmpls']]),
                               model.getId()):
                return
        return True

    def fixIntegrity(self):
        "Fix possible problems and rebuild caches."
        problems = []
        curs = self.db.cursor()
        self.save()
        oldSize = os.stat(self.path)[stat.ST_SIZE]

        # whether sqlite find a problem in its database
        if self.db.scalar("pragma integrity_check") != "ok":
            return (_("Collection is corrupt. Please see the manual."), False)

        # note types with a missing model
        ids = self.db.list("""
select id from notes where mid not in """ + ids2str(self.models.ids()))
        if ids:
            problems.append(
                ngettext("Deleted %d note with missing note type.",
                         "Deleted %d notes with missing note type.", len(ids))
                         % len(ids))
            self.remNotes(ids)

        # for each model
        for model in self.models.all():
            for template in model['tmpls']:
                if template['did'] == "None":
                    template['did'] = None
                    problems.append(_("Fixed AnkiDroid deck override bug."))
                    model.save()
            if model['type'] == MODEL_STD:
                # model with missing req specification
                if 'req' not in model:
                    model._updateRequired()
                    problems.append(_("Fixed note type: %s") % model.getName())
                # cards with invalid ordinal
                ids = self.db.list("""
select id from cards where ord not in %s and nid in (
select id from notes where mid = ?)""" %
                                   ids2str([template['ord'] for template in model['tmpls']]),
                                   model.getId())
                if ids:
                    problems.append(
                        ngettext("Deleted %d card with missing template.",
                                 "Deleted %d cards with missing template.",
                                 len(ids)) % len(ids))
                    self.remCards(ids)
            # notes with invalid field count
            ids = []
            for id, flds in self.db.execute(
                    "select id, flds from notes where mid = ?", model.getId()):
                if (flds.count("\x1f") + 1) != len(model['flds']):
                    ids.append(id)
            if ids:
                problems.append(
                    ngettext("Deleted %d note with wrong field count.",
                             "Deleted %d notes with wrong field count.",
                             len(ids)) % len(ids))
                self.remNotes(ids)
        # delete any notes with missing cards
        ids = self.db.list("""
select id from notes where id not in (select distinct nid from cards)""")
        if ids:
            cnt = len(ids)
            problems.append(
                ngettext("Deleted %d note with no cards.",
                         "Deleted %d notes with no cards.", cnt) % cnt)
            self._remNotes(ids)
        # cards with missing notes
        ids = self.db.list("""
select id from cards where nid not in (select id from notes)""")
        if ids:
            cnt = len(ids)
            problems.append(
                ngettext("Deleted %d card with missing note.",
                         "Deleted %d cards with missing note.", cnt) % cnt)
            self.remCards(ids)
        # cards with odue set when it shouldn't be
        ids = self.db.list(f"""
select id from cards where odue > 0 and (type={CARD_LRN} or queue={CARD_DUE}) and not odid""")
        if ids:
            cnt = len(ids)
            problems.append(
                ngettext("Fixed %d card with invalid properties.",
                         "Fixed %d cards with invalid properties.", cnt) % cnt)
            self.db.execute("update cards set odue=0 where id in "+
                ids2str(ids))
        # cards with odid set when not in a dyn deck
        dids = [id for id in self.decks.allIds() if not self.decks.isDyn(id)]
        ids = self.db.list("""
        select id from cards where odid > 0 and did in %s""" % ids2str(dids))
        if ids:
            cnt = len(ids)
            problems.append(
                ngettext("Fixed %d card with invalid properties.",
                         "Fixed %d cards with invalid properties.", cnt) % cnt)
            self.db.execute("update cards set odid=0, odue=0 where id in "+
                ids2str(ids))
        # tags
        self.tags.registerNotes()
        # field cache
        for model in self.models.all():
            self.updateFieldCache(model.nids())
        # new cards can't have a due position > 32 bits, so wrap items over
        # 2 million back to 1 million
        curs.execute(f"""
update cards set due=1000000+due%1000000,mod=?,usn=? where due>=1000000
and type = {CARD_NEW}""", [intTime(), self.usn()])
        if curs.rowcount:
            problems.append("Found %d new cards with a due number >= 1,000,000 - consider repositioning them in the Browse screen." % curs.rowcount)
        # new card position
        self.conf['nextPos'] = self.db.scalar(
            f"select max(due)+1 from cards where type = {CARD_NEW}") or 0
        # reviews should have a reasonable due #
        ids = self.db.list(
            "select id from cards where queue = 2 and due > 100000")
        if ids:
            problems.append("Reviews had incorrect due date.")
            self.db.execute(
                "update cards set due = ?, ivl = 1, mod = ?, usn = ? where id in %s"
                % ids2str(ids), self.sched.today, intTime(), self.usn())
        # v2 sched had a bug that could create decimal intervals
        curs.execute("update cards set ivl=round(ivl),due=round(due) where ivl!=round(ivl) or due!=round(due)")
        if curs.rowcount:
            problems.append("Fixed %d cards with v2 scheduler bug." % curs.rowcount)

        curs.execute("update revlog set ivl=round(ivl),lastIvl=round(lastIvl) where ivl!=round(ivl) or lastIvl!=round(lastIvl)")
        if curs.rowcount:
            problems.append("Fixed %d review history entries with v2 scheduler bug." % curs.rowcount)
        # models
        if self.models.ensureNotEmpty():
            problems.append("Added missing note type.")
        # and finally, optimize
        self.optimize()
        newSize = os.stat(self.path)[stat.ST_SIZE]
        txt = _("Database rebuilt and optimized.")
        ok = not problems
        print("Adding in collection.py")
        problems.append(txt)
        # if any problems were found, force a full sync
        if not ok:
            self.modSchema(check=False)
        self.save()
        return ("\n".join(problems), ok)

    def optimize(self):
        """Tell sqlite to optimize the db"""
        self.db.setAutocommit(True)
        self.db.execute("vacuum")
        self.db.execute("analyze")
        self.db.setAutocommit(False)
        self.lock()

    # Logging
    ##########################################################################

    def log(self, *args, **kwargs):
        """Generate the string [time] path:fn(): args list

        if args is not string, it is represented using pprint.pformat

        if self._debugLog is True, it is hadded to _logHnd
        if devMode is True, this string is printed

        TODO look traceback/extract stack and fn
        """
        if not self._debugLog:
            return
        def customRepr(arg):
            if isinstance(arg, str):
                return arg
            return pprint.pformat(arg)
        path, num, fn, y = traceback.extract_stack(
            limit=2+kwargs.get("stack", 0))[0]
        buf = "[%s] %s:%s(): %s" % (intTime(), os.path.basename(path), fn,
                                     ", ".join([customRepr(arg) for arg in args]))
        self._logHnd.write(buf + "\n")
        if devMode:
            print(buf)

    def _openLog(self):
        if not self._debugLog:
            return
        lpath = re.sub(r"\.anki2$", ".log", self.path)
        if os.path.exists(lpath) and os.path.getsize(lpath) > 10*1024*1024:
            lpath2 = lpath + ".old"
            if os.path.exists(lpath2):
                os.unlink(lpath2)
            os.rename(lpath, lpath2)
        self._logHnd = open(lpath, "a", encoding="utf8")

    def _closeLog(self):
        if not self._debugLog:
            return
        self._logHnd.close()
        self._logHnd = None

    # Card Flags
    ##########################################################################

    def setUserFlag(self, flag, cids):
        assert 0 <= flag <= 7
        self.db.execute("update cards set flags = (flags & ~?) | ?, usn=?, mod=? where id in %s" %
                        ids2str(cids), 0b111, flag, self.usn(), intTime())
