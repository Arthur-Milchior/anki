# Compile all LaTeX, warn about compilation errors
## Rationale
This add-on repare three related problems with anki's compilation
process for LaTeX.

### Errors
You never know whether your LaTeX is valid untill you actually see the
card containing the LaTeX. When this occur, you are probably learning
new cards and don't want to stop to correct your typo.

I thus prefer to know when an error occur when I'm creating or editing
a card. When a new card is created with an error, or when I'm creating
an error while editing a note, a warning box will pop-up to warn me.

During edition, a tooltip (yellow box) reminding you a bug exists regularly
occur. You may know that the bug is solved as soon as you don't see
the tooltip.
### Finding errors.
Furthermore, a tag #LaTeXError is added to notes with an error in
their LaTeX. To find and correct those notes, it suffices to search
for this tag.
### Synchronization
Ankiweb and smartphone can't compile LaTeX. Thus, when you create new
cards, don't click on "check media", synchronize, and use ankiweb,
ankidroid, anki on IOS, you have notes without their LaTeX. Since you
don't want to always have to remember to use "check media", you may
want to use this add-on. Since it compiles LaTeX as soon as it is
written, the image will always be generated.
## Warning
The browser does not update when a tag is added/removed. Thus you may
not trust the tag list in the browser to know whether your last edit
created/removed a bug.

### A problem when LaTeX header change
If you change the footer/header, Anki will not recompile your LaTeX code. In
particular, if it founds an error the last time it tried to compile
your LaTeX code, it will believes the error is still present even if,
changing the header, you may actually have corrected the error. In
order to ensure Anki tries to compile again, you need either to
restart anki (it won't recall what it already tried to compile), or
edit the code. You can usually add a space or a {} in your LaTeX
without changing your output.

### Too much images
Assume you write [$]\pi=3[/$], and a little bit later, you add [$]\pi=3.14[/$], and
a little bit later [$]\pi=3.1416[/$]. Since this add-on compile often,
the three versions of your code will have been compiled, and will have
generated LaTeX image, saved in your media folder. It takes space. So
you may still want sometime to do a "check media", to delete all of
those partial compilations.

## Configuration (Version 2.1 only)
"warningBox" configure when should a warning box tell you when you introduce a latex error. When warning are not used, yellow box (tooltips) are used instead. Its possible values are:
* "never": i.e.  always use tooltips
* "On first error" : with this option, you'll be warned each time you introduce an error in a note. That is, if a note has no LaTeX error and you introduce one, then you'll have a warning message. However, if the note already has a LaTeX error, you won't be notified again. (This is the default)

## Internal
This change Note.flush, still calling the former Note.flush.



## Links, licence and credits

Key         |Value
------------|-------------------------------------------------------------------
Copyright   | Arthur Milchior <arthur@milchior.fr>
Based on    | Anki code by Damien Elmes <anki@ichi2.net>
License     | GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
Source in   | https://github.com/Arthur-Milchior/anki-compile-latex-early/
Addon number| [769835008](https://ankiweb.net/shared/info/769835008)
Support me on| [![Ko-fi](https://ko-fi.com/img/Kofi_Logo_Blue.svg)](Ko-fi.com/arthurmilchior) or [![Patreon](http://www.milchior.fr/patreon.png)](https://www.patreon.com/bePatron?u=146206)
