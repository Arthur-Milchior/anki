# Differences with anki.
This files list the difference between regular anki and this forked
version. It also lists the different options in the Preferences's extra page.

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

