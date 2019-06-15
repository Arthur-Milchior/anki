This document describe the content of the file profiles.db
(unpickled). It contains a line _global, and a line by profile. Both
are described separately.

# Global
## ver
## firstRun
## created
## defaultLang
## updates
## suppressUpdate
## disabledAddons
## lastMsg
## id

# Profile

## mainWindowGeom
## mainWindowState
## numBackups
## lastOptimize
## fullSearch
## searchHistory
## lastColour
## stripHTML
## pastePNG
## deleteMedia
## preserveKeyboard
## syncKey
A key, given by the server during a synchronization. It is used
instead of the password. This allow to avoid to save the password in
the computer.

Note that this key allows to synchronize, so it is almost as powerful
than the password. The only things that can not be done with it are
the ones related to ankiweb only. I.e. sharing decks and add-ons, and
deleting the account.

## syncMedia
Boolean. whether media should be synchronized. It can be decided in
the profile option.

## autoSync
## allowHTML
## importMode
## getaddonsGeom
## addGeom
## editor3Splitter
## editorGeom
## editorState
## editorHeader
## studyDeck-defaultGeom
## studyDeck-selectModelGeom
## mediaDirectory
## studyDeck-selectDeckGeom
## editcurrentGeom
## syncUser
The login (i.e. email).
## deckconfGeom
## previewGeom
## checkmediadbGeom
## findreplaceGeom
## hideDeckLotsMsg
## importDirectory
## changeModelGeom
## CardLayoutGeom
## getTagGeom
## modelsGeom
## emptyCardsGeom
## modeloptsGeom
## exportDirectory
## hostNum
Initially None. Else a number sent during synchronization. The
synchronization is done with https://sync{hostNum}.ankiweb.net, except
the first time where it is https://sync.ankiweb.net.

## mediaState
## importState
## revlogGeom
## dyndeckconfGeom
## ViewHTMLGeom
## deckStatsGeom
## nm_user_color_map
## nm_color_a
## nm_style_scroll_bars
## nm_invert_latex
## nm_mode_settings
## start_at
## end_at
## nm_enable_night_mode
## nm_state_on
## nm_disabled_stylers
## nm_color_t
## nm_transparent_latex
## nm_color_b
## nm_color_s
## nm_invert_image
## nm_enable_in_dialogs
## addonsGeom
## addonconfGeom
## addonconfSplitter
