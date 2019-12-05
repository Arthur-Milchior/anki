# Direct to review
## Rationale
Someone did want to hide the number of cards to review. Which requires
to skip overview.

Furthermore, I personnaly never use overview; so I'm winning time
here. Even if I'm not sure I'm winning more time than what I spent
developping it.

The gear now contains an "overview" button, for people actually
wanting to go to overview.

## Internal
It changes:
* `AnkiQt.onOverview` by calling directly `onReview`

## Version 2.0
None

## TODO
Ensure that it's direct to reviewing, even with clicking "s" and
selecting a deck in the deck chooser.

## Links, licence and credits

Key         |Value
------------|-------------------------------------------------------------------
Copyright   | Arthur Milchior <arthur@milchior.fr>
Based on    | Anki code by Damien Elmes <anki@ichi2.net>
License     | GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
Source in   | https://github.com/Arthur-Milchior/anki-direct-to-review
Addon number| [1024346707](https://ankiweb.net/shared/info/1024346707)
Support me on| [![Ko-fi](https://ko-fi.com/img/Kofi_Logo_Blue.svg)](Ko-fi.com/arthurmilchior) or [![Patreon](http://www.milchior.fr/patreon.png)](https://www.patreon.com/bePatron?u=146206)
