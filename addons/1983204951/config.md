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