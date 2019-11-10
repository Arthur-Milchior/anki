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

    def __init__(self, col, server=None):
        self.col = col
        self.server = server

    def sync(self):
        "Returns 'noChanges', 'fullSync', 'success', etc"
        self.syncMsg = ""
        self.uname = ""
        # if the deck has any pending changes, flush them first and bump mod
        # time
        self.col.save()

        # step 1: login & metadata
        runHook("sync", "login")
        serverMeta = self.server.meta()
        self.col.log("rmeta", meta)
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
        "Bundle up small objects."
        d = dict(models=self.getModels(),
                 decks=self.getDecks(),
                 tags=self.getTags())
        if self.localNewer:
            d['conf'] = self.getConf()
            d['crt'] = self.col.crt
        return d

    def mergeChanges(self, localChange, serverChange):
        # then the other objects
        self.mergeModels(serverChange['models'])
        self.mergeDecks(serverChange['decks'])
        self.mergeTags(serverChange['tags'])
        if 'conf' in serverChange:
            self.mergeConf(serverChange['conf'])
        # this was left out of earlier betas
        if 'crt' in serverChange:
            self.col.crt = serverChange['crt']
        self.prepareToChunk()

    def sanityCheck(self):
        if not self.col.basicCheck():
            return "failed basic check"
        for t in "cards", "notes", "revlog", "graves":
            if self.col.db.scalar(
                "select count() from %s where usn = -1" % t):
                return "%s had usn = -1" % t
        for deck in self.col.decks.all():
            if deck['usn'] == -1:
                return "deck had usn = -1"
        for t, usn in self.col.tags.allItems():
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
        lim = self.usnLim()
        x = self.col.db.execute
        d = (self.maxUsn, lim)
        if table == "revlog":
            return x("""
select id, cid, %d, ease, ivl, lastIvl, factor, time, type
from revlog where %s""" % d)
        elif table == "cards":
            return x("""
select id, nid, did, ord, mod, %d, type, queue, due, ivl, factor, reps,
lapses, left, odue, odid, flags, data from cards where %s""" % d)
        else:
            return x("""
select id, guid, mid, mod, %d, tags, flds, '', '', flags, data
from notes where %s""" % d)

    def chunk(self):
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
        if "revlog" in chunk:
            self.mergeRevlog(chunk['revlog'])
        if "cards" in chunk:
            self.mergeCards(chunk['cards'])
        if "notes" in chunk:
            self.mergeNotes(chunk['notes'])

    # Deletions
    ##########################################################################

    def removed(self):
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
        mods = [model for model in self.col.models.all() if model['usn'] == -1]
        for model in mods:
            model['usn'] = self.maxUsn
        self.col.models.save()
        return mods

    def mergeModels(self, serverChanges):
        for serverModel in serverChanges:
            localModel = self.col.models.get(serverModel['id'])
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
            localDeck = self.col.decks.get(serverDeck['id'], False)
            # work around mod time being stored as string
            if localDeck and not isinstance(localDeck['mod'], int):
                localDeck['mod'] = int(localDeck['mod'])

            # if missing locally or server is newer, update
            if not localDeck or serverDeck['mod'] > localDeck['mod']:
                self.col.decks.update(serverDeck)
        for serverDeckOption in serverChanges[1]:
            try:
                localDeckOption = self.col.decks.getConf(serverDeckOption['id'])
            except KeyError:
                localDeckOption = None
            # if missing locally or server is newer, update
            if not localDeckOption or serverDeckOption['mod'] > localDeckOption['mod']:
                self.col.decks.updateConf(serverDeckOption)

    # Tags
    ##########################################################################

    def getTags(self):
        tags = []
        for t, usn in self.col.tags.allItems():
            if usn == -1:
                self.col.tags.tags[t] = self.maxUsn
                tags.append(t)
        self.col.tags.save()
        return tags

    def mergeTags(self, tags):
        self.col.tags.register(tags, usn=self.maxUsn)

    # Cards/notes/revlog
    ##########################################################################

    def mergeRevlog(self, logs):
        self.col.db.executemany(
            "insert or ignore into revlog values (?,?,?,?,?,?,?,?,?)",
            logs)

    def newerRows(self, data, table, modIdx):
        ids = (datum[0] for datum in data)
        lmods = {}
        for id, mod in self.col.db.execute(
            "select id, mod from %s where id in %s and %s" % (
                table, ids2str(ids), self.usnLim())):
            lmods[id] = mod
        update = []
        for datum in data:
            if datum[0] not in lmods or lmods[datum[0]] < datum[modIdx]:
                update.append(datum)
        self.col.log(table, data)
        return update

    def mergeCards(self, cards):
        self.col.db.executemany(
            "insert or replace into cards values "
            "(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            self.newerRows(cards, "cards", 4))

    def mergeNotes(self, notes):
        rows = self.newerRows(notes, "notes", 3)
        self.col.db.executemany(
            "insert or replace into notes values (?,?,?,?,?,?,?,?,?,?,?)",
            rows)
        self.col.updateFieldCache([note[0] for note in rows])

    # Col config
    ##########################################################################

    def getConf(self):
        return self.col.conf

    def mergeConf(self, conf):
        self.col.conf = conf

# Wrapper for requests that tracks upload/download progress
##########################################################################

class AnkiRequestsClient:

    verify = True
    timeout = 60

    def __init__(self):
        self.session = requests.Session()

    def post(self, url, data, headers):
        data = _MonitoringFile(data)
        headers['User-Agent'] = self._agentName()
        return self.session.post(
            url, data=data, headers=headers, stream=True, timeout=self.timeout, verify=self.verify)

    def get(self, url, headers=None):
        if headers is None:
            headers = {}
        headers['User-Agent'] = self._agentName()
        return self.session.get(url, stream=True, headers=headers, timeout=self.timeout, verify=self.verify)

    def streamContent(self, resp):
        resp.raise_for_status()

        buf = io.BytesIO()
        for chunk in resp.iter_content(chunk_size=HTTP_BUF_SIZE):
            runHook("httpRecv", len(chunk))
            buf.write(chunk)
        return buf.getvalue()

    def _agentName(self):
        from anki import version
        return "Anki {}".format(version)

# allow user to accept invalid certs in work/school settings
if os.environ.get("ANKI_NOVERIFYSSL"):
    AnkiRequestsClient.verify = False

    import warnings
    warnings.filterwarnings("ignore")

class _MonitoringFile(io.BufferedReader):
    def read(self, size=-1):
        data = io.BufferedReader.read(self, HTTP_BUF_SIZE)
        runHook("httpSend", len(data))
        return data

# HTTP syncing tools
##########################################################################

class HttpSyncer:

    def __init__(self, hkey=None, client=None, hostNum=None):
        self.hkey = hkey
        self.skey = checksum(str(random.random()))[:8]
        self.client = client or AnkiRequestsClient()
        self.postVars = {}
        self.hostNum = hostNum
        self.prefix = "sync/"

    def syncURL(self):
        if devMode:
            url = "https://l1sync.ankiweb.net/"
        else:
            url = SYNC_BASE % (self.hostNum or "")
        return url + self.prefix

    def assertOk(self, resp):
        # not using raise_for_status() as aqt expects this error msg
        if resp.status_code != 200:
            raise Exception("Unknown response code: %s" % resp.status_code)

    # Posting data as a file
    ######################################################################
    # We don't want to post the payload as a form var, as the percent-encoding is
    # costly. We could send it as a raw post, but more HTTP clients seem to
    # support file uploading, so this is the more compatible choice.

    def _buildPostData(self, fobj, comp):
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
        headers, body = self._buildPostData(fobj, comp)

        r = self.client.post(self.syncURL()+method, data=body, headers=headers)
        if not badAuthRaises and r.status_code == 403:
            return False
        self.assertOk(r)

        buf = self.client.streamContent(r)
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
        self.postVars = dict(
            k=self.hkey,
            s=self.skey,
        )
        ret = self.req(
            "meta", io.BytesIO(json.dumps(dict(
                v=SYNC_VER, cv="ankidesktop,%s,%s"%(versionWithBuild(), platDesc()))).encode("utf8")),
            badAuthRaises=False)
        if not ret:
            # invalid auth
            return
        return json.loads(ret.decode("utf8"))

    def applyGraves(self, **kw):
        return self._run("applyGraves", kw)

    def applyChanges(self, **kw):
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
        runHook("sync", "download")
        localNotEmpty = self.col.db.scalar("select 1 from cards")
        self.col.close()
        cont = self.req("download")
        tpath = self.col.path + ".tmp"
        if cont == "upgradeRequired":
            runHook("sync", "upgradeRequired")
            return
        open(tpath, "wb").write(cont)
        # check the received file is ok
        d = DB(tpath)
        assert d.scalar("pragma integrity_check") == "ok"
        remoteEmpty = not d.scalar("select 1 from cards")
        d.close()
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
        self.col = col
        self.server = server

    def sync(self):
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
