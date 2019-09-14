# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
import os

from anki.utils import isMac, isWin


class ProfileManager:
    def __init__(self, base=None):
        # instantiate base folder
        self._setBaseFolder(base)

    # Base creation
    ######################################################################

    def ensureBaseExists(self):
        try:
            self._ensureExists(self.base)
        except:
            # can't translate, as lang not initialized, and qt may not be
            print("unable to create base folder")
            QMessageBox.critical(
                None, "Error", """\
Anki could not create the folder %s. Please ensure that location is not \
read-only and you have permission to write to it. If you cannot fix this \
issue, please see the documentation for information on running Anki from \
a flash drive.""" % self.base)
            raise

    # Folder migration
    ######################################################################

    def _oldFolderLocation(self):
        if isMac:
            return os.path.expanduser("~/Documents/Anki")
        elif isWin:
            from aqt.winpaths import get_personal
            return os.path.join(get_personal(), "Anki")
        else:
            p = os.path.expanduser("~/Anki")
            if os.path.isdir(p):
                return p
            return os.path.expanduser("~/Documents/Anki")

    def maybeMigrateFolder(self):
        oldBase = self._oldFolderLocation()

        if oldBase and not os.path.exists(self.base) and os.path.isdir(oldBase):
            shutil.move(oldBase, self.base)

    # Folder handling
    ######################################################################

    def addonFolder(self):
        """The path to the add-on folder.

        Guarenteed to exists.
        It is in base, not in profile"""
        return self._ensureExists(os.path.join(self.base, "addons21"))

    # Helpers
    ######################################################################

    def _setBaseFolder(self, cmdlineBase):
        if cmdlineBase:
            self.base = os.path.abspath(cmdlineBase)
        elif os.environ.get("ANKI_BASE"):
            self.base = os.path.abspath(os.environ["ANKI_BASE"])
        else:
            self.base = self._defaultBase()
            self.maybeMigrateFolder()
        self.ensureBaseExists()

    def _ensureExists(self, path):
        """Create the path if it does not exists. Return the path"""
        if not os.path.exists(path):
            os.makedirs(path)
        return path
