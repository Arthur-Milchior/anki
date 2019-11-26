# -*- coding: utf-8 -*-
# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

# some add-ons expect json to be in the utils module
import copy
import functools
import json  # pylint: disable=unused-import
import locale
import math
import os
import platform
import random
import re
import shutil
import string
import subprocess
import sys
import tempfile
import time
import traceback
from contextlib import contextmanager
from hashlib import sha1
from html.entities import name2codepoint

from anki.lang import _, ngettext

# Time handling
##############################################################################

def intTime(scale=1):
    "The time in integer seconds. Pass scale=1000 to get milliseconds."
    return int(time.time()*scale)

timeTable = {
    "years": lambda number: ngettext("%s year", "%s years", number),
    "months": lambda number: ngettext("%s month", "%s months", number),
    "days": lambda number: ngettext("%s day", "%s days", number),
    "hours": lambda number: ngettext("%s hour", "%s hours", number),
    "minutes": lambda number: ngettext("%s minute", "%s minutes", number),
    "seconds": lambda number: ngettext("%s second", "%s seconds", number),
    }

inTimeTable = {
    "years": lambda number: ngettext("in %s year", "in %s years", number),
    "months": lambda number: ngettext("in %s month", "in %s months", number),
    "days": lambda number: ngettext("in %s day", "in %s days", number),
    "hours": lambda number: ngettext("in %s hour", "in %s hours", number),
    "minutes": lambda number: ngettext("in %s minute", "in %s minutes", number),
    "seconds": lambda number: ngettext("in %s second", "in %s seconds", number),
    }

def shortTimeFmt(type):
    return {
#T: year is an abbreviation for year. %s is a number of years
    "years": _("%sy"),
#T: m is an abbreviation for month. %s is a number of months
    "months": _("%smo"),
#T: d is an abbreviation for day. %s is a number of days
    "days": _("%sd"),
#T: h is an abbreviation for hour. %s is a number of hours
    "hours": _("%sh"),
#T: m is an abbreviation for minute. %s is a number of minutes
    "minutes": _("%sm"),
#T: s is an abbreviation for second. %s is a number of seconds
    "seconds": _("%ss"),
    }[type]

def fmtTimeSpan(time, pad=0, point=0, short=False, inTime=False, unit=99):
    "Return a string representing a time span (eg '2 days')."
    (type, point) = optimalPeriod(time, point, unit)
    time = convertSecondsTo(time, type)
    if not point:
        time = int(round(time))
    if short:
        fmt = shortTimeFmt(type)
    else:
        if inTime:
            fmt = inTimeTable[type](_pluralCount(time, point))
        else:
            fmt = timeTable[type](_pluralCount(time, point))
    timestr = "%%%(a)d.%(point)df" % {'a': pad, 'point': point}
    return locale.format_string(fmt % timestr, time)

def optimalPeriod(time, point, unit):
    if abs(time) < 60 or unit < 1:
        type = "seconds"
        point -= 1
    elif abs(time) < 3600 or unit < 2:
        type = "minutes"
    elif abs(time) < 60 * 60 * 24 or unit < 3:
        type = "hours"
    elif abs(time) < 60 * 60 * 24 * 30 or unit < 4:
        type = "days"
    elif abs(time) < 60 * 60 * 24 * 365 or unit < 5:
        type = "months"
        point += 1
    else:
        type = "years"
        point += 1
    return (type, max(point, 0))

def convertSecondsTo(seconds, type):
    if type == "seconds":
        return seconds
    elif type == "minutes":
        return seconds / 60
    elif type == "hours":
        return seconds / 3600
    elif type == "days":
        return seconds / 86400
    elif type == "months":
        return seconds / 2592000
    elif type == "years":
        return seconds / 31536000
    assert False

def _pluralCount(time, point):
    if point:
        return 2
    return math.floor(time)

# Locale
##############################################################################

def fmtPercentage(float_value, point=1):
    "Return float with percentage sign"
    fmt = '%' + "0.%(point)df" % {'point': point}
    return locale.format_string(fmt, float_value) + "%"

def fmtFloat(float_value, point=1):
    "Return a string with decimal separator according to current locale"
    fmt = '%' + "0.%(point)df" % {'point': point}
    return locale.format_string(fmt, float_value)

# HTML
##############################################################################
reComment = re.compile("(?s)<!--.*?-->")
reStyle = re.compile("(?si)<style.*?>.*?</style>")
reScript = re.compile("(?si)<script.*?>.*?</script>")
reTag = re.compile("(?s)<.*?>")
reEnts = re.compile(r"&#?\w+;")
reMedia = re.compile("(?i)<img[^>]+src=[\"']?([^\"'>]+)[\"']?[^>]*>")

def stripHTML(text):
    """Removes comment, style, script, and all tags. Replace entities by their unicode value"""
    text = reComment.sub("", text)
    text = reStyle.sub("", text)
    text = reScript.sub("", text)
    text = reTag.sub("", text)
    text = entsToTxt(text)
    return text

def stripHTMLMedia(text):
    """Removes comment, style, script, and all tags. Replace images by
their url. Replace entities by their unicode value"""
    text = reMedia.sub(" \\1 ", text)
    return stripHTML(text)

def minimizeHTML(text):
    "Correct Qt's verbose bold/underline/etc."
    text = re.sub('<span style="font-weight:600;">(.*?)</span>', '<b>\\1</b>',
               text)
    text = re.sub('<span style="font-style:italic;">(.*?)</span>', '<i>\\1</i>',
               text)
    text = re.sub('<span style="text-decoration: underline;">(.*?)</span>',
               '<u>\\1</u>', text)
    return text

def htmlToTextLine(text):
    """Transform a field into a html value to show in the browser list of cards."""
    text = text.replace("<br>", " ")
    text = text.replace("<br />", " ")
    text = text.replace("<div>", " ")
    text = text.replace("\n", " ")
    text = re.sub(r"\[sound:[^]]+\]", "", text)
    text = re.sub(r"\[\[type:[^]]+\]\]", "", text)
    text = stripHTMLMedia(text)
    text = text.strip()
    return text

def entsToTxt(html):
    """html, where entities are replaced by their unicode character."""
    # entitydefs defines nbsp as \xa0 instead of a standard space, so we
    # replace it first
    html = html.replace("&nbsp;", " ")
    def fixup(match):
        text = match.group(0)
        if text[:2] == "&#":
            # character reference
            try:
                if text[:3] == "&#x":
                    return chr(int(text[3:-1], 16))
                else:
                    return chr(int(text[2:-1]))
            except ValueError:
                pass
        else:
            # named entity
            try:
                text = chr(name2codepoint[text[1:-1]])
            except KeyError:
                pass
        return text # leave as is
    return reEnts.sub(fixup, html)

def bodyClass(col, card):
    """A string, containing "card", card position, and whether it's
    nightMode"""
    bodyclass = "card card%d" % (card.ord+1)
    if col.conf.get("nightMode"):
        bodyclass += " nightMode"
    return bodyclass

# IDs
##############################################################################

def hexifyID(id):
    return "%x" % int(id)

def dehexifyID(id):
    return int(id, 16)

def ids2str(ids):
    """Given a list of integers, return a string '(int1,int2,...)'."""
    return "(%s)" % ",".join(str(id) for id in ids)

def timestampID(db, table):
    "Return a non-conflicting timestamp for table."
    # be careful not to create multiple objects without flushing them, or they
    # may share an ID.
    time = intTime(1000)
    while db.scalar("select id from %s where id = ?" % table, time):
        time += 1
    return time

def maxID(db):
    "Return the first safe ID to use."
    now = intTime(1000)
    for tbl in "cards", "notes":
        now = max(now, db.scalar("select max(id) from %s" % tbl) or 0)
    return now + 1

# used in ankiweb
def base62(num, extra=""):
    table = string.ascii_letters + string.digits + extra
    buf = ""
    while num:
        num, mod = divmod(num, len(table))
        buf = table[mod] + buf
    return buf

_base91_extra_chars = "!#$%&()*+,-./:;<=>?@[]^_`{|}~"
def base91(num):
    # all printable characters minus quotes, backslash and separators
    return base62(num, _base91_extra_chars)

def guid64():
    "Return a base91-encoded 64bit random number."
    return base91(random.randint(0, 2**64-1))

# increment a guid by one, for note type conflicts
def incGuid(guid):
    return _incGuid(guid[::-1])[::-1]

def _incGuid(guid):
    table = string.ascii_letters + string.digits + _base91_extra_chars
    idx = table.index(guid[0])
    if idx + 1 == len(table):
        # overflow
        guid = table[0] + _incGuid(guid[1:])
    else:
        guid = table[idx+1] + guid[1:]
    return guid

# Fields
##############################################################################

def joinFields(list):
    return "\x1f".join(list)

def splitFields(string):
    """Transform the fields as in the database in a list of field"""
    return string.split("\x1f")

# Checksums
##############################################################################

def checksum(data):
    if isinstance(data, str):
        data = data.encode("utf-8")
    return sha1(data).hexdigest()

def fieldChecksum(data):
    # 32 bit unsigned number from first 8 digits of sha1 hash
    return int(checksum(stripHTMLMedia(data).encode("utf-8"))[:8], 16)

# Temp files
##############################################################################

_tmpdir = None

def tmpdir():
    "A reusable temp folder which we clean out on each program invocation."
    global _tmpdir
    if not _tmpdir:
        def cleanup():
            shutil.rmtree(_tmpdir)
        import atexit
        atexit.register(cleanup)
        _tmpdir = os.path.join(tempfile.gettempdir(), "anki_temp")
    if not os.path.exists(_tmpdir):
        os.mkdir(_tmpdir)
    return _tmpdir

def tmpfile(prefix="", suffix=""):
    (fd, name) = tempfile.mkstemp(dir=tmpdir(), prefix=prefix, suffix=suffix)
    os.close(fd)
    return name

def namedtmp(name, rm=True):
    "Return tmpdir+name. Deletes any existing file."
    path = os.path.join(tmpdir(), name)
    if rm:
        try:
            os.unlink(path)
        except (OSError, IOError):
            pass
    return path

# Cmd invocation
##############################################################################

@contextmanager
def noBundledLibs():
    oldlpath = os.environ.pop("LD_LIBRARY_PATH", None)
    yield
    if oldlpath is not None:
        os.environ["LD_LIBRARY_PATH"] = oldlpath

def call(argv, wait=True, **kwargs):
    """Execute a command and return its return code.

    If wait is set to False, don't wait and return immediatly 0
    (i.e. correct exit number)
    return -1 if executing the command raises OSErrors.

    If the returned value is considered as a Boolean, it returns
    whether the call returned an error.

    Keyword arguments
    argv -- the command to execute
    wait -- whether to wait for the end of the call before returning
    **kwargs -- arguments given to subprocess.Popen.
    """
    # ensure we don't open a separate window for forking process on windows
    if isWin:
        si = subprocess.STARTUPINFO()
        try:
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        except:
            # pylint: disable=no-member
            si.dwFlags |= subprocess._subprocess.STARTF_USESHOWWINDOW
    else:
        si = None
    # run
    try:
        with noBundledLibs():
            o = subprocess.Popen(argv, startupinfo=si, **kwargs)
    except OSError:
        # command not found
        return -1
    # wait for command to finish
    if wait:
        while 1:
            try:
                ret = o.wait()
            except OSError:
                # interrupted system call
                continue
            break
    else:
        ret = 0
    return ret

# OS helpers
##############################################################################

isMac = sys.platform.startswith("darwin")
isWin = sys.platform.startswith("win32")
isLin = not isMac and not isWin
devMode = os.getenv("ANKIDEV", "")

invalidFilenameChars = ":*?\"<>|"

def invalidFilename(str, dirsep=True):
    for char in invalidFilenameChars:
        if char in str:
            return char
    if (dirsep or isWin) and "/" in str:
        return "/"
    elif (dirsep or not isWin) and "\\" in str:
        return "\\"
    elif str.strip().startswith("."):
        return "."

def platDesc():
    """{system}:{version}, where system is mac, win, or lin.

    It is theoretically resistant to system call interuption.
    """
    # we may get an interrupted system call, so try this in a loop
    index = 0
    theos = "unknown"
    while index < 100:
        index += 1
        try:
            system = platform.system()
            if isMac:
                theos = "mac:%s" % (platform.mac_ver()[0])
            elif isWin:
                theos = "win:%s" % (platform.win32_ver()[0])
            elif system == "Linux":
                import distro
                r = distro.linux_distribution(full_distribution_name=False)
                theos = "lin:%s:%s" % (r[0], r[1])
            else:
                theos = system
            break
        except:
            continue
    return theos

# Debugging
##############################################################################

class TimedLog:
    def __init__(self):
        self._last = time.time()
    def log(self, text):
        path, num, fn, y = traceback.extract_stack(limit=2)[0]
        sys.stderr.write("%5dms: %s(): %s\n" % ((time.time() - self._last)*1000, fn, text))
        self._last = time.time()

# Version
##############################################################################

def versionWithBuild():
    from anki import version
    try:
        from anki.buildhash import build
    except:
        build = "dev"
    return "%s (%s)" % (version, build)

def identity(x):
    return x

def negation(x):
    return not x

# Classes to extend dicts
#############################################################################

@functools.total_ordering
class DictAugmented(dict):
    def __init__(self, manager, dict=None, name=None):
        if dict:
            self.load(manager, dict)
        else:
            assert (name is not None)
            self.new(manager, name)

    def load(self, manager, dict):
        self.manager = manager
        super().__init__(dict)

    def __eq__(self, other):
        return self.getName() == other.getName()

    def __lt__(self, other):
        return self.getName() < other.getName()

    def getName(self):
        return self['name']

    def deepcopy(self):
        dict = {}
        for key in self:
            dict[key] = copy.deepcopy(self[key])
        return self.__class__(self.manager, dict=dict)

class DictAugmentedIdUsn(DictAugmented):
    def __eq__(self, other):
        return self.getId() == other.getId()

    def getId(self):
        return self['id']

    def save(self):
        """State that the DeckManager has been changed. Changes the
        mod and usn of the potential argument.
        The potential argument can be either a deck or a deck
        configuration.
        """
        self['mod'] = intTime()
        self['usn'] = self.manager.col.usn()
        self.manager.save()

    def setId(self, newId):
        self['id'] = newId

class DictAugmentedInModel(DictAugmented):
    def load(self, model, dict):
        self.model = model
        super().load(model, dict)

    def new(self, name, default):
        fieldType = default.copy()
        fieldType['name'] = name
        self.load(model, fieldType)
