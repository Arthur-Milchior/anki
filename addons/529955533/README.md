# Regular backups
## Rationale
Sometime, I want to find an old version of my collection. For example,
to see how a card type used to be. Sadly, my oldest back-up is usually
two monthes old. Of course, this can be solved with a [differential backup](https://en.wikipedia.org/wiki/Differential_backup) system; but that is not the point here.

This add-on ensures that we keep at least one back-up by day for the last month, one back-up by month for the past year, and one back-up by year.

## Warning
### Uninstalling the add-on
If you uninstall the add-on, or if you disable it, the current back-up will stay. If you are not interested in them, you'll have to delete them yourself.

### It can't restore lost backups.
If you install this add-on today, you can be kind of sure that you'll have back-ups of your collection as it is this month/year for the future. However, it should be noted that this add-on can not help you to access your collection as it was before you installed the add-on. Indeed, this add-on can not create data which were already deleted. It only ensures that some data are kept.

### Missing image
Anki's backup are far from perfect. For example, they do not contains image. Thus you'll see risk to lose images with this add-ons. Actually, this risk already exists if your images are not synced, and that you delete a note with an image, check media, and then restore a backup.

### New computer
Back-ups are not synchronized. Which means that if you move to another computer, and don't copy the back-up folder, then this add-on become useless. Indeed, we won't have the back-up files.

### Consider whether you really want to conserve data
As with any backup system, you may think about whether you really want to keep data. If, by accident, you added in anki some private data, and then that you remove it from anki, then those data may still be in the back-up. They will remains in there as long as the back-up exists. Without this add-on, you could be sure that the data would eventually be deleted. With this add-on, if the data are in a yearly backup, then they will never be removed.

## Internal
This add-on change the method `aqt.main.AnkiQt.backup`, and calls the previous method.

## Version 2.0
None

## TODO
Allow to give more flexibility about how much to save

## Links, licence and credits

Key         |Value
------------|-------------------------------------------------------------------
Copyright   | Arthur Milchior <arthur@milchior.fr>
Based on    | Anki code by Damien Elmes <anki@ichi2.net>
License     | GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
Source in   | https://github.com/Arthur-Milchior/anki-
Addon number| [???????](https://ankiweb.net/shared/info/???????)
Support me on| [![Ko-fi](https://ko-fi.com/img/Kofi_Logo_Blue.svg)](Ko-fi.com/arthurmilchior) or [![Patreon](http://www.milchior.fr/patreon.png)](https://www.patreon.com/bePatron?u=146206)
