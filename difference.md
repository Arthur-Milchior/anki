# Differences with anki.
This files list the difference between regular anki and this forked
version. It also lists the different options in the Preferences's extra page.

## Explain errors
You obtain more detailled error message if a sync fail, and if you try
do do a «Check database».

It transform the very long method `fixIntegrity` into plenty of small
function. It would helps to do add-ons for this forked version of anki.

In the preferences, the button «Note with no card: create card 1
instead of deleting the note» chage the behavior of anki when he finds
a note which has no more card. This allow to lose the content of the
note, and let you correct the note instead to generate cards.

## Keep seen card.
By default, this version of anki does not delete a card if it has
already been seen once. Because, it should probably not be empty, and
so you may want to repair the card type, to create the card again.

If checked, the option "Delete empty cards only if they are new" set
back «Empty cards» to its original meaning; it'll delete even the seen
cards.

