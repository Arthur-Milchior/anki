import re

import anki
from anki.cards import Card
from anki.collection import _Collection
from anki.consts import *
from anki.hooks import runFilter
from anki.models import ModelManager
from anki.sound import stripSounds
from anki.template.template import Template, get_or_attr, modifier, modifiers
from anki.utils import splitFields

from .debug import debugFun


@modifier(None)
@debugFun
def render_unescaped(self, tag_name=None, context=None):
    """Render a tag without escaping it."""
    txt = get_or_attr(context, tag_name)
    if txt is not None:
        # some field names could have colons in them
        # avoid interpreting these as field modifiers
        # better would probably be to put some restrictions on field names
        showAField = bool(txt.strip())### MODIFIED
        return (txt,showAField)### MODIFIED
     # field modifiers
    parts = tag_name.split(':')
    extra = None
    if len(parts) == 1 or parts[0] == '':
        return ('{unknown field %s}' % tag_name,False)
    else:
        mods, tag = parts[:-1], parts[-1] #py3k has *mods, tag = parts

    txt = get_or_attr(context, tag)

    #Since 'text:' and other mods can affect html on which Anki relies to
    #process clozes, we need to make sure clozes are always
    #treated after all the other mods, regardless of how they're specified
    #in the template, so that {{cloze:text: == {{text:cloze:
    #For type:, we return directly since no other mod than cloze (or other
    #pre-defined mods) can be present and those are treated separately
    mods.reverse()
    mods.sort(key=lambda s: not s=="type")
    for mod in mods:
        # built-in modifiers
        if mod == 'text':
            # strip html
            txt = stripHTML(txt) if txt else ""
        elif mod == 'type':
            # type answer field; convert it to [[type:...]] for the gui code
            # to process
            return ("[[%s]]" % tag_name,False)### MODIFIED
        elif mod.startswith('cq-') or mod.startswith('ca-'):
            # cloze deletion
            mod, extra = mod.split("-")
            txt = self.clozeText(txt, extra, mod[1]) if txt and extra else ""
        else:
            # hook-based field modifier
            mod, extra = re.search("^(.*?)(?:\((.*)\))?$", mod).groups()
            txt = runFilter('fmod_' + mod, txt or '', extra or '', context,
                            tag, tag_name)
            if txt is None:
                return ('{unknown field %s}' % tag_name, False)### MODIFIED
    return (txt, True)### MODIFIED
Template.render_unescaped = render_unescaped



@debugFun
def render_tags(self, template, context):
    """Renders all the tags in a template for a context. Normally
    {{# and {{^ are removed"""
    repCount = 0
    showAField = False
    while 1:
        if repCount > 100:
            print("too many replacements")
            break
        repCount += 1

        # search for some {{foo}}
        match = self.tag_re.search(template)
        if match is None:
            break

        #
        tag, tag_type, tag_name = match.group(0, 1, 2)
        tag_name = tag_name.strip()
        try:
            func = modifiers[tag_type]
            replacement = func(self, tag_name, context)
            ########## Start new part
            if isinstance(replacement,tuple):
                replacement, showAField_ = replacement
                if showAField_:
                    showAField = True
            ########## End new part
                template = template.replace(tag, replacement)
        except (SyntaxError, KeyError):
            return "{{invalid template}}"
    return template, showAField

Template.render_tags =render_tags

@debugFun
def render(self, template=None, context=None, encoding=None):
    """Turns a Mustache template into something wonderful."""
    template = template or self.template
    context = context or self.context
    template = self.render_sections(template, context)

    result, showAField = self.render_tags(template, context)#MODIFIED
    if encoding is not None:
        result = result.encode(encoding)
    return result, showAField#MODIFIED
Template.render = render

@debugFun
def _renderQA(self, data, qfmt=None, afmt=None):
    """Returns hash of id, question, answer.

    Keyword arguments:
    data -- [cid, nid, mid, did, ord, tags, flds, cardFlags] (see db
    documentation for more information about those values)
    flds is a list of fields, not a dict.
    This corresponds to the information you can obtain in templates, using {{Tags}}, {{Type}}, etc..

    qfmt -- question format string (as in template)
    afmt -- answer format string (as in template)

    unpack fields and create dict
    TODO comment better

    """
    cid, nid, mid, did, ord, tags, flds, cardFlags = data
    flist = splitFields(flds)#the list of fields
    fields = {} #
    #name -> ord for each field, tags
    # Type: the name of the model,
    # Deck, Subdeck: their name
    # Card: the template name
    # cn: 1 for n being the ord+1
    # FrontSide :
    model = self.models.get(mid)
    assert model is not None #new (and fieldMap and items were not variables, but directly used
    fieldMap = self.models.fieldMap(model)
    items = fieldMap.items()
    for (name, (idx, conf)) in list(items):#conf is not used
        fields[name] = flist[idx]
    fields['Tags'] = tags.strip()
    fields['Type'] = model['name']
    fields['Deck'] = self.decks.name(did)
    fields['Subdeck'] = fields['Deck'].split('::')[-1]
    fields['CardFlag'] = self._flagNameFromCardFlags(cardFlags)
    if model['type'] == MODEL_STD:#Note that model['type'] has not the same meaning as fields['Type']
        template = model['tmpls'][ord]
    else:#for cloze deletions
        template = model['tmpls'][0]
    fields['Card'] = template['name']
    fields['c%d' % (ord+1)] = "1"
    # render q & a
    d = dict(id=cid)
    # id: card id
    qfmt = qfmt or template['qfmt']
    afmt = afmt or template['afmt']
    for (type, format) in (("q", qfmt), ("a", afmt)):
        if type == "q":#if/else is in the loop in order for d['q'] to be defined below
            format = re.sub("{{(?!type:)(.*?)cloze:", r"{{\1cq-%d:" % (ord+1), format)
            #Replace {{'foo'cloze: by {{'foo'cq-(ord+1), where 'foo' does not begins with "type:"
            format = format.replace("<%cloze:", "<%%cq:%d:" % (
                ord+1))
            #Replace <%cloze: by <%%cq:(ord+1)
        else:
            format = re.sub("{{(.*?)cloze:", r"{{\1ca-%d:" % (ord+1), format)
            #Replace {{'foo'cloze: by {{'foo'ca-(ord+1)
            format = format.replace("<%cloze:", "<%%ca:%d:" % (
                ord+1))
            #Replace <%cloze: by <%%ca:(ord+1)
            fields['FrontSide'] = stripSounds(d['q'])
            #d['q'] is defined during loop's first iteration
        fields = runFilter("mungeFields", fields, model, data, self) # TODO check
        html, showAField = anki.template.render(format, fields) #replace everything of the form {{ by its value #MODIFIED
        d["showAField"] = showAField#MODIFIED
        d[type] = runFilter(
            "mungeQA", html, type, fields, model, data, self) # TODO check
        # empty cloze?
        if type == 'q' and model['type'] == MODEL_CLOZE:
            if not self.models._availClozeOrds(model, flds, False):
                d['q'] += ("<p>" + _(
            "Please edit this note and add some cloze deletions. (%s)") % (
            "<a href=%s#cloze>%s</a>" % (HELP_SITE, _("help"))))
                #in the case where there is a cloze note type
                #without {{cn in fields indicated by
                #{{cloze:fieldName; an error message should be
                #shown
    return d
_Collection._renderQA = _renderQA

#TOTALLY NEW METHOD
@debugFun
def isEmpty(self):
    return not self._getQA()["showAField"]
Card.isEmpty = isEmpty

#TOTALLY NEW METHOD
@debugFun
def availOrds(self, m, flds):
    """
    self -- model manager
    m -- a model object
    """
    available = []
    flist = splitFields(flds)
    fields = {} #
    for (name, (idx, conf)) in list(self.fieldMap(m).items()):#conf is not used
        fields[name] = flist[idx]
    for ord in range(len(m["tmpls"])):
        template = m["tmpls"][ord]
        format = template['qfmt']
        html, showAField = anki.template.render(format, fields) #replace everything of the form {{ by its value TODO check
        if showAField:
            available.append(ord)
    return available
ModelManager.availOrds = availOrds
