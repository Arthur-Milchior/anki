# Database check

In this document, we consider the processing of checking of the
database. We actually consider three different checkings:
* The one which cause anki to tell that the database has
inconsistencies and that we should use run «Check Database».
* The action which occur when «Check Database» is run.
* The kind of database error which are not repaired nor fixed by anki.
(but they are fixed by the add-on [Database checker/fixer explained,
more fixers](https://ankiweb.net/shared/info/1135180054)).

## Warning of database inconsistency

We consider `anki.collection._Collection.basicCheck`. Note that,
contrary to what the name hints, this is not what occurs when you
press «Check Database». Instead, this is run twice during the
synchronization process to check whether the database is still
correct. Once before the sync starts, and once when it ends. Hence,
this is the process which may state that you need to run «Check
Database» because the database is inconsistent.

This checking does the four following checks:
* whether the model of each note is in the database
* whether the note of each card belong to the database
* whether each note has at least one card
* whether each card's ord is valid.

## Check Database
Here, we consider what really occur when you press «Check
database». We also explain the meaning of the error message. Note that
if you want to have more details, you should use add-on [Database
checker/fixer explained, more
fixers](https://ankiweb.net/shared/info/1135180054).

The method described here is `anki.collection._Collection.fixIntegrity`.

### Checking whether the database is ok
The first test is checking whether sqlite find a problem in the
database. If it is the case, anki prints "Collection is
corrupt. Please see the manual." In this case, it may be hard to
repair, because it may be possible that nothing may be retrieved from
a broken database.

### note type with a missing model
A note contains a field mid, whose value should be the id of a
model. If there is no such model, nothing can be done of the note, so
it's deleted. (I personnaly believe it makes no sens. The fields and
tags are still quite interesting, and should be shown to the user, so
they know what note to recreate. The note can be found in the file
deleted.txt, but you should read the manual carefully to know this
important fact).

In this occur, anki prints "Deleted %d card(s) with missing template."
with %d being the number of card deleted.

### AnkiDroid deck override bug
A card type `t` (a.k.a. template) has a key 'did'. When you create
a new note, the card with this card type are sent to the deck whose id
is `t['did']` if its not None.  Its entry may be "None" instead of
None. If it is the case, it is corrected. In this case, Anki prints
"Fixed AnkiDroid deck override bug."

### Fixing missing req.
A note type (a.k.a. model) has a key 'req', meaning requirements. For
more information about this complex notion, go read [template
generation rules](templates_generation_rules.md). If this key is
missing, it is computed and anki prints "Fixed note type: %s" with %s
the name of the model.

### Card with invalid ordinal
Each card `c` is associated to a card type. More precisely, to an integer,
which represents the position of the card type in the note type. This
is saved as `c.ord`. If `c.ord` does not correspond to a
position of a card type, this card should not exists. Thus, it is
deleted. Anki prints "Deleted %d card with missing template.", with %d
the number of cards deleted.

### Notes with invalid field count
Each note has a model and a list of fields. Each model has a list of
field names. Normally, both list have the same size. If it is not the
case, the note is not usable, and is deleted. (As above, I personnally
think that it's a bad thing to do. The fields and tags should be shown
to the user so they decide how to repair the note and keep the
information.) In this card, anki prints "Deleted %d note(s) with wrong
field count." with %d the number of deleted notes.

### Delete any notes with missing cards
If a note has no card, it becomes useless. It will never be seen
reviewed again. And he can't be edited in the browser. Since nothing
can be done with it, it is deleted.  (As far as I'm concerned, this is
one of the most ridiculous thing anki does. For one, as above, you
should warn explictly the user and let them know the fields and tags
which are deleted, so that they can decide whether a new note should
be created with those information. And furthermore, if they edit the
note type, some card may be generated, and the note will have card
!). Anki prints "Deleted %d note(s) with no cards." with %d the number
of note deleted.

### Cards with missing note
Each card is associated to a unique note. If the note is not in the
database, nothing can be done of the card and it is deleted. Note that
this is different from «Empty cards» action. Indeed, when «Empty card»
is pressed, it is actually check whether the card would be empty or
not, using the value of the field of the note, and the card
type. Without a note, this can not even be tested, since a card does
not contains the fields values. Anki prints "Deleted %d card(s) with
missing note." with %d the number of cards deleted.

### Cards with odue set when it shouldn't be
If a card is in learning or in the review queue, it seems that the
original due (odue) should be 0. (I must admit it's not clear why odue
is considered, but not due). This set odue to 0 in those cases. Anki
prints "Fixed %d card with invalid properties." with %d the number of
cards changed.

### Cards with odid set when not in a dyn deck
A card should have a «original deck» (odid) only if it's currently in
a filtered deck (a.k.a. dynamic deck). Thus, if it's not the case,
odid and odue are set to 0. Whether odue is non-zero is not tested. I
assume that it is because having a odue without odid is not actually a
problem. Anki prints "Fixed %d card with invalid properties." with %d
the number of cards with this problem.

### New cards can't have a due position > 32 bits
For some reason, anki believes that the due value of new cards should
be at most 1,000,000. So if its not the case, the number is changed to
1,000,000. One of the reason to do this is that it ensures that the
number fits on 32 bits.

Actually, it kind of makes sens. If the card is new, the due value
just give an order in which cards will be seen, and if the first
1,000,000 cards are shown in the correct order, the remaining may be
consireded not important right now. If the card is due, due is the
day in which the card will be seen. When doing this edition, anki
prints nothing.

### tags
Anki calls self.tags.registerNotes() (todo)

### nextPos
Anki set the next position value to the successor of the greatest ord
of new card. Note that if this is 1000000, then the nextPos will be a
number so big that it will be decreased during the next fixing of the
database.

### Reviews should have a reasonable due
TODO. a part of this has been changed since this text was written. below I explain how anki used to deal with due position.

Similarly to New cards can't have a due position > 32 bits, it is
assumed that the due value of review card (i.e. cards which are not
new anymore, and not in learning) is at most 100000 (there is one zero
less than in the case of new cards.). The due value is the number of
the
day where the card will be seen again for the next time. Computed as a
distance between this day, and the day the collection was
created. Note that 100000 corresponds to 274 years, so it is
reasonnable to assume that this is a number far bigger than what can
actually be usefull for a single user.

During those edition, anki prints nothing.

### Rounding decimal values
V2 scheduler used to have a bug which could create decimal interval
and due date for some reviewed cards. Those value should be
integers. Thus anki correct this by rounding those value. If this is
the case, anki prints "Fixed %d cards with v2 scheduler bug." with %d
the number of cards affected.

### Optimizing the database
Anki calls sqlite3 and tells it to optimize itself.


## Errors not taken into account (yet) by anki.

### Multiple instance of the same card type of the same note
In anki database, in the table cards, the pair (nid,ord) should be
unique. I.e. a note may have at most one card of each card type. This
is actually never checked. And it is a problem I reall had. probably
because of another add-on.
