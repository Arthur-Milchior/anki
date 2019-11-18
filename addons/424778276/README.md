# Keep model of add cards
## Rationale
For some reason, the note type in anki «add» window may suddenly
change. In the worst case, it may lead to losing data, if the new note
type has less fields than the old note type. It may also means you'll
submit the note in the wrong type if you didn't pay attention.

More precisely, this may occur in the following cases:
* In the browser, if you change the note type of a note already
  existing.
* If you use the importing window and change the note type.
* Using addon [Open multiple instances of the same
  window](https://ankiweb.net/shared/info/354407385), when you change
  the note type of a «add» window.
## Usage
This add-on ensure that the note type of a «add» window only change
when you choose a note type from the same window.

## Internal
* In module `aqt.addcards`, `AddCards` is replaced by a
  class. The new class inherits from the older one. It redefines
  `__init__` and `_reject`, by calling the previous method,
  and changing its hooks. It redefines
  `setupChoosers`, `onReset`, `_addCards`, by copy-pasting
  the previous code and doing some modification. Thus, it may be
  incompatible with other add-ons also editing those notes. Finally it
  creates a method `onResetSameModel`.
* Hooks currentModelChanged does not change anything in the "add"
  window. "reset" still call the method "onReset", but a version which
  does not change the model.
* The `ModelChooser` of the "add" window is a new class, inheriting
  from `aqt.modelchooser.ModelChooser`. It redefines `__init__`,
  calling the previous method and removing some hook. It redefine
  `onModelChange` by copy-paste the old code, removing everything
  affecting the environment, and affecting directly the current "add"
  window.

## Links, licence and credits

Key          |Value
-------------|-------------------------------------------------------------------
Copyright    | Arthur Milchior <arthur@milchior.fr>
Based on     | Anki code by Damien Elmes <anki@ichi2.net>
License      | GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
Source in    | https://github.com/Arthur-Milchior/anki-keep-model-in-add-cards
Addon number | [424778276](https://ankiweb.net/shared/info/424778276)
Support me on| [![Ko-fi](https://ko-fi.com/img/Kofi_Logo_Blue.svg)](Ko-fi.com/arthurmilchior) or [![Patreon](http://www.milchior.fr/patreon.png)](https://www.patreon.com/bePatron?u=146206)
