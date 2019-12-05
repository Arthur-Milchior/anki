from anki.find import Finder
from anki.media import *
from anki.notes import Note
from aqt import dialogs, mw

# oldCheck = MediaManager.check
# def check(self, local=None):
#     (missingFiles, unusedFiles) = oldCheck(self, local)
#     nids = set()
#     query = """select id from notes where flds like "" """

def check(self, local=None):
    "Return (missingFiles, unusedFiles)."
    mdir = self.dir()
    # gather all media references in NFC form
    allRefs = set()
    refsToNid = dict() # this dic is new
    for nid, mid, flds in self.col.db.execute("select id, mid, flds from notes"):
        noteRefs = self.filesInStr(mid, flds)
        # check the refs are in NFC
        for f in noteRefs:
            # if they're not, we'll need to fix them first
            if f != unicodedata.normalize("NFC", f):
                self._normalizeNoteRefs(nid)
                noteRefs = self.filesInStr(mid, flds)
                break
        # new. update refsToNid
        for f in noteRefs:
            if f not in refsToNid:
                refsToNid[f] = set()
            refsToNid[f].add(nid)
        # end new
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
    # NEW: A line here removed because it was a bug
    # New
    finder = Finder(mw.col)
    alreadyMissingNids = finder.findNotes("tag:MissingMedia")
    nidsOfMissingRefs = set()
    for ref in allRefs:
        nidsOfMissingRefs.update(refsToNid[ref])
        #print(f"nidsOfMissingRefs is now {nidsOfMissingRefs}")

    for nid in nidsOfMissingRefs:
        if nid not in alreadyMissingNids:
            print(f"missing nid {nid}")
            note = Note(mw.col, id = nid)
            note.addTag("MissingMedia")
            note.flush()

    for nid in alreadyMissingNids:
        if nid not in nidsOfMissingRefs:
            print(f"not missing anymore nid {nid}")
            note = Note(mw.col, id = nid)
            note.delTag("MissingMedia")
            note.flush()
    # end new

    # make sure the media DB is valid
    try:
        self.findChanges()
    except DBError:
        self._deleteDB()
    if dirFound:
        warnings.append(
            _("Anki does not support files in subfolders of the collection.media folder."))
    if allRefs:
        browser = dialogs.open("Browser", mw)
        browser.form.searchEdit.lineEdit().setText("tag:MissingMedia")
        browser.onSearchActivated()
    return (allRefs, unused, warnings)



MediaManager.check = check
print("Missing Media imported")
