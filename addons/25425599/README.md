# Field name in card deletion message
## Rationale
Let's say you use the "empty cards" action. It shows a messages of the
form:

> Empty card numbers: 3,4
> Fields:   [b] / Voiced<br>Bilabial<br>Plosive / [sound:e6fa97a9bb605e35c1a6694a19f83ef3.mp3]

are not really usefull. Because I've no clue what card number 3
is. Worst, I can't even go to check, because I can't do anything until
anki knows whether I want to delete those cards or not.

With this add-on, you'll instead get the message:
> Empty card numbers: Example, Test,
> Fields:   [b] / Voiced<br>Bilabial<br>Plosive / [sound:e6fa97a9bb605e35c1a6694a19f83ef3.mp3]

So you know that cards Example and Test will be deleted.
## Warning
The deletion process is exactly the same as before, only the message
is changed. So there should be no problem.

## Internal
It changes method anki._Collection.emptyCardReport and don't call
the last version of this method
## Advice
Maybe think about using [Delete empty new
cards](https://ankiweb.net/shared/info/1402327111), so that you
don't delete a card you already saw by accident

## Version 2.0
None
## Links, licence and credits

Key         |Value
------------|-------------------------------------------------------------------
Copyright   | Arthur Milchior <arthur@milchior.fr>
Based on    | Anki code by Damien Elmes <anki@ichi2.net>
License     | GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
Source in   | https://github.com/Arthur-Milchior/anki-clearer-empty-card
Addon number| [25425599](https://ankiweb.net/shared/info/25425599)
