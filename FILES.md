This document describe the different files and folders you'll find in this
folder. Files in subfolder are described in the file FILES.md in this
subfolder. I also indicate which files are in original anki source
code, and which are added by the author of those comments.

This should helps an (add-on) developpers, by letting them know where
to search for informations.

# Folders

## [anki](anki/FILES.md)
This folder contains most of the back-end. That is it contains
everything related to the database and its content. It allows to
manipulate decks, decks' option, cards, notes, note type, templates,
tags, and so on. It also deals with synchronization.

## [aqt](aqt/FILES.md)
This folder contains most of the controller. It contains methods for
each possible actions in anki. It also contains the values associated
to each windows. It does not contains the actual code used to create
the window. However, it contains the code used to enter informatinos
into the window.

Note that running tools/build_ui.sh add a subfolder aqt/forms/. This
folder contains code compiled from designer/ which generates the window.

## designer
This folder contains the windows description, as .ui file, (a format
related to pyqt). When running tools/build_ui.sh, its content is
compiled into python code and sent into aqt/forms/. Those new files
are used to generate the window.

This folder also contains some images used by the GUI but not by its
HTML part.

## tests
As the name suggest it, this folder contains tests. Any change made to
anki must not break those tests. As any tests, they are not exhaustive
and a change may break them even if they do not detect anything.

## tools
Some script. Most of them are used to compile anki. The only exception
is tools/runanki.system.in. A copy of this file is used to start anki
from source.

## web
This title is kinda misleading. This file is not actually used for
ankiweb, nor for anything related to internet.

An important part of anki's user interface is coded in
html/css/javascript. The javascript and the python may interact and
call functions created in the other language. The python generate the
html, which imports the css, js and images files from this folder.

# Files
I do not any markdown file, readme file, makefile, and git
related file.

## anki.1
The unix manual (man) page

## anki.desktop
Description of anki used by the Gnome's window manager in UNIX
system to create an entry on the desktop. It may be used by any window
manager reading .desktop file.

## anki.png
Anki's  logo

## anki.xml
Mime information. It states that .colpkg and .apkg files are anki's
file.

## anki.xpm
A X pixMap file, used to represent anki's logo in pixel art.

## pkgkey.asc
A public pgp key. It's not clear where it is used, if anywhere.

## requirements.txt
The list of python library used by anki. Used during installation from
source, during the step ```pip3 install -r requirements.txt```.

## runanki
A python file allowing to start anki from source.

## .travis.yml
A Yaml file ensuring that Travis know how to integrate anki.
