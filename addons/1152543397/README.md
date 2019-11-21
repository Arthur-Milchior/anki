# Postpone card's review
## Rationale
Some people find anki frustrating because it does not forgive you if
you skip a day or a week. When you come back, anki tells you to review
many days of cards immediatly. That's overwhelming, and sometime, it
makes people quit anki.

While anki's right in a theoretical sens, it is wrong in a practical
sens. It may be better for the memory to see everything as soon as
possible. But in practice, it's even better to be late and not to quit
anki.

This add-on is thus made for those people, who knows they are human,
and not perfect machine. Who knows that it's better to cheat with anki
a little bit than to quit it. This add-on change the due date of every
cards already learned once, and add to it as many day as you want.

If you want to go one week in holiday, just add 7 days to every cards,
and you'll see the same number of cards as usual when you come
back. (Note however that you may find that you have forgotten more
cards than usual).

### Second constraint
This add-on should also satisfies a second constraint. You don't need
it to review cards.

You'll use this add-on to change the due date of cards. But once it's
done and you have synchronized your deck, you can see the cards on any
computer, phone, or using ankiweb.

## Usage
You can either add delays to every cards or only to selected one.

### All cards
In the main window, open ```tools``` then ```Postpone cards```.

### Selected cards
In the browser, select every card you want to move. Select ```Edit```,
then select ```Postpone cards```, and the delay will only be
added to cards which you have selecteds and which are due.

### Both cases
A window will ask you how many days of delay you want to
add. Enter the number, and press ok.

The number can be either negative or positive. It means you can also
remove days. This may mostly be useful if you figure out you have
added to many days.

The interval of each card is also changed, to reflect the change in
due date. See the configuration section below to learn more about it.

## Configuration
The documentation for the configuration file can be found on
[config.md](https://github.com/Arthur-Milchior/Anki-postpone-reviews/config.md).


## Internal
This add-on does not change any method. Of course, it adds actions in
menus.

## Version 2.0
There are nothing similar in version 2.0 as far as I know

## TODO
### Adding smaller intervals to cards due later
Let us assume you had spent a week without using anki. You use this
add-on and tell anki so that you don't have to immediatly see 7 cards.

But, imagine: may be even if you don't want to see a full week of
cards in a single day, you'd accept to see 2 days of cards. It will
take twice as more time, but in a week, you won't be late anymore.

If you set this option to 2, you'll see two days of card every day
during a week.

In practice, it means that instead of adding 7 days to every single
cards, it will add 7 days to the cards due 7 days ago. It will add 6
days to the card due 6 and 5 days ago. It will add 4 days to the cards
due 4 and 3 days ago, and so on.

### Reorder in function of priority
This add-on does not take into account which cards are urgent and
which ones can wait. Maybe you took a week of holiday. During those
holidays, you were supposed to see cards which you last saw the week
before the holiday, and some other cards you last saw 6 months
ago. Clearly, the first one is more urgent than the second one.

Using this option, you'll still have the same number of cards to see
today, but you'll see the more urgent one first.

Not that the more urgent one may potentially be the hardest one. If
you use this option, you may have a lot of «see again» in the first
days, instead of having a few of them during the whole week.

## Links, licence and credits

Key         |Value
------------|-------------------------------------------------------------------
Copyright   | Arthur Milchior <arthur@milchior.fr>, Jasonbarc https://github.com/jasonsparc
Based on    | Anki code by Damien Elmes <anki@ichi2.net>
License     | GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
Source in   | https://github.com/Arthur-Milchior/Anki-postpone-reviews
Addon number| [1152543397](https://ankiweb.net/shared/info/1152543397)
