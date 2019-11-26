# -*- coding: utf-8 -*-
# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

import gzip
import io
import json
import os
import random

import requests

import anki
from anki.consts import *
from anki.db import DB, DBError
from anki.utils import (checksum, devMode, ids2str, intTime, platDesc,
                        versionWithBuild)

from .hooks import runHook
from .lang import ngettext

# syncing vars
HTTP_TIMEOUT = 90
HTTP_PROXY = None
HTTP_BUF_SIZE = 64*1024

class UnexpectedSchemaChange(Exception):
    pass

# Incremental syncing
##########################################################################

class Syncer:

    """The hook "sync" takes as parameter a string describing what is
    going to be done. It seems that, by default, those hook are empty.

    lmod -- last modified of the collection in milliseconds
    rmod -- last modified of the collection in milliseconds
    minUsn -- USN of the collection
    col -- its collection
    server -- the server. Object of class RemoteServer in pratice
    syncMsg -- By default the empty string. Otherwise, a message from meta.
    uname -- username (login/email)
    tablesLeft -- A subset of ["revlog", "cards", "notes"], stating which tables have not yet be synchronized.
    cursor -- A cursor to the table revlog, cards, or notes, allowing to find elements not yet received from the database.

    """

    def __init__(self, col, server=None):
        """Save in the Syncer the value of the two parameters. """
        #It is not clear what is done if server is None. But it never occurs in this code
        self.col = col
        self.server = server

    def sync(self):
        """
        Possible return values:
        * badAuth: wrong login or password
        * clockOff: there is more than 5 minutes of difference between
        the clock here and on server. Thus synchronization rejected.
        * noChanges: mod's value are the same in collection and
        server. It means that not a single change occured, thus there
        are nothing to synchronize.
        * fullSync: the schema differ in collection and on server. A
        full sync is thus required.
        * basicCheckFailed: if the basic check fails
        * sanityCheckFailed: if the sanity check fails according to
        sync.
        * success: everything went all right.
        """
        self.syncMsg = ""
        self.uname = ""
        # if the deck has any pending changes, flush them first and bump mod
        # time
        self.col.save()

        # step 1: login & metadata
        runHook("sync", "login")
        serverMeta = self.server.meta()
        self.col.log("rmeta", serverMeta)
        if not serverMeta:
            return "badAuth"
        # server requested abort?
        self.syncMsg = serverMeta['msg']
        if not serverMeta['cont']:
            return "serverAbort"
        else:
            # don't abort, but if 'msg' is not blank, gui should show 'msg'
            # after sync finishes and wait for confirmation before hiding
            pass
        serverScm = serverMeta['scm']
        serverTs = serverMeta['ts']
        serverMod = serverMeta['mod']
        self.maxUsn = serverMeta['usn']
        self.uname = serverMeta.get("uname", "")
        self.hostNum = serverMeta.get("hostNum")
        localMeta = self.meta()
        self.col.log("lmeta", localMeta)
        localMod = localMeta['mod']
        self.minUsn = localMeta['usn']
        localScm = localMeta['scm']
        localTs = localMeta['ts']
        if abs(serverTs - localTs) > 300:
            self.col.log("clock off")
            return "clockOff"
        if localMod == serverMod:
            self.col.log("no changes")
            return "noChanges"
        elif localScm != serverScm:
            self.col.log("schema diff")
            return "fullSync"
        self.localNewer = localMod > serverMod
        # step 1.5: check collection is valid
        if not self.col.basicCheck():
            self.col.log("basic check")
            return "basicCheckFailed"
        # step 2: startup and deletions
        runHook("sync", "meta")
        serverRem = self.server.start(minUsn=self.minUsn, lnewer=self.localNewer)

        # apply deletions to server
        localGraves = self.removed()
        while localGraves:
            gchunk, localGraves = self._gravesChunk(localGraves)
            self.server.applyGraves(chunk=gchunk)

        # then apply server deletions here
        self.remove(serverRem)

        # ...and small objects
        localChange = self.changes()
        serverChange = self.server.applyChanges(changes=localChange)
        try:
            self.mergeChanges(localChange, serverChange)
        except UnexpectedSchemaChange:
            self.server.abort()
            return self._forceFullSync()
        # step 3: stream large tables from server
        runHook("sync", "server")
        ################ done
        while 1:
            runHook("sync", "stream")
            chunk = self.server.chunk()
            self.col.log("server chunk", chunk)
            self.applyChunk(chunk=chunk)
            if chunk['done']:
                break
        # step 4: stream to server
        runHook("sync", "client")
        while 1:
            runHook("sync", "stream")
            chunk = self.chunk()
            self.col.log("client chunk", chunk)
            self.server.applyChunk(chunk=chunk)
            if chunk['done']:
                break
        # step 5: sanity check
        runHook("sync", "sanity")
        check = self.sanityCheck()
        ret = self.server.sanityCheck2(client=check)
        if ret['status'] != "ok":
            return self._forceFullSync()
        # finalize
        runHook("sync", "finalize")
        mod = self.server.finish()
        self.finish(mod)
        return "success"

    def _forceFullSync(self):
        # roll back and force full sync
        self.col.rollback()
        self.col.modSchema(False)
        self.col.save()
        return "sanityCheckFailed"

    def _gravesChunk(self, graves):
        """A pair. If graves contains less than 250 elements, then grave,None. Else the 250 first elements of graves, and the remaining elements)"""
        lim = 250
        chunk = dict(notes=[], cards=[], decks=[])
        for cat in "notes", "cards", "decks":
            if lim and graves[cat]:
                chunk[cat] = graves[cat][:lim]
                graves[cat] = graves[cat][lim:]
                lim -= len(chunk[cat])

        # anything remaining?
        if graves['notes'] or graves['cards'] or graves['decks']:
            return chunk, graves
        return chunk, None

    def meta(self):
        """A dictionnary with:
        -mod, scm, usn according to col's data
        -ts the actual time stamp
        -musn, msg and cont, initialized to some default constant
        """
        return dict(
            mod=self.col.mod,
            scm=self.col.scm,
            usn=self.col._usn,
            ts=intTime(),
            musn=0,
            msg="",
            cont=True
        )

    def changes(self):
        """Bundle up small objects.

        A dict with models, decks, tags. If mod is newer here than on server, then conf and crt.
        """
        bundle = dict(models=self.getModels(),
                      decks=self.getDecks(),
                      tags=self.getTags())
        if self.localNewer:
            bundle['conf'] = self.getConf()
            bundle['crt'] = self.col.crt
        return bundle

    def mergeChanges(self, localChange, serverChange):
        """
        serverChange --
        """
        # then the other objects
        self.mergeModels(serverChange['models'])
        self.mergeDecks(serverChange['decks'])
        self.mergeTags(serverChange['tags'])
        if 'conf' in serverChange:
            self.mergeConf(serverChange.getConfId())
        # this was left out of earlier betas
        if 'crt' in serverChange:
            self.col.crt = serverChange['crt']
        self.prepareToChunk()

    def sanityCheck(self):
        """Check whether the synchronization went well.

        USN should not be -1 in cards, notes, revlog, graves, deck,
        tag, model. If it is the case, return a string giving the name of the
        table not satisfying it.

        If a non-root deck has no parent, it is created.

        Returns:
        [three numbers to show in anki
        list/footer. I.e. Number of new cards, learning repetition,
        review card. (for selected deck),
        number of card,
        number of notes,
        number of revlog,
        number of grave,
        number of models,
        numbel of decks,
        number of deck's options.]
        """
        if not self.col.basicCheck():
            return "failed basic check"
        for type in "cards", "notes", "revlog", "graves":
            if self.col.db.scalar(
                "select count() from %s where usn = -1" % type):
                return "%s had usn = -1" % type
        for deck in self.col.decks.all():
            if deck['usn'] == -1:
                return "deck had usn = -1"
        for type, usn in self.col.tags.allItems():
            if usn == -1:
                return "tag had usn = -1"
        found = False
        for model in self.col.models.all():
            if model['usn'] == -1:
                return "model had usn = -1"
        if found:
            self.col.models.save()
        self.col.sched.reset()
        # check for missing parent decks
        self.col.sched.deckDueList()
        # return summary of deck
        return [
            list(self.col.sched.counts()),
            self.col.db.scalar("select count() from cards"),
            self.col.db.scalar("select count() from notes"),
            self.col.db.scalar("select count() from revlog"),
            self.col.db.scalar("select count() from graves"),
            len(self.col.models.all()),
            len(self.col.decks.all()),
            len(self.col.decks.allConf()),
        ]

    def usnLim(self):
        return "usn = -1"

    def finish(self, mod=None):
        self.col.ls = mod
        self.col._usn = self.maxUsn + 1
        # ensure we save the mod time even if no changes made
        self.col.db.mod = True
        self.col.save(mod=mod)
        return mod

    # Chunked syncing
    ##########################################################################

    def prepareToChunk(self):
        self.tablesLeft = ["revlog", "cards", "notes"]
        self.cursor = None

    def cursorForTable(self, table):
        """A cursor returning the entire line from the table argument, where
        usn is -1, and replaced by maxUsn.

        The content of the table is not changed however.
        """
        lim = self.usnLim() # "usn = -1"
        x = self.col.db.execute
        if table == "revlog":
            return self.col.db.execute("""
select id, cid, %d, ease, ivl, lastIvl, factor, time, type
from revlog where %s""" % (self.maxUsn, lim))
        elif table == "cards":
            return self.col.db.execute("""
select id, nid, did, ord, mod, %d, type, queue, due, ivl, factor, reps,
lapses, left, odue, odid, flags, data from cards where %s""" % (self.maxUsn, lim))
        else:
            return self.col.db.execute("""
select id, guid, mid, mod, %d, tags, flds, '', '', flags, data
from notes where %s""" % (self.maxUsn, lim))

    def chunk(self):
        """A dictionnary containing keys K in 'revlog', 'cards', 'notes' whose
        usn value is -1. Each entry is an entire line of the table K,
        except that usn is replaced by maxUsn.

        It also contains 'done', a Boolean stating which states whether every lines are treated.

        If the table is empty, usn is changed from -1 to maxUsn and
        its name is removed from self.tablesLeft.
        """
        buf = dict(done=False)
        lim = 250
        while self.tablesLeft and lim:
            curTable = self.tablesLeft[0]
            if not self.cursor:
                self.cursor = self.cursorForTable(curTable)
            rows = self.cursor.fetchmany(lim)
            fetched = len(rows)
            if fetched != lim:
                # table is empty
                self.tablesLeft.pop(0)
                self.cursor = None
                # mark the objects as having been sent
                self.col.db.execute(
                    "update %s set usn=? where usn=-1"%curTable,
                    self.maxUsn)
            buf[curTable] = rows
            lim -= fetched
        if not self.tablesLeft:
            buf['done'] = True
        return buf

    def applyChunk(self, chunk):
        """
        Everything in chunk is added to the collection, unless it is
        already in and modified later in the collection than on the server.

        chunk -- a dict containing some key from 'revlog', 'cards', and
        'notes'. Each of their values are a line (log, card or note),
        which is new on the server.
        """
        if "revlog" in chunk:
            self.mergeRevlog(chunk['revlog'])
        if "cards" in chunk:
            self.mergeCards(chunk['cards'])
        if "notes" in chunk:
            self.mergeNotes(chunk['notes'])

    # Deletions
    ##########################################################################

    def removed(self):
        """A dict associating to 'cards', 'notes' and 'decks' the list of ids
        of such object deleted sync last synchronization. Change the
        usn value of those graves element to indicate that they have
        been deleted.

        """
        cards = []
        notes = []
        decks = []

        curs = self.col.db.execute(
            "select oid, type from graves where usn = -1")

        for oid, type in curs:
            if type == REM_CARD:
                cards.append(oid)
            elif type == REM_NOTE:
                notes.append(oid)
            else:
                decks.append(oid)

        self.col.db.execute("update graves set usn=? where usn=-1",
                             self.maxUsn)

        return dict(cards=cards, notes=notes, decks=decks)

    def remove(self, graves):
        """Remove the notes, cards and decks whose id are in graves['notes'],
        graves['cards'] and graves['decks']. Don't remove child of
        deleted deck, nor its card if any remain.

        """
        # pretend to be the server so we don't set usn = -1
        self.col.server = True

        # notes first, so we don't end up with duplicate graves
        self.col._remNotes(graves['notes'])
        # then cards
        self.col.remCards(graves['cards'], notes=False)
        # and decks
        for oid in graves['decks']:
            self.col.decks.rem(oid, childrenToo=False)

        self.col.server = False

    # Models
    ##########################################################################

    def getModels(self):
        """
        The list of models whose usn is -1. I.e. the ones which have been created/changed since last sync.
        Their usn is then changed no maxUsn.
        """
        mods = [model for model in self.col.models.all() if model['usn'] == -1]
        for model in mods:
            model['usn'] = self.maxUsn
        self.col.models.save()
        return mods

    def mergeModels(self, serverChanges):
        """
        serverChange -- a list of model (note type) object. They are assumed to have been changed on server since last sync.

        Each note type whose mod time is greater on server, or which does not exists in collection, is copied into the collection.
        """
        for serverModel in serverChanges:
            localModel = self.col.models.get(serverModel.getId())
            # if missing locally or server is newer, update
            if not localModel or serverModel['mod'] > localModel['mod']:
                # This is a hack to detect when the note type has been altered
                # in an import without a full sync being forced. A future
                # syncing algorithm should handle this in a better way.
                if localModel:
                    if len(localModel['flds']) != len(serverModel['flds']):
                        raise UnexpectedSchemaChange()
                    if len(localModel['tmpls']) != len(serverModel['tmpls']):
                        raise UnexpectedSchemaChange()
                self.col.models.update(serverModel)

    # Decks
    ##########################################################################

    def getDecks(self):
        """A list of size two, with decks and deck's configuration (option),
        with usn equal to -1. I.e. modified since last sync. Their usn
        is changed to maxUsn, i.e. the one currently considered.

        """
        decks = [deck for deck in self.col.decks.all() if deck['usn'] == -1]
        for deck in decks:
            deck['usn'] = self.maxUsn
        dconf = [deck for deck in self.col.decks.allConf() if deck['usn'] == -1]
        for deck in dconf:
            deck['usn'] = self.maxUsn
        self.col.decks.save()
        return [decks, dconf]

    def mergeDecks(self, serverChanges):
        for serverDeck in serverChanges[0]:
            localDeck = self.col.decks.get(serverDeck.getId(), False)
            # work around mod time being stored as string
            if localDeck and not isinstance(localDeck['mod'], int):
                localDeck['mod'] = int(localDeck['mod'])

            # if missing locally or server is newer, update
            if not localDeck or serverDeck['mod'] > localDeck['mod']:
                serverDeck.update()
        for serverDeckOption in serverChanges[1]:
            try:
                localDeckOption = self.col.decks.getConf(serverDeckOption.getId())
            except KeyError:
                localDeckOption = None
            # if missing locally or server is newer, update
            if not localDeckOption or serverDeckOption['mod'] > localDeckOption['mod']:
                self.col.decks.updateConf(serverDeckOption)

    # Tags
    ##########################################################################

    def getTags(self):
        """A list of tags with usn equal to -1. I.e. modified since last
        sync. Their usn is changed to maxUsn, i.e. the one currently
        considered.

        """
        tags = []
        for tag, usn in self.col.tags.allItems():
            if usn == -1:
                self.col.tags.tags[tag] = self.maxUsn
                tags.append(tag)
        self.col.tags.save()
        return tags

    def mergeTags(self, tags):
        """Given a list/set of tags, add any tag missing in the registry to
        the registry. If there is such a new tag, call the hook
        newTag.

        """
        self.col.tags.register(tags, usn=self.maxUsn)

    # Cards/notes/revlog
    ##########################################################################

    def mergeRevlog(self, logs):
        """Each log from logs is added to the table revlog, unless a rev with
        the same id is already there. (The id is unique with extremly
        high probability, thus it would be the same review).

        """
        self.col.db.executemany(
            "insert or ignore into revlog values (?,?,?,?,?,?,?,?,?)",
            logs)

    def newerRows(self, data, table, modIdx):
        """
        The subset of `data` which either are not in the collection
        (according to their id), or such that the last modification in
        the server is greater than in the collection.

        data -- a container of tuple, each representing an entry of
        the table 'table' from the server, i.e. to be updated or
        created.
        table -- 'card' or 'note', name of a table
        modIdx -- index of mod in the tuple
        """
        ids = (datum[0] for datum in data)
        lmods = {} # subset of (id,mod) of data's id in which usn is -1.
        for id, mod in self.col.db.execute(
            "select id, mod from %s where id in %s and %s" % (
                table, ids2str(ids), self.usnLim())):
            lmods[id] = mod
        update = [] # lines from server (data), which either are not
        # in the collection, or such that the mod time is greater on
        # the server than in the collection.
        for datum in data:
            if datum[0] not in lmods or lmods[datum[0]] < datum[modIdx]:
                update.append(datum)
        self.col.log(table, data)
        return update

    def mergeCards(self, cards):
        """Each card from cards is added to the table cards, unless a card
        with the same id is already there and has a newer mod
        time. (The id is unique with extremly high probability, thus
        it would be the same review).

        """
        rows = self.newerRows(cards, "cards", 4)
        self.col.db.executemany(
            "insert or replace into cards values "
            "(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            rows)

    def mergeNotes(self, notes):
        """Each note from notes is added to the table notes, unless a note
        with the same id is already there and has a newer mod
        time. (The id is unique with extremly high probability, thus
        it would be the same review).

        The field cache of those notes are then modified.
        """
        rows = self.newerRows(notes, "notes", 3)
        self.col.db.executemany(
            "insert or replace into notes values (?,?,?,?,?,?,?,?,?,?,?)",
            rows)
        self.col.updateFieldCache([note[0] for note in rows])

    # Col config
    ##########################################################################

    def getConf(self):
        """The conf of the collection."""
        return self.col.conf

    def mergeConf(self, conf):
        """Change collection's conf to the argument"""
        self.col.conf = conf

# Wrapper for requests that tracks upload/download progress
##########################################################################

class AnkiRequestsClient:
    """
    session -- A request session object
    verify -- Whether to verify the certificate. By default true unless the os ANKI_NOVERIFYSSL is set to truthy.
    timeout -- as for requests
    """
    verify = True
    timeout = 60
    def __init__(self):
        self.session = requests.Session()

    def post(self, url, data, headers):
        """
        Similar to a post request, where:
        * User-Agent name is added
        * hook httpSend is run
        * stream is true, timeout and verify are as in the class.
        """
        data = _MonitoringFile(data)
        headers['User-Agent'] = self._agentName()
        return self.session.post(
            url, data=data, headers=headers, stream=True, timeout=self.timeout, verify=self.verify)

    def get(self, url, headers=None):
        """
        Similar to a post request, where:
        * User-Agent name is added to header
        * stream is true, timeout and verify are as in the class.
        """
        if headers is None:
            headers = {}
        headers['User-Agent'] = self._agentName()
        return self.session.get(url, stream=True, headers=headers, timeout=self.timeout, verify=self.verify)

    def streamContent(self, resp):
        """
        Return a string containing the content of the entire response to a request.

        If the response is not successful, raise requests.exceptions.HTTPError
        """
        resp.raise_for_status()

        buf = io.BytesIO()
        for chunk in resp.iter_content(chunk_size=HTTP_BUF_SIZE):
            runHook("httpRecv", len(chunk))
            buf.write(chunk)
        return buf.getvalue()

    def _agentName(self):
        """Anki versionNumber"""
        from anki import version
        return "Anki {}".format(version)

# allow user to accept invalid certs in work/school settings
if os.environ.get("ANKI_NOVERIFYSSL"):
    AnkiRequestsClient.verify = False

    import warnings
    warnings.filterwarnings("ignore")

class _MonitoringFile(io.BufferedReader):
    def read(self, size=-1):
        """"Similar to io.BufferedReader's read method, where the hook httpSend is emitted after data is found."""
        data = io.BufferedReader.read(self, HTTP_BUF_SIZE)
        runHook("httpSend", len(data))
        return data

# HTTP syncing tools
##########################################################################

class HttpSyncer:
    """
    skey -- a random  8 hexadecimal value
    hostNum -- the value of hostNum in the profile (i.e. a number which states the number of the ankiweb server which is used to synchronize)
    hkey -- the value of SyncKey in the profile (i.e. a random string replacing the password)
    postVars -- dictionnary to use in the post request.
    prefix -- main folder in anki server to use for the synchrozination. By default sync, except for media where it is msync
    client -- a client, allowing at least to post() and streamContent. By default AnkiRequestsClient
    """
    def __init__(self, hkey=None, client=None, hostNum=None):
        self.hkey = hkey
        self.skey = checksum(str(random.random()))[:8]
        self.client = client or AnkiRequestsClient()
        self.postVars = {}
        self.hostNum = hostNum
        self.prefix = "sync/"

    def syncURL(self):
        """
        Start of the url to use for synchrozination. Some other subfolder/file may be staten after.

        It depends on whether we are in devmode, and of the hostNum value.s
        """
        if devMode:
            url = "https://l1sync.ankiweb.net/"
        else:
            url = SYNC_BASE % (self.hostNum or "")
        return url + self.prefix

    def assertOk(self, resp):
        """Raise an exception unless status code of resp is 200"""
        # not using raise_for_status() as aqt expects this error msg
        if resp.status_code != 200:
            raise Exception("Unknown response code: %s" % resp.status_code)

    # Posting data as a file
    ######################################################################
    # We don't want to post the payload as a form var, as the percent-encoding is
    # costly. We could send it as a raw post, but more HTTP clients seem to
    # support file uploading, so this is the more compatible choice.

    def _buildPostData(self, fobj, comp):
        """
        A pair (headers, buffer) as follow.

        buffer's position is 0. It contains, separated by "--Anki-sync-boundary",
«Content-Disposition: form-data; name="{key}"

value
»
        where key,values come from self.postVars, and also contains key 'c', whose value is 1 if it's compressing, 0 otherwise.

If there is an object, then it also contains
«
Content-Disposition: form-data; name="data"; filename="data"\r\n\
Content-Type: application/octet-stream\r\n\r\n"»
{object}
»
        In any case, it ends with
«--
»
        the header is a dict with 'Content-Type' and 'Content-Length'.


        comp -- whether to compress. If truthy, it's the compresslevel passed to gzip.
        fobj -- an object which can be read.
        """
        BOUNDARY=b"Anki-sync-boundary"
        bdry = b"--"+BOUNDARY
        buf = io.BytesIO()
        # post vars
        self.postVars['c'] = 1 if comp else 0
        for (key, value) in list(self.postVars.items()):
            buf.write(bdry + b"\r\n")
            buf.write(
                ('Content-Disposition: form-data; name="%s"\r\n\r\n%s\r\n' %
                (key, value)).encode("utf8"))
        # payload as raw data or json
        rawSize = 0
        if fobj:
            # header
            buf.write(bdry + b"\r\n")
            buf.write(b"""\
Content-Disposition: form-data; name="data"; filename="data"\r\n\
Content-Type: application/octet-stream\r\n\r\n""")
            # write file into buffer, optionally compressing
            if comp:
                tgt = gzip.GzipFile(mode="wb", fileobj=buf, compresslevel=comp)
            else:
                tgt = buf
            while 1:
                data = fobj.read(65536)
                if not data:
                    if comp:
                        tgt.close()
                    break
                rawSize += len(data)
                tgt.write(data)
            buf.write(b"\r\n")
        buf.write(bdry + b'--\r\n')
        size = buf.tell()
        # connection headers
        headers = {
            'Content-Type': 'multipart/form-data; boundary=%s' % BOUNDARY.decode("utf8"),
            'Content-Length': str(size),
        }
        buf.seek(0)

        if size >= 100*1024*1024 or rawSize >= 250*1024*1024:
            raise Exception("Collection too large to upload to AnkiWeb.")

        return headers, buf

    def req(self, method, fobj=None, comp=6, badAuthRaises=True):
        """
        The answer to a post request, to /method, whose body comes from self.postVars, compression and potentially the object fobj.

        method -- the «file», i.e. last part of the URL. It states which can of data we send/request. It may be:
        * hostKey, meta for initialization of sync
        * applyGraves, applyChanges, start, chunk, applyChunk, sanityCheck2, finish, abort for normal syn
        * download, upload for full sync
        * begin, mediaChanges, downloadFiles, uploadChanges, mediaSanity, newMediaTest for media
        fobj -- An object which can be read and must be send
        comp -- Level of compression to use for gzip.
        badAuthRaises -- whether to accept 403 status without raising error. Instead return False.
        """
        headers, body = self._buildPostData(fobj, comp)

        req = self.client.post(self.syncURL()+method, data=body, headers=headers)
        if not badAuthRaises and req.status_code == 403:
            return False
        self.assertOk(req)

        buf = self.client.streamContent(req)
        return buf

# Incremental sync over HTTP
######################################################################

class RemoteServer(HttpSyncer):

    def __init__(self, hkey, hostNum):
        HttpSyncer.__init__(self, hkey, hostNum=hostNum)

    def hostKey(self, user, pw):
        "Returns hkey or none if user/pw incorrect."
        self.postVars = dict()
        ret = self.req(
            "hostKey", io.BytesIO(json.dumps(dict(u=user, p=pw)).encode("utf8")),
            badAuthRaises=False)
        if not ret:
            # invalid auth
            return
        self.hkey = json.loads(ret.decode("utf8"))['key']
        return self.hkey

    def meta(self):
        """ Ask the server for an object which should contain


        """
        self.postVars = dict(
            k=self.hkey,
            s=self.skey,
        )
        d = dict(v=SYNC_VER, cv="ankidesktop,%s,%s"%(versionWithBuild(), platDesc()))
        ret = self.req(
            "meta", io.BytesIO(json.dumps(d).encode("utf8")),
            badAuthRaises=False)
        if not ret:
            # invalid auth
            return
        return json.loads(ret.decode("utf8"))

    def applyGraves(self, **kw):
        return self._run("applyGraves", kw)

    def applyChanges(self, **kw):
        """Send every small change to the server."""
        return self._run("applyChanges", kw)

    def start(self, **kw):
        return self._run("start", kw)

    def chunk(self, **kw):
        return self._run("chunk", kw)

    def applyChunk(self, **kw):
        return self._run("applyChunk", kw)

    def sanityCheck2(self, **kw):
        return self._run("sanityCheck2", kw)

    def finish(self, **kw):
        return self._run("finish", kw)

    def abort(self, **kw):
        return self._run("abort", kw)

    def _run(self, cmd, data):
        return json.loads(
            self.req(cmd, io.BytesIO(json.dumps(data).encode("utf8"))).decode("utf8"))

# Full syncing
##########################################################################

class FullSyncer(HttpSyncer):

    def __init__(self, col, hkey, client, hostNum):
        HttpSyncer.__init__(self, hkey, client, hostNum=hostNum)
        self.postVars = dict(
            k=self.hkey,
            v="ankidesktop,%s,%s"%(anki.version, platDesc()),
        )
        self.col = col

    def download(self):
        """Download a database from the server. If instead it receives
        "upgradeRequired", a message stating to go on ankiweb is
        shown. Otherwise, if the downloaded db has no card while
        current collection has card, it returns
        "downloadClobber". Otherwise, the downloaded database replace
        the collection's database.

        It also change message to "Downloading for AnkiWeb...".

        """
        runHook("sync", "download")
        #whether the collection has at least one card.
        localNotEmpty = self.col.db.scalar("select 1 from cards limit 1")
        self.col.close()
        cont = self.req("download")
        tpath = self.col.path + ".tmp"
        if cont == "upgradeRequired":
            runHook("sync", "upgradeRequired")
            return
        open(tpath, "wb").write(cont)
        # check the received file is ok
        db = DB(tpath)
        assert db.scalar("pragma integrity_check") == "ok"
        remoteEmpty = not db.scalar("select 1 from cards limit 1")
        db.close()
        # accidental clobber?
        if localNotEmpty and remoteEmpty:
            os.unlink(tpath)
            return "downloadClobber"
        # overwrite existing collection
        os.unlink(self.col.path)
        os.rename(tpath, self.col.path)
        self.col = None

    def upload(self):
        "True if upload successful."
        runHook("sync", "upload")
        # make sure it's ok before we try to upload
        if self.col.db.scalar("pragma integrity_check") != "ok":
            return False
        if not self.col.basicCheck():
            return False
        # apply some adjustments, then upload
        self.col.beforeUpload()
        if self.req("upload", open(self.col.path, "rb")) != b"OK":
            return False
        return True

# Media syncing
##########################################################################
#
# About conflicts:
# - to minimize data loss, if both sides are marked for sending and one
#   side has been deleted, favour the add
# - if added/changed on both sides, favour the server version on the
#   assumption other syncers are in sync with the server
#

class MediaSyncer:

    def __init__(self, col, server=None):
        """Save in the Syncer the value of the two parameters"""
        self.col = col
        self.server = server

    def sync(self):
        """
        Return either:
        * "corruptMediaDB": if reading the  database raise an exception
        * "noChanges": if the usn on collection and server are the same
        * "OK": if everything was correctly downloaded and uploaded
        * Any other message  sent by the server during mediaSanity check.

        It sends the following messages:
        * begin: send hostkey and "ankidesktop,{anki's version number},{platform}:{platform's
  version}". Returing an id to use until the end of communication
        * mediaChanges: the name of new/modified medias, and usn in collection. Return name of new/modified media on server
        * downloadFiles: request files named by the server when necessary, receive zip files with up to 25 files, and save them in the collection.
        * uploadChanges: Send zip files with up to 25 files.
        * mediaSanity: sending the number of media to server, to check whether there is the same number online. If not, empty media database and return value sent by the server.
        """
        # check if there have been any changes
        runHook("sync", "findMedia")
        self.col.log("findChanges")
        try:
            self.col.media.findChanges()
        except DBError:
            return "corruptMediaDB"

        # begin session and check if in sync
        lastUsn = self.col.media.lastUsn()
        ret = self.server.begin()
        srvUsn = ret['usn']
        if lastUsn == srvUsn and not self.col.media.haveDirty():
            return "noChanges"

        # loop through and process changes from server
        self.col.log("last local usn is %s"%lastUsn)
        self.downloadCount = 0
        while True:
            data = self.server.mediaChanges(lastUsn=lastUsn)

            self.col.log("mediaChanges resp count %d"%len(data))
            if not data:
                break

            need = []
            lastUsn = data[-1][1]
            for fname, rusn, rsum in data:
                lsum, ldirty = self.col.media.syncInfo(fname)
                self.col.log(
                    "check: lsum=%s rsum=%s ldirty=%d rusn=%d fname=%s"%(
                        (lsum and lsum[0:4]),
                        (rsum and rsum[0:4]),
                        ldirty,
                        rusn,
                        fname))

                if rsum:
                    # added/changed remotely
                    if not lsum or lsum != rsum:
                        self.col.log("will fetch")
                        need.append(fname)
                    else:
                        self.col.log("have same already")
                    if ldirty:
                        self.col.media.markClean([fname])
                elif lsum:
                    # deleted remotely
                    if not ldirty:
                        self.col.log("delete local")
                        self.col.media.syncDelete(fname)
                    else:
                        # conflict; local add overrides remote delete
                        self.col.log("conflict; will send")
                else:
                    # deleted both sides
                    self.col.log("both sides deleted")
                    if ldirty:
                        self.col.media.markClean([fname])

            self._downloadFiles(need)

            self.col.log("update last usn to %d"%lastUsn)
            self.col.media.setLastUsn(lastUsn) # commits

        # at this point we're all up to date with the server's changes,
        # and we need to send our own

        updateConflict = False
        toSend = self.col.media.dirtyCount()
        while True:
            zip, fnames = self.col.media.mediaChangesZip()
            if not fnames:
                break

            runHook("syncMsg", ngettext(
                "%d media change to upload", "%d media changes to upload", toSend)
                    % toSend)

            processedCnt, serverLastUsn = self.server.uploadChanges(zip)
            self.col.media.markClean(fnames[0:processedCnt])

            self.col.log("processed %d, serverUsn %d, clientUsn %d" % (
                processedCnt, serverLastUsn, lastUsn
            ))

            if serverLastUsn - processedCnt == lastUsn:
                self.col.log("lastUsn in sync, updating local")
                lastUsn = serverLastUsn
                self.col.media.setLastUsn(serverLastUsn) # commits
            else:
                self.col.log("concurrent update, skipping usn update")
                # commit for markClean
                self.col.media.db.commit()
                updateConflict = True

            toSend -= processedCnt

        if updateConflict:
            self.col.log("restart sync due to concurrent update")
            return self.sync()

        lcnt = self.col.media.mediaCount()
        ret = self.server.mediaSanity(local=lcnt)
        if ret == "OK":
            return "OK"
        else:
            self.col.media.forceResync()
            return ret

    def _downloadFiles(self, fnames):
        self.col.log("%d files to fetch"%len(fnames))
        while fnames:
            top = fnames[0:SYNC_ZIP_COUNT]
            self.col.log("fetch %s"%top)
            zipData = self.server.downloadFiles(files=top)
            cnt = self.col.media.addFilesFromZip(zipData)
            self.downloadCount += cnt
            self.col.log("received %d files"%cnt)
            fnames = fnames[cnt:]

            count = self.downloadCount
            runHook("syncMsg", ngettext(
                "%d media file downloaded", "%d media files downloaded", count)
                    % count)

# Remote media syncing
##########################################################################

class RemoteMediaServer(HttpSyncer):

    def __init__(self, col, hkey, client, hostNum):
        self.col = col
        HttpSyncer.__init__(self, hkey, client, hostNum=hostNum)
        self.prefix = "msync/"

    def begin(self):
        """Send a request to initialize the communication. It contains:
        * 'k': the hostkey (a number sent during synchronization of data, to identify the user)
        * 'v': "ankidesktop,{anki's version number},{platform}:{platform's
        version}", with platform being either win, lin, mac or unknown. In
        the last case, there are no version sent.

        Set the identification number as provided by the server. This
        number is used for this communication only.

        Raise an exception if the response contains an error field or is not json.

        """
        self.postVars = dict(
            k=self.hkey,
            v="ankidesktop,%s,%s"%(anki.version, platDesc())
        )
        ret = self._dataOnly(self.req(
            "begin", io.BytesIO(json.dumps(dict()).encode("utf8"))))
        self.skey = ret['sk']
        return ret

    # args: lastUsn
    def mediaChanges(self, **kw):
        self.postVars = dict(
            sk=self.skey,
        )
        return self._dataOnly(
            self.req("mediaChanges", io.BytesIO(json.dumps(kw).encode("utf8"))))

    # args: files
    def downloadFiles(self, **kw):
        return self.req("downloadFiles", io.BytesIO(json.dumps(kw).encode("utf8")))

    def uploadChanges(self, zip):
        # no compression, as we compress the zip file instead
        return self._dataOnly(
            self.req("uploadChanges", io.BytesIO(zip), comp=0))

    # args: local
    def mediaSanity(self, **kw):
        return self._dataOnly(
            self.req("mediaSanity", io.BytesIO(json.dumps(kw).encode("utf8"))))

    def _dataOnly(self, resp):
        """
        If the error in resp  is truthy, log it, raise an exception. Otherwise, return the data of resp.

        resp -- a json utf8 string. Otherwise raise an exception. Received from the server
        """
        resp = json.loads(resp.decode("utf8"))
        if resp['err']:
            self.col.log("error returned:%s"%resp['err'])
            raise Exception("SyncError:%s"%resp['err'])
        return resp['data']

    # only for unit tests
    def mediatest(self, cmd):
        self.postVars = dict(
            k=self.hkey,
        )
        return self._dataOnly(
            self.req("newMediaTest", io.BytesIO(
                json.dumps(dict(cmd=cmd)).encode("utf8"))))
