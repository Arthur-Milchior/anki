# Export cards selected in the Browser
## Rationale
Sometime, I want to export only some notes. And the cards are not all
in the same deck. I wanted to be able to just select cards in the
browser and export them. Thus, this add-on is here.

Another problem with anki's exporting system is that it exports cards,
and not notes. Image that you have a card in a deck, and its sibling
(other card of the same note) in another deck. And that you export the
deck of the first card. Only the first card will be exported. Now, if
you import the exported package, Anki will eventually detect that some
siblings are missing, and will generate those as new cards. Thus the
entire review history of the siblings will be missing. Personnally, I
prefer to export siblings, even if it means exporting more than a
deck. But since people may disagree, this option is configurable.

## Usage
Open the Browser, select the cards you want to export. Then go to
Edit>Export selection (Ctrl+Shift+E), and the standard exporting
window will open, but with a new options: "Browser's
selection". Keeping this option, you can export your selection as you
exported decks.

## Configuration
You can ignore this section. Unless you really want
to export cards without their siblings in package/exporters installed
by other add-ons, default should be okay.

"siblings": A mapping stating, for each kind of export option, whether you want that cards are exported with their siblings (other cards from the same note).
* null means that you use the "default" setting.
* true means that, when you export a card, you export their siblings.
* false means that you can export cards without their siblings.

The entry of the "siblings" mapping are keys of exporter, or the constant "default". To control exporter created by other add-on, check their code to find their "key" value, and add it to this mapping. The default values are:
* "default": the default value, when no other are used.
* "Notes in Plain Text": exporting notes as txt files.
* "Cards in Plain Text": exporting cards as txt files.
* "Anki Deck Package": exporting a .apkg file
If another exporter is added by an add-on, add its key to this mapping

"Anki 2.0 Deck" is not listed. Indeed, when the entire collection is exported, this parameter becomes useless.

## Internal
This add-on change
* in `aqt.exporting`, the method `ExportDialog.__init__`. The new
  method calls the previous version of the method.
* in `aqt.exporting`, the methods `ExportDialog.setup`,
  `ExportDialog.accept`. The new methods do not call the previous
  version of the method.
* in `anki.exporting`, the method `Exporter.cardIds` is
  modified. The former version of the method is called if the exporter
  is called from the browser with a non-empty selection.
* in `anki.exporting`, the method `AnkiExporter.exportInto` is
  redefined, not calling the previous version. A single line is
  changed. This change is sent to Anki in a (pull
  request)[https://github.com/dae/anki/pull/263].

## Version 2.0
Sorry, but no such version, unless someone wants to pay for it.

## Links, licence and credits

Key         |Value
------------|-------------------------------------------------------------------
Copyright   | Arthur Milchior <arthur@milchior.fr>
Based on    | Anki code by Damien Elmes <anki@ichi2.net>
License     | GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
Source in   | https://github.com/Arthur-Milchior/anki-export-from-browser
Addon number| [1983204951](https://ankiweb.net/shared/info/1983204951)
Support me on| [![Ko-fi](https://ko-fi.com/img/Kofi_Logo_Blue.svg)](Ko-fi.com/arthurmilchior) or [![Patreon](http://www.milchior.fr/patreon.png)](https://www.patreon.com/bePatron?u=146206)
