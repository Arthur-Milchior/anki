# Differences with anki.
This files list the difference between regular anki and this forked
version. It also lists the different options in the Preferences's extra page.

## "Close and lose current input ?" (1574383623)
Anki will ask you to confirm whether you want to close a card where
a sticky field did change.

## Add card: change note only if you ask for it (424778276)
Yeah, this description seems ridiculous. But actually, anki does not
respect this.

## Add-on folder: keep more files (225953877)
When add-on are updated, all files are deleted, with some
exceptions. You can decide in the preferences which files are
kepts. Anki's default contains only config.json and the folder
user_files. This also adds `.git` `.gitignore` `.svn` and `.github`.

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

## Allowing complex card template (1713990897)
All version of anki bugs if you have a complex card template. For example,
if your template is enclosed in {{^field}} and {{/field}}. This option
allow complex card template. The only problem is that official anki
and smartphone apps won't be able to display those cards, and may want
to remove them if you press «check cards».

## Anki quicker (802285486)
Those modification makes anki quicker. Technical details are on the
add-on page.

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

## Edit new model without full sync (1988880085)

As long as you didn't sync your collection, you can add/remove/edit
field and card type to your new note types without having to do a full sync.

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

## Frozen Fields (516643804)
Add a small icon near the name of the field to make it sticky or not.

## Keep seen card.
By default, this version of anki does not delete a card if it has
already been seen once. Because, it should probably not be empty, and
so you may want to repair the card type, to create the card again.

If checked, the option "Delete empty cards only if they are new" set
back «Empty cards» to its original meaning; it'll delete even the seen
cards.

## Keeping note which have no cards (2018640062)
If you do «Empty cards», and a note has no more card, then you see a
warning, and the browser open to show you what notes have this
problem. You can thus correct them and avoid loosing the content of
their fields.

If you want to remove this feature, and have anki's default, uncheck
«Keep note without any card and warn» in the preferences.

## Merge decks (443286122)
If you move/rename a deck and that it conflicts with an already
existing deck, Anki will ask whether you want to merge decks.

## Multi column note editor (3491767031, 2064123047)
Allow to have editors with multiple columns. Allow to keep some fields
on their own line.

## New line in Json (112201952)
In order to lead configurations be easier to edit, this add-on allow
newline in json strings. It allow add newlines in the add-on
configuration editor.

## Open a window multiple time (354407385)
Allows to open multiple copy of the same window.

In the preferences, you can decide which you can open multiple time.

TODO: do it better than using stacks

## Postpone reviews (1152543397)

In the main window «Tool>Postpone reviews» allow you to tell anki that
you'll go (or have been) in holiday during a week, and so Anki should
add 7 days to every cards which are due. So, back from holiday, you'll
find anki as if you never left.

In the browser, you can select cards, then do «Cards>Postpone reviews»
to apply the same effect to selected cards only.

WARNING: This is a really bad idea. Because, you will see a lot of
cards too late and forget them. However, if you feel that, without
this feature, you'll just quit, then it's still better using it.

Note that the number of day could be negative. If you postpone review
by -1 day, then you'll see today tomorrow's card.

### Configuration

When you are late, this is taken into account by anki. For example, if
a card has a delay of two days, you take a week of vacation, and you
succesfully review the card, anki will remark that you recalled the
card seven days after last seeing it. Thus, it won't consider that the
delay is two days, but that it is seven days. And thus it will
computer a new delays of fourteen days, may be.

If you want to have this effect fully taken into account while using
this feature, in the preferences>extra, set «When adding days»
to 1. If you want that Anki totally ignores the fact that you have
added some days, and that it considers that the interval was two days,
then set this number to 0. If you want that anki considers this
postponing, but not totally, set a number between 0 and 1.

The «When removing days» feature is similar to the «When adding days»,
but consider days removed.

## Refresh browser (1347728560, 832679841)
Add the short-cut CTRL-F5 in browser to update the search

## Remove "Map to" in item import window for CSV (46741504)
Because of this text, the keyboard can't be used to search a field. I
thus remove it.

## See review instead of overview.
Most of the time, I don't care for overview; so going directly to
review is fine for me.

## Sort new cards (1665261045)
In the browser, and in the gear near the deck, you can change the
order in which you see new cards. You'll need to read
https://github.com/Arthur-Milchior/anki_sort_cards to learn how this
new order can be parametrized.

## Tag missing media (2027876532)
If a note is supposed to have media (image or audio), it will have the
tag "MissingMedia", when you «check media».

The prefenece "In case of missing media, show the notes in the
browser" allows to decide whether the browser show you the list of
notes with missing media when you check media.

## Update add-ons (1847544206)

While syncing collection, add-ons will be updated. Updates are exactly
the same process as when you click on the update button in the add-on manager.

## Usable card report (25425599)
Add more informations in the «empty card» report.
### Minutes in the browser
Allow the columns in browser to show hours and minutes. It may helps
to see more precisely when cards in learning are due, and see in which
order cards and notes where added/edited.

