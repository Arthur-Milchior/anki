# Update add-ons at start
## Rationale
I don't want to have to think about updating my add-ons. So this
add-on does it when I load a profile.

It uses the same process for update than anki. That is: it updates
only add-ons installed using the add-on manager. And you can decide tu
update all or none of the add-ons.

## Warning
If your computer is off-line, you'll have a tooltip stating no update
occurs.

This uses anki default update method, and so has the same limitation:
it only update all or none of the add-ons.

## Technical
Ideally, I'd like this to run when anki loads. It makes no sens to do
it when loading a profile. However, the add-on manager is entirely
front-end, and requires the use of the main window, hence it requires
a profile to be loaded.

## Version 2.0
None

## TODO
* A configuration option to synchronize add-ons while you synchronize
the collection.
* Being able to synchronize only some add-ons.

## Links, licence and credits

Key         |Value
------------|-------------------------------------------------------------------
Copyright   | Arthur Milchior <arthur@milchior.fr>
Based on    | Anki code by Damien Elmes <anki@ichi2.net>
License     | GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
Source in   | https://github.com/Arthur-Milchior/anki-auto-update-addons
Addon number| [1847544206](https://ankiweb.net/shared/info/1847544206)
Support me on| [![Ko-fi](https://ko-fi.com/img/Kofi_Logo_Blue.svg)](Ko-fi.com/arthurmilchior) or [![Patreon](http://www.milchior.fr/patreon.png)](https://www.patreon.com/bePatron?u=146206)
