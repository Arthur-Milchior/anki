# Sort new cards as you want
## Rationale
The order in which I see new cards matters A LOT in my learning
process. And I believe that anki does not offer enough freedom with
this. This add-on wants to correct that. For example, it offer the
following possibilities.

### Random, with Siblings of seen card first.
Anki allows you to randomize the order of cards. However, it ensures
that when you see a new card of a note, all other new cards of the
same note are shown soon after. Indeed, since their content are
related, Anki believes that it's best if there is not too much time
between the first review of two cards of the same note.

Except that actually, it does not work this way. Once you randomize a
deck, the order of new card does not take into account which cards
have a seen siblings, and which ones have note. So, if you want to
randomize, but see siblings of seen card first, now you can.

The configuraton to enter is `"seen first", "note random", "card position"`
(The exact meaning of this configuration will be explained in the
"Configuration" section).

### Really random order
Maybe actually, you really want to see all cards in random order. You
don't want to see siblings together, you may want sometime to see 2nd
card before first one... In this card, use the configuration `"card random"`.


### See all the first cards, then all the second cards, etc...
I've got a note type where the first card is "easy", the
second card is "harder" and so on. So you may want to see all first
cards, then all second card when the first cards have been seen.

The configuration for this is one of:
* `"card position", "note creation"` if you want to see notes in the order in
  which they were added
* `"card position", "note random"` if you want to always see notes in the same
  order, but a random order
* `"card position", "card random"` if you want to see cards in random order
  (but still all first cards first, and so on...)

### Sort by date of creation of the note
Actually, even "show new card in order added" does not show new card
in order they are added. Let me explain. It mostly shows cards in order in
which there note are added. If a note (or note type) is edited so that
new cards are edited, then the new card is dealt as follow:
* if the card as new siblings, it's position is the same as the one of
  its sibling
* otherwise, it's considered as the lattest card.

This makes no sens to me. And you can now really sort cards using the
configuration `"note creation", "card position"`

## Warning
This add-on is still experimental. Do a back up of your collection and
check your result before actually doing real change to the order of
new cards.

The order is computed taking into consideration the cards and notes
which currently exists. It does not takes into consideration cards
which will be added later. You need to sort again when you add new
card. So this add-on is mostly interesting if you believe you won't
need to add things to the deck regularly.


## Configuration
The configuration is given by a list of parameter, separated by
commas. (Technically, this is a json list, where the enclosings ``
and `` are omitted.)

Sorting is done according to first parameter. In case of equality
according to second parameter. And so on. A paramater is either a
string `"rule"`, or a pair `("rule", False)`. If it is a string, the
sort is as follows:
* "seen first": show siblings of cards which have already been seen.
* "new first": show notes whose no card have been seen first
* "card position": sort cards according to their position in the note
* "note creation": sort according to the date of creation of the note
* "mod": sort according to the last time the note was modified
* "note random": sort randomly notes; but leave cards of the same note
  together.
* "card creation": sort according to the date of creation of the card.
* "card random": sort randomly in case of ambiguity in the previous cases.

Note that there are no equality in the two last cases; the order is
complete, so it's useless to add more parameters after "card creation"
or after "random".

If the parameter is a pair, it means this order is reversed.

### Example
Let's explain the examples given above.

The configuration `"seen first", "note random", "card position"` means
that cards with a sibling already seens are shown first. Then the
order of all cards are randomized. (But even if the order is
randomized, if a card has a seen sibling, it'll be first in the random
order). Then for different cards of the same note, the first card will
be seen before the second one, etc...

The configuration `"card random"` simply states that all cards are
randomized.

The configuration `"card position", "note creation"` means that all
first cards are seen, then all second cards, ... And since there may
be multiple first card, we see the one of the oldest note first, and
then the one of the second oldest note, ... and only when all of those
first cards are seen, the second card of the oldest note is seen. etc...

## Internal
A value "special sort" is added to each deck object and to the
configuration of the collection, to recall the last value used for
each deck and for the collection.

## Version 2.0
None

## TODO
A beautiful graphical interface

## Links, licence and credits

Key         |Value
------------|-------------------------------------------------------------------
Copyright   | Arthur Milchior <arthur@milchior.fr>
Based on    | Anki code by Damien Elmes <anki@ichi2.net>
License     | GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
Source in   | https://github.com/Arthur-Milchior/anki_sort_cards
Addon number| [1665261045](https://ankiweb.net/shared/info/1665261045)
Support me on| [![Ko-fi](https://ko-fi.com/img/Kofi_Logo_Blue.svg)](Ko-fi.com/arthurmilchior) or [![Patreon](http://www.milchior.fr/patreon.png)](https://www.patreon.com/bePatron?u=146206)
