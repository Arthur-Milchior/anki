# coding: utf-8

import anki.template
from anki.consts import *
from anki.utils import joinFields, stripHTML
from tests.shared import getEmptyCol


def reqSize(model):
    if model['type'] == MODEL_CLOZE:
        return
    assert (len(model['tmpls']) == len(model['req']))

def test_modelDelete():
    deck = getEmptyCol()
    f = deck.newNote()
    f['Front'] = '1'
    f['Back'] = '2'
    deck.addNote(f)
    assert deck.cardCount() == 1
    deck.models.current().rem()
    assert deck.cardCount() == 0

def test_modelCopy():
    deck = getEmptyCol()
    m = deck.models.current()
    m2 = m.copy_()
    assert m2.getName() == "Basic copy"
    assert m2.getId() != m.getId()
    assert len(m2['flds']) == 2
    assert len(m['flds']) == 2
    assert len(m2['flds']) == len(m['flds'])
    assert len(m['tmpls']) == 1
    assert len(m2['tmpls']) == 1
    assert m.scmhash() == m2.scmhash()
    reqSize(m)
    reqSize(m2)

def test_fields():
    d = getEmptyCol()
    f = d.newNote()
    f['Front'] = '1'
    f['Back'] = '2'
    d.addNote(f)
    m = d.models.current()
    # make sure renaming a field updates the templates
    m['flds'][0].rename("NewFront")
    assert "{{NewFront}}" in m['tmpls'][0]['qfmt']
    h = m.scmhash()
    # add a field
    f = m.newField("foo")
    f.add()
    assert d.getNote(m.nids()[0]).fields == ["1", "2", ""]
    assert m.scmhash() != h
    # rename it
    f.rename("bar")
    assert d.getNote(m.nids()[0])['bar'] == ''
    # delete back
    m['flds'][1].rem()
    assert d.getNote(m.nids()[0]).fields == ["1", ""]
    # move 0 -> 1
    m['flds'][0].move(1)
    assert d.getNote(m.nids()[0]).fields == ["", "1"]
    # move 1 -> 0
    m['flds'][1].move(0)
    assert d.getNote(m.nids()[0]).fields == ["1", ""]
    # add another and put in middle
    f = m.newField("baz")
    f.add()
    f = d.getNote(m.nids()[0])
    f['baz'] = "2"
    f.flush()
    assert d.getNote(m.nids()[0]).fields == ["1", "", "2"]
    # move 2 -> 1
    m['flds'][2].move(1)
    assert d.getNote(m.nids()[0]).fields == ["1", "2", ""]
    # move 0 -> 2
    m['flds'][0].move(2)
    assert d.getNote(m.nids()[0]).fields == ["2", "", "1"]
    # move 0 -> 1
    m['flds'][0].move(1)
    assert d.getNote(m.nids()[0]).fields == ["", "2", "1"]

def test_templates():
    d = getEmptyCol()
    m = d.models.current(); mm = d.models
    t = m.newTemplate("Reverse")
    t['qfmt'] = "{{Back}}"
    t['afmt'] = "{{Front}}"
    t.add()
    m.save()
    reqSize(m)
    f = d.newNote()
    f['Front'] = '1'
    f['Back'] = '2'
    d.addNote(f)
    assert d.cardCount() == 2
    (c, c2) = f.cards()
    # first card should have first ord
    assert c.ord == 0
    assert c2.ord == 1
    # switch templates
    c.template().move(1)
    reqSize(m)
    c.load(); c2.load()
    assert c.ord == 1
    assert c2.ord == 0
    # removing a template should delete its cards
    assert m['tmpls'][0].rem()
    assert d.cardCount() == 1
    reqSize(m)
    # and should have updated the other cards' ordinals
    c = f.cards()[0]
    assert c.ord == 0
    assert stripHTML(c.q()) == "1"
    # it shouldn't be possible to orphan notes by removing templates
    t = m.newTemplate("tmpl name")
    t.add()
    reqSize(m)
    assert not m['tmpls'][0].rem()
    reqSize(m)

def test_cloze_ordinals():
    d = getEmptyCol()
    d.models.byName("Cloze").setCurrent()
    m = d.models.current(); mm = d.models
    
    #We replace the default Cloze template
    t = m.newTemplate("ChainedCloze")
    t['qfmt'] = "{{text:cloze:Text}}"
    t['afmt'] = "{{text:cloze:Text}}"
    t.add()
    m.save()
    m['tmpls'][0].rem()
    
    f = d.newNote()
    f['Text'] = '{{c1::firstQ::firstA}}{{c2::secondQ::secondA}}'
    d.addNote(f)
    assert d.cardCount() == 2
    (c, c2) = f.cards()
    # first card should have first ord
    assert c.ord == 0
    assert c2.ord == 1
    

def test_text():
    d = getEmptyCol()
    m = d.models.current()
    m['tmpls'][0]['qfmt'] = "{{text:Front}}"
    m.save()
    f = d.newNote()
    f['Front'] = 'hello<b>world'
    d.addNote(f)
    assert "helloworld" in f.cards()[0].q()

def test_cloze():
    d = getEmptyCol()
    d.models.byName("Cloze").setCurrent()
    f = d.newNote()
    assert f.model().getName() == "Cloze"
    # a cloze model with no clozes is not empty
    f['Text'] = 'nothing'
    assert d.addNote(f)
    # try with one cloze
    f = d.newNote()
    f['Text'] = "hello {{c1::world}}"
    assert d.addNote(f) == 1
    assert "hello <span class=cloze>[...]</span>" in f.cards()[0].q()
    assert "hello <span class=cloze>world</span>" in f.cards()[0].a()
    # and with a comment
    f = d.newNote()
    f['Text'] = "hello {{c1::world::typical}}"
    assert d.addNote(f) == 1
    assert "<span class=cloze>[typical]</span>" in f.cards()[0].q()
    assert "<span class=cloze>world</span>" in f.cards()[0].a()
    # and with 2 clozes
    f = d.newNote()
    f['Text'] = "hello {{c1::world}} {{c2::bar}}"
    assert d.addNote(f) == 2
    (c1, c2) = f.cards()
    assert "<span class=cloze>[...]</span> bar" in c1.q()
    assert "<span class=cloze>world</span> bar" in c1.a()
    assert "world <span class=cloze>[...]</span>" in c2.q()
    assert "world <span class=cloze>bar</span>" in c2.a()
    # if there are multiple answers for a single cloze, they are given in a
    # list
    f = d.newNote()
    f['Text'] = "a {{c1::b}} {{c1::c}}"
    assert d.addNote(f) == 1
    assert "<span class=cloze>b</span> <span class=cloze>c</span>" in (
        f.cards()[0].a())
    # if we add another cloze, a card should be generated
    cnt = d.cardCount()
    f['Text'] = "{{c2::hello}} {{c1::foo}}"
    f.flush()
    assert d.cardCount() == cnt + 1
    # 0 or negative indices are not supported
    f['Text'] += "{{c0::zero}} {{c-1:foo}}"
    f.flush()
    assert len(f.cards()) == 2

def test_cloze_mathjax():
    d = getEmptyCol()
    d.models.byName("Cloze").setCurrent()
    f = d.newNote()
    f['Text'] = r'{{c1::ok}} \(2^2\) {{c2::not ok}} \(2^{{c3::2}}\) \(x^3\) {{c4::blah}} {{c5::text with \(x^2\) jax}}'
    assert d.addNote(f)
    assert len(f.cards()) == 5
    assert "class=cloze" in f.cards()[0].q()
    assert "class=cloze" in f.cards()[1].q()
    assert "class=cloze" not in f.cards()[2].q()
    assert "class=cloze" in f.cards()[3].q()
    assert "class=cloze" in f.cards()[4].q()

def test_chained_mods():
    d = getEmptyCol()
    d.models.byName("Cloze").setCurrent()
    m = d.models.current(); mm = d.models
    
    #We replace the default Cloze template
    t = m.newTemplate("ChainedCloze")
    t['qfmt'] = "{{cloze:text:Text}}"
    t['afmt'] = "{{cloze:text:Text}}"
    t.add()
    m.save()
    m['tmpls'][0].rem()
    
    f = d.newNote()
    q1 = '<span style=\"color:red\">phrase</span>'
    a1 = '<b>sentence</b>'
    q2 = '<span style=\"color:red\">en chaine</span>'
    a2 = '<i>chained</i>'
    f['Text'] = "This {{c1::%s::%s}} demonstrates {{c1::%s::%s}} clozes." % (q1,a1,q2,a2)
    assert d.addNote(f) == 1
    assert "This <span class=cloze>[sentence]</span> demonstrates <span class=cloze>[chained]</span> clozes." in f.cards()[0].q()
    assert "This <span class=cloze>phrase</span> demonstrates <span class=cloze>en chaine</span> clozes." in f.cards()[0].a()

def test_modelChange():
    deck = getEmptyCol()
    basic = deck.models.byName("Basic")
    cloze = deck.models.byName("Cloze")
    reqSize(basic)
    reqSize(cloze)
    # enable second template and add a note
    m = deck.models.current(); mm = deck.models
    t = m.newTemplate("Reverse")
    t['qfmt'] = "{{Back}}"
    t['afmt'] = "{{Front}}"
    t.add()
    m.save()
    reqSize(basic)
    f = deck.newNote()
    f['Front'] = 'f'
    f['Back'] = 'b123'
    assert str(f.mid) == basic['id']
    deck.addNote(f)
    # switch fields
    map = {0: 1, 1: 0}
    basic.change(basic, [f.id], map, None)
    f.load()
    assert str(f.mid) == basic['id']
    assert f['Front'] == 'b123'
    assert f['Back'] == 'f'
    # switch cards
    c0 = f.cards()[0]
    c1 = f.cards()[1]
    assert "b123" in c0.q()
    assert "f" in c1.q()
    assert c0.ord == 0
    assert c1.ord == 1
    basic.change(basic, [f.id], None, map)
    f.load(); c0.load(); c1.load()
    assert str(f.mid) == basic['id']
    assert "f" in c0.q()
    assert "b123" in c1.q()
    assert c0.ord == 1
    assert c1.ord == 0
    # .cards() returns cards in order
    assert f.cards()[0].id == c1.id
    # delete first card
    map = {0: None, 1: 1}
    basic.change(basic, [f.id], None, map)
    f.load()
    assert str(f.mid) == basic['id']
    c0.load()
    # the card was deleted
    try:
        c1.load()
        assert 0
    except TypeError:
        pass
    # but we have two cards, as a new one was generated
    assert len(f.cards()) == 2
    # an unmapped field becomes blank
    assert f['Front'] == 'b123'
    assert f['Back'] == 'f'
    basic.change(basic, [f.id], map, None)
    f.load()
    assert str(f.mid) == basic['id']
    assert f['Front'] == ''
    assert f['Back'] == 'f'
    # another note to try model conversion
    f = deck.newNote()
    f['Front'] = 'f2'
    f['Back'] = 'b2'
    deck.addNote(f)
    assert basic.useCount() == 2
    assert cloze.useCount() == 0
    map = {0: 0, 1: 1}
    cloze.change(basic, [f.id], map, map)
    f.load()
    assert str(f.mid) == cloze['id']
    assert f['Text'] == "f2"
    assert len(f.cards()) == 2
    # back the other way, with deletion of second ord
    basic['tmpls'][1].rem()
    reqSize(basic)
    assert deck.db.scalar("select count() from cards where nid = ?", f.id) == 2
    basic.change(cloze, [f.id], map, map)
    f.load()
    assert str(f.mid) == basic['id']
    assert deck.db.scalar("select count() from cards where nid = ?", f.id) == 1

def test_templates():
    d = dict(Foo="x", Bar="y")
    assert anki.template.render("{{Foo}}", d) == "x"
    assert anki.template.render("{{#Foo}}{{Foo}}{{/Foo}}", d) == "x"
    assert anki.template.render("{{#Foo}}{{Foo}}{{/Foo}}", d) == "x"
    assert anki.template.render("{{#Bar}}{{#Foo}}{{Foo}}{{/Foo}}{{/Bar}}", d) == "x"
    assert anki.template.render("{{#Baz}}{{#Foo}}{{Foo}}{{/Foo}}{{/Baz}}", d) == ""

def test_availOrds():
    d = getEmptyCol()
    m = d.models.current(); mm = d.models
    t = m['tmpls'][0]
    f = d.newNote()
    f['Front'] = "1"
    # simple templates
    assert m.availOrds(joinFields(f.fields)) == [0]
    t['qfmt'] = "{{Back}}"
    m.save(template=True)
    assert not m.availOrds(joinFields(f.fields))
    # AND
    t['qfmt'] = "{{#Front}}{{#Back}}{{Front}}{{/Back}}{{/Front}}"
    m.save(template=True)
    assert not m.availOrds(joinFields(f.fields))
    t['qfmt'] = "{{#Front}}\n{{#Back}}\n{{Front}}\n{{/Back}}\n{{/Front}}"
    m.save(template=True)
    assert not m.availOrds(joinFields(f.fields))
    # OR
    t['qfmt'] = "{{Front}}\n{{Back}}"
    m.save(template=True)
    assert m.availOrds(joinFields(f.fields)) == [0]
    t['Front'] = ""
    t['Back'] = "1"
    assert m.availOrds(joinFields(f.fields)) == [0]
