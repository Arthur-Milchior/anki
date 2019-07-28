# Changing a note type without requiring a full new sync.
## Rationale
Currently, changing a note type require to sync the entire collection. This add-on symply removes this restriction and assumethat you, the user, will act wisely in order to avoid creating bugs.

It means that you must sync all your devices before changing a note type, and then sync them after the note type. I.e. you must act exactly has you would have done without this add-on.

## Warning
If you select a note `n` on your computer, and change its note type,
then you must not do ANYTHING with this note type on any other
computer, smartphone, etc... before you have synchronized
them. Otherwise, you risk to loose some cards, or even the note.

## Internal
In version 2.1

This add-on modifies `aqt.browser.ChangeModel.accept`; the new method
call the last one. It also modifies
`anki.collection._Collection.modSchema` while
`aqt.browser.ChangeModel.accept` runs, and set it back to its original
value afterward.

### Version 2.0
It changes `anki.model.ModelManager.change`.

Note for developpers
The method change, of ModelManager, is changed. It now returns the list of the new note ids of the changed note

Update 2018-01-10: The creation date of note is preserved as much as possible (the date is incremented of a few miliseconds). The creation date of card is not preserved.


## Links, licence and credits

Key         |Value
------------|-------------------------------------------------------------------
Copyright   | Arthur Milchior <arthur@milchior.fr>
Based on    | Anki code by Damien Elmes <anki@ichi2.net>
License     | GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
Source in   | https://github.com/Arthur-Milchior/anki-change-note-type.git
Addon number| [719871418](https://ankiweb.net/shared/info/719871418)
Support me on| [![Ko-fi](https://ko-fi.com/img/Kofi_Logo_Blue.svg)](https://Ko-fi.com/arthurmilchior) or [![Patreon](http://www.milchior.fr/patreon.png)](https://www.patreon.com/bePatron?u=146206)
