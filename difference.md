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

