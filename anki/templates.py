from anki.utils import DictAugmentedInModel, ids2str, intTime, joinFields

defaultTemplate = {
    'name': "",
    'ord': None,
    'qfmt': "",
    'afmt': "",
    'did': None,
    'bqfmt': "",
    'bafmt': "",
    # we don't define these so that we pick up system font size until set
    #'bfont': "Arial",
    #'bsize': 12,
}

class Template(DictAugmentedInModel):
    """Templates are not necessarily in the model. If they are not, method add
    must be used to add them.  Only use them once the field is
    entirely configured (so that compilation of req is done correction
    for example)

    """

    def new(self, model, name):
        """A new template, whose content is the one of
        defaultTemplate, and name is name.
        It's used in order to import mnemosyn, and create the standard
        model during anki's first initialization. It's not used in day to day anki.
        """
        super().new(model, name, defaultTemplate)

    def add(self):
        """Add this template in model, as last element.

        """
        if self.model.getId():
            self.model.manager.col.modSchema(check=True)
        self.model['tmpls'].append(self)
        self.model._updateTemplOrds()
        self.model.save()

    def rem(self):
        """Remove the input template from the model model.
        Return False if removing template would leave orphan
        notes. Otherwise True
        """
        assert len(self.model['tmpls']) > 1
        # find cards using this template
        ord = self.model['tmpls'].index(self)
        cids = self.model.manager.col.db.list("""
select card.id from cards card, notes note where card.nid=note.id and mid = ? and ord = ?""",
                                 self.model.getId(), ord)
        # all notes with this template must have at least two cards, or we
        # could end up creating orphaned notes
        if self.model.manager.col.db.scalar("""
select nid, count() from cards where
nid in (select nid from cards where id in %s)
group by nid
having count() < 2
limit 1""" % ids2str(cids)):
            return False
        # ok to proceed; remove cards
        self.model.manager.col.modSchema(check=True)
        self.model.manager.col.remCards(cids)
        # shift ordinals
        self.model.manager.col.db.execute("""
update cards set ord = ord - 1, usn = ?, mod = ?
 where nid in (select id from notes where mid = ?) and ord > ?""",
                             self.model.manager.col.usn(), intTime(), self.model.getId(), ord)
        self.model['tmpls'].pop(ord)
        if 'req' in self.model:
            # True except for quite new models, especially in tests.
            self.model['req'].pop(ord)
        self.model._updateTemplOrds()
        self.model.save(recomputeReq=False)
        return True

    def move(self, idx):
        """Move input self to position idx in model.
        Move also every other self to make this consistent.
        Comment again after that TODODODO
        """
        oldidx = self.model['tmpls'].index(self)
        if oldidx == idx:
            return
        oldidxs = dict((id(self), self['ord']) for self in self.model['tmpls'])
        self.model['tmpls'].remove(self)
        self.model['tmpls'].insert(idx, self)
        self.model._updateTemplOrds()
        # generate change map
        map = [("when ord = %d then %d" % (oldidxs[id(self)], self['ord']))
               for self in self.model['tmpls']]
        # apply
        self.model.save(recomputeReq=False)
        self.model.manager.col.db.execute("""
update cards set ord = (case %s end),usn=?,mod=? where nid in (
select id from notes where mid = ?)""" % " ".join(map),
                             self.model.manager.col.usn(), intTime(), self.model.getId())

    # Tools
    ##################################################

    def useCount(self):
        """The number of cards which used template number ord of the
        model obj.
        Keyword arguments
        model -- a model object."""
        return self.col.db.scalar("""
select count() from cards, notes where cards.nid = notes.id
and notes.mid = ? and cards.ord = ?""", self.model.getId(), self['ord'])

    # Required field/text cache
    ##########################################################################

    def _req(self, flds):
        """A rule which is supposed to determine whether a card should be
        generated or not according to its fields.
        See ../documentation/templates_generation_rules.md
        """
        ankiflagFlds = ["ankiflag"] * len(flds)
        emptyFlds = [""] * len(flds)
        data = [1, 1, self.model.getId(), 1, self['ord'], "", joinFields(ankiflagFlds), 0]
        # The html of the card at position ord where each field's content is "ankiflag"
        full = self.model.manager.col._renderQA(data)['q']
        data = [1, 1, self.model.getId(), 1, self['ord'], "", joinFields(emptyFlds), 0]
        # The html of the card at position ord where each field's content is the empty string ""
        empty = self.model.manager.col._renderQA(data)['q']

        # if full and empty are the same, the self is invalid and there is
        # no way to satisfy it
        if full == empty:
            return "none", [], []
        type = 'all'
        req = []
        for i in range(len(flds)):
            tmp = ankiflagFlds[:]
            tmp[i] = ""
            data[6] = joinFields(tmp)
            # if no field content appeared, field is required
            if "ankiflag" not in self.model.manager.col._renderQA(data)['q']:
                req.append(i)
        if req:
            return type, req
        # if there are no required fields, switch to any mode
        type = 'any'
        req = []
        for i in range(len(flds)):
            tmp = emptyFlds[:]
            tmp[i] = "1"
            data[6] = joinFields(tmp)
            # if not the same as empty, this field can make the card non-blank
            if self.model.manager.col._renderQA(data)['q'] != empty:
                req.append(i)
        return type, req
