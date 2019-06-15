This document discuss the `due` value of new card. It's main goal
is to express why I believe it to be currently broken. I will give
plenty of way to have wrong `due` values, without even installing an
add-on.

It also propose ways to fix it, and explain the problem I see with all
of them. Which, I believe, argues that the definition of `due` should be
slightly changed.

In this document, I will only consider new cards, but I will not
repeat it again.

# Definition
Because some terms are confusing, I have to state some explicit
definition now.

## New card.
When I write «new card» in this document, it always mean a card which
has the property to be «new». It may be a card created years ago. When
I speak of a card which has just been created, I'll write «the created
card».

## What is `due` ?
New cards are shown in a particular order. Computing this order may
takes some time. So, instead, anki pre-compute this order. This
precomputation is called `due`. Each new card has an integer value
called `due`. The cards which should be seen first have the lowest
`due` value.

The `due` value is a 32 bit integer. This is ensured because each time
a `due` value is greater than 1,000,000, it is changed to 1,000,000
during database check.

## Reordering a deck
I'll speak a lot about "reordering a deck", so let me introduce this
notion here. By «reordering a deck», I mean going to the deck option
and changing «new card in random order» to «new cards in order added»
and reciprocally. This action ensure that each card of the deck get a
new `due` value, almost according to the description of the option
(but not totally).


## Properties that the `due` value should hold
### Siblings
For the sake of the simplicity, let us assume in this section
(Siblings) that sibling cards belong to the same deck.

Ideally, if you have seen a new card, you'll see its sibling very
soon. In the best case, as soon as you see a new card from the same
deck, you'll see the new siblings of any card you have already seen,
unless those cards are already buried/suspended. You'll discover a new
note only if no such new siblings exists.  This certainly may help to
remember the whole content of the note.

This is ensured by giving the same `due` date to all siblings. So all
new card with the smallest `due` date are siblings. However when you
reorder a deck, and set it to random order, a new card may have a high
`due` value and siblings which are not new. This means that you'll
have to wait quite some time to see a new sibling of a seen card.


The property that all siblings have the same `due` date is true while
notes are created. If each sibling of a card belong to the same deck
(not considering subdecks), and this deck is reordered (i.e. in deck's
option, the new card in random order/order added) is toggled.

However, this property may get lost in at least two cases:
* if a card is reordered while its sibling is not
* if siblings belong to different deck, and one deck gets reordered

### Uniqueness
Normally, each card with the same `due` value belongs to the same
note. This is ensured because each time a `due` value is required,
(i.e. when adding a card or reordering a deck), the `due` value
chosen are greater than the maximal `due` value already present in
the collection.

This property is true almost all the time, at least unless you or an
add-on change the database directly. However, there is one case where
this became false, if the `due` value of a card is 1,000,000 or
greater. In this case:
* until april 2019 (anki 2.1.12): all cards have `due` value 1,000,000.
* since april 2019 (anki 2.1.13): the due values are computed modulo
  1,000,000, which means that you may have a lot of cards with due
  value 0, 1, ...

### Order of adding cards
If a deck has «new card in order added», then the `due` card
represents the order in which card are added to the collection. When
cards are created using anki directly, or imported from a CSV file, it
simply means that the `due` are in the same order than the `created`
value. However, if a deck is imported (for example by downloading it
from ankiweb first), then the `created` value represents the day where
the card was created originally, and not the day were the cards were
added to our collection.

In particular, it means that the «order added» can never be recomputed
once it is lost. This can be seen using the following steps:
* take a deck with «new card in random order».
* add it a new note
* import a deck (which was created before your new note was created)
* toggle the deck to new card in order added.

You'll see that the imported notes are shown before the note you
created, while they were added after it.

### Random order
If a deck has «new cards in random order», the notes should be seen in
an unpredictable order.

Actually, this occurs only in two cases:
* when the notes are imported in the deck from an anki2 file,
* for cards present in the deck when the deck has been reordered,

## How to reproduce bugs
In this section, I explain how to have a few strange result, without
using any add-on. The argument here is not that those bug occurs
often. It just illustrate that something may be quite wrong when
things as simple as changing the deck of a card occurs.

### Random deck not actually random
Create an empty deck, set it to «new cards in random order». Then add
10 notes. Review this deck. You'll see card in order added. The
problem here is that cards created are not randomized, only card
present in the deck when the deck option was changed.

### How to obtain an arbitrary order in any deck
Create 10 decks, with 10 decks option. In each deck, put a card.  Then
reorder each deck. Finally, put the 10 cards in the same deck. If you
review this deck, you'll see the card in the order in which you have
reordered deck. This is far from being the «order added» nor a «random
order».

### Creating cards of an already existing note
A card may be created for a note already existing. This may occur in
at least two ways. By adding text in an empty field, or by editing the
note type (either changing a card type already existing, or adding a
new card type).

This may have two distinct effect, depending on whether this note
still have a new card. If a note has a new card, the `due` value of the
created new card is the same as the one of the new card(s) already
existing. However, if no such new card existed, then the `due` value of
the created card is higher than all other `due` value in the collection.

Both action have sens, depending on whether you want to consider when
notes are added, or when cards are added. But the fact that the `due`
value is so different depending on this property is clearly not what
is expected.

### `Due` 1,000,000
As explained above, the `due` of a card is a 32 bits integer. To
ensure that it remains so, when database is checked, every `due`
greater than 1,000,00 is:
* until april 2019 (anki 2.1.12): changed to 1,000,000 . This mean
  that as soon as a single card has value 1,000,000, all new cards
  have this `due` value. Thus `due` becomes totally useless.
* since april 2019 (anki 2.1.13): changed to their value modulo
  1,000,000. Thus the last card added will have due value 0, 1,
  ... and will become the first card to be reviewed.

According to
(lovac42)[https://anki.tenderapp.com/discussions/ankidesktop/33664-due-value-of-new-card-being-1000000#comment_47198513],
at least 3 of the 10 random deck he checked has `due` value greater than
1,000,000. This means that, each time a user download such a deck,
there is a high risk that this very problem occurs. Worst, if this
user share a deck later, this bug will propagate.



## Possible solution
### Order computed
The first thing which, I believe, should be done is to stop calling
«order added» and use instead «order created». This is quite
important, because that the only think which can actually be computed
by anki.

### No `due` for new cards except for random order
When you want to select a card in a deck and you want to show cards in
order created, then you can use a sql query which takes new card with
minimal `(id,ord)`. This is as easy as finding minimal `due`, and it
will always work.

### Select siblings for random decks
In a deck in which new cards are selected in random order, select new
cards with have a non-new sibling first. This can be done by having a
binary flag stating whether there is a non-new sibling. This is non
trivial to code, because this flag may have to change often, but it's
not computationally hard.

### Recompute `due` in decks more often
As explained above, as soon as new card are added in a random deck,
and as soon as as card move to another deck, the `due` value may become
wrong. Thus I believe that, if `due` is kept, it should be recomputed
when the deck is changed. No need to recompute it each time a card is
added. Just mark the deck as needed recomputation, and do the
recomputation when new cards are reviewed. Note that, this partially
defeat the purpose of preprocessing.

Note also that this is what does the add-on [https://github.com/Arthur-Milchior/anki-correct-`due`]

### Do a recomputation of all due values
If database check realize that some `due` value is 1,000,000, then
all due value should be recomputed. As long as there are less than
1,000,000 new card, the order may be kept, while keeping small values.

As explained above, I highly doubt that keeping the current `due`
order is important, because they have almost no meaning
currently. However, I should note that, this can't simply be
implemented using `col.sched.sortCards` as proposed by
(lovac42)[https://github.com/Arthur-Milchior/anki-correct-due/issues/1]. Indeed,
this method gives the same `due` value to each card of a note,
while different card may have different `due` values, as explained
above. It means that this method may change the order of some new cards.
