# Counts
Here is the list of everything countend in the add-on. Not everything
can be displayed in a column. This document is mostly for people
working on the code.

## Values already computed by basic anki
### review today
The number of review cards to see today.

### new today
The number of new cards to learn today.

### Repetition of today learning
Numbers of review you'll see of cards in learning today.

## Numbers directly computed in the database
### learning now from today
Number of cards in learning to see today which was planified today.

### flag i
Cards flagged with flag i.

### learning today from past
Cards in learning to see today and which have waited at least a day.

### learning later today
Cards in learning which are due today but not now.

They were last seen today. There are no cards from past days, due
todays but not now.

### learning future
Cards in learning such that this review will not occur today (no way
of knowing whether its from today or from a past day)

### learning today repetition from today
Number of repetition you'll see today of cards currently in learning
such that last repetition was today.

Similar to Repetition of today
learning, restricting cards to the one seen today.

### learning today repetition from past
Number of repetition you'll see today of cards currently in learning
such that last repetition was NOT today.

Similar to last case, appart
from the negation

### learning repetition from today
Number of repetition you'll see ANY day of cards currently in learning
such that last repetition was today.

Similar to "learning today
repetition from today" case, appart that we count repetition not to
see today.

### learning repetition from past
Number of repetition you'll see ANY day of cards currently in learning
such that last repetition was NOT today.

Similar to "learning today
repetition from past" case, appart that we count repetition not to
see today. Similar to "learning repetition from today" apart from the negation.

### review due
Number of cards whach have already been seen and are due today (even
if it's greater than the maximal number of card the coniguration allow
to see for this deck)

### unseen
Number of cards which have never graduated and are not in learning.

### buried
Number of buried card

### suspended
Number of suspended card

### cards
Number of cards

### notes
Number of notes

### undue
Cards which have already been seen at least once, are not in learning,
are not due today.

### mature
any card already seen with an interval at least 21 days

### young
any card already seen with an interval at one day at most 20 days

## Sum of previous values

### learning now
Number of cards in learning ready to be seen (from today+from yesterday).

### learning later
Number of cards in learning not ready to be seen (to see later today,
or in the future).

### learning card
Number of cards in learning (now+later)

### learning today repetition
Number of repetition to cards in learding today (sum of repetition
from card from a past day, and from today).

Isn't it equal to "Repetition of today learning"???TODO

### learning repetition
Numbers of repetition of cards in learning, any days (sum of
repetitions from today and from past days)

### learning future repetition
Number of repetition of cards in learning, but not today. (Numbers of
repetition minus repetition to do today)

### review later
Cards to review, which are due, but won't be seen today because of
deck's configuration's limit. (review due - review today)

### reviewed today
Cards whose last succesfull review was today. (A card deleted after
review is not counted anymore. A card reviewed and moved is counted in
its new deck. A card reviewed many time is counted once. Cards in
learning are not counted. TODO: find how to easily find how to count
cards in learning whose last review is today)

### repeated today
Number of times you saw today a question from this deck. (A card
deleted after review is not counted anymore. A card reviewed and moved
is counted in its new deck.)

### repeated today
Number of times you saw a question from this deck anytime in the
past. (A card deleted after review is not counted anymore. A card
reviewed and moved is counted in its new deck.)

### unseen later
Cards never seen, and won't be seen today because of deck's
configuration's limit. (unseen - new today)

### repetition seen today
Number of repetition of cards to see today which are not new

### repetition today
Numbers of repetition of cards to see today

### cards seen today
Number of cards to see today which are not nue

### today
Number of cards to see today


Similar to Repetition of today learning, but each card is counted
once, even if it'll be seen multiple time.


# Sets
When we consider note, we must use sets instead of numbers. Because a
note may be in multiple subdeck, and we don't want to count it
multiple times.

The size of the sets are then counted and added in the previous
dictionnary.

### notes
The set of nids from this deck

### marked
the set of nids of marked notes in this deck

# Texts
Here, we have columns content which is more than just text

## Time
### learning now
Number of minute/seconds before a card in learning can be seen (only
if a value is not already given)

## Pair of value
Mature/young
Notes/cards
Buried/suspend
Reviewed/repeated today

## flags
flags 1 to 4.
### all flags
(considering flag 0, i.e. no flag).

## Now and later

### Review
review today (review later)

### unseen new
new today (unseen later)

### Learning today
learning now (learning later today)
