# -*- coding: utf-8 -*-
# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

from anki.consts import MODEL_CLOZE
from anki.lang import _
from anki.model import Model

models = []

# Basic
##########################################################################

def _newBasicModel(col, name=None):
    mm = col.models
    model = mm.new(name or _("Basic"))
    fm = model.newField(_("Front"))
    fm.add()
    fm = model.newField(_("Back"))
    fm.add()
    template = model.newTemplate(_("Card 1"))
    template['qfmt'] = "{{"+_("Front")+"}}"
    template['afmt'] = "{{FrontSide}}\n\n<hr id=answer>\n\n"+"{{"+_("Back")+"}}"
    template.add()
    return model

def addBasicModel(col):
    model = _newBasicModel(col)
    model.add()
    return model

models.append((lambda: _("Basic"), addBasicModel))

# Basic w/ typing
##########################################################################

def addBasicTypingModel(col):
    mm = col.models
    model = _newBasicModel(col, _("Basic (type in the answer)"))
    template = model['tmpls'][0]
    template['qfmt'] = "{{"+_("Front")+"}}\n\n{{type:"+_("Back")+"}}"
    template['afmt'] = "{{"+_("Front")+"}}\n\n<hr id=answer>\n\n{{type:"+_("Back")+"}}"
    model.add()
    return model

models.append((lambda: _("Basic (type in the answer)"), addBasicTypingModel))

# Forward & Reverse
##########################################################################

def _newForwardReverse(col, name=None):
    mm = col.models
    model = _newBasicModel(col, name or _("Basic (and reversed card)"))
    template = model.newTemplate(_("Card 2"))
    template['qfmt'] = "{{"+_("Back")+"}}"
    template['afmt'] = "{{FrontSide}}\n\n<hr id=answer>\n\n"+"{{"+_("Front")+"}}"
    template.add()
    return model

def addForwardReverse(col):
    model = _newForwardReverse(col)
    model.add()
    return model

models.append((lambda: _("Basic (and reversed card)"), addForwardReverse))

# Forward & Optional Reverse
##########################################################################

def addForwardOptionalReverse(col):
    mm = col.models
    model = _newForwardReverse(col, _("Basic (optional reversed card)"))
    av = _("Add Reverse")
    fm = model.newField(av)
    fm.add()
    template = model['tmpls'][1]
    template['qfmt'] = "{{#%s}}%s{{/%s}}" % (av, template['qfmt'], av)
    model.add()
    return model

models.append((lambda: _("Basic (optional reversed card)"),
        addForwardOptionalReverse))

# Cloze
##########################################################################

def addClozeModel(col):
    mm = col.models
    model = mm.new(_("Cloze"))
    model['type'] = MODEL_CLOZE
    txt = _("Text")
    fm = model.newField(txt)
    fm.add()
    fm = model.newField(_("Extra"))
    fm.add()
    template = model.newTemplate(_("Cloze"))
    fmt = "{{cloze:%s}}" % txt
    model['css'] += """
.cloze {
 font-weight: bold;
 color: blue;
}
.nightMode .cloze {
 color: lightblue;
}"""
    template['qfmt'] = fmt
    template['afmt'] = fmt + "<br>\n{{%s}}" % _("Extra")
    template.add()
    model.add()
    return model

models.append((lambda: _("Cloze"), addClozeModel))
