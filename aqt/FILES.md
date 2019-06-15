As the file with [same name in parent directory](../FILES.md), this
document contains a succint description of the content of each file
from this folder.

The only folder is forms, which is obtained by compiling
(../designers). Thus, it content won't be described here. The files in
this folder does not contains the code to describe the QT window. It
sometime contains HTML content to put in those windows. And it
populate the window's value


We first describe windows. We then describe everything else
# Windows
## About
This file deal with the "Help>About" window

## AddCards
This file deal with the window opened in order to add a new note in
anki. It thus also add cards (and in fact rejects to add a note
without cards). It use the Editor as a subwindow.


## Addons
This file deals with addons. More precisely, it deals with:
* The add-on manager.
* The edition of add-on's configuration
* Downloading a new add-on

## Browser
This file deal with the browser. It use the
Editor as a subwindow when a single card is selected.

## clayout
This file contains a single class CardLayout. It describes the way to
present a card. Either during review, preview, and edition of card's
type.

## customstudy
The window "custom study". When a deck is selected but reviewing is
not yet started, you can open this window to review more cards.

## deckBrowser
The content of of the main window when it show decks.

## deckchooser
The window allowing to choose a deck. Either to choose were new cards
are added, or to choose where to move an existing card.

## deckconf
The window "option". Obtained from the main window by clicking on the
gear and then Options.

## DynDeckConf
The window used to create and edit a filtered deck (also known as
dynamic deck)

## EditCurrent
The window used to edit the card currently being reviewed. It use the
Editor as a subwindow.

## Editor
The subwindow used to edit the content of a note. It is used in the
browser when a single card is selected, in editcurrent and in addcard.

## Error
The window which show when anything was written on stderr.

## Exporting
The window opened to export cards or notes. It can be opened by
File>Export from the main window, or by selecting a deck's gear and
then Export.

## Fields
The window which allow to add/remove/rename fields from a note
type. It can be opened in the editor, or in the note's type manager.

## Importing
The windows for importing cards. It is not the window to find the
file, but the window to deal with it.

## Main
The first window opened when the profile is loaded. It may contain
either the list of decks, a deck's overview, or the card being
reviewed. It always contains Toolbar

## mediasrv
TODO

## ModelChooser
The window which allow to choose a note's type (a.k.a. a model in
anki's code).
It also deals with the button used to open this window.
It can be opened in the addCard's window, note importer,
and when changing a note's type.

## Model
The window allowing to change a notes type (a.k.a. a model in anki's
code). This is obtained from any editor or from the note's managare by
clicking on "cards".

## Overview
The content of the main window when a deck is selected but review did
not start yet.

## pinnedModules
Allow to keep some python packages that are commonly used by add-ons,
but no longer used by Anki itself, available in the official builds.

## preferences
The preference for the whole collection. Obtained from the main window
by "Tools>Preferences".

## Profiles
The profile manager. The first thing opened by anki. And obtained
again by "File>Switch profile"

## Progress
The window showing how much an action progress. Used while checking
the database, the media, the empty cards, etc...

## Reviewer
The content of the main window, when a card is beeing shown.

## Sound
The window used to record a sound

## Stats
The stat window. Obtained by pressing the button "Stats" in the main
window.

## StudyDeck
The window opened by "Tools>Study deck" (shortcut /) allow to start
 reviewing the selected deck.

## Sync
Window showing the progress of the synchronization

## TagEdit
An editor of card. Not clear which one. TODO

## TagLimit
The window obtained by selecting a normal deck, then Custom
Study>Study by card state or tag>Choose tags.

## Toolbar
The line on top of the main window, with "Decks, add, browse, stats,
sync"

## Update
Message to check whether anki can be updated or not.

 It can also
be opened from card adder. And from the browser in order to move a
card to another deck.



# else Everything
## downloader
Used to download add-ons. It does not corresponds to a window.

## Qt
Ensure that QT has the correct version. QT's function are used
through this file.

## Utils
A lot of tools used by many window for standard actions to do.

## WebView
Page to show content encoded as HTML.

## WinPath
Find path in windows.
