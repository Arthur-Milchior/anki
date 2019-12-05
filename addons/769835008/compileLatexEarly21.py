# -*- coding: utf-8 -*-
# Copyright: Arthur Milchior arthur@milchior.fr
# License: GNU GPL, version 3 or later; http://www.gnu.org/copyleft/gpl.html
# Feel free to contribute to the code on https://github.com/Arthur-Milchior/anki-compile-latex-early/
# Add-on number: 769835008

import os
import re
import unicodedata

import anki.notes
from anki.consts import *
from anki.hooks import wrap
from anki.lang import _
from anki.latex import _buildImg, _latexFromHtml, build, regexps
from anki.notes import Note
from anki.utils import checksum
from aqt import mw
from aqt.utils import showWarning, tooltip


def mungeQA(html, type, fields, model, data, col):
    "Convert TEXT with embedded latex tags to image links. Returns the HTML and whether an error occurred."
    error = False
    for match in regexps['standard'].finditer(html):
        link, er = _imgLink(col, match.group(1), model)
        html = html.replace(match.group(), link)
        error = error or er
    for match in regexps['expression'].finditer(html):
        link, er = _imgLink(
            col, "$" + match.group(1) + "$", model)
        html = html.replace(match.group(), link)
        error = error or er
    for match in regexps['math'].finditer(html):
        link, er = _imgLink(
            col,
            "\\begin{displaymath}" + match.group(1) + "\\end{displaymath}", model)
        html = html.replace(match.group(), link)
        error = error or er
    return html, error

buggedLatex ={}

def _imgLink(col, latex, model):
    """A pair containing:
    An img link for LATEX, creating if necesssary. 
    Whether an error occurred."""
    txt = _latexFromHtml(col, latex)
    if txt in buggedLatex:
        return (buggedLatex[txt],True)
    if model.get("latexsvg", False):
        ext = "svg"
    else:
        ext = "png"

    # is there an existing file?
    fname = "latex-%s.%s" % (checksum(txt.encode("utf8")), ext)
    link = '<img class=latex src="%s">' % fname
    if os.path.exists(fname):
        return (link,False)

    # building disabled?
    if not build:
        return ("[latex]%s[/latex]" % latex,False)

    err = _buildImg(col, txt, fname, model)
    if err:
        buggedLatex[txt]=err
        return (err,True)
    else:
        return (link,False)

oldFlush = Note.flush
def filesInStr(self, mid, string, includeRemote=False):
    """The list of media's path in the string
    
    Keyword arguments:
    self -- the media manager
    mid -- the id of the model of the note whose string is considered
    string -- A string, which corresponds to a field of a note
    includeRemote -- whether the list should include contents which is with http, https or ftp
    """
    l = []
    model = self.col.models.get(mid)
    strings = []
    someError = False
    if model['type'] == MODEL_CLOZE and "{{c" in string:
       # if the field has clozes in it, we'll need to expand the
        # possibilities so we can render latex
        strings = self._expandClozes(string)
    else:
        strings = [string]
    for string in strings:
        # handle latex
        (string,error) = mungeQA(string, None, None, model, None, self.col)
        someError = error or someError
        # extract filenames
        for reg in self.regexps:
            for match in re.finditer(reg, string):
                fname = match.group("fname")
                isLocal = not re.match("(https?|ftp)://", fname.lower())
                if isLocal or includeRemote:
                    l.append(fname)
    return (l,someError)

def noteFlush(note, mod=None):
    someError=False
    for field in note.fields:
        (_,error)=filesInStr(note.col.media, note.mid, field, note, mod)
        someError = someError or error
    if someError:
        if note.hasTag("LaTeXError"):
            tooltip("Some LaTex compilation error remains.")
        else:
            note.addTag("LaTeXError")
            whichAlert=  mw.addonManager.getConfig(__name__).get("warningBox",True)
            message = "There was some LaTex compilation error."
            if whichAlert.lower() == "never":
                tooltip(message)
            else:
                showWarning(message)
    else:
        if note.hasTag("LaTeXError"):
            note.delTag("LaTeXError")
            tooltip("There are no more LaTeX error.")
    oldFlush(note,mod=mod)
      
  
Note.flush = noteFlush
#this is a test for update
