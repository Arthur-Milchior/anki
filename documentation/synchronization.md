In this file, I present anki's synchronization process. I first
describe the general mechanism used in anki's code (desktop
version). I then describe each step.


# Protocol
Each transmission uses post. The method `foo` send its request to
either https://l1sync.ankiweb.net/{m}sync/foo, or
https://sync{d}.ankiweb.net/{m}sync/foo, where `{d}` is a value provided by the
server during the previous sync (initially the empty string), and {m}
is "m" if and only if it's a media synchronization, otherwise, it is
the empty string.

The header is a dictionnary containing:
* 'Content-Type': 'multipart/form-data; boundary=%s' % "Anki-sync-boundary".decode("utf8"),
* 'Content-Length': the size of everything sent in the body

The body contains, separated by "--Anki-sync-boundary",:
«Content-Disposition: form-data; name="{key}"

value
»
for a dictionnary of pair key-value. Those values describe the
message sent (i.e. key to connect, identification number, whether
compression is not used). But does not contain the actual data (unless
the actual data is the key, when a connection should be established).

If the protocol requires to sent an object, then it is sent as
«
Content-Disposition: form-data; name="data"; filename="data"\r\n\
Content-Type: application/octet-stream\r\n\r\n"»
{object}
»
Object is build as follow:
* object is dumped into json
* result is encoded in UTF8
* io.BytesIO is applied to it.s
* compressed with gzip, compression level 6

The message then ends with «--
»


## Normal synchronization
Each message sent in the following protocol send at least the
dictionnary containing:
* 'c': whether the object sent is compressed with gzip.
* 'k': the hkey,
* 's': a random string of 8 chars

With one exception, the hostkey post request does not contain the two
last values (since this request allows to discover those values).
### HostKey
The hostKey is an identifier given by the server which replace the
pair login/password. It is saved by anki when you sync. If you don't
have an hkey, anki asks to your login/password, and begin by sending a
request for an hostKey.

The post request `hostkey` request contains no post objects. Its
objects is the dictionnary with:
* 'u': the user login
* 'p': the password.

It return the hostkey.


### Meta
The post request `meta` request contains  as object the dictionnary:
* 'v': SYNC_VER (currently 9, but I assume it may change when anki
  version change)
* 'cv': "ankidesktop,{versionWithBuild},{}"

It should return a dict containing:
* msg: An arbitrary message to show to the user at the end of the
  sync. Usually the empty string.
* cont: if its falsy, it means the server abort.
* scm: a schema modification time. If it's not equal to the
  collection's scm value, it mean that some part of the collection was
  modified (note type, card type) since last sync, and thus full
  update is required.
* ts: time stamp. The time according to the server. If the difference
  in time between server and computer is greater than 5 minutes, the
  synchronization is rejected. (Time zone are of cours taken into
  account)
* mod: the time of the last modification on the server. If it's value
  is equal to mod on the computer, it means that no change did occur,
  thus sync is not required.
* usn: Unique synchronization number. The greater usn of some anki
  object on the server is usn. Thus, the next modification will have
  synchronization number usn+1, to emphasize the state that it occurs
  after this synchronization.
* uname: (equivalent to syncName in the profile). The user name (i.e. login/email). It must be sent because the user
  may have chaged it on the server.
* hostnum: as in the profile. Its a value indicating which url/server to
  use for synchronization with anki.

### Basic check
The database will check that everything is consistent before
resuming. This is the first time it will occur. This check is
described in [BD_Check.md].

Hook ("sync","meta") is now called, but seems to have absolutly no
effect.

### Start
The post request `start` is sent with object a dictionnary:
* 'minUsn': the collection's value USN. I.e. the last number sent by
  the server (plus one). It represents the minimal USN of change that
  need to be downloaded.
* 'lnewer': whether collections's mod is greater than server's mod.

It return a dictionnary associating to each key a list of ids of
things to delete. Keys are notes, cards and decks. The content of the
deleted deck is not deleted, nor are the children of the deck if it
has any.

### applyGraves
The post request `start` is sent with object a dictionnary with a
unique key 'changes' whose value is a dict with keys "notes", "cards",
and "decks", each containing ids of object deleted since last
synchronization. At most 250 are sent, the command may be sent
multiple time if required.

### applyChanges
The post request `start` is sent with object a dictionnary with a
unique entry "changes", whose value is a dict with keys 'models',
'decks', 'tags' as they are saved as dict in the database. If mod is
newer here than on server, then the dict in the dict also contains key
'conf' and 'crt'.

It returns a dictionnary with:
* models: container of model (note type) dictionnary.
* decks: a list of two elements
** the decks, as in the case of models
** the dconf (deck options). As in the case of models.
* 'tags': the container of tags added.
* 'conf': (not mandatory. Probably only here if it did indeed changed)
* 'crt': as conf.

In each case, it sends only thing which changed, which may have to be
replaced in the collection. It is possible that the replacement does
not occur if the model have also been modified in the collection and
that the time of this modification is after the time of the
modification saved on the server.

### chunk
The post request `chunk` does not send anything. It receive a
dictionnary (the chunks) containing some keys in  'revlog', 'cards'
and 'notes', containing lines to enter in the table of database with
the same name (unless an entry with the same id is already here).

It also contains `done`, stating whether there are no more thing to download.

This post request is repeated until chunk['done'] is truthy. Each time,
hook ("sync","server") is called. But seems to have absolutly no effect.

### stream
The post request `applyChunk` takes as input a dictionnary, similar
to the one receveide by the `chunk` method. I.e. containing
keys `revlog`, `cards`, `notes` and `done`. This dic contains at most
250 elements.

This post request is repeated until there are no more new lines to
sent. Each time, hook ("sync","server") is called. But seems to have
absolutly no effect.

### sanityCheck

Hook ("sync","sanity") is called. It changes the message to
"Checking...".

It calls basic check and then ensures that USN should not be -1 in
cards, notes, revlog, graves, deck, tag, model. If it is the case,
return a string giving the name of the table not satisfying it.

If a non-root deck has no parent, it is created.


It computes the list `c`
* three numbers to show in anki
* list/footer. I.e. Number of new cards, learning repetition,
* review card. (for selected deck),
* number of card,
* number of notes,
* number of revlog,
* number of grave,
* number of models,
* number of decks,
* number of deck's options.

### sanityCheck2
The method `sanityCheck2` is now called. It sends as objects
result `c` from sanityCheck. It returns a dictionnary `dic`
which contains a key 'status'. Two paths are then taken, depending on
whether `dic['sync']` is the string 'ok' or not.

I assume taht `ok` occurs if the server, doing the same
computation, finds the same result. If so, it is possible that a sync
fail if it is done almost at time of new day, since the number of card
to review would be distinct on server and on computer.

#### Finish (If it's 'ok')
runHook("sync", "finalize") is called. It does nothing.

The method `finish` does not sent any object. It returns a number,
which will become collections's `ls` value.

Collection _usn value is incremented to be maxUsn+1.

Database is considered to be modified. And then collection is saved.

#### If it's anything but 'ok'
Collection is rollback. State schema is modified. Save the collection


## Media Syncing
A special method exists for test. We do not consider it in this
document.

Except for the `begin` command,  the dictionnary of value sent contains a single element:
* 'sk': whose value is an identification number returned by the server
  to be used during this connexion.

### Finding media changed
hook("sync","findMedia") is run. The window's text become "Checking media...".

### begin
The first method used id `begin`. Its dictionnary is:
* 'k': the hostkey
* 'v': "ankidesktop,{anki's version number},{platform}:{platform's
  version}", with platform being either win, lin, mac or unknown. In
  the last case, there are no version sent.

It receive a json utf8 dictionnary with:
* identification number. This number is sent back to the server with
  each next communication.
* usn: date of last modification of medias on the server

if server's usn is equal to collection's greatest usn, no change are
found and the sync halts.
### mediaChanges
The method `mediaChanges` send the last USN of medias in the
collection.

It returns a list. Each element of the list is a triple:
* name, the name of the media file which is believed to be new or
  changed on the server.
* usn, date of the last change of this file
* sum. Either a falsy value is the media is deleted. Or a checksum of
  the file to test whether two files are equal.

Those elements are probably in non-decreasing order of USN.

Each such media is logged. If the media is new or changed on server,
it is added to the list `need`. If the media existed and was
dirty, it is cleaned.

If the media is deleted on the server and not dirty, then it is also
deleted in the collection. Otherwise, if it is dirty, it log
"conflict; will send", but actually do nothing.

If both sides see the data as deleted, log this information and clean
it on the collection side.
### downloadFiles
The method `downloadFiles` sends a dict with a unique key 'files',
whose value is the first 25 files which must be downloaded.

Returns a zip file containing:
* _meta, a file containing a json dict associtaing to each name of file in zip (except meta) a name to be used in the media folder
* arbitrary fields to save in the media folder

The hook "syncMsg" is run, with a message stating how many files were
downloaded. It changes the message on the progress window.

This is done until there are no more files to download.

### LastUsn
Change the last usn of media to the Usn of the last file announced in
data.

### uploadChanges
This step occurs as long as media must be sent.
Hook ("syncMsg") is run and state how many media still need to be
sent.

The post method `uploadChange` contains as object a zip file,
containing:
* from 1 to 25 files
* a file _meta, associating to each file name in the zip directory
  another name to be used in the collection. I assume that the name in
  a zip file are limited and this allow to still have any name
  accepted on the operating system.

Return a pair with:
* the number of file processed,
* the last usn on server which become the collection's new lastUsn in
  the database. The db is then sync.



This is done in loop until there no more data to send.

If at some step, the change of last usn is not equal to the number of
media sent, it means that concurrent update occured. This is
logged. When the entire syncing process ended, it is entirely
restarted.

### mediaSanity
The post request `mediaSanity` sends a dic with a unique key
`local` whose value is the number of media. It returns a
string. This string is returned by the method sync. If the string is
not "OK", the media database is emptied by method
`anki.media.MediaManager.forceResync`.

## Full upload

run hook ("sync", "upload"). It change the text to "Uploading to
AnkiWeb...".

It check whether the database is in correct state, and basic check
(see [DB_check.md]). In case of problem, no upload and return False.

* change usn -1 to 0 in notes, card and revlog, and all models, tags, decks, deck options.
* empty graves.
* Update usn
* set modSchema to true (no nead for new upload)
* update last sync time to current schema
* Save or rollback collection's db according to save.
* Close collection's db, media's db and log.

The method is `upload`, it contains as object the collection database.

## Full download

run hook ("sync", "upload"). It change the text to "Downloading for
AnkiWeb...".

The post method `download` takes no deal argument. It may returns
the string is "upgradeRequired", the hook is called ("sync",
"upgradeRequired") and halts. It show the message "Please visit
AnkiWeb, upgrade your deck, then try again."

Otherwise, it returns a sqlite database. It is checked to be a
database readable with at least a card. If it has no card and current
collectio has card, then nothing the downloaded db is deleted,
otherwise it becomes the collection's database.
