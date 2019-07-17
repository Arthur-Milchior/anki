# Computing the next review interval

The manual kind of let you guess how the
[intervals](https://apps.ankiweb.net/docs/manual.html#reviews) are
computed. But actually, you never get the real number, unless you read
the code. So, here is the exact rules.


For the new cards (in learning
cards), it is in method `_answerLrncard`. For the review cards, it
is in methods `_answerRevCard` and `_rescheduleRev`.

## Fuzzyness
Below, we explain how to compute a number of day for the new
interval. Sometime, we'll state that this number is "fuzzied". I.e. it
is slightly increased or decreased, in order to add randomnes, as
[explained in the
manual](https://apps.ankiweb.net/docs/manual.html#what-spaced-repetition-algorithm-does-anki-use).

We now explain the fuzzy function. The code described here is in
method `_fuzzedIvlRange`.

* If the interval is 1, then its fuzzy version is 1.
* If the interval is 2, its fuzzy version is 2 or 3.
* If the interval is at least three days, it's fuzzy version is a
  number between `interval-fuzz` and `interval+fuzz`. That is,
  a few days may be added or removed. We now explain how `fuzz`
  is computed.
  * If the interval is less than a week, then `fuzz` is 1.
  * If the interval is between 7 and 19 days, `fuzz` is 2
  * If the interval is between 20 and 26 days, `fuzz` is 3.
  * If the interval is between 27 and 09 days, `fuzz` is 4.
  * If the interval is at least a hundrad days, `fuzz` is 5
    percent of the interval.

## Parameters
We first list the parameters taken into account.

### Last interval
Last time you reviewed a card, an interval was assigned to it. It is
taken into account to compute the new interval. Unless this is a new
card.

### Easyness factor
Each card have a parameter called its easyness. It can be seen in the
«ease» factor of the browser.

The initial easyness, for new cards, depends on the deck. In the
deck's option, in the «New Cards» tag, it's «starting ease». By
default, it's 250%. This number never gets below 130.

When a review card lapse, it is decreased by 200. If you press hard,
it decreases by 150. If you press easy, it increases by 150.

For the mathematically inclined person, you can think of easyness as
the second derivative. Indeed the interval (which is the first
derivative) increases quicker when easyness is great. Those numbers,
-200, -150, 0 and 150, would be the four possible jounces, i.e., the
fourth derivatives.

### Interval modifier
Each deck option have an interval modifier. By default it's 1. You can
edit it in anki. (In code, it's `ivlFct`)

### Due date
The date at which you were supposed to see the review card.

### Delay
If you are late reviewing your card, we also take into account how
late you are. This is called the delay of the card.

## The formulas
The methods mentionned below appear in `anki.sched.Scheduler`.

### Filtered deck
If the card is in filtered deck, if the filter option "reschedule
cards based on my answers in this deck" is not checked, then the
interval is not modified and this review is not taken into account. We
now assume that this option is checked

#### Lapse of filtered
Two cases must be considered, depending on whether the card is seen in
advance or not.

If you review a card in advance, it's next due date can only
increase. If you lapsed the card, this lapse won't be taken into
account for the due date and interval. Only
success are taken into account.

If the card was already due, then the new nue date is the next
day. Interval is not modified however.

(Technically, the due date is the max between the old due date, and
the due date planned by this review)

#### Successful review of filtered
The new interval is the maximum between old interval and
elapsed*((easyness factor/1000)+1.2)/2, with elapsed being the time
between today and the last review.

This number is constrained to be between 1 and the `maxIvl` of the
card's configuration. This number is not fuzzified.

This formula is in the method `_dynIvlBoost`.

### Standard deck
#### New card
New cards stay in learning mode for some time. It is said to be
graduating when it leaves it.
##### Graduating
This case is quite easy. The initial interval is chosen according to
the values in the deck options. "graduating interval" and "easy
interval". Fuzziness is applied.
##### Remaining in learning mode
Each step is taken according to the deck option. In anki, in the
option, in New Cards, you can find «steps (in minutes)». This give the
list of successive steps.

#### Review cards
The new interval depends on which buttons is pressed. The main part of
the computation is done in the method `_nextRevIvl`.

Fuzziness is applied in the three cases. In all three case, the result
is at most maximal interval set in the deck's option.
##### Button Hard
In this case, the new interval is equal to the product of:
* the sum of the interval, and a fourth of the delay
* 1.2
* the interval modifier divided by 100

If this number is at most the
last interval, then the new interval is equal to the last interval,
plus one.

The result is rounded to the lowest integer.


##### Button good
In this case, the new interval is equal to the product of:
* the sum of the interval, and the half of the delay
* The easyness factor
* the interval modifier divided by 100

If this number is at most the one of the button hard, then the  new
interval is equal to the hard interval plus one. (This could be the
case if easiness is less than 1.2 and there is no delay)

##### Button easy
In this case, the new interval is equal to the product of:
* the sum of the interval, and the delay
* The easyness factor
* The easyness factor of the deck. It can be found in the deck's
  option, review tag, "easy bonus"
* the interval modifier divided by 100

If this number is at most the one of the button good, then the  new
interval is equal to the good interval plus one. (This could be the
case if you choose a very low easyness for the deck)


### Again
This case is quite easy. There is a number of steps, as in the deck's
option's lapse tag. Each time again is pressed, it starts at the first
step. Then the difference of time between two steps is as in this
list. When it graduates again, schedule for the day after.

When graduating again, the new interval is tomorrow Its done in
`_rescheduleAsRev`
