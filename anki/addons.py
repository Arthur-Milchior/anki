# Copyright: Ankitects Pty Ltd and contributors
# -*- coding: utf-8 -*-
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
"""Module for managing add-ons.

An add-on here is defined as a subfolder in the add-on folder containing a file __init__.py
A managed add-on is an add-on whose folder's name contains only
digits.
"""

import io
import json
import os
import re
import traceback
import zipfile
from collections import defaultdict
from zipfile import ZipFile

import jsonschema
import markdown
from jsonschema.exceptions import ValidationError
from send2trash import send2trash

from anki.consts import appShared
from anki.incorporatedAddons import incorporatedAddonsDict
from anki.lang import _
from anki.sync import AnkiRequestsClient
from anki.utils import intTime


class AddonManager:
    """pm -- some anki.profiles.ProfileManager. Used to get the base folder."""
    ext = ".ankiaddon"
    _manifest_schema = {
        "type": "object",
        "properties": {
            "package": {"type": "string", "meta": False},
            "name": {"type": "string", "meta": True},
            "mod": {"type": "number", "meta": True},
            "conflicts": {
                "type": "array",
                "items": {"type": "string"},
                "meta": True
            }
        },
        "required": ["package", "name"]
    }

    def __init__(self, pm):
        self.dirty = False
        self.pm = pm

    def allAddons(self):
        """List of installed add-ons' folder name

        In alphabetical order of folder name. I.e. add-on number for downloaded add-ons.
        Reverse order if the environment variable  ANKIREVADDONS is set.

        A folder is an add-on folder iff it contains __init__.py.

        """
        addonFolders = []
        for addonFolder in os.listdir(self.addonsFolder()):
            path = self.addonsFolder(addonFolder)
            if not os.path.exists(os.path.join(path, "__init__.py")):
                continue
            addonFolders.append(addonFolder)
        addonFolders.sort()
        if os.getenv("ANKIREVADDONS", ""):
            addonFolders = reversed(addonFolders)
        return addonFolders

    def managedAddons(self):
        """List of managed add-ons.

        In alphabetical order of folder name. I.e. add-on number for downloaded add-ons.
        Reverse order if the environment variable  ANKIREVADDONS is set.
        """
        return [addonFolderName for addonFolderName in self.allAddons()
                if re.match(r"^\d+$", addonFolderName)]

    def addonsFolder(self, dir=None):
        """Path to a folder.

        To the add-on folder by default, guaranteed to exists.
        If dir is set, then the path to the add-on dir, not guaranteed
        to exists

        dir -- TODO
        """

        root = self.mw.pm.addonFolder()
        if not dir:
            return root
        return os.path.join(root, dir)


    def loadAddons(self):
        """List of errors due to add-on loading"""
        errors = []
        for dir in self.allAddons():
            meta = self.addonMeta(dir)
            if meta.get("disabled"):
                continue
            if self.isIncorporated(dir):
                continue
            self.dirty = True
            try:
                __import__(dir)
            except:
                errors.append((traceback.format_exc(), meta))
        return errors

    def isIncorporated(self, dir):
        return dir in incorporatedAddonsDict or (re.match(r"^\d+$", dir) and int(dir) in incorporatedAddonsDict)

    # Metadata
    ######################################################################

    def _addonMetaPath(self, dir):
        """Path of the configuration of the addon dir"""
        return os.path.join(self.addonsFolder(dir), "meta.json")

    def addonMeta(self, dir):
        """The config of add-on dir if it exists, empty config otherwise"""
        path = self._addonMetaPath(dir)
        try:
            with open(path, encoding="utf8") as file:
                return json.load(file)
        except:
            return dict()

    def writeAddonMeta(self, dir, meta):
        path = self._addonMetaPath(dir)
        with open(path, "w", encoding="utf8") as file:
            json.dump(meta, file)

    def isEnabled(self, dir):
        meta = self.addonMeta(dir)
        return not meta.get('disabled')

    def toggleEnabled(self, dir, enable=None):
        """The list of add-ons which are disabled because they are
        incompatible with add-on currently enabled.

        """
        meta = self.addonMeta(dir)
        enabled = enable if enable is not None else meta.get("disabled")
        conflicting = None
        if enabled is True:
            conflicting = self._disableConflicting(dir)

        meta['disabled'] = not enabled
        self.writeAddonMeta(dir, meta)
        return addons

    def addonName(self, dir):
        """The name of the addon.

        It is found either in "name" parameter of the configuration in
        directory dir of the add-on directory.
        Otherwise dir is used."""
        return self.addonMeta(dir).get("name", dir)

    def annotatedName(self, dir):
        buf = self.addonName(dir)
        if not self.isEnabled(dir):
            buf += _(" (disabled)")
        if self.isIncorporated(dir):
            buf += _(" (incorporated)")
        return buf

    # Installing and deleting add-ons
    ######################################################################

    def install(self, file, manifest=None):
        """Install add-on from path or file-like object. Metadata is read
        from the manifest file, with keys overriden by supplying a 'manifest'
        dictionary"""
        try:
            zfile = ZipFile(file)
        except zipfile.BadZipfile:
            return False, "zip"

        with zfile:
            file_manifest = self.readManifestFile(zfile)
            if manifest:
                file_manifest.update(manifest)
            manifest = file_manifest
            if not manifest:
                return False, "manifest"
            package = manifest["package"]
            conflicts = manifest.get("conflicts", [])
            found_conflicts = self._disableConflicting(package,
                                                       conflicts)
            meta = self.addonMeta(package)
            self._install(package, zfile)
        schema = self._manifest_schema["properties"]
        manifest_meta = {k: value for k, value in manifest.items()
                         if k in schema and schema[k]["meta"]}
        meta.update(manifest_meta)
        self.writeAddonMeta(package, meta)

        return True, meta["name"], found_conflicts

    def _install(self, dir, zfile):
        # previously installed?
        base = self.addonsFolder(dir)
        if os.path.exists(base):
            self.backupUserFiles(dir)
            if not self.deleteAddon(dir): # To install, previous version should be deleted. If it can't be deleted for an unkwown reason, we try to put everything back in previous state.
                self.restoreUserFiles(dir)
                return

        os.mkdir(base)
        self.restoreUserFiles(dir)

        # extract
        for name in zfile.namelist():
            if name.endswith("/"):
                # folder; ignore
                continue

            path = os.path.join(base, name)
            # skip existing user files
            if os.path.exists(path) and name.startswith("user_files/"):
                continue
            zfile.extract(name, base)


    # Conflict resolution
    ######################################################################

    def addonConflicts(self, dir):
        return self.addonMeta(dir).get("conflicts", [])

    def allAddonConflicts(self):
        all_conflicts = defaultdict(list)
        for dir in self.allAddons():
            if not self.isEnabled(dir):
                continue
            conflicts = self.addonConflicts(dir)
            for other_dir in conflicts:
                all_conflicts[other_dir].append(dir)
        return all_conflicts

    def _disableConflicting(self, dir, conflicts=None):
        conflicts = conflicts or self.addonConflicts(dir)

        installed = self.allAddons()
        found = [conflict for conflict in conflicts if conflict in installed and self.isEnabled(conflict)]
        found.extend(self.allAddonConflicts().get(dir, []))
        if not found:
            return []

        for package in found:
            self.toggleEnabled(package, enable=False)

        return found

    # Installing and deleting add-ons
    ######################################################################

    def readManifestFile(self, zfile):
        try:
            with zfile.open("manifest.json") as file:
                data = json.loads(file.read())
            jsonschema.validate(data, self._manifest_schema)
            # build new manifest from recognized keys
            schema = self._manifest_schema["properties"]
            manifest = {key: data[key] for key in data.keys() & schema.keys()}
        except (KeyError, json.decoder.JSONDecodeError, ValidationError):
            # raised for missing manifest, invalid json, missing/invalid keys
            return {}
        return manifest

    def deleteAddon(self, dir):
        """Delete the add-on folder of add-on dir. Returns True on success"""
        try:
            send2trash(self.addonsFolder(dir))
            return True
        except OSError as e:
            return False

    # Processing local add-on files
    ######################################################################

    def processPackages(self, paths):
        log = []
        errs = []
        for path in paths:
            base = os.path.basename(path)
            ret = self.install(path)
            if ret[0] is False:
                if ret[1] == "zip":
                    msg = _("Corrupt add-on file.")
                elif ret[1] == "manifest":
                    msg = _("Invalid add-on manifest.")
                else:
                    msg = "Unknown error: {}".format(ret[1])
                errs.append(_("Error installing <i>%(base)s</i>: %(error)s"
                              % dict(base=base, error=msg)))
            else:
                log.append(_("Installed %(name)s" % dict(name=ret[1])))
                if ret[2]:
                    log.append(_("The following conflicting add-ons were disabled:") + " " + " ".join(ret[2]))
        return log, errs

    # Downloading
    ######################################################################
    def installIds(self, rets):
        """A pair, with messae about what was downloaded, and a list of error messages.

        Takes the values returned by pyQt's download of add-ons and install them."""
        log = []
        errs = []
        for addonNumber, ret in rets.items():
            if ret[0] == "error":
                errs.append(_("Error downloading %(id)s: %(error)s") % dict(id=addonNumber, error=ret[1]))
                continue
            data, fname = ret
            fname = fname.replace("_", " ")
            name = os.path.splitext(fname)[0]
            ret = self.install(io.BytesIO(data),
                               manifest={"package": str(addonNumber), "name": name,
                                         "mod": intTime()})
            if ret[0] is False:
                if ret[1] == "zip":
                    msg = _("Corrupt add-on file.")
                elif ret[1] == "manifest":
                    msg = _("Invalid add-on manifest.")
                else:
                    msg = "Unknown error: {}".format(ret[1])
                errs.append(_("Error downloading %(id)s: %(error)s") % dict(
                    id=addonNumber, error=msg))
            else:
                log.append(_("Downloaded %(fname)s" % dict(fname=name)))
                if ret[2]:
                    log.append(_("The following conflicting add-ons were disabled:") + " " + " ".join(ret[2]))

        return log, errs

    # Updating
    ######################################################################

    def checkForUpdates(self):
        """The list of add-ons not up to date. Compared to the server's information."""
        client = AnkiRequestsClient()

        # ..of enabled items downloaded from ankiweb
        addons = [dir
                  for dir in self.managedAddons()
                  if not self.addonMeta(dir).get("disabled")]
        mods = []
        while addons:
            chunk = addons[:25]
            del addons[:25]
            mods.extend(self._getModTimes(client, chunk))
        return self._updatedIds(mods)


    def _getModTimes(self, client, chunk):
        """The list of (id,mod time) for add-ons whose id is in chunk.

        client -- an ankiRequestsclient
        chunck -- a list of add-on number"""
        resp = client.get(
            aqt.appShared + "updates/" + ",".join(chunk))
        if resp.status_code == 200:
            return resp.json()
        else:
            raise Exception("Unexpected response code from AnkiWeb: {}".format(resp.status_code))

    def _updatedIds(self, mods):
        """Given a list of (id,last mod on server), returns the sublist of
        add-ons not up to date."""
        updated = [str(dir)
                   for dir, ts in mods
                   if self.addonMeta(str(dir)).get("mod", 0) < (ts or 0)]
        return updated

    # Add-on Config
    ######################################################################

    """Dictionnary from modules to function to apply when add-on
    manager is called on this config."""
    _configButtonActions = {}
    """Dictionnary from modules to function to apply when add-on
    manager ends an update. Those functions takes the configuration,
    parsed as json, in argument."""
    _configUpdatedActions = {}

    def addonConfigDefaults(self, dir):
        """The (default) configuration of the addon whose
        name/directory is dir.

        This file should be called config.json"""
        path = os.path.join(self.addonsFolder(dir), "config.json")
        try:
            with open(path, encoding="utf8") as file:
                return json.load(file)
        except:
            return None

    def addonConfigHelp(self, dir):
        """The configuration of this addon, obtained as configuration"""
        path = os.path.join(self.addonsFolder(dir), "config.md")
        if os.path.exists(path):
            with open(path, encoding="utf-8") as file:
                return markdown.markdown(file.read())
        else:
            return ""


    def addonFromModule(self, module):
        """Returns the string of module before the first dot"""
        return module.split(".",1)[0]

    def configAction(self, addon):
        """The function to call for addon when add-on manager ask for
        edition of its configuration."""
        return self._configButtonActions.get(addon)

    def configUpdatedAction(self, addon):
        """The function to call for addon when add-on edition has been done
        using add-on manager.

        """
        return self._configUpdatedActions.get(addon)

    # Add-on Config API
    ######################################################################


    def getConfig(self, module):
        """The current configuration.

        More precisely:
        -None if the module has no file config.json
        -otherwise the union of:
        --default config from config.json
        --the last version of the config, as saved in meta

        Note that if you edited the dictionary obtained from the
        configuration file without calling self.writeConfig(module,
        config), then getConfig will not return current config

        """
        addon = self.addonFromModule(module)
        # get default config
        config = self.addonConfigDefaults(addon)
        if config is None:
            return None
        # merge in user's keys
        meta = self.addonMeta(addon)
        userConf = meta.get("config", {})
        config.update(userConf)
        return config

    def setConfigAction(self, module, fn):
        """Change the action of add-on manager for the edition of the
        current add-ons config.

        Each time the user click in the add-on manager on the button
        "config" button, fn is called. Unless fn is falsy, in which
        case the standard procedure is used

        Keyword arguments:
        module -- the module/addon considered
        fn -- a function taking no argument, or a falsy value
        """
        addon = self.addonFromModule(module)
        self._configButtonActions[addon] = fn

    def setConfigUpdatedAction(self, module, fn):
        """Allow a function to add on new configurations.

        Each time the configuration of module is modified in the
        add-on manager, fn is called on the new configuration.

        Keyword arguments:
        module -- __name__ from module's code
        fn -- A function taking the configuration, parsed as json, in
        """
        addon = self.addonFromModule(module)
        self._configUpdatedActions[addon] = fn

    def writeConfig(self, module, conf):
        """The config for the module whose name is module  is now conf"""
        addon = self.addonFromModule(module)
        meta = self.addonMeta(addon)
        meta['config'] = conf
        self.writeAddonMeta(addon, meta)

    # user_files
    ######################################################################

    def _userFilesPath(self, sid):
        """The path of the user file's folder."""
        return os.path.join(self.addonsFolder(sid), "user_files")

    def _userFilesBackupPath(self):
        """A path to use for back-up. It's independent of the add-on number."""
        return os.path.join(self.addonsFolder(), "files_backup")

    def backupUserFiles(self, sid):
        """Move user file's folder to a folder called files_backup in the add-on folder"""
        userFilePath = self._userFilesPath(sid)
        if os.path.exists(userFilePath):
            os.rename(userFilePath, self._userFilesBackupPath())

    def restoreUserFiles(self, sid):
        """Move the back up of user file's folder to its normal location in
        the folder of the addon sid"""
        userFilePath = self._userFilesPath(sid)
        bp = self._userFilesBackupPath()
        # did we back up userFiles?
        if not os.path.exists(bp):
            return
        os.rename(bp, userFilePath)

    # Web Exports
    ######################################################################

    _webExports = {}

    def setWebExports(self, module, pattern):
        addon = self.addonFromModule(module)
        self._webExports[addon] = pattern

    def getWebExports(self, addon):
        return self._webExports.get(addon)
