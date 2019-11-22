# Keep files not in add-on folder not in user files
## Rationale
I want to keep a `.git` folder in my add-on folder, and still be able
to update my add-ons. When an add-on is updated, the entire content of
the add-on's folder is deleted, which means that .git is deleted too. 

This add-on ensure that some files are keep. By default it's
`user_files` (as by default in anki), `.git`, `.gitignore` and `.svn`.

## Configuration
You can add or remove some files/folder to keep.

## Internal
This change the methods `aqt.addons.AddonManager.backupUserFiles` and
`aqt.addons.AddonManager.restoreUserFiles`.

## Version 2.0
None


## Links, licence and credits

Key         |Value
------------|-------------------------------------------------------------------
Copyright   | Arthur Milchior <arthur@milchior.fr>
Based on    | Anki code by Damien Elmes <anki@ichi2.net>
License     | GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
Source in   | https://github.com/Arthur-Milchior/anki-keep-files-in-addon-Folder
Addon number| [225953877](https://ankiweb.net/shared/info/225953877)
