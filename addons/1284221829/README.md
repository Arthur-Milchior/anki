# "Close and lose current input ?" for sticky fields
## Rationale
If you try to close the "add card" window, and you have some content,
anki warns you and check whether you really want to cloze the window.

Except that it does not takes into accont content in the sticky
fields. Probably because, in this case, the content may comes from the
last note, and it's not a problem if you lose it.

I want anki to takes sticky fields into account; if the content
changed since the last note, then I want to be warned. Otherwise, no
trouble, just close the window.

This is exactly what this add-on does; it warns if there is changed
content if the sticky field.

## Warning
This add-on is incompatible with add-on [46741504: Allows empty first
field during adding and import](https://ankiweb.net/shared/info/46741504).
## Internal
This add-on change the methods: 
* `aqt.addacrds.AddCards.__init__` and calls the previous method
* `aqt.addacrds.AddCards.addNote` and calls the previous method
* `aqt.addacrds.AddCards.ifCanClose`
* `aqt.editor.Editor.fieldsAreBlank`

## Version 2.0
None

## TODO
Create an add-on mixing this one and 46741504

## Links, licence and credits

Key         |Value
------------|-------------------------------------------------------------------
Copyright   | Arthur Milchior <arthur@milchior.fr>
Based on    | Anki code by Damien Elmes <anki@ichi2.net>
License     | GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
Source in   | https://github.com/Arthur-Milchior/anki-Close-and-lose-current-input-for-sticky-fields
Addon number| [1284221829](https://ankiweb.net/shared/info/1284221829)
Support me on| [![Ko-fi](https://ko-fi.com/img/Kofi_Logo_Blue.svg)](Ko-fi.com/arthurmilchior) or [![Patreon](http://www.milchior.fr/patreon.png)](https://www.patreon.com/bePatron?u=146206)
