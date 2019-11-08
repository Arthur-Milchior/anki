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

## Sort new cards (1665261045)
In the browser, and in the gear near the deck, you can change the
order in which you see new cards. You'll need to read
https://github.com/Arthur-Milchior/anki_sort_cards to learn how this
new order can be parametrized.

