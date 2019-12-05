import re

from anki.models import ModelManager


def _modSchemaIfRequired(col, m):
    if m['id'] and m.get("ls", 0) != self.col.ls:
        self.col.modSchema(check=True)
ModelManager._modSchemaIfRequired = _modSchemaIfRequired

def removeLS(self):
    for m in self.all():
        if "ls" in m:
            del m["ls"]
Models.removeLS = removeLS

oldBeforeUpload = Models.beforeUpload
def beforeUpload(self):
    self.removeLS
    oldBeforeUpload(self)
Models.beforeUpload = beforeUpload


## Replacing by _modSchemaIfRequired
def rem(self, m):
    "Delete model, and all its cards/notes."
    self._modSchemaIfRequired(self.col, m)
    current = self.current()['id'] == m['id']
    # delete notes/cards
    self.col.remCards(self.col.db.list("""
select id from cards where nid in (select id from notes where mid = ?)""",
                                  m['id']))
    # then the model
    del self.models[str(m['id'])]
    self.save()
    # GUI should ensure last model is not deleted
    if current:
        self.setCurrent(list(self.models.values())[0])
ModelManager.rem = rem

def setSortIdx(self, m, idx):
    assert 0 <= idx < len(m['flds'])
    self._modSchemaIfRequired(self.col, m)
    m['sortf'] = idx
    self.col.updateFieldCache(self.nids(m))
    self.save(m)
ModelManager.setSortIdx = setSortIdx

def addField(self, m, field):
    # only mod schema if model isn't new.
    # usn is -1 if either model is new or model has been changed.
    # in the second case, schema is already marked as modified.
    self._modSchemaIfRequired(self.col, m)
    m['flds'].append(field)
    self._updateFieldOrds(m)
    self.save(m)
    def add(fields):
        fields.append("")
        return fields
    self._transformFields(m, add)
ModelManager.addField = addField

def remField(self, m, field):
    self._modSchemaIfRequired(self.col, m)
    # save old sort field
    sortFldName = m['flds'][m['sortf']]['name']
    idx = m['flds'].index(field)
    m['flds'].remove(field)
    # restore old sort field if possible, or revert to first field
    m['sortf'] = 0
    for c, f in enumerate(m['flds']):
        if f['name'] == sortFldName:
            m['sortf'] = c
            break
    self._updateFieldOrds(m)
    def delete(fields):
        del fields[idx]
        return fields
    self._transformFields(m, delete)
    if m['flds'][m['sortf']]['name'] != sortFldName:
        # need to rebuild sort field
        self.col.updateFieldCache(self.nids(m))
    # saves
    self.renameField(m, field, None)
ModelManager.remField = remField

def moveField(self, m, field, idx):
    self._modSchemaIfRequired(self.col, m)
    oldidx = m['flds'].index(field)
    if oldidx == idx:
        return
    # remember old sort field
    sortf = m['flds'][m['sortf']]
    # move
    m['flds'].remove(field)
    m['flds'].insert(idx, field)
    # restore sort field
    m['sortf'] = m['flds'].index(sortf)
    self._updateFieldOrds(m)
    self.save(m)
    def move(fields, oldidx=oldidx):
        val = fields[oldidx]
        del fields[oldidx]
        fields.insert(idx, val)
        return fields
    self._transformFields(m, move)
ModelManager.moveField = moveField

def renameField(self, m, field, newName):
    self._modSchemaIfRequired(self.col, m)
    pat = r'{{([^{}]*)([:#^/]|[^:#/^}][^:}]*?:|)%s}}'
    def wrap(txt):
        def repl(match):
            return '{{' + match.group(1) + match.group(2) + txt +  '}}'
        return repl
    for t in m['tmpls']:
        for fmt in ('qfmt', 'afmt'):
            if newName:
                t[fmt] = re.sub(
                    pat % re.escape(field['name']), wrap(newName), t[fmt])
            else:
                t[fmt] = re.sub(
                    pat  % re.escape(field['name']), "", t[fmt])
    field['name'] = newName
    self.save(m)
ModelManager.renameField = renameField

def addTemplate(self, m, template):
    "Note: should col.genCards() afterwards."
    # usn is -1 if either model is new or model has been changed.
    # in the second case, schema is already marked as modified.
    self._modSchemaIfRequired(self.col, m)
    m['tmpls'].append(template)
    self._updateTemplOrds(m)
    self.save(m)
ModelManager.addTemplate = addTemplate

def remTemplate(self, m, template):
    "False if removing template would leave orphan notes."
    assert len(m['tmpls']) > 1
    # find cards using this template
    ord = m['tmpls'].index(template)
    cids = self.col.db.list("""
select c.id from cards c, notes f where c.nid=f.id and mid = ? and ord = ?""",
                             m['id'], ord)
    # all notes with this template must have at least two cards, or we
    # could end up creating orphaned notes
    if self.col.db.scalar("""
select nid, count() from cards where
nid in (select nid from cards where id in %s)
group by nid
having count() < 2
limit 1""" % ids2str(cids)):
        return False
    # ok to proceed; remove cards
    self._modSchemaIfRequired(self.col, m)
    self.col.remCards(cids)
    # shift ordinals
    self.col.db.execute("""
update cards set ord = ord - 1, usn = ?, mod = ?
 where nid in (select id from notes where mid = ?) and ord > ?""",
                         self.col.usn(), intTime(), m['id'], ord)
    m['tmpls'].remove(template)
    self._updateTemplOrds(m)
    self.save(m)
    return True
ModelManager.remTemplate = remTemplate

def change(self, m, nids, newModel, fmap, cmap):
    self._modSchemaIfRequired(self.col, m)
    assert newModel['id'] == m['id'] or (fmap and cmap)
    if fmap:
        self._changeNotes(nids, newModel, fmap)
    if cmap:
        self._changeCards(nids, m, newModel, cmap)
    self.col.genCards(nids)
ModelManager.change = change

oldNew = ModelManager.new
def new(self, name):
    m = oldNew(self, name)
    m['usn'] = self.col.usn()
    return m
ModelManager.new = new

oldCopy = ModelManager.copy
def copy(self, name):
    m = oldCopy(self, name)
    m['usn'] = self.col.usn()
    return m
ModelManager.copy = copy

def addField(self, m, field):
    self._modSchemaIfRequired(self.col, m)
    m['flds'].append(field)
    self._updateFieldOrds(m)
    self.save(m)
    def add(fields):
        fields.append("")
        return fields
    self._transformFields(m, add)
ModelManager.addField = addField

def addTemplate(self, m, template):
    "Note: should col.genCards() afterwards."
    # usn is -1 if either model is new or model has been changed.
    # in the second case, schema is already marked as modified.
    self._modSchemaIfRequired(self.col, m)
    m['tmpls'].append(template)
    self._updateTemplOrds(m)
    self.save(m)
ModelManager.addTemplate = addTemplate
