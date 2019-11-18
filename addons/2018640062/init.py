from anki.lang import _
from aqt import dialogs, mw
from aqt.main import *


def onEmptyCards(self):
        """Method called by Tools>Empty Cards..."""
        self.progress.start(immediate=True)
        print("Calling new onEmptyCards")
        cids = set(self.col.emptyCids()) #change here to make a set
        if not cids:
            self.progress.finish()
            tooltip(_("No empty cards."))
            return
        print(f"Calling emptyCardReport from new onEmptyCards with cids {cids}")
        report = self.col.emptyCardReport(cids)
        self.progress.finish()
        part1 = ngettext("%d card", "%d cards", len(cids)) % len(cids)
        part1 = _("%s to delete:") % part1
        diag, box = showText(part1 + "\n\n" + report, run=False,
                geomKey="emptyCards")
        box.addButton(_("Delete Cards"), QDialogButtonBox.AcceptRole)
        box.button(QDialogButtonBox.Close).setDefault(True)
        def onDelete():
            nonlocal cids
            print(f"Calling new onDelete with cids {cids}")
            saveGeom(diag, "emptyCards")
            QDialog.accept(diag)
            self.checkpoint(_("Delete Empty"))
            # Beginning of changes
            nidToCidsToDelete = dict()
            for cid in cids:
                card = self.col.getCard(cid)
                note = card.note()
                nid = note.id
                if nid not in nidToCidsToDelete:
                    print(f"note {nid} not yet in nidToCidsToDelete. Thus adding it")
                    nidToCidsToDelete[nid] = set()
                else:
                    print(f"note {nid} already in nidToCidsToDelete.")
                nidToCidsToDelete[nid].add(cid)
                print(f"Adding card {cid} to note {nid}.")
            emptyNids = set()
            cardsOfEmptyNotes = set()
            for nid, cidsToDeleteOfNote in nidToCidsToDelete.items():
                note = self.col.getNote(nid)
                cidsOfNids = set([card.id for card in note.cards()])
                print(f"In note {nid}, the cards are {cidsOfNids}, and the cards to delete are {cidsToDeleteOfNote}")
                if cidsOfNids == cidsToDeleteOfNote:
                    print(f"Both sets are equal")
                    emptyNids.add(note.id)
                    cids -= cidsOfNids
                else:
                    print(f"Both sets are different")
            self.col.remCards(cids, notes = False)
            nidsWithTag = set(self.col.findNotes("tag:NoteWithNoCard"))
            print (f"emptyNids is {emptyNids}, nidsWithTag is {nidsWithTag}")
            for nid in emptyNids - nidsWithTag:
                note = self.col.getNote(nid)
                note.addTag("NoteWithNoCard")
                print(f"Adding tag to note {note.id}")
                note.flush()
            for nid in nidsWithTag - emptyNids:
                note = self.col.getNote(nid)
                note.delTag("NoteWithNoCard")
                print(f"Removing tag from note {note.id}")
                note.flush()
            if emptyNids:
                showWarning(f"""{len(emptyNids)} note(s) should have been deleted because they had no more cards. They now have the tag "NoteWithNoCard". Please go check them. Then either edit them to save their content, or delete them from the browser.""")
                browser = dialogs.open("Browser", mw)
                browser.form.searchEdit.lineEdit().setText("tag:NoteWithNoCard")
                browser.onSearchActivated()
            # end of changes
            tooltip(ngettext("%d card deleted.", "%d cards deleted.", len(cids)) % len(cids))
            self.reset()
        box.accepted.connect(onDelete)
        diag.show()
