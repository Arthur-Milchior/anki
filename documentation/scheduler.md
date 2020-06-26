# What is actually a scheduler

The scheduler is a really complex code. I do not believe it needs to
be so complex, but currently it is. Here is an explanation of the
three principal things the scheduler does.

## Reviewing a card
The simplest activity consists in reviewing a card. The exact system
to compute the new due date is explained in
[computing_intervals.md][]. Reviewing the card means changing its next
due date, ease, interval. It also means means changing the number of
card reviewed in the card's deck and its ancestors. It may also means
burying its siblings.

## Computing the deck due tree
A tree is a list of deck, where each deck have its own tree of
descendants. To be precise, in graph theory, the structure would be a
forest of rooted trees.

There are two kinds trees, the deck due tree and the deck tree. The
deck tree is now created by the deck manager. The deck due tree is
similar to the deck tree, but it also contains the number displayed in
the deck browser. I.e. number of new cards to see today, number of
cards to review today, and, depending of the scheduler, either the
number of cards in learning or the number of steps in learning that
will occur today.

This deck due tree is essentially computed as follow. The deck tree is
first computed. Then, the daily limits are propagated from each deck
to its descendants, to ensure that deck "A::B" has no more new card
than deck "A". Then, from leaves to roots, the number of cards to
review in each deck is computed. The number of cards to review in its
children is added to the deck's number, and then the limit is
applied. So if "A" has at most three new cards by day, and "A::B" and
"A::C" has at most two new cards by day, "A::B" and "A::C" will both
display they have two new cards to display, but "A" will only display
that it has three new cards to review.

## Reviewing
While reviewing, the Scheduler is in charge of two things: computing
the numbers displayed by the reviewer and finding cards to
review. I'll deal with both cases now:

### Computing the number of cards to review
The computation is done the same way as the computation explained
above, but is restricted to the selected deck. To be more precise, it
uses limits from ancestors of the selected deck and card counts from
the descendants of the selected deck.

Each time a card is reviewed, the numbers are changed; i.e. if a new
card is reviewed, the count of new cards to review today in the
selected deck is decremented. This makes sens because the only way to
review the card is from the reviewer, and that it mainly takes its
cards from the scheduler. If the "undo" method sends a card back to
the reviewer, it manually deal with changing this number in the
scheduler back to its expected value.

Each time you make a significant change to the collection such as
undo, manually (un)bury, reschedule, (un)suspend, edit a card, the
scheduler "resets". Resetting tells the scheduler to recounts those
numbers. I believe it to be highly inneficient because if you are in
the browser, those numbers are not even displayed, so it's a lost of
compute.



You should note that "bury siblings" does not call reset. It means
that the number of cards displayed may not always be
accurante. I.e. if you have a deck with a limit of two new cards by
day, and it contains exactly two new cards which are siblings, you'll
see that the number of cards you'll review today is "2". However
you'll actually only review a single new card today since the sibling
is going to get buried. I want to emphasize that it would be extremly
simple to partially solve this problem, by counting distincts nids
instead of counting ids. The problem is that it will only solve the
problems for siblings appearing in the same deck. This was suggested
on anki forum https://forums.ankiweb.net/t/improving-daily-counts/507
while I wrote this post. I'll update it if any answera rrive.


### Finding a card to review
The scheduler is in charge to give the scheduler the next card to
display, thanks to `getCard`.

### Simple explanation

For the sake of simplicit, I am going to assume that you set the
preferences to display review cards first, then new cards. The other
cases are not really different.

The scheduler first check in all decks whether there is any card in
learning that are due now. More precisely, if it's a card that has
been in learning for a few minutes or hour, it'll show it first. If
the card was already in learning the past day and that the learning
step is greater than a day, it'll wait to display it.

If there is no such card, the scheduler will then look in all decks to
check whether there are cards to review today. Here it differs
depending on the scheduler. In version 1, it loops through each deck
in dictionnary order. It also uses limits to decide whether it should
find a card from a specific deck. In version 2, it looks in all decks
simultaneously, which allows to do mixed review; however it means it
can get cards from a subdeck even if the daily limit of this subdeck
is already reached.

If there is no review card to review, it will search for a new
card. Searching for new cards is done the same way than searching for
rev cards in scheduler version 1. If there is no such new card, it
will finally do the same thing with cards in learning that have been
in learning whose step was greater than a day. If it still finds no
card, it halts and the reviewer understand that the daily reviews are
done for this deck.


### Improvement: counting the number of card due
Since the scheduler knows the number of new/review card to see today,
it will use this information. If the number states that that are no
more cards in review to see today, it will not loop through decks to
find one.

### Improvement: queues of cards
If you have a deck with a lot of subdeck, the process described above
is extremly slow. It would mean that you need to iterate through each
deck to find the next card to review. Here is the improvement mades by
anki to make the process quicker.

Anki has four queues of cards. One for each kind of cards described
above. Anki will simply put in each queue the next card to review in
this queue. So instead of looking in all decks whether there is a card
in learning for today, a review card, a new card, or a card in
learning with a step greater than one day, anki will simply look
whether the queues are empty or not, and take the first card from the
first non-empty queue.

When a card is reviewed, all siblings of this cards are removed from
the queues. That is always the case, because even if you didn't check
"bury siblings", this action will ensure that you have some spacing
between a card and its siblings. Too be very precise, it only ensure
the spacing if both siblings are in the same deck and if you don't
make a change resetting the collection.

Each time the scheduler resets, the queues are emptied.

### Improvement: partially filling the queues
The improvement "queues of cards" is an extremely long process too. It
is better because only the first call to the scheduler will fill
the queue and then each future call will be quick. However, being slow
to start review is not a good idea, and furthermore, if you ever
suspend, bury, undo, etc... you should do it all again.

Instead, the rev and new queue will get filled with cards from only a
single deck. As soon as anki find a subdeck of the current deck with
cards to review, it will fetch all cards to review today in this deck
and add them to this queue. Anki will also recall the list of queues
that it has to check. So, when starting the process, Anki will first
recall that it need to check all subdecks of current deck. When Anki
discover that a deck has no new/due card to review, it'll remove this
deck to the list of deck to consider. This ensure that the queue gets
filled quickly and that duplicate works does not occur.

Each time the scheduler resets, the queues of decks is filled again
with all descendants of the selected decks.

### Proposed improvement: prefetching next card.
Here is an improvement I suggest. This improvement is not important
for anki, because on computer, database seems to be quite quick. I
believe it is an high improvement for ankidroid because it will reduce
the time spent waiting for a new card each time queues needs to be
refilled.

This consists simply in calling "getCard" in advance and saving the
result. On the next "getCard" from the reviewer, it gets the saved
card, and the next card is computed in background while the user can
review its card. It even allows to pre compute the question and
answer, which saves even more time.

The only problem I've met when implementing this idea is that,
usually, the "next" card is the card currently reviewed. This is
because usually, the scheduler review the card first and send the next
card only once the review is saved. If instead the next card is
precomputed, we should manually take the review into account.

This means that, if the "next card" is the current card or a sibling
of the current card, it should be discarded, and another "next card"
should be pre-fetched.

Actually, when we know what the current card currently is, we can
simply remove the current cards and its siblings from all queues,
which should remove the last problem most of the time. 

It should be noted that the reviewer gets its card from the scheduler
and from the "undo" function. So it's not enough to assume that the
current card is the result of the last call to "getCard". 
