# coding: utf-8

from anki.errors import DeckRenameError
from tests.shared import assertException, getEmptyCol


def test_basic():
    deck = getEmptyCol()
    # we start with a standard deck
    assert len(deck.decks.decks) == 1
    # it should have an id of 1
    assert deck.decks.name(1)
    # create a new deck
    parent = deck.decks.byName("new deck", create=True)
    assert parent
    parentId = parent.getId()
    assert len(deck.decks.decks) == 2
    # should get the same id
    assert deck.decks.id("new deck") == parentId
    # we start with the default deck selected
    assert deck.decks.selected() == 1
    assert deck.decks.active() == [1]
    # we can select a different deck
    parent.select()
    assert deck.decks.selected() == parentId
    assert deck.decks.active() == [parentId]
    # let's create a child
    child = deck.decks.byName("new deck::child", create=True)
    childId = child.getId()
    # it should have been added to the active list
    assert deck.decks.selected() == parentId
    assert deck.decks.active() == [parentId, childId]
    # we can select the child individually too
    child.select()
    assert deck.decks.selected() == childId
    assert deck.decks.active() == [childId]
    # parents with a different case should be handled correctly
    deck.decks.id("ONE")
    m = deck.models.current()
    m['did'] = deck.decks.id("one::two")
    m.save()
    n = deck.newNote()
    n['Front'] = "abc"
    deck.addNote(n)
    # this will error if child and parent case don't match
    deck.sched.deckDueList()

def test_remove():
    deck = getEmptyCol()
    # create a new deck, and add a note/card to it
    g1 = deck.decks.id("g1")
    f = deck.newNote()
    f['Front'] = "1"
    f.model()['did'] = g1
    deck.addNote(f)
    c = f.cards()[0]
    assert c.did == g1
    # by default deleting the deck leaves the cards with an invalid did
    assert deck.cardCount() == 1
    deck.decks.get(g1).rem()
    assert deck.cardCount() == 1
    c.load()
    assert c.did == g1
    # but if we try to get it, we get the default
    assert deck.decks.name(c.did) == "[no deck]"
    # let's create another deck and explicitly set the card to it
    g2 = deck.decks.id("g2")
    c.did = g2; c.flush()
    # this time we'll delete the card/note too
    deck.decks.get(g2).rem(cardsToo=True)
    assert deck.cardCount() == 0
    assert deck.noteCount() == 0

def test_rename():
    d = getEmptyCol()
    deck = d.decks.byName("hello::world", create=True)
    # should be able to rename into a completely different branch, creating
    # parents as necessary
    deck.rename("foo::bar")
    assert "foo" in d.decks.allNames()
    assert "foo::bar" in d.decks.allNames()
    assert "hello::world" not in d.decks.allNames()
    # create another deck
    deck = d.decks.id("tmp", create=True)
    # we can't rename it if it conflicts
    assertException(
        Exception, lambda: deck.rename("foo"))
    # when renaming, the children should be renamed too
    d.decks.id("one::two::three")
    deck = d.decks.byName("one", create=True)
    deck.rename("yo")
    for n in "yo", "yo::two", "yo::two::three":
        assert n in d.decks.allNames()
    # over filtered
    filtered = d.decks.newDyn("filtered")
    child = d.decks.byName("child", create=True)
    assertException(DeckRenameError, lambda: child.rename("filtered::child"))
    assertException(DeckRenameError, lambda: child.rename("FILTERED::child"))
    # changing case
    d.decks.id("PARENT")
    d.decks.id("PARENT::CHILD")
    assertException(DeckRenameError, lambda: child.rename("PARENT::CHILD"))
    assertException(DeckRenameError, lambda: child.rename("PARENT::child"))



def test_renameForDragAndDrop():
    d = getEmptyCol()

    def deckNames():
        return [ name for name in sorted(d.decks.allNames()) if name != 'Default' ]

    languages = d.decks.byName('Languages', create=True)
    languages_did = languages.getId()
    chinese = d.decks.byName('Chinese', create=True)
    chinese_did = chinese.getId()
    hsk = d.decks.byName('Chinese::HSK', create=True)
    hsk_did = hsk.getId()

    # Renaming also renames children
    chinese.renameForDragAndDrop(languages_did)
    assert deckNames() == [ 'Languages', 'Languages::Chinese', 'Languages::Chinese::HSK' ]

    # Dragging a deck onto itself is a no-op
    languages.renameForDragAndDrop(languages_did)
    assert deckNames() == [ 'Languages', 'Languages::Chinese', 'Languages::Chinese::HSK' ]

    # Dragging a deck onto its parent is a no-op
    hsk.renameForDragAndDrop(chinese_did)
    assert deckNames() == [ 'Languages', 'Languages::Chinese', 'Languages::Chinese::HSK' ]

    # Dragging a deck onto a descendant is a no-op
    languages.renameForDragAndDrop(hsk_did)
    assert deckNames() == [ 'Languages', 'Languages::Chinese', 'Languages::Chinese::HSK' ]

    # Can drag a grandchild onto its grandparent.  It becomes a child
    hsk.renameForDragAndDrop(languages_did)
    assert deckNames() == [ 'Languages', 'Languages::Chinese', 'Languages::HSK' ]

    # Can drag a deck onto its sibling
    hsk.renameForDragAndDrop(chinese_did)
    assert deckNames() == [ 'Languages', 'Languages::Chinese', 'Languages::Chinese::HSK' ]

    # Can drag a deck back to the top level
    chinese.renameForDragAndDrop(None)
    assert deckNames() == [ 'Chinese', 'Chinese::HSK', 'Languages' ]

    # Dragging a top level deck to the top level is a no-op
    chinese.renameForDragAndDrop(None)
    assert deckNames() == [ 'Chinese', 'Chinese::HSK', 'Languages' ]

    # can't drack a deck where sibling have same name
    new_hsk = d.decks.byName("HSK", create=True)
    new_hsk_did = new_hsk.getId()
    assertException(DeckRenameError, lambda: new_hsk.renameForDragAndDrop(chinese_did))
    d.decks.get(new_hsk_did).rem()

    # can't drack a deck where sibling have same name different case
    new_hsk = d.decks.byName("hsk", create=True)
    new_hsk_did = new_hsk.getId()
    assertException(DeckRenameError, lambda: new_hsk.renameForDragAndDrop(chinese_did))
    d.decks.get(new_hsk_did).rem()

    # '' is a convenient alias for the top level DID
    hsk.renameForDragAndDrop('')
    assert deckNames() == [ 'Chinese', 'HSK', 'Languages' ]

def test_check():
    d = getEmptyCol()

    d.decks.id("foo")
    d.decks.id("bar")
    FOO = d.decks.byName("bar", create=True)
    FOO["name"] = "FOO"
    FOO.save()
    d.decks._checkDeckTree()
    assert "foo" not in d.decks.allNames() or "FOO" not in d.decks.allNames()
