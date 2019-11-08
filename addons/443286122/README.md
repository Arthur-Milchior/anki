# Merging deck
## Rationale
Decks are more or less than folder/directory in our computer. It
contains contents, subdecks.... With one main difference, you can't
merge decks. 

Sometime, I just want to merge deck. I want to move every card from
one deck to another. I also may want to consider that A::X::Y and X::Y
are the same deck. Currently, the only way to do this is by going in
the browser, selecting cards subdeck by subdeck, and moving them. It
takes a lot of time.

This add-on allows you to merge decks. More precisely, instead of
simply telling you "That deck already exists.", the add-on will asks
you whether you want to merge the moved deck into the other deck.

Let's say you have decks:
* A::X::Y
* X::Y
* X::Z

and you drag and drop X onto A.
It'll ask whether you want to merge X into A::X. If you accept, the
content of X will move into A::X. The content of X::Y to A::X::Y. And
X::Z will be moved to A::X::Z, as it would have been without this
add-on.

## Warning
When you merge a deck into another deck, it loses it's
configuration. The configuration of the decks in which things are
merged (A::X in the previous example) is kept.

## Configuration
None

## Internal
It modifies the methods:
* aqt.deckbrowser._dragDeckOnto
* aqt.deckbrowser._rename
* anki.decks.rename
* anki.decks.rename.renameForDragAndDrop

## Version 2.0
None

## Links, licence and credits

Key         |Value
------------|-------------------------------------------------------------------
Copyright   | Arthur Milchior <arthur@milchior.fr>
Based on    | Anki code by Damien Elmes <anki@ichi2.net>
License     | GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
Source in   | https://github.com/Arthur-Milchior/anki-merge-decks
Addon number| [443286122](https://ankiweb.net/shared/info/443286122)
Support me on| [![Ko-fi](https://ko-fi.com/img/Kofi_Logo_Blue.svg)](Ko-fi.com/arthurmilchior) or [![Patreon](http://www.milchior.fr/patreon.png)](https://www.patreon.com/bePatron?u=146206)
