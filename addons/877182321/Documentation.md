This file explain how this add-on works.

# Files
## ChangeFunction
This file is in charge of monkey-patching each function which must be
monkey patched.

## Config
This file is in charge of reading user's configuration. It also update
it if an outdated configuration file is found.

## Debug
Function which helps debugging. Normally, mayDebug and shouldDebug
must be False in the code distributed, and thus no debugging occurs.

## Html
Contains all of the HTML which is used do generate the list of deck in
the main window. The HTML is either contained in a string variable if
it does not change. Or in a small function which takes parameter and
return the html string.

## Strings
This associate to each column some string describing it. A short one
used in the header of the column. And a longer one used in the overlay
describing the number.

## Tree
Contains functions used to compute informations globally. I.e. how
many cards there are of each kind in each deck (not considering the
subdeck). And how many time to wait before the next review.

It's computed globally because it allows to do a single query. Instead
of having to do one query by deck.

## Node
Globally, it contains everything else. It contains each computation
which must be done recursively, on a deck by deck basis. And the
function to print each deck.
