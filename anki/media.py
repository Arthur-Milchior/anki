# -*- coding: utf-8 -*-
# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
"""
self.dir media's directory
self.col the collection
self.db the database for media (note that it's different from the collection database)

Table media:
fname -- the name of the file in media directory
csum -- checksum of the content of the file last time it was checked. Null indicate deleted file
mtime -- time of last modification
dirty -- 0 if the data is not dirty, 1 if it is dirty

table meta: a single entry, with:
dirMod -- date of the last modification of the media directory according to the os
lastUsn -- int synchronisation number of the last synchronisation
"""
import io
import json
import os
import pathlib
import re
import sys
import traceback
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import zipfile

from anki.consts import *
from anki.db import DB, DBError
from anki.lang import _
from anki.latex import mungeQA
from anki.utils import checksum, isMac, isWin


class MediaManager:
    """
    _dir -- the directory of media. Unless server is given to the constructor, in this cas it's None. Directory is changed to it during synchronization, and then changed back to previous directory.
    _oldcwd -- the working directory when media manager is created. The directory is changed to this value when the MediaManager is closed. If server is given in the constructor, then it's None.

"""

    """Captures the argument foo of [sound:foo]"""
    soundRegexps = [r"(?i)(\[sound:(?P<fname>[^]]+)\])"]
    """Captures the argument foo of <img src=foo bar>, ignoring quotes around foo."""
    imgRegexps = [
        # src element quoted case
        r"(?i)(<img[^>]* src=(?P<str>[\"'])(?P<fname>[^>]+?)(?P=str)[^>]*>)",
        # unquoted case
        r"(?i)(<img[^>]* src=(?!['\"])(?P<fname>[^ >]+)[^>]*?>)",
    ]
    regexps = soundRegexps + imgRegexps

    def __init__(self, col, server):
        """
        TODO

        server -- always false in Anki"""
        self.col = col
        if server:
            self._dir = None
            return
        # media directory
        self._dir = re.sub(r"(?i)\.(anki2)$", ".media", self.col.path)
        if not os.path.exists(self._dir):
            os.makedirs(self._dir)
        try:
            self._oldcwd = os.getcwd()
        except OSError:
            # cwd doesn't exist
            self._oldcwd = None
        try:
            os.chdir(self._dir)
        except OSError:
            raise Exception("invalidTempFolder")
        # change database
        self.connect()

    def connect(self):
        """Ensure the existence of a database in current format, connected in self.db."""
        if self.col.server:
            return
        path = self.dir()+".db2"
        create = not os.path.exists(path)
        os.chdir(self._dir)
        self.db = DB(path)
        if create:
            self._initDB()
        self.maybeUpgrade()

    def _initDB(self):
        self.db.executescript("""
create table media (
 fname text not null primary key,
 csum text,           -- null indicates deleted file
 mtime int not null,  -- zero if deleted
 dirty int not null
);

create index idx_media_dirty on media (dirty);

create table meta (dirMod int, lastUsn int); insert into meta values (0, 0);
""")

    def maybeUpgrade(self):
        """Upgrade database in old format to current format."""
        oldpath = self.dir()+".db"
        if os.path.exists(oldpath):
            self.db.execute('attach "../collection.media.db" as old')
            try:
                self.db.execute("""
    insert into media
     select media.fname, csum, mod, ifnull((select 1 from log l2 where l2.fname=oldMedia.fname limit 1), 0) as dirty
     from old.media oldMedia
     left outer join old.log l using (fname)
     union
     select fname, null, 0, 1 from old.log where type=1;""")
                self.db.execute("delete from meta")
                self.db.execute("""
    insert into meta select dirMod, usn from old.meta
    """)
                self.db.commit()
            except Exception as e:
                # if we couldn't import the old db for some reason, just start
                # anew
                self.col.log("failed to import old media db:"+traceback.format_exc())
            self.db.execute("detach old")
            npath = "../collection.media.db.old"
            if os.path.exists(npath):
                os.unlink(npath)
            os.rename("../collection.media.db", npath)

    def close(self):
        """Close database connection.

        don't do anything if server is truthy.
        change dir back to old working dir"""
        if self.col.server:
            return
        self.db.close()
        self.db = None
        # change cwd back to old location
        if self._oldcwd:
            try:
                os.chdir(self._oldcwd)
            except:
                # may have been deleted
                pass

    def _deleteDB(self):
        """Delete connected DB, connect to a new one"""
        path = self.db._path
        self.close()
        os.unlink(path)
        self.connect()

    def dir(self):
        """The directory of media"""
        return self._dir

    def _isFAT32(self):
        if not isWin:
            return
        # pylint: disable=import-error
        import win32api, win32file
        try:
            name = win32file.GetVolumeNameForVolumeMountPoint(self._dir[:3])
        except:
            # mapped & unmapped network drive; pray that it's not vfat
            return
        if win32api.GetVolumeInformation(name)[4].lower().startswith("fat"):
            return True

    # Adding media
    ##########################################################################
    # opath must be in unicode

    def addFile(self, opath):
        """Copy the file at path opath to collection.media,

        Name may be changed to ensure unicity.
        """
        with open(opath, "rb") as file:
            return self.writeData(opath, file.read())

    def writeData(self, opath, data, typeHint=None):
        """Add data in the file of name opath in media dir.

        Only file name of opath is keep.
        If file as no extension, and it is jpg or png according to typeHint, then add extension
        Add a number extension if this name already exists

        """
        # if fname is a full path, use only the basename
        fname = os.path.basename(opath)

        # if it's missing an extension and a type hint was provided, use that
        if not os.path.splitext(fname)[1] and typeHint:
            # mimetypes is returning '.jpe' even after calling .init(), so we'll do
            # it manually instead
            typeMap = {
                "image/jpeg": ".jpg",
                "image/png": ".png",
            }
            if typeHint in typeMap:
                fname += typeMap[typeHint]

        # make sure we write it in NFC form (pre-APFS Macs will autoconvert to NFD),
        # and return an NFC-encoded reference
        fname = unicodedata.normalize("NFC", fname)
        # ensure it's a valid filename
        base = self.cleanFilename(fname)
        (root, ext) = os.path.splitext(base)
        def repl(match):
            return " (%d)" % (int(match.group(1))+1)
        # find the first available name
        csum = checksum(data)
        while True:
            fname = root + ext
            path = os.path.join(self.dir(), fname)
            # if it doesn't exist, copy it directly
            if not os.path.exists(path):
                with open(path, "wb") as file:
                    file.write(data)
                return fname
            # if it's identical, reuse
            with open(path, "rb") as file:
                if checksum(file.read()) == csum:
                    return fname
            # otherwise, increment the index in the filename
            reg = r" \((\d+)\)$"
            if not re.search(reg, root):
                root = root + " (1)"
            else:
                root = re.sub(reg, repl, root)

    # String manipulation
    ##########################################################################

    def filesInStr(self, mid, string, includeRemote=False):
        """The list of media's path in the string.

        Medias starting with _ are treated as any media.

        Each clozes are expanded in every possible ways. It allows
        for different strings to be created.

        Concerning the part of the string related to LaTeX, media are
        generated as explained in latex._imgLink's docstring

        Keyword arguments:
        mid -- the id of the model of the note whose string is considered
        string -- A string, which corresponds to a field of a note
        includeRemote -- whether the list should include contents which is with http, https or ftp
        """
        filesInStr = []
        model = self.col.models.get(mid, orNone=False)
        strings = []
        if model.isCloze() and "{{c" in string:
            # if the field has clozes in it, we'll need to expand the
            # possibilities so we can render latex
            strings = self._expandClozes(string)
        else:
            strings = [string]
        for string in strings:
            # handle latex
            string = mungeQA(string, None, None, model, None, self.col)
            # extract filenames
            for reg in self.regexps:
                for match in re.finditer(reg, string):
                    fname = match.group("fname")
                    isLocal = not re.match("(https?|ftp)://", fname.lower())
                    if isLocal or includeRemote:
                        filesInStr.append(fname)
        return filesInStr

    def _expandClozes(self, string):
        """The list of all strings, where the clozes are expanded.

        For each cloze number n, there is a string with cloze n replaced by [...] or by [hint], and every other clozes replaced by their text.

        There is also a text where each cloze are replaced by their value; i.e. the answer"""
        ords = set(re.findall(r"{{c(\d+)::.+?}}", string))
        #The set of clozes occurring in the string
        from anki.template.template import clozeReg
        def qrepl(match):
            """The text by which the cloze m must be replaced in the question."""
            if match.group(4):
                return "[%s]" % match.group(4)
            else:
                return "[...]"
        def arepl(match):
            """The text by which the cloze m must be replaced in the answer."""
            return match.group(2)
        strings = [ #Replace every other clozes by their content
            (re.sub(clozeReg%".+?", "\\2", #Replace the cloze number #ord by the deletion
                    re.sub(clozeReg%ord, qrepl, string)))
            for ord in ords]
        strings.append(re.sub(clozeReg%".+?", arepl, string))
        return strings

    def transformNames(self, txt, func):
        """Apply func to all subtext matching the regexps txt."""
        for reg in self.regexps:
            txt = re.sub(reg, func, txt)
        return txt

    def strip(self, txt):
        """Delete all text matching the regexps txt"""
        for reg in self.regexps:
            txt = re.sub(reg, "", txt)
        return txt

    def escapeImages(self, string, unescape=False):
        """Replace local image url by replacing special character by the
        escape %xx or reciprocally depending on unescape value."""
        if unescape:
            fn = urllib.parse.unquote
        else:
            fn = urllib.parse.quote
        def repl(match):
            tag = match.group(0)
            fname = match.group("fname")
            if re.match("(https?|ftp)://", fname):
                return tag
            return tag.replace(fname, fn(fname))
        for reg in self.imgRegexps:
            string = re.sub(reg, repl, string)
        return string

    # Rebuilding DB
    ##########################################################################

    def check(self, local=None):
        "Return (missingFiles, unusedFiles, warnings)."
        mdir = self.dir()
        # gather all media references in NFC form
        allRefs = set()
        for nid, mid, flds in self.col.db.execute("select id, mid, flds from notes"):
            noteRefs = self.filesInStr(mid, flds)
            # check the refs are in NFC
            for file in noteRefs:
                # if they're not, we'll need to fix them first
                if file != unicodedata.normalize("NFC", file):
                    self._normalizeNoteRefs(nid)
                    noteRefs = self.filesInStr(mid, flds)
                    break
            allRefs.update(noteRefs)
        # loop through media folder
        unused = []
        if local is None:
            files = os.listdir(mdir)
        else:
            files = local
        renamedFiles = False
        dirFound = False
        warnings = []
        for file in files:
            if not local:
                if not os.path.isfile(file):
                    # ignore directories
                    dirFound = True
                    continue
            if file.startswith("_"):
                # leading _ says to ignore file
                continue

            if self.hasIllegal(file):
                name = file.encode(sys.getfilesystemencoding(), errors="replace")
                name = str(name, sys.getfilesystemencoding())
                warnings.append(
                    _("Invalid file name, please rename: %s") % name)
                continue

            nfcFile = unicodedata.normalize("NFC", file)
            # we enforce NFC fs encoding on non-macs
            if not isMac and not local:
                if file != nfcFile:
                    # delete if we already have the NFC form, otherwise rename
                    if os.path.exists(nfcFile):
                        os.unlink(file)
                        renamedFiles = True
                    else:
                        os.rename(file, nfcFile)
                        renamedFiles = True
                    file = nfcFile
            # compare
            if nfcFile not in allRefs:
                unused.append(file)
            else:
                allRefs.discard(nfcFile)
        # if we renamed any files to nfc format, we must rerun the check
        # to make sure the renamed files are not marked as unused
        if renamedFiles:
            return self.check(local=local)
        nohave = [ref for ref in allRefs if not ref.startswith("_")]
        # make sure the media DB is valid
        try:
            self.findChanges()
        except DBError:
            self._deleteDB()

        if dirFound:
            warnings.append(
                _("Anki does not support files in subfolders of the collection.media folder."))
        return (nohave, unused, warnings)

    def _normalizeNoteRefs(self, nid):
        note = self.col.getNote(nid)
        for index, fld in enumerate(note.fields):
            nfc = unicodedata.normalize("NFC", fld)
            if nfc != fld:
                note.fields[index] = nfc
        note.flush()

    # Copying on import
    ##########################################################################

    def have(self, fname):
        """Whether a fil with name fname exists in the media directory"""
        return os.path.exists(os.path.join(self.dir(), fname))

    # Illegal characters and paths
    ##########################################################################

    _illegalCharReg = re.compile(r'[][><:"/?*^\\|\0\r\n]')

    def stripIllegal(self, str):
        """str, without its illegal characters"""
        return re.sub(self._illegalCharReg, "", str)

    def hasIllegal(self, str):
        """Whether str contains a illegal character.

        Either according to _illegalCharReg, or because it can't be encoded if file system encoding"""
        if re.search(self._illegalCharReg, str):
            return True
        try:
            str.encode(sys.getfilesystemencoding())
        except UnicodeEncodeError:
            return True
        return False

    def cleanFilename(self, fname):
        fname = self.stripIllegal(fname)
        fname = self._cleanWin32Filename(fname)
        fname = self._cleanLongFilename(fname)
        if not fname:
            fname = "renamed"

        return fname

    def _cleanWin32Filename(self, fname):
        if not isWin:
            return fname

        # deal with things like con/prn/etc
        path = pathlib.WindowsPath(fname)
        if path.is_reserved():
            fname = "renamed" + fname
            assert not pathlib.WindowsPath(fname).is_reserved()

        return fname

    def _cleanLongFilename(self, fname):
        # a fairly safe limit that should work on typical windows
        # paths and on eCryptfs partitions, even with a duplicate
        # suffix appended
        namemax = 136

        if isWin:
            pathmax = 240
        else:
            pathmax = 1024

        # cap namemax based on absolute path
        dirlen = len(os.path.dirname(os.path.abspath(fname)))
        remaining = pathmax - dirlen
        namemax = min(remaining, namemax)
        assert namemax > 0

        if len(fname) > namemax:
            head, ext = os.path.splitext(fname)
            headmax = namemax - len(ext)
            head = head[0:headmax]
            fname = head + ext
            assert(len(fname) <= namemax)

        return fname

    # Tracking changes
    ##########################################################################

    def findChanges(self):
        "Scan the media folder if it's changed, and note any changes in the db."
        if self._changed():
            self._logChanges()

    def haveDirty(self):
        """Whether the database has at least one dirty element"""
        return self.db.scalar("select 1 from media where dirty=1 limit 1")

    def _mtime(self, path):
        """Time of most recent content modification of file at path.

        Expressed in seconds."""
        return int(os.stat(path).st_mtime)

    def _checksum(self, path):
        """Checksum of file at path"""
        with open(path, "rb") as file:
            return checksum(file.read())

    def _changed(self):
        "Return dir mtime if it has changed since the last findChanges()"
        # doesn't track edits, but user can add or remove a file to update
        mod = self.db.scalar("select dirMod from meta")
        mtime = self._mtime(self.dir())
        if not self._isFAT32() and mod and mod == mtime:
            return False
        return mtime

    def _logChanges(self):
        (added, removed) = self._changes()
        media = ( [(file, self._checksum(file), mtime, 1)
                   for file, mtime in added ]
                  + [(file, None, 0, 1)
                     for file in removed])
        # update media db
        self.db.executemany("insert or replace into media values (?,?,?,?)",
                            media)
        self.db.execute("update meta set dirMod = ?", self._mtime(self.dir()))
        self.db.commit()

    def _changes(self):
        self.cache = {}
        for (name, csum, mod) in self.db.execute(
            "select fname, csum, mtime from media where csum is not null"):
            # previous entries may not have been in NFC form
            normname = unicodedata.normalize("NFC", name)
            self.cache[normname] = [csum, mod, False]
        added = []
        removed = []
        # loop through on-disk files
        with os.scandir(self.dir()) as it:
            for file in it:
                # ignore folders and thumbs.db
                if file.is_dir():
                    continue
                if file.name.lower() == "thumbs.db":
                    continue
                # and files with invalid chars
                if self.hasIllegal(file.name):
                    continue
                # empty files are invalid; clean them up and continue
                sz = file.stat().st_size
                if not sz:
                    os.unlink(file.name)
                    continue
                if sz > 100*1024*1024:
                    self.col.log("ignoring file over 100MB", file.name)
                    continue
                # check encoding
                normname = unicodedata.normalize("NFC", file.name)
                if not isMac:
                    if file.name != normname:
                        # wrong filename encoding which will cause sync errors
                        if os.path.exists(normname):
                            os.unlink(file.name)
                        else:
                            os.rename(file.name, normname)
                else:
                    # on Macs we can access the file using any normalization
                    pass

                # newly added?
                mtime = int(file.stat().st_mtime)
                if normname not in self.cache:
                    added.append((normname, mtime))
                else:
                    # modified since last time?
                    if mtime != self.cache[normname][1]:
                        # and has different checksum?
                        if self._checksum(normname) != self.cache[normname][0]:
                            added.append((normname, mtime))
                    # mark as used
                    self.cache[normname][2] = True
        # look for any entries in the cache that no longer exist on disk
        for (normname, value) in list(self.cache.items()):
            if not value[2]:
                removed.append(normname)
        return added, removed

    # Syncing-related
    ##########################################################################

    def lastUsn(self):
        return self.db.scalar("select lastUsn from meta")

    def setLastUsn(self, usn):
        self.db.execute("update meta set lastUsn = ?", usn)
        self.db.commit()

    def syncInfo(self, fname):
        """(Checkusm, dirty number) from media with name fname"""
        ret = self.db.first(
            "select csum, dirty from media where fname=?", fname)
        return ret or (None, 0)

    def markClean(self, fnames):
        for fname in fnames:
            self.db.execute(
                "update media set dirty=0 where fname=?", fname)

    def syncDelete(self, fname):
        """Delete the file fname if it is not in media directory."""
        if os.path.exists(fname):
            os.unlink(fname)
        self.db.execute("delete from media where fname=?", fname)

    def mediaCount(self):
        """Number of media according to database"""
        return self.db.scalar(
            "select count() from media where csum is not null")

    def dirtyCount(self):
        """Number of dirty media according to database.

        (couting the one potentially deleted)"""
        return self.db.scalar(
            "select count() from media where dirty=1")

    def forceResync(self):
        self.db.execute("delete from media")
        self.db.execute("update meta set lastUsn=0,dirMod=0")
        self.db.commit()
        self.db.setAutocommit(True)
        self.db.execute("vacuum")
        self.db.execute("analyze")
        self.db.setAutocommit(False)

    # Media syncing: zips
    ##########################################################################

    def mediaChangesZip(self):
        """
        The pair with:
        * A string encoding a zip files with:
        ** media to upload
        ** _meta: a json list associating to each name (as in zip) to
        the real name of the file
        * list of media considered
        """
        zipFile = io.BytesIO()
        zip = zipfile.ZipFile(zipFile, "w", compression=zipfile.ZIP_DEFLATED)

        fnames = []
        # meta is list of (fname, zipname), where zipname of None
        # is a deleted file
        meta = []
        sz = 0#sum of the size of the media.

        # loop over dirty medias. At most SYNC_ZIP_COUNT = 25 elements
        for index, (fname, csum) in enumerate(self.db.execute(
                        "select fname, csum from media where dirty=1"
                        " limit %d"%SYNC_ZIP_COUNT)):

            fnames.append(fname)
            normname = unicodedata.normalize("NFC", fname)

            if csum:
                self.col.log("+media zip", fname)
                zip.write(fname, str(index))
                meta.append((normname, str(index)))
                sz += os.path.getsize(fname)
            else:
                self.col.log("-media zip", fname)
                meta.append((normname, ""))

            if sz >= SYNC_ZIP_SIZE:
                break

        zip.writestr("_meta", json.dumps(meta))
        zip.close()
        return zipFile.getvalue(), fnames

    def addFilesFromZip(self, zipData):
        """
        Copy each file from zipData (except _meta) to the media
        folder, and add those files to the media database. Rename the
        file according to _meta.

        zipData -- A byte tream containing a zipfile, containing:
        * _meta, a file containing a json dict associtaing to each name of file in zip (except meta) a name to be used in the media folder
        * arbitrary fields to save in the media folder
        """
        zipFile = io.BytesIO(zipData)
        zip = zipfile.ZipFile(zipFile, "r")
        media = []
        # get meta info first
        meta = json.loads(zip.read("_meta").decode("utf8"))
        # then loop through all files
        cnt = 0
        for info in zip.infolist():
            if info.filename == "_meta":
                # ignore previously-retrieved meta
                continue
            else:
                data = zip.read(info)
                csum = checksum(data)
                name = meta[info.filename]
                # normalize name
                name = unicodedata.normalize("NFC", name)
                # save file
                with open(name, "wb") as file:
                    file.write(data)
                # update db
                media.append((name, csum, self._mtime(name), 0))
                cnt += 1
        if media:
            self.db.executemany(
                "insert or replace into media values (?,?,?,?)", media)
        return cnt
