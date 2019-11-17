# Quicker Anki
Plenty of part of anki may become more efficient. More precisely, anki
is not optimized for power user, and some actions may become slow when
you have a big collection or complicated notes. This add-on improve
the speed of some actions. In the case where you only use basic card
and have a small collection, you probably won't see any difference
while installing this add-on.

## Warning
This add-on change plenty of methods. Which means that this add-on
risks to be incompatible with other add-on. Incompatible add-on will
be listed here when I learn about them.

In particular it is incompatible with add-ons:
* [12287769](https://ankiweb.net/shared/info/12287769) «Explain
deletion». This add-on ensure that the file `deleted.txt` state
why notes are deleted.
* [Database checker/fixer explained, more fixers 1135180054](https://ankiweb.net/shared/info/1135180054)

Please instead use-addon
[777545149](https://ankiweb.net/shared/info/777545149) which merges
those three add-ons

## What this add-on improve
### Note type with a lot of card type
Assume you have a note type with a lot of card type, or with a lot of
card.
* Assume you edit the note type. Then, closing the editor and
  saving the note type may take several minutes. This is because anki
  recompute some useless data and does not consider the fact that
  some template did not change.
* Assume that you add a card, it sometime takes many seconds. A big
  part is also lost recomputing useless data.

This add-on just ensure that those computations are done only when it
is required.

### Reordering cards
Let us assume you switch a deck so that cards are selected in random
order (or so that they are selected in creation order). Then anki
reorder every card, and they discard the reordering of cards which are
not new, which makes no sens.

This add-on ensures that only new cards are reordered.


## Usage
Just install this add-on.
## Version 2.0
None
## Internal
We give methods changed by this add-on.

Both adding card and changing note type require to change:
* anki.models.ModelManager.save

To change note type's editino, we change:
* aqt.clayout.CardLayout.__init__
* aqt.clayout.CardLayout.onRemove
* aqt.clayout.CardLayout.onReorder
* aqt.clayout.CardLayout.onAddCard
* aqt.clayout.CardLayout.reject
* aqt.fields.FieldDialog.reject
* aqt.fields.FieldDialog.__init__
* aqt.fields.FieldDialog._uniqueName
* anki.collection._Collection.genCards
* anki.models.ModelManager._updateRequired
* anki.models.ModelManager._syncTemplates
* anki.models.ModelManager.availOrds

To improve the creation of note, we change:
* aqt.editor.Editor.saveAddModeVars
* aqt.fields.FieldDialog.reject
* aqt.models.Moleds.onRename
* aqt.models.Moleds.modelChanged
* aqt.models.Moleds.onAdd
* aqt.models.Moleds.saveModel

To reorder card quickly, we change:
* anki.sched.Scheduler.randomizeCards
* anki.sched.Scheduler.orderCards
* anki.sched.Scheduler.sortCards
* anki.schedv2.Scheduler.randomizeCards
* anki.schedv2.Scheduler.orderCards
* anki.schedv2.Scheduler.sortCards



## Links, licence and credits

Key         |Value
------------|-------------------------------------------------------------------
Copyright   | Arthur Milchior <arthur@milchior.fr>
Based on    | Anki code by Damien Elmes <anki@ichi2.net>
License     | GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
Source in   | https://github.com/Arthur-Milchior/anki-fast-note-type-editor
Addon number| [802285486](https://ankiweb.net/shared/info/802285486)
Support me on| [![Ko-fi](https://ko-fi.com/img/Kofi_Logo_Blue.svg)](Ko-fi.com/arthurmilchior) or [![Patreon](http://www.milchior.fr/patreon.png)](https://www.patreon.com/bePatron?u=146206)

## Notes

I believe it should be implemented in anki's core code, but this was
refused.
* https://anki.tenderapp.com/discussions/ankidesktop/32549-potential-pull-request
* https://github.com/dae/anki/pull/297#issuecomment-481120247

Some methods calling `anki.models.ModelManager.save`  are not
modified, because they are long and rarely used; so it's better no to
touch them to avoid incompatibility with :
* anki.collection._Collection.fixIntegrity
* aqt.importing.ImportDialog.accept
* anki.storage._upgradeSchema
* anki.storage._upgradeClozeModel
