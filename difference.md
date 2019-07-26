# Differences with anki.
This files list the difference between regular anki and this forked
version. It also lists the different options in the Preferences's extra page.

## Explain deletion (12287769)
In your collection's folder, the file `deleted_long.txt` contains a
list of every notes deleted, the reason of the deletion, and some
other informations. It's saved as CSV, so that it can be recovered
(with difficulty, but it theoretically can)

## Explain errors
You obtain more detailled error message if a sync fail, and if you try
do do a «Check database».

It transform the very long method `fixIntegrity` into plenty of small
function. It would helps to do add-ons for this forked version of anki.

In the preferences, the button «Note with no card: create card 1
instead of deleting the note» chage the behavior of anki when he finds
a note which has no more card. This allow to lose the content of the
note, and let you correct the note instead to generate cards.

## Anki quicker (802285486)
Those modification makes anki quicker. Technical details are on the
add-on page.
