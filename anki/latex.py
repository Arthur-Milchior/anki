# -*- coding: utf-8 -*-
# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

import html
import os
import re
import shutil

from anki.hooks import addHook
from anki.lang import _
from anki.utils import call, checksum, isMac, namedtmp, stripHTML, tmpdir

pngCommands = [
    ["latex", "-interaction=nonstopmode", "tmp.tex"],
    ["dvipng", "-D", "200", "-T", "tight", "tmp.dvi", "-o", "tmp.png"]
]

svgCommands = [
    ["latex", "-interaction=nonstopmode", "tmp.tex"],
    ["dvisvgm", "--no-fonts", "--exact", "-Z", "2", "tmp.dvi", "-o", "tmp.svg"]
]

build = True # if off, use existing media but don't create new
regexps = {
    "standard": re.compile(r"\[latex\](.+?)\[/latex\]", re.DOTALL | re.IGNORECASE),
    "expression": re.compile(r"\[\$\](.+?)\[/\$\]", re.DOTALL | re.IGNORECASE),
    "math": re.compile(r"\[\$\$\](.+?)\[/\$\$\]", re.DOTALL | re.IGNORECASE),
    }


# add standard tex install location to osx
if isMac:
    os.environ['PATH'] += ":/usr/texbin:/Library/TeX/texbin"

def stripLatex(text):
    """The input text without its LaTeX environment."""
    for match in regexps['standard'].finditer(text):
        text = text.replace(match.group(), "")
    for match in regexps['expression'].finditer(text):
        text = text.replace(match.group(), "")
    for match in regexps['math'].finditer(text):
        text = text.replace(match.group(), "")
    return text

def mungeQA(*args, **kwargs):
    """Same as mungeQAandErr, but with html only"""
    return mungeQAandErr(*args, **kwargs)[0]

def mungeQAandErr(html, type, fields, model, data, col):
    """A pair:
    * Html, where LaTeX parts are replaced by some HTML.
    * Whether there is an error

    see _imgLink docstring regarding the rules for LaTeX media.

    keyword arguments:
    html -- the text in which to find the LaTeX to be replaced.
    type -- not used. "q" or "a" for question and answer
    fields -- not used. A dictionnary containing Tags, Type(model
    name), Deck, Subdeck(part after last ::), card: template
    name... TODO (see collection._renderQA for more info)
    model -- the model in which is compiled the note. It deals with
    the header/footer, and the image file format
    data -- not used. [cid, nid, mid, did, ord, tags, flds]
    col -- the current collection. It deals with media folder
    """
    error = False
    for prefix, key, suffix in {("", "standard",""), ("$", "expression", "$"), ("\\begin{displaymath}", "math", "\\end{displaymath}")}:
        for match in regexps[key].finditer(html):
            textToCompile = prefix+match.group(1)+suffix
            link, er = _imgLink(col, textToCompile, model)
            html = html.replace(match.group(), link)
            error = error or er
    return (html, error)

def _imgLink(col, latex, model):
    """A pair:
    * Some HTML to display instead of the LaTeX code.
    * whether there is an error during LaTeX compilation.

    If some image already exists, related to this LaTeX code, an HTML
    code showing this image is returned.
    Otherwise, the latex code is compiled, and everything happen as in
    the previous case.

    In case of compilation error, an error message explaining the
    error (or asking whether program latex and dvipng/dvisvgm are
    installed) is returned.

    During the compilation the compiled file is in tmp.tex and its
    output (err and std) in latex_log.tex, replacing previous files of
    the same name. Both of those file are in the tmpdir as in
    utils.py.

    Keyword arguments:
    col -- the current collection. It is used for the media folder (and
    as argument for _latexFromHtml, where it seems to be useless)
    latex -- the latex code to compile
    model -- the model in which is compiled the note. It deals with
    the header/footer, and the image file format.
    """
    txt = _latexFromHtml(col, latex)

    if txt in col.buggedLatex:
        return col.buggedLatex[txt], True
    if model.get("latexsvg", False):
        ext = "svg"
    else:
        ext = "png"

    # is there an existing file?
    fname = "latex-%s.%s" % (checksum(txt.encode("utf8")), ext)
    link = '<img class=latex src="%s">' % fname
    if os.path.exists(fname):
        return (link, False)

    # building disabled?
    if not build:
        return ("[latex]%s[/latex]" % latex, False)

    err, compilationWasTried = _buildImg(col, txt, fname, model)
    if err:
        col.buggedLatex[txt] = err
        return err, True
    else:
        return (link, False)

def _latexFromHtml(col, latex):
    """Convert entities and fix newlines.

    First argument is not used.
    """
    latex = re.sub("<br( /)?>|<div>", "\n", latex)
    latex = stripHTML(latex)
    return latex

def _buildImg(col, latex, fname, model):
    """An error message if something did not work correctly.

    Generate an image file from latex code

    latex's header and foot is added as in the model. The image is
    named fname and added to the media folder of this collection.

    The compiled file is in tmp.tex and its output (err and std) in
    latex_log.tex, replacing previous files of the same name. Both of
    those file are in the tmpdir as in utils.py

    Compiles to svg if latexsvg is set to true in the model, otherwise
    to png. The compilation commands are given above.

    In case of error, return: * an error message to be displayed
    instead of the LaTeX document. (Note that this image is not
    displayed in AnkiDroid. It is probably shown only in computer
    mode)
    * whether it's a problem with the LaTeX (otherwise, it's a
    compilation problem, and it may be worth trying again)

    Keyword arguments:
    col -- the current collection. It deals with media folder
    latex -- the code LaTeX to compile, as given in fields
    fname -- the name given to the generated png
    model -- the model in which is compiled the note. It deals with
    the header/footer, and the image file format
    """
    # add header/footer
    latex = (model["latexPre"] + "\n" +
             latex + "\n" +
             model["latexPost"])
    # it's only really secure if run in a jail, but these are the most common
    tmplatex = latex.replace("\\includegraphics", "")
    for bad in ("\\write18", "\\readline", "\\input", "\\include",
                "\\catcode", "\\openout", "\\write", "\\loop",
                "\\def", "\\shipout"):
        # don't mind if the sequence is only part of a command
        bad_re = "\\" + bad + "[^a-zA-Z]"
        if re.search(bad_re, tmplatex):
            return (_("""\

For security reasons, '%s' is not allowed on cards. You can still use \
it by placing the command in a different package, and importing that \
package in the LaTeX header instead.""") % bad, True)

    # commands to use?
    if model.get("latexsvg", False):
        latexCmds = svgCommands
        ext = "svg"
    else:
        latexCmds = pngCommands
        ext = "png"

    # write into a temp file
    log = open(namedtmp("latex_log.txt"), "w")
    texpath = namedtmp("tmp.tex")
    texfile = open(texpath, "w", encoding="utf8")
    texfile.write(latex)
    texfile.close()
    mdir = col.media.dir()
    oldcwd = os.getcwd()
    png = namedtmp("tmp.%s" % ext)
    try:
        # generate an image
        os.chdir(tmpdir())
        for latexCmd in latexCmds:
            if call(latexCmd, stdout=log, stderr=log):
                return _errMsg(latexCmd[0], texpath)
        # add the image to the media folder
        shutil.copyfile(png, os.path.join(mdir, fname))
        return "", True
    finally:
        os.chdir(oldcwd)
        log.close()

def _errMsg(type, texpath):
    """A pair with:
    * an error message, in html, concerning LaTeX compilation.
    * whether compilation at least started

    This message contains LaTeX outputs if it exists, or a message
    asking whether the program latex and dvipng/dvisvgm are installed.

    Keyword arguments
    type -- the (begin of the) executed command
    texpath -- the path to the (temporary) file which was compiled
    """
    msg = (_("Error executing %s.") % type) + "<br>"
    msg += (_("Generated file: %s") % texpath) + "<br>"
    try:
        with open(namedtmp("latex_log.txt", rm=False)) as file:
            log = file.read()
        if not log:
            raise Exception()
        msg += "<small><pre>" + html.escape(log) + "</pre></small>"
        compilationWasTried = True
    except:
        msg += _("Have you installed latex and dvipng/dvisvgm?")
        compilationWasTried = False
    return msg, compilationWasTried

# setup q/a filter
addHook("mungeQA", mungeQA)
#This hook is called collection._renderQA. See mungeQA comment to know
#the parameters
