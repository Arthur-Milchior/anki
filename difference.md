# Differences with anki.
This files list the difference between regular anki and this forked
version. It also lists the different options in the Preferences's extra page.

## Add-on folder: keep more files (225953877)
When add-on are updated, all files are deleted, with some
exceptions. You can decide in the preferences which files are
kepts. Anki's default contains only config.json and the folder
user_files. This also adds `.git` `.gitignore` `.svn` and `.github`.

## Explain errors
You obtain more detailled error message if a sync fail, and if you try
do do a «Check database».

It transform the very long method `fixIntegrity` into plenty of small
function. It would helps to do add-ons for this forked version of anki.

In the preferences, the button «Note with no card: create card 1
instead of deleting the note» chage the behavior of anki when he finds
a note which has no more card. This allow to lose the content of the
note, and let you correct the note instead to generate cards.

