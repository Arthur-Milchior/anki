import csv
import os
from aqt.main import *
from ..config import getUserOption
from anki.utils import intTime, splitFields
import datetime


def onRemNotes(self, col, nids, reason=""):
        """Append (reason,deletion time id, deletion time readable, id, model id, fields) to the end of deleted_long.txt

        This is done for each id of nids.
        This method is added to the hook remNotes; and executed on note deletion.
        """
        #difference: another file is used, and it logs more data, with more separators
        path = os.path.join(self.pm.profileFolder(), getUserOption("deleted file",True))#difference: file name
        existed = os.path.exists(path)
        newline = '' if getUserOption("deletion log in CSV", True) else None
        with open(path, "a", newline = newline) as f:
            if getUserOption("deletion log in CSV", True):
                writer = csv.writer(f)
            if not existed:
                f.write("reason\tdeletion time id\thuman deletion time\tid\tmid\tfields\t\n")#difference: more fields
            for id, mid, flds in col.db.execute(
                    "select id, mid, flds from notes where id in %s" %
                ids2str(nids)):
                fields = splitFields(flds)
                if getUserOption("deletion log in CSV", True):
                    writer.writerow([reason,str(intTime()),str(datetime.datetime.now()),str(id), str(mid)]+fields)
                else:
                    f.write(("\t".join([str(id), str(mid)] + fields)+"\n").encode("utf8"))

AnkiQt.onRemNotes = onRemNotes
