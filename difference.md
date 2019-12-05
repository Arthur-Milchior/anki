# Differences with anki.
This files list the difference between regular anki and this forked
version. It also lists the different options in the Preferences's extra page.

## Add/remove deck prefix (683170394)
In the browser, you can select cards, and then do `Decks > Add
prefix`, to add the same prefix to the deck name of all of those
cards. This ensure that they all belong to a same deck, while keeping
the same deck hierarchy. `Decks > Remove prefix` allows to remove this
common prefix and thus cancel the action `Add prefix`.

## Added today (861864770)
Add an option in the add card window to open the browser with notes
created today.


## Advanced browser (874215009)
This add-on adds many features. In particular, for devs, it adds a
class for browser's column, in order to add more columns easily

## Allow to keep first field empty (46741504)

## Batch Edit (291119185)
Allow to make the same edit to multiple cards. Either changing a
field, or adding text after/before it.

In preferences, you can decide whether you add a new line between the
old text and the added one.

## Browser from reviewer: open directly the deck (1555020859)

## Compile LaTeX as soon as possible (769835008)

As soon as a note with LaTeX is saved, its latex is compiled. A
message warns when there is an error. To save time, once an expression
failed, it's not tried again.

## Copy note (1566928056)
If you select notes in the browser, and do `Notes>Copy Notes` or
`Ctrl+Alt+C`, a copy of the notes are created.

You have two options in the preferences:
* "Preserve date of creation": keeps the «Created» value in the
  browser. It is particularly interesting if you review cards
  according to their creation date.
* "Preserve easyness, interval, due date, ...": this create a copy of
  each card, as close as possible to the original card. If you uncheck
  this, instead, your new cards will be fresh, and you'll start review
  from 0.

## Explain errors
You obtain more detailled error message if a sync fail, and if you try
do do a «Check database».

It transform the very long method `fixIntegrity` into plenty of small
function. It would helps to do add-ons for this forked version of anki.

In the preferences, the button «Note with no card: create card 1
instead of deleting the note» chage the behavior of anki when he finds
a note which has no more card. This allow to lose the content of the
note, and let you correct the note instead to generate cards.
This add-on adds many features to the browser.

### Improvment for dev
To add a column, you only need to add one more object of type BrowserColumn.
This add-on adds many features. In particular, for devs, it adds a
class for browser's column, in order to add more columns easily

### Sorting everything
You can sort any columns. Including decks, cards, notes, tags.

### Improvment for dev
To add a column, you only need to add one more object of type BrowserColumn.

## Export notes selected in the Browser (1983204951)
Selects some cards in the browser. Then `Cards>Export cards` allow you
to export the cards. This is similar to exporting a deck, except that
you have more fine control. You can essentially export anything that
you can query in the browser or that you can select.

Note that, if you export a deck, or a selection of cards, and that you
export cards, you are also exporting the notes of those
cards. However, some cards may be missing. When importing those cards,
the missing cards will be generated, and will be totally new. You may
lose data this way.  In the preference "Export siblings of exported
cards" allow you to avoid losing data, by exporting the siblings of
exported cards. The problem being, of course, that you may export
cards in decks you did not select. Thus, importing those cards may
potentially create more decks than expected.

## Keep seen card.
By default, this version of anki does not delete a card if it has
already been seen once. Because, it should probably not be empty, and
so you may want to repair the card type, to create the card again.

If checked, the option "Delete empty cards only if they are new" set
back «Empty cards» to its original meaning; it'll delete even the seen
cards.

## Refresh browser (1347728560, 832679841)
Add the short-cut CTRL-F5 in browser to update the search

## Remove "Map to" in item import window for CSV (46741504)
Because of this text, the keyboard can't be used to search a field. I
thus remove it.

## Update add-ons (1847544206)

While syncing collection, add-ons will be updated. Updates are exactly
the same process as when you click on the update button in the add-on manager.

## Usable card report (25425599)
Add more informations in the «empty card» report.
### Minutes in the browser
Allow the columns in browser to show hours and minutes. It may helps
to see more precisely when cards in learning are due, and see in which
order cards and notes where added/edited.

