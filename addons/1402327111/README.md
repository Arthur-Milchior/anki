# Delete empty cards only if they are new
## Rationale
I do not like to delete cards. If some cards where reviewed and no
longer exists, it is probably a sign that I made something wrong. When
I correct this error, those empty cards will still be here with their
review history. Great !

However, I sometime create thoushands of new cards by accident, when I
edit a card type. I want to be able to delete those card.

The tradeoff I found is deleting cards only when they are new.
If, sometime, I find and empty card, already seen, and it's not a
mistake, I just have to suspend it, and everything is all right.
## Usage
From main window, select "Tools">"Empty new cards". It acts similarly
to "Empty cards".

## Internal
This add-on redefine anki.collectino._Collection.genCards during the
process. The new method call the previous one.

The previous method is set back once the action is done.


## Links, licence and credits

Key         |Value
------------|-------------------------------------------------------------------
Copyright   | Arthur Milchior <arthur@milchior.fr>
Based on    | Anki code by Damien Elmes <anki@ichi2.net>
License     | GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
Source in   | https://github.com/Arthur-Milchior/anki-empty-new-cards
Addon number| [1402327111](https://ankiweb.net/shared/info/1402327111)
Support me on| [![Ko-fi](https://ko-fi.com/img/Kofi_Logo_Blue.svg)](Ko-fi.com/arthurmilchior) or [![Patreon](http://www.milchior.fr/patreon.png)](https://www.patreon.com/bePatron?u=146206)
