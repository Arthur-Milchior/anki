As the file with [same name in parent directory](../FILES.md), this
document contains a succint description of the content of each file
from this folder.



# Folders
## Template
This folder deals with the template language used by anki's card's
type. This language, also called mustache, which uses a lot of  {{ and
of }}.

The content of this folder as another copyright than anki.

## Importing
Deal with importing files into anki. The file may be either created by
anki or by another program

# Files
We consider files related to the entirety of anki, such as database
and constants. And then files which encode a particular part of anki
such as note and decks.

## Anki-wide files
The files considered in this section are not related to the data of
some particular profile.

### __init__
This ensure that python is at least 3.5, with UTF-8 locale. It
contains anki's version number.

Note that ```from anki import *``` imports ```anki.storage.collection```.

### consts
This file contains constants. Those constants are used in any other
files. They also are used to encode/decode the content of the
database.

### Error
This file contains two kind of exceptions. A general AnkiError
exception. And DeckRenameError.

### Exporter
This file contain a main class ```Exporter```. This class is inherited
by other classes which allow to export's anki cards, note, deck or
package. Exporting is done with or without meta data. Those meta data
are, for example, the decks' name and note's type. Exporting with
metadata create a sqlite database. Exporting without metadata create a
csv file.

### Hooks
This file contains functions used to create and run hooks and
filters. It can also be used to "wrap" functions, as explained in
anki's add-on's documentation.

### Langs
This file contains functions used to localize anki in different
language. It does not contains the actual translation.

### Latex
This file contains functions used to compile LaTeX from the notes'
field into images.

### Mpv
This file contains the code used to read and record sounds. This
contains the part related directly to the MPV player.

### Sound
This file contains functions used to find the sound(s) to play in
notes' field. It also controls mpv.

## Utils
This class contains a lot of methods used to do transformation on
data. Those transformations may be used in any other classes.

## Files used to represents some a single value
Most files contains a single are associated to a notion of interest in
anki. Examples of such notions are cards, notes, decks, note
type... Some files contains a second kind of notion, associated to the
first one. For example (decks.py) also contains the values represents
decks' option.

Each of those files define a single class, used to manipulate those
values. We subdivise this section in two, depending on whether one or
multiple instances of this class exists simultaneously.

### Class with many instances
Each value we consider in this section is encoded in python as an
instance of a class. Those class are defined in the files presented in
this section

#### Cards
This file define a class Card. An instance of Card represents an
anki's card. It serves to create new cards, and find cards from the
collection.

#### Notes
This file define a class Note. An instance of Note represents an
anki's note. It serves to create new notes, and find notes from the
collection.

#### db
This file contains a single class, DB. Each instance of DB represents
a connexion to a sqlite database. Queries are not made directly to the
database, but through an instance of DB. For example, it ensures that
if some values is written in the database, the collection is marked to
be modified, and a synchronization is planified. Some other methods,
such as ```rollback```, only consists in calling the method with the
same name on the underlying database.

#### Stats
Go see "Stats" in the following section.

### Class with a single instances
The files in this section allow to encode some values. Those values
are encoded as dictionnaries. Each file define a single class, which
define method to edit those dictionnaries. Those classes are called
manager. Each instance is associated to a collection. Thus a new
instance is created each time the profile is changed.

While it is not clear why anki's author used manager. Why values are
dictionnaries and not object. The best guess of the documentation's
writer is that it corresponds to the way to save data in the
database. Each data considered in this section is saved as a json
string in the database.

#### collection
This file contains a single class _Collection. A collection represents
a profile. Each time the user is changed, the collection is closed and
a new collection is opened.

This class contains a lot of paramaters related to the profile such as
the profile's id. It contains also a lot of method to create or get
any kind of values. For example, ```newNote``` allow to create a new
note, associated to this collection. And ```getNote``` allows to
obtain a note from the collection. Note that those could be done
directly using the class Note, but the collection must be passed as
argument when the class is created. Using those functions allows to
avoid doing this.

#### Decks
This file contains a single class, ```DeckManager```. This of course
deals with decks. Each deck being a single dictionnary. The
DeckManager also deals with the decks' option, also known as "configuration".

#### Finder
A finder object allow to find cards or notes satisfying some
query. The query is the same as the one used in the browser and in
filtered decks.

#### Media
This file contains a class MediaManager. This class's instance deal
with medias. It update the media database and the media folder of the
current collection.

#### Models
This file contain a single class, called ModelManager. A note type,
also called model in the code, is encoded as a dictionnary. Each card
type, also known as template in the code, is also encoded using a
dictionnary. This class allow to get and change models.

#### Sched and schedv2
This fill contain a single class Scheduler. The instance of the
scheduler has two purposes. It allow to find the following card to
study. And when a card is studied, it reschedule it.

Each file correpsonds to a distinct scheduler. A big part is common to
both scheduler and could actually have been merged into a single
class.

#### Stats
This deck contains two subclass. CardStats and CollectionStats. Each
class allow to compute and show statistics of review of a single card
or of the whole collection. Note that the first class should have been
in the previous section and not in this one.

#### Statsbg
The stat bacground image, encoded in base64.

#### Stdmodels
This class contains function to create the basic models. It is used to
initiate the collection. It is also used to import notes which were
exported from another software.

#### Storage
This file contains a single class Collection. This is used to create a
new collection or open it from the database's profile.

#### Sync
This class contains code used to synchronize the collection with the server.

#### Tags
This class contains a single class called TagManager. It is used to
edit the set of tags saved in the collection. It does not deal with
the tag in a single note. The collection save tag in order to autocomplete.
