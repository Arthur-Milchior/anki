Here is the documentation of vocabulary found in anki code and not in
anki's documentation. Because it's mostly internal stuff.

# Collection
## Deck conf
That's one of the option which can be applied to a deck in the main
page.

## Model
What code calls model is called «note type» in Anki's
documentation. The name model is still found in the synchronization
protocol, and in «mid», which represents id of note type.

## Template
What code calls template is called «card type» in Anki's
documentation.

## id's
The idea of an object is often denoted as `Oid`, with O the
initial of the kind of object. Thus cid, nid, mid, did and oid, for
ids of card, note, model, deck, and original deck.

However, in the object itself, the id is denoted as `id` and not
as `Oid`. For example, the id of a card is `card.id`.


# Main window
The main window may display different kind of content. The «state» of
the main window is the kind of content on it.

* Reviewer: The window with a card, and button to answer.
* DeckBrowser: The list of decks
* sync: waiting for sync to finish (the content is the same as
  deckbrowser)
* overview: what you obtain when selecting a deck but not yet studying it
* profileManager: no window, instead ask to choose for a profile
* startup: empty window, before collection is loaded.
