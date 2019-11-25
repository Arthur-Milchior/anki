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
    mm.addField(model, fm)
    fm = model.newField(_("Back"))
    mm.addField(model, fm)
    template = mm.newTemplate(model, _("Card 1"))
    template['qfmt'] = "{{"+_("Front")+"}}"
    template['afmt'] = "{{FrontSide}}\n\n<hr id=answer>\n\n"+"{{"+_("Back")+"}}"
    mm.addTemplate(model, template)
    return model

def addBasicModel(col):
    model = _newBasicModel(col)
    col.models.add(model)
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
    mm.add(model)
    return model

models.append((lambda: _("Basic (type in the answer)"), addBasicTypingModel))

# Forward & Reverse
##########################################################################

def _newForwardReverse(col, name=None):
    mm = col.models
    model = _newBasicModel(col, name or _("Basic (and reversed card)"))
    template = mm.newTemplate(model, _("Card 2"))
    template['qfmt'] = "{{"+_("Back")+"}}"
    template['afmt'] = "{{FrontSide}}\n\n<hr id=answer>\n\n"+"{{"+_("Front")+"}}"
    mm.addTemplate(model, template)
    return model

def addForwardReverse(col):
    model = _newForwardReverse(col)
    col.models.add(model)
    return model

models.append((lambda: _("Basic (and reversed card)"), addForwardReverse))

# Forward & Optional Reverse
##########################################################################

def addForwardOptionalReverse(col):
    mm = col.models
    model = _newForwardReverse(col, _("Basic (optional reversed card)"))
    av = _("Add Reverse")
    fm = model.newField(av)
    mm.addField(model, fm)
    template = model['tmpls'][1]
    template['qfmt'] = "{{#%s}}%s{{/%s}}" % (av, template['qfmt'], av)
    mm.add(model)
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
    mm.addField(model, fm)
    fm = model.newField(_("Extra"))
    mm.addField(model, fm)
    template = mm.newTemplate(model, _("Cloze"))
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
    mm.addTemplate(model, template)
    mm.add(model)
    return model

models.append((lambda: _("Cloze"), addClozeModel))
