# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

import argparse
import builtins
import getpass
import gettext
import locale
import sys
import tempfile

import anki.lang
from anki import version as _version
from anki.consts import (  # imported because those variables were originally in this file
    appChanges, appDonate, appHelpSite, appShared, appUpdate, appWebsite)
from anki.lang import langDir
from anki.utils import checksum, isLin, isMac
from aqt import about, addcards, browser, editcurrent, preferences, stats
from aqt.qt import *

appVersion=_version
mw = None # set on init

moduleDir = os.path.split(os.path.dirname(os.path.abspath(__file__)))[0]

try:
    import aqt.forms
except ImportError as e:
    if "forms" in str(e):
        print("If you're running from git, did you run build_ui.sh?")
        print()
    raise


# Dialog manager
##########################################################################
# ensures only one copy of the window is open at once, and provides
# a way for dialogs to clean up asynchronously when collection closes

# A window object must contain:
# - windowState():
# - activateWindow()
# - raise_()
# - Either:
# -- If it can be closed immediatly:
# --- silentlyClose must exists and be truthy,
# --- have a function close() defined
# -- Or, if some actions must be done before closing:
# --- define a method closeWithCallback(callback)
# --- This method should ensure a safe closure of the window
# --- and then call callback

# A window class must contain:
# - A constructor, which return a window object.

# to integrate a new window:
# - add it to _dialogs
# - have the window opened via aqt.dialogs.open(<name>, self)
# - have a method reopen(*args), called if the user ask to open the window a second time. Arguments passed are the same than for original opening.

#- make preferences modal? cmd+q does wrong thing



class DialogManager:
    """Associating to a window name a pair (as a list...)

    The element associated to WindowName Is composed of:
    First element is the class to use to create the window WindowName.
    Second element is the instance of this window, if it is already open. None otherwise
    """
    _dialogs = {
        "AddCards": [addcards.AddCards, None],
        "Browser": [browser.Browser, None],
        "EditCurrent": [editcurrent.EditCurrent, None],
        "DeckStats": [stats.DeckStats, None],
        "About": [about.show, None],
        "Preferences": [preferences.Preferences, None],
    }


    def open(self, name, *args, **kwargs):
        """Open a window of kind name.

        Open (and show) the one already opened, if it
        exists. Otherwise a new one.

        keyword arguments:
        args -- values passed to the opener.
        name -- the name of the window to open
        """
        (creator, instance) = self._dialogs[name]
        if instance:
            if instance.windowState() & Qt.WindowMinimized:
                instance.setWindowState(instance.windowState() & ~Qt.WindowMinimized)
            instance.activateWindow()
            instance.raise_()
            if hasattr(instance,"reopen"):
                instance.reopen(*args, **kwargs)
            return instance
        else:
            instance = creator(*args, **kwargs)
            self._dialogs[name][1] = instance
            return instance

    def markClosed(self, name):
        """Window name is now considered as closed. It removes the element from _dialogs."""
        self._dialogs[name] = [self._dialogs[name][0], None]

    def allClosed(self):
        """
        Whether all windows (except the main window) are marked as
        closed.
        """
        return not any(windowInstance for (windowClass, windowInstance) in self._dialogs.values())

    def closeAll(self, onsuccess):
        """Close all windows (except the main one). Call onsuccess when it's done.

        Return True if some window needed closing.
        None otherwise

        Keyword arguments:
        onsuccess -- the function to call when the last window is closed.
        """

        # can we close immediately?
        if self.allClosed():
            onsuccess()
            return

        # ask all windows to close and await a reply
        for (name, (creator, instance)) in self._dialogs.items():
            if not instance:
                continue

            def callback():
                """Call onsuccess if all window (except main) are closed."""
                if self.allClosed():
                    onsuccess()
                else:
                    # still waiting for others to close
                    pass

            if getattr(instance, "silentlyClose", False):
                instance.close()
                callback()
            else:
                instance.closeWithCallback(callback)

        return True

dialogs = DialogManager()


# Language handling
##########################################################################
# Qt requires its translator to be installed before any GUI widgets are
# loaded, and we need the Qt language to match the gettext language or
# translated shortcuts will not work.

_gtrans = None
_qtrans = None

def setupLang(pm, app, force=None):
    global _gtrans, _qtrans
    try:
        locale.setlocale(locale.LC_ALL, '')
    except:
        pass
    lang = force or pm.meta["defaultLang"]
    dir = langDir()
    # gettext
    _gtrans = gettext.translation(
        'anki', dir, languages=[lang], fallback=True)
    def fn__(arg):
        print("accessing _ without importing from anki.lang will break in the future")
        print("".join(traceback.format_stack()[-2]))
        from anki.lang import _
        return _(arg)
    def fn_ngettext(a, b, c):
        print("accessing ngettext without importing from anki.lang will break in the future")
        print("".join(traceback.format_stack()[-2]))
        from anki.lang import ngettext
        return ngettext(a, b, c)

    builtins.__dict__['_'] = fn__
    builtins.__dict__['ngettext'] = fn_ngettext
    anki.lang.setLang(lang, local=False)
    if lang in ("he","ar","fa"):
        app.setLayoutDirection(Qt.RightToLeft)
    else:
        app.setLayoutDirection(Qt.LeftToRight)
    # qt
    _qtrans = QTranslator()
    if _qtrans.load("qt_" + lang, dir):
        app.installTranslator(_qtrans)

# App initialisation
##########################################################################

class AnkiApp(QApplication):

    # Single instance support on Win32/Linux
    ##################################################

    appMsg = pyqtSignal(str)

    KEY = "anki"+checksum(getpass.getuser())
    TMOUT = 30000

    def __init__(self, argv):
        QApplication.__init__(self, argv)
        self._argv = argv

    def secondInstance(self):
        # we accept only one command line argument. If it's missing, send
        # a blank screen to just raise the existing window
        opts, args = parseArgs(self._argv)
        buf = "raise"
        if args and args[0]:
            buf = os.path.abspath(args[0])
        if self.sendMsg(buf):
            print("Already running; reusing existing instance.")
            return True
        else:
            # send failed, so we're the first instance or the
            # previous instance died
            QLocalServer.removeServer(self.KEY)
            self._srv = QLocalServer(self)
            self._srv.newConnection.connect(self.onRecv)
            self._srv.listen(self.KEY)
            return False

    def sendMsg(self, txt):
        sock = QLocalSocket(self)
        sock.connectToServer(self.KEY, QIODevice.WriteOnly)
        if not sock.waitForConnected(self.TMOUT):
            # first instance or previous instance dead
            return False
        sock.write(txt.encode("utf8"))
        if not sock.waitForBytesWritten(self.TMOUT):
            # existing instance running but hung
            QMessageBox.warning(None, "Anki Already Running",
                                 "If the existing instance of Anki is not responding, please close it using your task manager, or restart your computer.")

            sys.exit(1)
        sock.disconnectFromServer()
        return True

    def onRecv(self):
        sock = self._srv.nextPendingConnection()
        if not sock.waitForReadyRead(self.TMOUT):
            sys.stderr.write(sock.errorString())
            return
        path = bytes(sock.readAll()).decode("utf8")
        self.appMsg.emit(path)
        sock.disconnectFromServer()

    # OS X file/url handler
    ##################################################

    def event(self, evt):
        if evt.type() == QEvent.FileOpen:
            self.appMsg.emit(evt.file() or "raise")
            return True
        return QApplication.event(self, evt)

def parseArgs(argv):
    "Returns (opts, args)."
    # py2app fails to strip this in some instances, then anki dies
    # as there's no such profile
    if isMac and len(argv) > 1 and argv[1].startswith("-psn"):
        argv = [argv[0]]
    parser = argparse.ArgumentParser(description="Anki " + appVersion)
    parser.usage = "%(prog)s [OPTIONS] [file to import]"
    parser.add_argument("-b", "--base", help="path to base folder", default="")
    parser.add_argument("-p", "--profile", help="profile name to load", default="")
    parser.add_argument("-l", "--lang", help="interface language (en, de, etc)")
    return parser.parse_known_args(argv[1:])

def setupGL(pm):
    if isMac:
        return

    mode = pm.glMode()

    # work around pyqt loading wrong GL library
    if isLin:
        import ctypes
        ctypes.CDLL('libGL.so.1', ctypes.RTLD_GLOBAL)

    # catch opengl errors
    def msgHandler(type, ctx, msg):
        if "Failed to create OpenGL context" in msg:
            QMessageBox.critical(None, "Error", "Error loading '%s' graphics driver. Please start Anki again to try next driver." % mode)
            pm.nextGlMode()
            return
        else:
            print("qt:", msg)
    qInstallMessageHandler(msgHandler)

    if mode == "auto":
        return
    elif isLin:
        os.environ["QT_XCB_FORCE_SOFTWARE_OPENGL"] = "1"
    else:
        os.environ["QT_OPENGL"] = mode

def run(argv=None):
    try:
        _run(argv=argv)
    except Exception as e:
        traceback.print_exc()
        QMessageBox.critical(None, "Startup Error",
                             "Please notify support of this error:\n\n"+
                             traceback.format_exc())

def _run(argv=None, exec=True):
    """Start AnkiQt application or reuse an existing instance if one exists.

    If the function is invoked with exec=False, the AnkiQt will not enter
    the main event loop - instead the application object will be returned.

    The 'exec' and 'argv' arguments will be useful for testing purposes.

    If no 'argv' is supplied then 'sys.argv' will be used.
    """
    global mw

    if argv is None:
        argv = sys.argv

    # parse args
    opts, args = parseArgs(argv)

    # profile manager
    from aqt.profiles import ProfileManager
    pm = ProfileManager(opts.base)

    # gl workarounds
    setupGL(pm)

    # opt in to full hidpi support?
    if not os.environ.get("ANKI_NOHIGHDPI"):
        QCoreApplication.setAttribute(Qt.AA_EnableHighDpiScaling)

    # Opt into software rendering. Useful for buggy systems.
    if os.environ.get("ANKI_SOFTWAREOPENGL"):
        QCoreApplication.setAttribute(Qt.AA_UseSoftwareOpenGL)

    # create the app
    QCoreApplication.setApplicationName("Anki")
    QGuiApplication.setDesktopFileName("anki.desktop")
    app = AnkiApp(argv)
    if app.secondInstance():
        # we've signaled the primary instance, so we should close
        return

    # disable icons on mac; this must be done before window created
    if isMac:
        app.setAttribute(Qt.AA_DontShowIconsInMenus)

    # proxy configured?
    from urllib.request import proxy_bypass, getproxies
    if 'http' in getproxies():
        # if it's not set up to bypass localhost, we'll
        # need to disable proxies in the webviews
        if not proxy_bypass("127.0.0.1"):
            print("webview proxy use disabled")
            proxy = QNetworkProxy()
            proxy.setType(QNetworkProxy.NoProxy)
            QNetworkProxy.setApplicationProxy(proxy)

    # we must have a usable temp dir
    try:
        tempfile.gettempdir()
    except:
        QMessageBox.critical(
            None, "Error", """\
No usable temporary folder found. Make sure C:\\temp exists or TEMP in your \
environment points to a valid, writable folder.""")
        return

    pm.setupMeta()

    if opts.profile:
        pm.openProfile(opts.profile)

    # i18n
    setupLang(pm, app, opts.lang)

    if isLin and pm.glMode() == "auto":
        from aqt.utils import gfxDriverIsBroken
        if gfxDriverIsBroken():
            pm.nextGlMode()
            QMessageBox.critical(None, "Error", "Your video driver is incompatible. Please start Anki again, and Anki will switch to a slower, more compatible mode.")
            sys.exit(1)

    # load the main window
    import aqt.main
    mw = aqt.main.AnkiQt(app, pm, opts, args)
    if exec:
        app.exec()
    else:
        return app
