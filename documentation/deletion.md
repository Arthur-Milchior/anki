# Deletion
Deleting cards and notes seems to be a simple notion. Actually, there
are plenty of cases which are not straightforward and which needs to
be taken into account.

## Deleting a note directly

This is the simplest case. If you select a card in the browser, or is
reviewing a card, and you decide to delete it, you'll delete the
entire note. This is also what occurs if you delete a note type. (Note
that if you have in your collection a note whose note type is unkwown,
or with a wrong number of field, or which has no card, it will also be
silently deleted during a database check.)

## Deleting cards
Here are the following way to delete a card.
* deleting a deck
* deletion requested by a synchronization.

It should be noted that, in those two cases, if the note still
exists and the card is not empty, the next «check database» will
regenerate those cards, but they'll be considered to be brand new
cards.

* changing a note's note type.

You change use «change the note type» without actually changing it,
and just moving a card to «nothing». Note however that, if this card
is not empty, it will immediatly be regenerated. Thus what you are
doing is only changing this card for a new card (and potentially
changing it's deck, because anki may have to guess the deck for the
new card.)

* deleting a card type (this can not be done if this is the card type
  of the only card of a note)
* deleting the note containing the card
* deleting empty cards

Of course this last option only delete empty cards.

* doing a database check
this delete cards if the card has a position which is incorrect, or if
it's note does not exists anymore.


## Deleting each card of a note
By default, if each card of a note are deleted, then the note is also
deleted.

There is one exception of this rule: when the card suppresion is due
to a synchronization. In this case, the note may stay in your
collection, with no card. I believe that the reason for this choice is
that some cards may be downloaded later in the synchronization for
this note, thus this note should be keep. And anyway, if there are
really no card at all, then the note should also be deleted in the server,
and thus the synchronization will eventually request the deletion of
the note. (See [synchronization.md] for more details)



This rules sometimes make sens. If you delete a deck, you probably don't
expect it's card to respawn later in another deck as new card. Except
that it also means that if you did a mistake in a note template, you
may lose every note when you click on «Empty cards...». And while it
may be acceptable to lose cards (especially if they are all new), I
believe that losing a note is a huge problem, because you can't
recreate them automatically.
