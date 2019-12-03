import re

from anki.hooks import runFilter
from anki.utils import stripHTML, stripHTMLMedia

from anki.template import furigana; furigana.install()
from anki.template import hint; hint.install()

clozeReg = r"(?si)\{\{(c)%s::(.*?)(::(.*?))?\}\}"
"""clozeReg % n is the regexp recognizing the occurrences of close number n.
   clozeReg %.+? is the regexp recognizing any cloze occurrence.
   group 0 is c. Group 1 is the cloze, group 2 is the hint with ::, group 3 is the hint.
"""
#(?si) means .dot match all strings, ignore case

modifiers = {}
def modifier(symbol):
    """Decorator for associating a function with a Mustache tag modifier.

    @modifier('P')
    def render_tongue(self, tag_name=None, context=None):
        return ":P %s" % tag_name

    {{P yo }} => :P yo
    """
    def set_modifier(func):
        modifiers[symbol] = func
        return func
    return set_modifier


def get_or_attr(obj, name, default=None):
    """If its a susbscriptable: obj[name]. Else obj.name. Else default"""
    try:
        return obj[name]
    except KeyError:
        return default
    except:
        try:
            return getattr(obj, name)
        except AttributeError:
            return default


class Template:
    """TODO

    A template object contains:
    template -- ; see ../models.py
    context -- a dictionnary containing at least:
    ** the fields
    ** the  value for Tags, Type, Deck, Subdeck, Fields, FrontSide (on
    the  back).
    ** Containing "cn:1" with n the ord of the field
    """
    # The regular expression used to find a #section
    # I.e. {{# or {{^
    # from {{#foo}}bar{{/foo}} return ({{#foo}}bar{{/foo}},foo,bar)
    section_re = None

    # The regular expression used to find a tag.  The tag can start by
    # #, =, &, !, >,{ or the empty string.
    # from {{sfoo}} return ({{sfoo}},s,foo)
    tag_re = None

    # Opening tag delimiter
    otag = '{{'

    # Closing tag delimiter
    ctag = '}}'

    def __init__(self, template, context=None, encoding=None):
        self.template = template
        self.context = context or {}
        self.compile_regexps()
        self.encoding = encoding

    def render(self):
        """Turns a Mustache template into something wonderful."""
        self.template = self.render_sections(self.template, self.context)
        result = self.render_tags(self.template, self.context)
        if self.encoding is not None:
            result = result.encode(self.encoding)
        return result

    def compile_regexps(self):
        """Compiles our section and tag regular expressions."""
        #Opening and closing tag. Currently {{ and }}
        tags = { 'otag': re.escape(self.otag), 'ctag': re.escape(self.ctag) }

        # See the comment for section_re
        section = r"%(otag)s[\#|^]([^\}]*)%(ctag)s(.+?)%(otag)s/\1%(ctag)s"
        self.section_re = re.compile(section % tags, re.M|re.S)

        # See the comment for tag_re
        tag = r"%(otag)s(#|=|&|!|>|\{)?(.+?)\1?%(ctag)s+"
        self.tag_re = re.compile(tag % tags)

    def render_sections(self, template, context):
        """replace {{#foo}}bar{{/foo}} and {{^foo}}bar{{/foo}} by
        their normal value."""
        while 1:
            match = self.section_re.search(template)
            if match is None:
                break

            section, section_name, inner = match.group(0, 1, 2)
            section_name = section_name.strip()

            # val will contain the content of the field considered
            # right now
            val = None
            match = re.match(r"c[qa]:(\d+):(.+)", section_name)
            if match:
                # get full field text
                txt = get_or_attr(context, match.group(2), None)
                match = re.search(clozeReg%match.group(1), txt)
                if match:
                    val = match.group(1)
            else:
                val = get_or_attr(context, section_name, None)

            replacer = ''
            # Whether it's {{^
            inverted = section[2] == "^"
            # Ensuring we don't consider whitespace in val
            if val:
                val = stripHTMLMedia(val).strip()
            if bool(val) != inverted:
                replacer = inner

            template = template.replace(section, replacer)

        return template

    def render_tags(self, template, context):
        """Renders all the tags in a template for a context. Normally
        {{# and {{^ are already removed."""
        repCount = 0
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
                template = template.replace(tag, replacement)
            except (SyntaxError, KeyError):
                return "{{invalid template}}"

        return template

    # {{{ functions just like {{ in anki
    @modifier('{')
    def render_tag(self, tag_name, context):
        return self.render_unescaped(tag_name, context)

    @modifier('!')
    def render_comment(self, tag_name=None, context=None):
        """Rendering a comment always returns nothing."""
        return ''

    @modifier(None)
    def render_unescaped(self, tag_name=None, context=None):
        """Render a tag without escaping it."""
        txt = get_or_attr(context, tag_name)
        if txt is not None:
            # some field names could have colons in them
            # avoid interpreting these as field modifiers
            # better would probably be to put some restrictions on field names
            return txt

        # field modifiers
        parts = tag_name.split(':')
        extra = None
        if len(parts) == 1 or parts[0] == '':
            return '{unknown field %s}' % tag_name
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
                return "[[%s]]" % tag_name
            elif mod.startswith('cq-') or mod.startswith('ca-'):
                # cloze deletion
                mod, extra = mod.split("-")
                txt = self.clozeText(txt, extra, mod[1]) if txt and extra else ""
            else:
                # hook-based field modifier
                mod, extra = re.search(r"^(.*?)(?:\((.*)\))?$", mod).groups()
                txt = runFilter('fmod_' + mod, txt or '', extra or '', context,
                                tag, tag_name)
                if txt is None:
                    return '{unknown field %s}' % tag_name
        return txt

    def clozeText(self, txt, ord, type):
        reg = clozeReg
        if not re.search(reg%ord, txt):
            return ""
        txt = self._removeFormattingFromMathjax(txt, ord)
        def repl(match):
            # replace chosen cloze with type
            if type == "q":
                if match.group(4):
                    buf = "[%s]" % match.group(4)
                else:
                    buf = "[...]"
            else:
                buf = match.group(2)
            # uppercase = no formatting
            if match.group(1) == "c":
                buf = "<span class=cloze>%s</span>" % buf
            return buf
        txt = re.sub(reg%ord, repl, txt)
        # and display other clozes normally
        return re.sub(reg%r"\d+", "\\2", txt)

    # look for clozes wrapped in mathjax, and change {{cx to {{Cx
    def _removeFormattingFromMathjax(self, txt, ord):
        openings = ["\\(", "\\["]
        closings = ["\\)", "\\]"]
        # flags in middle of expression deprecated
        creg = clozeReg.replace("(?si)", "")
        regex = r"(?si)(\\[([])(.*?)"+(creg%ord)+r"(.*?)(\\[\])])"
        def repl(match):
            enclosed = True
            for closing in closings:
                if closing in match.group(1):
                    enclosed = False
            for opening in openings:
                if opening in match.group(7):
                    enclosed = False
            if not enclosed:
                return match.group(0)
            # remove formatting
            return match.group(0).replace("{{c", "{{C")
        txt = re.sub(regex, repl, txt)
        return txt

    @modifier('=')
    def render_delimiter(self, tag_name=None, context=None):
        """Changes the Mustache delimiter."""
        try:
            self.otag, self.ctag = tag_name.split(' ')
        except ValueError:
            # invalid
            return
        self.compile_regexps()
        return ''
