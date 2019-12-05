# Browser from reviewer, show the card/note/deck
## Rationale
When I open the browser, I often want to see the current card, and not
the current note. This is actually a strong problem if I use the
advanced browser add-on, with the note-mode.

This is even more of a problem because, if for some reason the page is
reloaded, the number of lines increases, because it automatically
switches from showing a single note to showing the current deck.

Thus, this add-on allow you to decide, when you are reviewing, whether
you see only the current card, the current note, or the current deck.

From the overview page, it opens the current deck.

## Configuration
There is a single option, which must be set to "deck", "card" or
"note", depending on what you want to see

## Internal
This add-on only change the method
`aqt.browser.Browser.setupSearch`. The new method does not call the
last one.

## Version 2.0
None

## TODO

## Links, licence and credits

Key         |Value
------------|-------------------------------------------------------------------
Copyright   | Arthur Milchior <arthur@milchior.fr>
Based on    | Anki code by Damien Elmes <anki@ichi2.net>
License     | GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
Source in   | https://github.com/Arthur-Milchior/anki-browser-from-reviewer
Addon number| [???????](https://ankiweb.net/shared/info/???????)
Support me on| [![Ko-fi](https://ko-fi.com/img/Kofi_Logo_Blue.svg)](Ko-fi.com/arthurmilchior) or [![Patreon](http://www.milchior.fr/patreon.png)](https://www.patreon.com/bePatron?u=146206)
