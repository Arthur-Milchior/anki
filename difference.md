# Differences with anki.
This files list the difference between regular anki and this forked
version. It also lists the different options in the Preferences's extra page.

## Advanced browser (874215009)
This add-on adds many features. In particular, for devs, it adds a
class for browser's column, in order to add more columns easily

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

## Refresh browser (1347728560, 832679841)
Add the short-cut CTRL-F5 in browser to update the search

## Update add-ons (1847544206)

While syncing collection, add-ons will be updated. Updates are exactly
the same process as when you click on the update button in the add-on manager.

## Usable card report (25425599)
Add more informations in the «empty card» report.
### Minutes in the browser
Allow the columns in browser to show hours and minutes. It may helps
to see more precisely when cards in learning are due, and see in which
order cards and notes where added/edited.

