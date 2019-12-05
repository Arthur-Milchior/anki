import os

from aqt.addons import AddonManager

from .config import getUserOption

defaultBaseNames = {"user_files", ".git", ".gitignore", ".svn"}

def backupUserFiles(self, sid):
    """Move user file's folder to a folder called files_backup in the add-on folder"""
    if not os.path.exists(self._userFilesBackupPath()):
        os.mkdir(self._userFilesBackupPath())
    for filename in getUserOption("base names", defaultBaseNames):
        p = os.path.join(self.addonsFolder(sid), filename)
        if os.path.exists(p):
            os.rename(p, os.path.join(self._userFilesBackupPath(), filename))

def restoreUserFiles(self, sid):
    """Move the back up of user file's folder to its normal location in
    the folder of the addon sid"""
    
    for filename in getUserOption("base names", defaultBaseNames):
        if os.path.exists(os.path.join(self._userFilesBackupPath(), filename)):
            os.rename(os.path.join(self._userFilesBackupPath(), filename), os.path.join(self.addonsFolder(sid), filename))

    if os.path.exists(self._userFilesBackupPath()):
        os.rmdir(self._userFilesBackupPath())

AddonManager.backupUserFiles = backupUserFiles
AddonManager.restoreUserFiles = restoreUserFiles
