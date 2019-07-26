# Database checker/fixer explained, more fixers
## Rationale
This add-on simultaneously solve two related problems.

### Meaningful error message
Sometime, anki warns you that your database has trouble. That you
should run «Check database» to correct it. I find this quite
frustrating, because I've no clue what's wrong. And since it may
happens many time, I would like to understand what's wrong to avoid
repeating the error. This is especially important for add-on
developpers, because if our add-ons break the database, it would be
better to know exactly how it breaks, so that we can correct
this. Hence, this add-on change message sent by the methods used to
check and to fix the database, so that it explains exactly what it
does.

More information on the error messages can be found on
https://github.com/Arthur-Milchior/anki/blob/master/documentation/DB_Check.md

### Checking what anki forgot to check
There are kind(s) of error(s) that anki does not check. This add-on
also check and correct those kind of errors. The following error(s)
are currently considered: * Whether you have a note which has two
distinct cards for the same card type. If this is the case, it keeps
the card with greatest interval. In case of equality, it keeps the one
with greatest easyness. In case of equality the one with greates due
date. Otherwise, an arbitrary card. I explain in [the
forum](https://anki.tenderapp.com/discussions/ankidesktop/32854-two-cards-of-the-same-note-with-same-nid#comment_47016398)
how this could occur without having a single add-on installed.


## Warning
This add-on is incompatible with add-on
* [12287769](https://ankiweb.net/shared/info/12287769) «Explain
deletion». This add-on ensure that the file `deleted.txt` state
why notes are deleted.
* [Quicker Anki: 802285486](https://ankiweb.net/shared/info/802285486)
  which makes some operation quicker.


Please instead use-addon
[777545149](https://ankiweb.net/shared/info/777545149) which merges
those three add-ons


With one exception, this add-on does not actually edit the
database. All editions are done by anki original code. The exception
being the check which are done by this add-on and not by anki. Right
now, it's only: checking whether a note has a duplicate card.

## Internal
In the class `anki.collection._Collection`, it changes the
methods:
* `basicCheck`, a method used thrice during sync to check whether
everything is ok or whether there is an inconsistency.
* `fixIntegrity`, the method which is used when clicking on "Check
Database".
* `_checkFailed`. The new method explain the problem comes from
  the server.

## Version 2.0
None

## TODO
Use config to allow user to choose to have only one of the two
functionnality. Allow to choose which card to keep.

Make it compatible with add-on mentionned above.

## Links, licence and credits

Key         |Value
------------|-------------------------------------------------------------------
Copyright   | Arthur Milchior <arthur@milchior.fr>
Based on    | Anki code by Damien Elmes <anki@ichi2.net>
License     | GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
Source in   | https://github.com/Arthur-Milchior/anki-database-check-explained
Addon number| [1135180054](https://ankiweb.net/shared/info/1135180054)
Support me on| [![Ko-fi](https://ko-fi.com/img/Kofi_Logo_Blue.svg)](Ko-fi.com/arthurmilchior) or [![Patreon](http://www.milchior.fr/patreon.png)](https://www.patreon.com/bePatron?u=146206)
