# Tag notes with no card
## Rationale
Sometime, you press «Empty cards...», and anki also delete
note. Because when a note has no more card, anki deletes it. (see
[https://github.com/Arthur-Milchior/anki/blob/master/documentation/deletion.md]
for more information about deletion)

However, maybe you didn't actually want to delete the whole note and
lose its entire content. May be you thought anki were going to delete
a few card which became empty, not realizing it will in fact delete
EVERY cards, and thus delete the note, and its fields, and its tag...

With this add-on, when you press «Empty cards», cards are deleted as
usual, with one exception. If deleting the cards leave the note empty,
then the cards are not deleted. Instead, the tag NoteWithNoCard is
added to those notes, and the browser is opened to show those notes.

You can still delete those notes if that's what you want, but you have
either to disable this add-on and restart anki, or to delete them
manually from the browser.

## Warning
The tag NoteWithNoCard is automatically removed from notes which now
have a card, when you use «empty cards». This is probably what you
want, so that the tag states the truth.

Note that a note with no cards can also occurs because of the
synchronization process. In which card, this add-on won't save the
note. Instead, you can save it using add-on
[1135180054](https://ankiweb.net/shared/info/1135180054).

## Version 2.0
Port by [lovac42](https://github.com/lovac42/anki-keep-empty-note)

## Internal
This add-on modifies the method aqt.main.AnkiQt.onEmptyCards.

## Links, licence and credits

Key         |Value
------------|-------------------------------------------------------------------
Copyright   | Arthur Milchior <arthur@milchior.fr>
Based on    | Anki code by Damien Elmes <anki@ichi2.net>
License     | GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
Source in   | https://github.com/Arthur-Milchior/anki-keep-empty-note
Addon number| [2018640062](https://ankiweb.net/shared/info/2018640062)
Support me on| [![Ko-fi](https://ko-fi.com/img/Kofi_Logo_Blue.svg)](Ko-fi.com/arthurmilchior) or [![Patreon](http://www.milchior.fr/patreon.png)](https://www.patreon.com/bePatron?u=146206)
