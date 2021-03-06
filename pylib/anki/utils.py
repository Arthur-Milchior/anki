# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

from __future__ import annotations

# some add-ons expect json to be in the utils module
import json  # pylint: disable=unused-import
import locale
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
from typing import Iterable, Iterator, List, Optional, Union

from anki.dbproxy import DBProxy

_tmpdir: Optional[str]

# Time handling
##############################################################################


def intTime(scale: int = 1) -> int:
    "The time in integer seconds. Pass scale=1000 to get milliseconds."
    return int(time.time() * scale)


# Locale
##############################################################################


def fmtPercentage(float_value, point=1) -> str:
    "Return float with percentage sign"
    fmt = "%" + "0.%(point)df" % {"point": point}
    return locale.format_string(fmt, float_value) + "%"


def fmtFloat(float_value, point=1) -> str:
    "Return a string with decimal separator according to current locale"
    fmt = "%" + "0.%(point)df" % {"point": point}
    return locale.format_string(fmt, float_value)


# HTML
##############################################################################
reComment = re.compile("(?s)<!--.*?-->")
reStyle = re.compile("(?si)<style.*?>.*?</style>")
reScript = re.compile("(?si)<script.*?>.*?</script>")
reTag = re.compile("(?s)<.*?>")
reEnts = re.compile(r"&#?\w+;")
reMedia = re.compile("(?i)<img[^>]+src=[\"']?([^\"'>]+)[\"']?[^>]*>")


def stripHTML(text: str) -> str:
    """Removes comment, style, script, and all tags. Replace entities by their unicode value"""
    text = reComment.sub("", text)
    text = reStyle.sub("", text)
    text = reScript.sub("", text)
    text = reTag.sub("", text)
    text = entsToTxt(text)
    return text


def stripHTMLMedia(text: str) -> str:
    """Removes comment, style, script, and all tags. Replace images by
their url. Replace entities by their unicode value"""
    text = reMedia.sub(" \\1 ", text)
    return stripHTML(text)


def minimizeHTML(text: str) -> str:
    "Correct Qt'text verbose bold/underline/etc."
    text = re.sub('<span style="font-weight:600;">(.*?)</span>', "<b>\\1</b>", text)
    text = re.sub('<span style="font-style:italic;">(.*?)</span>', "<i>\\1</i>", text)
    text = re.sub(
        '<span style="text-decoration: underline;">(.*?)</span>', "<u>\\1</u>", text
    )
    return text


def htmlToTextLine(text: str) -> str:
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


def entsToTxt(html: str) -> str:
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
        return text  # leave as is

    return reEnts.sub(fixup, html)


# IDs
##############################################################################


def hexifyID(id) -> str:
    return "%x" % int(id)


def dehexifyID(id) -> int:
    return int(id, 16)


def ids2str(ids: Iterable[Union[int, str]]) -> str:
    """Given a list of integers, return a string '(int1,int2,...)'."""
    return "(%s)" % ",".join(str(id) for id in ids)


def timestampID(db: DBProxy, table: str) -> int:
    "Return a non-conflicting timestamp for table."
    # be careful not to create multiple objects without flushing them, or they
    # may share an ID.
    time = intTime(1000)
    while db.scalar("select id from %s where id = ?" % table, time):
        time += 1
    return time


def maxID(db: DBProxy) -> int:
    "Return the first safe ID to use."
    now = intTime(1000)
    for tbl in "cards", "notes":
        now = max(now, db.scalar("select max(id) from %s" % tbl) or 0)
    return now + 1


# used in ankiweb
def base62(num: int, extra: str = "") -> str:
    table = string.ascii_letters + string.digits + extra
    buf = ""
    while num:
        num, mod = divmod(num, len(table))
        buf = table[mod] + buf
    return buf


_base91_extra_chars = "!#$%&()*+,-./:;<=>?@[]^_`{|}~"


def base91(num: int) -> str:
    # all printable characters minus quotes, backslash and separators
    return base62(num, _base91_extra_chars)


def guid64() -> str:
    "Return a base91-encoded 64bit random number."
    return base91(random.randint(0, 2 ** 64 - 1))


# increment a guid by one, for note type conflicts
def incGuid(guid) -> str:
    return _incGuid(guid[::-1])[::-1]


def _incGuid(guid) -> str:
    table = string.ascii_letters + string.digits + _base91_extra_chars
    idx = table.index(guid[0])
    if idx + 1 == len(table):
        # overflow
        guid = table[0] + _incGuid(guid[1:])
    else:
        guid = table[idx + 1] + guid[1:]
    return guid


# Fields
##############################################################################


def joinFields(list: List[str]) -> str:
    return "\x1f".join(list)


def splitFields(string: str) -> List[str]:
    """Transform the fields as in the database in a list of field"""
    return string.split("\x1f")


# Checksums
##############################################################################


def checksum(data: Union[bytes, str]) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return sha1(data).hexdigest()


def fieldChecksum(data: str) -> int:
    # 32 bit unsigned number from first 8 digits of sha1 hash
    return int(checksum(stripHTMLMedia(data).encode("utf-8"))[:8], 16)


# Temp files
##############################################################################

_tmpdir = None


def tmpdir() -> str:
    "A reusable temp folder which we clean out on each program invocation."
    global _tmpdir
    if not _tmpdir:

        def cleanup():
            if os.path.exists(_tmpdir):
                shutil.rmtree(_tmpdir)

        import atexit

        atexit.register(cleanup)
        _tmpdir = os.path.join(tempfile.gettempdir(), "anki_temp")
    try:
        os.mkdir(_tmpdir)
    except FileExistsError:
        pass
    return _tmpdir


def tmpfile(prefix: str = "", suffix: str = "") -> str:
    (fd, name) = tempfile.mkstemp(dir=tmpdir(), prefix=prefix, suffix=suffix)
    os.close(fd)
    return name


def namedtmp(name: str, rm: bool = True) -> str:
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
def noBundledLibs() -> Iterator[None]:
    oldlpath = os.environ.pop("LD_LIBRARY_PATH", None)
    yield
    if oldlpath is not None:
        os.environ["LD_LIBRARY_PATH"] = oldlpath


def call(argv: List[str], wait: bool = True, **kwargs) -> int:
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
        si = subprocess.STARTUPINFO()  # type: ignore
        try:
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW  # type: ignore
        except:
            # pylint: disable=no-member
            si.dwFlags |= subprocess._subprocess.STARTF_USESHOWWINDOW  # type: ignore
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

invalidFilenameChars = ':*?"<>|'


def invalidFilename(str, dirsep=True) -> Optional[str]:
    for char in invalidFilenameChars:
        if char in str:
            return char
    if (dirsep or isWin) and "/" in str:
        return "/"
    elif (dirsep or not isWin) and "\\" in str:
        return "\\"
    elif str.strip().startswith("."):
        return "."
    return None


def platDesc() -> str:
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
                import distro  # pytype: disable=import-error # pylint: disable=import-error

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
    def __init__(self) -> None:
        self._last = time.time()

    def log(self, text) -> None:
        path, num, fn, y = traceback.extract_stack(limit=2)[0]
        sys.stderr.write(
            "%5dms: %s(): %s\n" % ((time.time() - self._last) * 1000, fn, text)
        )
        self._last = time.time()


# Version
##############################################################################


def versionWithBuild() -> str:
    from anki.buildinfo import version, buildhash

    return "%s (%s)" % (version, buildhash)


def pointVersion() -> int:
    from anki.buildinfo import version

    return int(version.split(".")[-1])
