#  New line in strings in configurations/json
## Rationale
In standard json, string should not contain newlines. They should
contain "\n" instead, the standard symbols to represents a
newline. Which clearly create a readability problem. In particular
when an add-on configuration contains code (python, latex, whatever).

Thus, I wanted to have the right to have newlines in strings in
json. And when I use the configuration editor, I want to see new
lines insteads of \n.
## Usage

This add-on allow you to write new line in your string. The add-on
will replace them by "\n" before json load the configuration. This
works both for configuration in the file meta.json, and for the the
add-on manager's configuration editor.

## Warning
Note that it will not put newlines in the configuration written
in meta.conf. Indeed, this would create at least two problems:
* We can't control the order in which add-ons are loaded. Thus all
add-ons loaded before this current add-on would fail when trying to
read their configuration.
* If you decide to uninstall this add-on, no configuration with new
lines could be read anymore. (In particular, this would happen if you
synchronize your configuration using another add-on).
## Internal
This add-on has an effect on ALL json strings read by the
program. New lines in strings will always be removed and replaced by
\n. Thus this add-on may affect more than configurations. However,
this add-on call the standard json.loads() function, thus even another
add-on affecting json.loads() should still be compatible with the
current addon. Futhermore, this add-on has no effect on valid
json. Thus the potential change would only be that some invalid json
would be accepted, it seems harmless.

Furthermore, this add-on change ConfigEditor.updateText in module
aqt.addons. It does not call the previous function, thus the current
add-on will be incompatible with another add-on changing this method.

## Links, licence and credits

Key         |Value
------------|-------------------------------------------------------------------
Copyright   | Arthur Milchior <arthur@milchior.fr>
Based on    | Anki code by Damien Elmes <anki@ichi2.net>
License     | GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
Source in   | https://github.com/Arthur-Milchior/anki-json-new-line
Addon number| [112201952](https://ankiweb.net/shared/info/112201952)
