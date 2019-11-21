# Tag missing media
## Rationale
When you click on «check media», anki gives the list of missing
media. I find that it does not help a lot to correct them. Indeed, I
would need to check by hand each missing media in the browser.

This add-on ensures that, when «check media» is used, it adds the tag
"MissingMedia" to each note with a missing media and open the browser
with the notes which have a missing media.

## Warning
check media also removes the tag «MissingMedia» from notes which does
not have a missing media. So that if you have corrected a note, it
does not appear anymore when you search for notes with Missing Media.
## Internal
It totally redefines the method `anki.media.MediaManager.check`. So
this add-on is incompatible with any other add-on changing this
method.

## Version 2.0
None


## Links, licence and credits

Key         |Value
------------|-------------------------------------------------------------------
Copyright   | Arthur Milchior <arthur@milchior.fr>
Based on    | Anki code by Damien Elmes <anki@ichi2.net>
License     | GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
Source in   | https://github.com/Arthur-Milchior/anki-tag-missing-medias
Addon number| [2027876532](https://ankiweb.net/shared/info/2027876532)
Support me on| [![Ko-fi](https://ko-fi.com/img/Kofi_Logo_Blue.svg)](Ko-fi.com/arthurmilchior) or [![Patreon](http://www.milchior.fr/patreon.png)](https://www.patreon.com/bePatron?u=146206)
