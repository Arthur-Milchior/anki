import re

from anki.utils import DictAugmentedInModel

defaultField = {
    'name': "",
    'ord': None,
    'sticky': False,
    # the following alter editing, and are used as defaults for the
    # template wizard
    'rtl': False,
    'font': "Arial",
    'size': 20,
    # reserved for future use
    'media': [],
}

class Field(DictAugmentedInModel):
    """Field are not necessarily in the model. If they are not, method add
    must be used to add them.  Only use them once the field is
    entirely configured (so that compilation of req is done correction
    for example)

    """

    def new(self, manager, name):
        """A new field, similar to the default one, whose name is name."""
        super().new(manager, name, defaultField)

    def add(self):
        """Append the field field as last element of the model model.
        todo
        Keyword arguments
        """
        # only mod schema if model isn't new
        if self.model['id']:
            self.model.manager.col.modSchema(check=True)
        self.model['flds'].append(self)
        self.model._updateFieldOrds()
        self.model.save()
        def add(fieldsContents):
            fieldsContents.append("")
            return fieldsContents
        self.model._transformFields(add)

    def rename(self, newName):
        """Rename the field. In each template, find the mustache related to
        this field and change them.
        field -- the field dictionnary
        newName -- either a name. Or None if the field is deleted.
        """
        self.model.manager.col.modSchema(check=True)
        #Regexp associating to a mustache the name of its field
        pat = r'{{([^{}]*)([:#^/]|[^:#/^}][^:}]*?:|)%s}}'
        def wrap(txt):
            def repl(match):
                return '{{' + match.group(1) + match.group(2) + txt +  '}}'
            return repl
        for template in self.model['tmpls']:
            for fmt in ('qfmt', 'afmt'):
                if newName:
                    template[fmt] = re.sub(
                        pat % re.escape(self.getName()), wrap(newName), template[fmt])
                else:
                    template[fmt] = re.sub(
                        pat  % re.escape(self.getName()), "", template[fmt])
        self.setName(newName)
        self.model.save()
