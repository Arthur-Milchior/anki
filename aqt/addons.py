# Copyright: Ankitects Pty Ltd and contributors
# -*- coding: utf-8 -*-
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
"""Module for managing add-ons.

An add-on here is defined as a subfolder in the add-on folder containing a file __init__.py
A managed add-on is an add-on whose folder's name contains only
digits.
"""

import json
import re
import sys

import aqt
import aqt.forms
from anki.addons import AddonManager as AM
from anki.lang import _, ngettext
from aqt.downloader import downloadIds
from aqt.qt import *
from aqt.utils import (askUser, getFile, isWin, openFolder, openLink,
                       restoreGeom, restoreSplitter, saveGeom, saveSplitter,
                       showInfo, showWarning, tooltip)


class AddonManager(AM):
    """
    dirty -- whether an add-on is loaded
    mw -- the main window
    """

    def __init__(self, mw):
        self.mw = mw
        super().__init__(mw.pm)
        self.dirty = False
        self.mw.form.actionAdd_ons.triggered.connect(self.onAddonsDialog)
        sys.path.insert(0, self.addonsFolder())

    def loadAddons(self):
        for tb, meta in super().loadAddons():
            showWarning(_("""\
An add-on you installed failed to load. If problems persist, please \
go to the Tools>Add-ons menu, and disable or delete the add-on.

When loading '%(name)s':
%(traceback)s
""") % dict(name=meta.get("name", dir), traceback=tb))

    def onAddonsDialog(self):
        AddonsDialog(self)

    # Installing and deleting add-ons
    ######################################################################

    def deleteAddon(self, dir):
        """Delete the add-on folder of add-on dir. Returns True on success"""
        r = super().deleteAddon(dir)
        if not r:
            showWarning(_("Unable to update or delete add-on. Please start Anki while holding down the shift key to temporarily disable add-ons, then try again.\n\nDebug info: %s") % e,
                        textFormat="plain")
        return r

    # Processing local add-on files
    ######################################################################

    def processPackages(self, paths):
        self.mw.executeInProgress(lambda:super().processPackages(paths))

    # Downloading
    ######################################################################

    def downloadIds(self, ids):
        return self.mw.executeInProgress(lambda:self.installIds(downloadIds(ids, self.mw)))

    # Updating
    ######################################################################

    def checkForUpdates(self):
        """The list of add-ons not up to date. Compared to the server's information."""
        self.mw.executeInProgress(super().checkForUpdates)

    def onCheckForUpdates(self, stateNoUpdateAvailable=True):
        """Whether an update did occur"""
        try:
            updated = self.checkForUpdates()
        except Exception as e:
            showWarning(_("Please check your internet connection.") + "\n\n" + str(e),
                        textFormat="plain")
            return

        if not updated:
            if stateNoUpdateAvailable:
                tooltip(_("No updates available."))
        else:
            names = [self.addonName(d) for d in updated]
            if askUser(_("Update the following add-ons?") +
                               "\n" + "\n".join(names)):
                log, errs = self.downloadIds(updated)
                if log:
                    log_html = "<br>".join(log)
                    if len(log) == 1:
                        tooltip(log_html, parent=self)
                    else:
                        showInfo(log_html, parent=self, textFormat="rich")
                if errs:
                    showWarning("\n\n".join(errs), parent=self, textFormat="plain")

                return True

# Add-ons Dialog
######################################################################

class AddonsDialog(QDialog):

    def __init__(self, addonsManager):
        self.mgr = addonsManager
        self.mw = addonsManager.mw

        super().__init__(self.mw)

        self.form = aqt.forms.addons.Ui_Dialog()
        self.form.setupUi(self)
        self.form.getAddons.clicked.connect(self.onGetAddons)
        self.form.installFromFile.clicked.connect(self.onInstallFiles)
        self.form.checkForUpdates.clicked.connect(self.onCheckForUpdates)
        self.form.toggleEnabled.clicked.connect(self.onToggleEnabled)
        self.form.viewPage.clicked.connect(self.onViewPage)
        self.form.viewFiles.clicked.connect(self.onViewFiles)
        self.form.delete_2.clicked.connect(self.onDelete)
        self.form.config.clicked.connect(self.onConfig)
        self.form.addonList.itemDoubleClicked.connect(self.onConfig)
        self.form.addonList.currentRowChanged.connect(self._onAddonItemSelected)
        self.setAcceptDrops(True)
        self.redrawAddons()
        restoreGeom(self, "addons")
        self.show()

    def dragEnterEvent(self, event):
        mime = event.mimeData()
        if not mime.hasUrls():
            return None
        urls = mime.urls()
        ext = self.mgr.ext
        if all(url.toLocalFile().endswith(ext) for url in urls):
            event.acceptProposedAction()

    def dropEvent(self, event):
        mime = event.mimeData()
        paths = []
        for url in mime.urls():
            path = url.toLocalFile()
            if os.path.exists(path):
                paths.append(path)
        self.onInstallFiles(paths)

    def reject(self):
        saveGeom(self, "addons")
        return QDialog.reject(self)

    def redrawAddons(self):
        addonList = self.form.addonList
        mgr = self.mgr
        
        self.addons = [(mgr.annotatedName(addon), addon) for addon in mgr.allAddons()]
        self.addons.sort()

        selected = set(self.selectedAddons())
        addonList.clear()
        for name, dir in self.addons:
            item = QListWidgetItem(name, addonList)
            if not mgr.isEnabled(dir) or mgr.isIncorporated(dir):
                item.setForeground(Qt.gray)
            if dir in selected:
                item.setSelected(True)

        addonList.repaint()

    def _onAddonItemSelected(self, row_int):
        try:
            addon = self.addons[row_int][1]
        except IndexError:
            addon = ''
        self.form.viewPage.setEnabled(bool(re.match(r"^\d+$", addon)))
        self.form.config.setEnabled(bool(self.mgr.getConfig(addon) or
                                         self.mgr.configAction(addon)))

    def selectedAddons(self):
        idxs = [selectedIndex.row() for selectedIndex in self.form.addonList.selectedIndexes()]
        return [self.addons[idx][1] for idx in idxs]

    def onlyOneSelected(self):
        dirs = self.selectedAddons()
        if len(dirs) != 1:
            showInfo(_("Please select a single add-on first."))
            return
        return dirs[0]

    def onToggleEnabled(self):
        for dir in self.selectedAddons():
            self.mgr.toggleEnabled(dir)
        self.redrawAddons()

    def onViewPage(self):
        addon = self.onlyOneSelected()
        if not addon:
            return
        if re.match(r"^\d+$", addon):
            openLink(aqt.appShared + "info/{}".format(addon))
        else:
            showWarning(_("Add-on was not downloaded from AnkiWeb."))

    def onViewFiles(self):
        # if nothing selected, open top level folder
        selected = self.selectedAddons()
        if not selected:
            openFolder(self.mgr.addonsFolder())
            return

        # otherwise require a single selection
        addon = self.onlyOneSelected()
        if not addon:
            return
        path = self.mgr.addonsFolder(addon)
        openFolder(path)

    def onDelete(self):
        selected = self.selectedAddons()
        if not selected:
            return
        if not askUser(ngettext("Delete the %(num)d selected add-on?",
                                "Delete the %(num)d selected add-ons?",
                                len(selected)) %
                               dict(num=len(selected))):
            return
        for dir in selected:
            if not self.mgr.deleteAddon(dir):
                break
        self.form.addonList.clearSelection()
        self.redrawAddons()

    def onGetAddons(self):
        GetAddons(self)

    def onInstallFiles(self, paths=None):
        if not paths:
            key = (_("Packaged Anki Add-on") + " (*{})".format(self.mgr.ext))
            paths = getFile(self, _("Install Add-on(s)"), None, key,
                            key="addons", multi=True)
            if not paths:
                return False

        log, errs = self.mgr.processPackages(paths)

        if log:
            log_html = "<br>".join(log)
            if len(log) == 1:
                tooltip(log_html, parent=self)
            else:
                showInfo(log_html, parent=self, textFormat="rich")
        if errs:
            msg = _("Please report this to the respective add-on author(s).")
            showWarning("<br><br>".join(errs + [msg]), parent=self, textFormat="rich")

        self.redrawAddons()

    def onCheckForUpdates(self):
        if self.mgr.onCheckForUpdates():
            self.redrawAddons()

    def onConfig(self):
        """Assuming a single addon is selected, either:
        -if this add-on as a special config, set using setConfigAction, with a
        truthy value, call this config.
        -otherwise, call the config editor on the current config of
        this add-on"""

        addon = self.onlyOneSelected()
        if not addon:
            return

        # does add-on manage its own config?
        act = self.mgr.configAction(addon)
        if act:
            act()
            return

        conf = self.mgr.getConfig(addon)
        if conf is None:
            showInfo(_("Add-on has no configuration."))
            return

        ConfigEditor(self, addon, conf)


# Fetching Add-ons
######################################################################

class GetAddons(QDialog):

    def __init__(self, dlg):
        QDialog.__init__(self, dlg)
        self.addonsDlg = dlg
        self.mgr = dlg.mgr
        self.mw = self.mgr.mw
        self.form = aqt.forms.getaddons.Ui_Dialog()
        self.form.setupUi(self)
        button = self.form.buttonBox.addButton(
            _("Browse Add-ons"), QDialogButtonBox.ActionRole)
        button.clicked.connect(self.onBrowse)
        restoreGeom(self, "getaddons", adjustSize=True)
        self.exec_()
        saveGeom(self, "getaddons")

    def onBrowse(self):
        openLink(aqt.appShared + "addons/2.1")

    def accept(self):
        # get codes
        try:
            ids = [int(addonNumber) for addonNumber in self.form.code.text().split()]
        except ValueError:
            showWarning(_("Invalid code."))
            return

        log, errs = self.mgr.downloadIds(ids)

        if log:
            log_html = "<br>".join(log)
            if len(log) == 1:
                tooltip(log_html, parent=self)
            else:
                showInfo(log_html, parent=self, textFormat="rich")
        if errs:
            showWarning("\n\n".join(errs), textFormat="plain")

        self.addonsDlg.redrawAddons()
        QDialog.accept(self)

# Editing config
######################################################################

class ConfigEditor(QDialog):

    def __init__(self, dlg, addon, conf):
        super().__init__(dlg)
        self.addon = addon
        self.conf = conf
        self.mgr = dlg.mgr
        self.form = aqt.forms.addonconf.Ui_Dialog()
        self.form.setupUi(self)
        restore = self.form.buttonBox.button(QDialogButtonBox.RestoreDefaults)
        restore.clicked.connect(self.onRestoreDefaults)
        self.setupFonts()
        self.updateHelp()
        self.updateText(self.conf)
        restoreGeom(self, "addonconf")
        restoreSplitter(self.form.splitter, "addonconf")
        self.show()

    def onRestoreDefaults(self):
        default_conf = self.mgr.addonConfigDefaults(self.addon)
        self.updateText(default_conf)
        tooltip(_("Restored defaults"), parent=self)

    def setupFonts(self):
        font_mono = QFontDatabase.systemFont(QFontDatabase.FixedFont)
        font_mono.setPointSize(font_mono.pointSize() + 1)
        self.form.editor.setFont(font_mono)

    def updateHelp(self):
        txt = self.mgr.addonConfigHelp(self.addon)
        if txt:
            self.form.label.setText(txt)
        else:
            self.form.scrollArea.setVisible(False)

    def updateText(self, conf):
        self.form.editor.setPlainText(
            json.dumps(conf, ensure_ascii=False, sort_keys=True,
                       indent=4, separators=(',', ': ')))

    def onClose(self):
        saveGeom(self, "addonconf")
        saveSplitter(self.form.splitter, "addonconf")

    def reject(self):
        self.onClose()
        super().reject()

    def accept(self):
        """
        Transform the new config into json, and either:
        -pass it to the special config function, set using
        setConfigUpdatedAction if it exists,
        -or save it as configuration otherwise.

        If the config is not proper json, show an error message and do
        nothing.
        -if the special config is falsy, just save the value
        """
        txt = self.form.editor.toPlainText()
        try:
            new_conf = json.loads(txt)
        except Exception as e:
            showInfo(_("Invalid configuration: ") + repr(e))
            return

        if not isinstance(new_conf, dict):
            showInfo(_("Invalid configuration: top level object must be a map"))
            return

        if new_conf != self.conf:
            self.mgr.writeConfig(self.addon, new_conf)
            # does the add-on define an action to be fired?
            act = self.mgr.configUpdatedAction(self.addon)
            if act:
                act(new_conf)

        self.onClose()
        super().accept()
