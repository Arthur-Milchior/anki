# Edit new models without full sync
## Rationale
Currently, anki asks you for a full sync as soon as you add a
field/card type to a note. This is actually useless when the note is
new and has not been synchronized, since there is no change to tell
ankiweb about. 

So this add-ons simply ensure that no full sync is required when a
note type not synchronized is used.

I should note that this has been created as a PR in Anki, so this
may eventually becomes useless.

## Warnings

### Potential risk if you import twice a deck
There is a rare risk, which I can't avoid, appart by telling you not
to do it. Here is what you should not do:
* import the same deck in two computers.
* edit the deck in one of the computer
* sync both computer.

If it's the case, you may have bug during review (if you changed the
number of fields) or you may simply find that you have incorrect
card/field content.

### Mystery
As ankiweb is closed source, I don't actually now entirely for sure
what occurs there. I may have missed something. In the worse case,
anki will tell you there is a database inconsistency and ask for a
full sync.

## Internal
In anki.models.ModelManager it modifies:
* rem
* setSortIdx
* addField
* remField
* moveField
* renameField
* addTemplate
* change
* new
* copy
* addField
* addTemplate


## Version 2.0
None


## Links, licence and credits

Key         |Value
------------|-------------------------------------------------------------------
Copyright   | Arthur Milchior <arthur@milchior.fr>
Based on    | Anki code by Damien Elmes <anki@ichi2.net>
License     | GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
Source in   | https://github.com/Arthur-Milchior/anki-freely-edit-new-note-type
Addon number| [1988880085](https://ankiweb.net/shared/info/1988880085)
Support me on| [![Ko-fi](https://ko-fi.com/img/Kofi_Logo_Blue.svg)](Ko-fi.com/arthurmilchior) or [![Patreon](http://www.milchior.fr/patreon.png)](https://www.patreon.com/bePatron?u=146206)
