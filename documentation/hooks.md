# All hooks in anki.
This document contains a description of all hooks in Anki at time of
writting.

Each description contains the argument the hook expect. A description
of when the hook is called. And which functions are in the
hook. Either in anki's code. Or in some add-ons, which may serve as
example.

## Hooks
Some hooks are similar. For examples, hooks used to add action to
context menu (menu opened by right clicking). Thus, I sort the hooks
by similarity.

### Menues
In this section, we consider menues. Either obtained by doing a right
click. Or by the top-bar menu.

Unless specified otherwise, no functions are added to the hook.

#### Top menu
##### browser.setupMenus
Called from browser when menus are created.

#### Context menues
A context menu is obtained by right-clicking somewhere.

Unless specified otherwise, those hooks takes two arguments:
* self: the window or subwindow on which a right click is done
* m: a qmenu object which will be shown near to the click. In which
  more actions can be added.

##### AnkiWebView.contextMenuEvent
It allows to add actions to do by right clicking in any html window
using aqt.webview.

Called in aqt.webview.AnkiWebView.contextMenuEvent

##### browser.onContextMenu
Called when right clicking in the columns of the browser.

Called in aqt.browser.Browser.onContextMenu.

##### EditorWebView.contextMenuEvent
Called from aqt.editor.EditorWebView.contextMenuEvent, the part of the
window used to edit note.

##### Reviewer.contextMenuEvent
Called from aqt.reviewer.Reviewer.showContextMenu: the class for the
reviewer of cards in the main window

#### Other menues
###### setupEditorButtons
Called from aqt.editor.Editor.setupWeb, with the buttons on right top,
and the editor itself. It would allow to add more buttons on the top
right of editors

##### mungeEditingFontName
Contains aqt.editor.fontMungeHack, which return the input, by
replacing the end of the string, if it's " L" by " Light". Because of
some difference between name in QFont and WebEngine.

Called in aqt.editor.Editor.fonts, when the list of filters is generated.

##### showDeckOptions
Called from aqt.deckbrowser.DeckBrowser._showOptions. Allow to add
actions to do to list of decks, after Rename, options, export, and
delete.

For example, add-on [Change option
recursively](https://ankiweb.net/shared/info/751420631) uses it to add
the way to change option of deck and subdecks.

##### AddCards.onHistory
Called from aqt.addcards.AddCards.onHistory, i.e. when you click on
the History button of the "add card" window. It allow mostly to add
more cards, for example in addon [Open 'Added Today' from
Reviewer](https://ankiweb.net/shared/info/861864770).

### State changes
The hooks in this section are called when something change.

##### exportersList
Arguments is:
* exps: a list of exporter (i.e. class implementing
  anki.exporting.Exporter. )

It is called in anki.exporting.exporters(), a function which returns
the list of exporters existing in the code. It allows to add (or
remove ?) exporters, and thus to export in other file format. Thus it
allows to add other element in the export window.

#### Model Change
##### odueInvalid
Contains anki.main.AnkiQt.onOdueInvalid, which show a warning and ask
to check the database.

Called from anki.cards.Cards.flush and .flushSched if a card's queue
is rev, has an odue value but is not in a dynamic deck.

##### afterStateChange
##### beforeStateChange
It's called just after and just before the main window's state
changed.

Arguments are:  state, oldState, *args

See aqt.main's documentation to know which are the potential states.

##### currentModelChanged
Called when the note type (a.k.a. model) is changed. It's run only
from modelchooser. It the windows importdialog, deckchooser,
changemodel and addcards are opened/closed, the following methods are
added/removed from this hook: aqt.importing.ImportDialog.modelChanged,
aqt.deckchooser.DeckChooser.onModelChange,
aqt.browser.ChangeModel.onReset and
aqt.addcards.AddCards.onModelChange.

##### reset
Contains the method self.onReset, where self is the class
aqt.addcards.AddCards, aqt.modelchooser.ModelChooser,
aqt.studydeck.StudyDeck, aqt.browser.Browser, aqt.browser.ChangeModel,
aqt.main.AnkiQt, aqt.editcurrent.EditCurrent, while those windows are
opened. This function is essentially similar to reopening the window,
setting everything according to the current state of the collection.

It is called from aqt.AnkiQt.reset, i.e. when the collection should be
reseted, if a collection is loaded. This is called often, when
anything occurs to the collection.

##### leech
Contains anki.reviewer.onLeech. Which state that a card is a leech,
and maybe that it is suspended. It also contains function for tests
(not considered in this documentation).

It is called from both scheduler, when a card become a leech.

##### remNotes
Contains aqt.main.AnkiQt.onRemNotes, a method adding a line about
deletion in the file deleted.txt. The argument is the collection and
the ids of the removed notes.

It is called from anki.collection._Collection._remNotes.

##### newDeck
Called from anki.decks.DeckManager.id when a new deck is created.

Contains aqt.browser.Browser.maybeRefreshSidebar (if the browser is
on), which change the side bar of the browser if it is visible, to
show the new deck.

##### newModel
Called from anki.ModelManager.models.save each time note type
(a.k.a. models) are saved (even if the model is not new)

Contains aqt.browser.Browser.maybeRefreshSidebar (if the browser is
on), which change the side bar of the browser if it is visible, to
show the new deck.

##### modSchema
Contains aqt.main.AnkiQt.onSchemaMod, which ask the used to confirm
they accept a change requiring to upload the full database.

Is called as a filter in anki.collection._Collection.modSchema, with
parameter True. If it returns False, i.e. the user cancels, then an
error is raised, aborting the schema modification.

##### newTag
Called from anki.tags.TagManager.register(tags) if at least one of the
tag of tags is new.

Contains aqt.browser.Browser.maybeRefreshSidebar (if the browser is
on), which change the side bar of the browser if it is visible, to
show the new deck.

#### GUI change
###### editFocusLost
contains aqt.browser.Browser.refreshCurrentCardFilter,
i.e. aqt.browser.Browser.refreshCurrentCard. Hence refresh the note in
the dataModel and (re)render the preview.

Called from aqt.editor.Editor.onBridgeCmd when the command starts by
"Blur" (I have no idea what it means)

##### setupEditorShortcuts
Arguments are:  cuts, self

Called from aqt.editor.Editor.setupShortcuts, i.e. when the note
editor is shown somewhere.

The two arguments are the list of shortcuts, and the editor. This
allow to add more shortcut to the editor.

##### self.state+"StateShortcuts"
Called from aqt.main.AnkiQt.setStateShortcuts. I.e. for
aqt.reviewer.Reviewer.show and aqt.overview.Overview.show.

The argument is the list of shortcuts for the current states. It
allows to add more shortcut to this state.

###### setupStyle
Called from aqt.main.AnkiQt.setupStyle. Hence during
aqt.main.AnkiQt.setupUI. Takes as argument the buffer, as a string,,
with its QMenuBar and QTleeWidget. Not clear exactly what it does,
because I don't know graphical user interface.

##### profileLoaded
Called in anki.main.AnkiQt.loadProfile, after the end of the loading,
before calling the onsuccess function given in argument. Note that the
collection is not yet accessible from the main window.

An add-on used this to ensure that some event is executed after
profile is loaded, and not at start-up as is the default.

##### unloadProfile
Called anki.main.AnkiQt.unloadProfile, i.e. when anki exits, when
there is a change of profile. It contains anki.sound.stopMplayer,
which stop the music player.

##### tagsUpdated
Called from aqt.editor.Editor.saveTags, with as argument the note
contained in the editor. Hence when the note should be saved.

##### browser.rowChanged
Called when the selected card(s) are changed in the browser. After the
change is processed, but before rendering the view.

##### loadNote
It's called from aqt.editor.Editor.loadNote.oncallback, when a note is
loaded in the editor (i.e. the bottom part appearing in the browser
when a single card is selected).

Contains aqt.browser.Browser.onLoadNote while the browser is
open. Takes as argument the editor. This function refresh the current
card, using the note in the editor.

##### undoState
Contains aqt.browser.Browser.onUndoState(on) if a browser is
opened. This method turn the undo action on or off according to the
Boolean value of `on`. It change the text of this action.

It is called from aqt.main.AnkiQt.maybeEnableUndo, which change the
undo action from the main window.

##### revertedCard
Called with the id of a card, when the reviewer is loaded, and the
last review is undone.

##### revertedState
Similar to undoState, but when «undo» is called from the main
window, not in review mode.

##### showAnswer
Called at the end of `aqt.reviewer.Reviewer._showAnswer`.

##### showQuestion
Called at the end of `aqt.reviewer.Reviewer._showQuestion`.

### Unknown
Those hooks are called in a part of code I don't understand yet. Help
is welcomed.

##### mpvWillPlay
Contains aqt.main.AnkiQt.onMpvWillPlay, which seems to change the
_activeWindowOnPlay to some window, unless the argument file is a video.

Called from anki.sound.MpvManager.queueFile(file), with the file as
argument. This method is called while anki.sound.setupMpv, from
anki.main.AnkiQt.setupSound, from anki.main.AnkiQt.setupUI, from
anki.main.AnkiQt.__init__. Hence it seems to be called only once.

##### editFocusGained
Arguments are:  self.note, self.currentField

##### editTimer
Arguments are:  self.note

Contains aqt.browser.Browser.refreshCurrentCard when the browser is open.
##### exportedMediaFiles
Arguments are:  c: a path

Contains aqt.exporting.ExportDialog.exportedMedia but only while
aqt.exporting.ExportDialog.accept runs, while it calls
aqt.exporting.ExportDialog.exporter.exportInto where
aqt.exporting.ExportDialog.exporter is some class of anki.exporting.

Called from anki.AnkiPackageExporter._exportMedia each time a media is
exported.

##### noteChanged
Called from anki.main.AnkiQt.noteChanged(nid), with argument
nid. Seems to never be called.

### Network
##### httpRecv

Contains a function recvEvent while some download occur. The hook is
removed when the download ended.

The download may be either an add-on, or a synchronization.

This method takes as argument a number of byt, add it to some count
`self.recvTotal` and then emitting something as a QT object. In
the case of synchronization, if the sync is aborted, it raises an
exception.

It is called from anki.sync.AnkiRequestsClient.streamcontent when a
chink of data is received. This data may be either an add-on or a synchronization.

##### httpSend
Similar to httpRecv, but for emissiond of synchronization, and not for
reception.

Called from anki.sync._MonitoringFile.read.

##### sync
Contains, equivalently:
* (lambda type:aqt.sync.SyncThread.fireEvent("sync",type)),
* (lambda type:aqt.sync.SyncThread.event.emit("sync",type))
* (lambda type:aqt.sync.onEvent("sync",type))
but only while aqt.sync.SyncThread.run runs, i.e. while anki synchronization is
running. Here, event is a pyqtSignal(str, str)

It is called from anki.sync.Syncer.sync, each time the
synchronization's step change. The different step/type are, in this
order:
* login: just after saving the collection
* meta: startup and deletions
* server: stream large tables from server
* client: stream to server
* sanity: sanity check
* finalize

Furthermore, there is the step/type "stream" called while streaming
occur in steps Server and client.

It's not clear what is the goal of this, since the output of the hook
is never used, and the function does not have any access to the
synchronizer object.

It's also called from anki.sync.FullSyncer.download, with the
following type:
* download
* upgradeRequired
and from anki.sync.FullSyncer.uplad, with the types:
* upload

And from anki.sync.MediaSyncer.sync, with:
* findMedia.

##### syncMsg
Contains aqt.sync.SyncThread.run.syncMsg, hence (lambda
msg:aqt.sync.SyncThread.fireEvent("syncMsg",msg)), hence (lambda
msg:aqt.sync.SyncThread.event.emit("syncMsg",msg)), where event is a
pyqtSignal(str, str).

It contains this function only while the synchronization thread
runs.

It's called from anki.sync.MediaSyncer.sync with a text stating how
many media remains to upload. And from
anki.sync.MediaSyncer._downloadFiles, where it states how many media
remains to download.


### Adding options
##### search
called from anki.find.Finder.__init__, with the argument
anki.find.Finder.search. This is a dictionnary from terms which can be
used in a search (in browser, in filtered deck) to a function giving a
sql query satisfying this search. This allow to add new terms and
function to this list.

### fmod
The following four filters are called from
anki.template.template.Template.render_unescaped. When a field start
by `{{foo:`, i.e. it is `{{foo:bar}}`, the filter fmod_foo is
called on the content of the field bar. This may occur multiple time,
since multiple modifier may begin a mustache.

For example, the add-on [Edit Field During
Review](https://ankiweb.net/shared/info/1549412677) add a hook
fmod_edit, so that you can use `{{edit:` in card type.

##### fmod_kanji
##### fmod_kana
##### fmod_furigana
Contains methods anki.template.kanji, .kana, and .furigana. This edit
the text given in argument. Replacing &nbsp; by spaces. And then some
transformation which I don't understand. It's supposed to be for Japan language.

##### fmod_hint
Contains anki.template.hint.hint. A method which generate html for
hints link in questions. And the js code which replace the hint
link by the hint.



#### Hooks called, but from methods which are never called themselves.
##### colLoading
Arguments are:  self.col
It seems to be never called. More precisely, it's called in
aqt.main.AnkiQt._colLoadingState, which itself is never called.
##### mpvIdleHook
Contains aqt.main.AnkiQt.onMpvIdle. Not clear yet what it does.

Called from anki.sound.MpvManager.on_idle, which seems to be never
called.

##### reviewCleanup
Called from aqt.reviewer.Reviewer.cleanup, hence from
anki.main.AnkiQt._reviewCleanup assuming the new state is neither
"resetRequired" nor "review". Which itself seems to never be called.



### Preparing question and answers
##### mungeQA
Contains anki.latex.mungeQA. A method which generate HTML which show
an image which contains the compilation result of the LaTeX given in input.

Called from anki.collection._Collection._renderQA.

Arguments are:
* the card template, with fields replaced by their values.
* "q" or "a"
* map sending fields to their value (and special name)
* the model object
* 8-tuple of data
* the collection

###### prepareQA
Called from aqt.reviewer.Reviewer._showQuestion, with the text of the
question, the card object and the text "reviewQuestion".

Called from aqt.reviewer.Reviewer._showAnswer, with the text of the
answer, the card object and the text "reviewAnswer".

Called from aqt.clayout.Reviewer._renderPreview, with the text of the
question, the card object and the text "reviewQuestion".

Called from aqt.clayout.Reviewer._renderPreview, with the text of the
answer, the card object and the text "reviewAnswer".

###### mungeFields
Called from aqt.collection._Collection._renderQA, after {{type: are
processed, <cloze, are processed, {{FrontSide}} is processed, but
before processing clozes.

## Notes
I omit the runHook of web/reviewer.js, which seems unrelated to the
purpose of this document.

It is possible that this document becomes outdated. Since the author
of the documentation and of anki are two distinct people who almost
don't talk, it's hard to know when change occur. Thus Hooks added or
modified after the writting of this document may be missing. In which
case the author would love to be contacted to learn about this fact.
