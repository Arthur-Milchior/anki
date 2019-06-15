# -*- coding: utf-8 -*-
# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

import copy
import json
import os
import re

from anki.collection import _Collection
from anki.consts import *
from anki.db import DB
from anki.lang import _
from anki.stdmodels import (addBasicModel, addBasicTypingModel, addClozeModel,
                            addForwardOptionalReverse, addForwardReverse)
from anki.utils import intTime, isWin


def Collection(path, lock=True, server=False, log=False):
    """Open a new or existing collection. Path must be unicode.

    server -- always False in anki without add-on.
    log -- Boolean stating whether log must be made in the file, with same name than the collection, but ending in .log.
    """
    assert path.endswith(".anki2")
    path = os.path.abspath(path)
    create = not os.path.exists(path)
    if create:
        base = os.path.basename(path)
        for char in ("/", ":", "\\"):
            assert char not in base
    # connect
    db = DB(path)
    db.setAutocommit(True)
    if create:
        ver = _createDB(db)
    else:
        ver = _upgradeSchema(db)
    db.execute("pragma temp_store = memory")
    db.execute("pragma cache_size = 10000")
    if not isWin:
        db.execute("pragma journal_mode = wal")
    db.setAutocommit(False)
    # add db to col and do any remaining upgrades
    col = _Collection(db, server, log)
    if ver < SCHEMA_VERSION:
        _upgrade(col, ver)
    elif ver > SCHEMA_VERSION:
        raise Exception("This file requires a newer version of Anki.")
    elif create:
        # add in reverse order so basic is default
        addClozeModel(col)
        addBasicTypingModel(col)
        addForwardOptionalReverse(col)
        addForwardReverse(col)
        addBasicModel(col)
        col.save()
    if lock:
        col.lock()
    return col

def _upgradeSchema(db):
    """
    Change the database schema from version 1 to 2 and 2 to 3 if required.

    Return the version number when this function starts.
    """
    ver = db.scalar("select ver from col")
    if ver == SCHEMA_VERSION:
        return ver
    # add odid to cards, edue->odue
    ######################################################################
    if db.scalar("select ver from col") == 1:
        db.execute("alter table cards rename to cards2")
        _addSchema(db, setColConf=False)
        db.execute("""
insert into cards select
id, nid, did, ord, mod, usn, type, queue, due, ivl, factor, reps, lapses,
left, edue, 0, flags, data from cards2""")
        db.execute("drop table cards2")
        db.execute("update col set ver = 2")
        _updateIndices(db)
    # remove did from notes
    ######################################################################
    if db.scalar("select ver from col") == 2:
        db.execute("alter table notes rename to notes2")
        _addSchema(db, setColConf=False)
        db.execute("""
insert into notes select
id, guid, mid, mod, usn, tags, flds, sfld, csum, flags, data from notes2""")
        db.execute("drop table notes2")
        db.execute("update col set ver = 3")
        _updateIndices(db)
    return ver

def _upgrade(col, ver):
    """Change the collection, assumed to be in version `ver`, to current
    version. It does not change the schema."""
    if ver < 3:
        # new deck properties
        for deck in col.decks.all():
            deck['dyn'] = DECK_STD
            deck['collapsed'] = False
            col.decks.save(deck)
    if ver < 4:
        col.modSchema(check=False)
        clozes = []
        for model in col.models.all():
            if not "{{cloze:" in model['tmpls'][0]['qfmt']:
                model['type'] = MODEL_STD
                col.models.save(model)
            else:
                clozes.append(model)
        for model in clozes:
            _upgradeClozeModel(col, model)
        col.db.execute("update col set ver = 4")
    if ver < 5:
        col.db.execute("update cards set odue = 0 where queue = 2")
        col.db.execute("update col set ver = 5")
    if ver < 6:
        col.modSchema(check=False)
        import anki.models
        for model in col.models.all():
            model['css'] = anki.models.defaultModel['css']
            for template in model['tmpls']:
                if 'css' not in template:
                    # ankidroid didn't bump version
                    continue
                model['css'] += "\n" + template['css'].replace(
                    ".card ", ".card%d "%(template['ord']+1))
                del template['css']
            col.models.save(model)
        col.db.execute("update col set ver = 6")
    if ver < 7:
        col.modSchema(check=False)
        col.db.execute(
            "update cards set odue = 0 where (type = 1 or queue = 2) "
            "and not odid")
        col.db.execute("update col set ver = 7")
    if ver < 8:
        col.modSchema(check=False)
        col.db.execute(
            "update cards set due = due / 1000 where due > 4294967296")
        col.db.execute("update col set ver = 8")
    if ver < 9:
        # adding an empty file to a zip makes python's zip code think it's a
        # folder, so remove any empty files
        changed = False
        dir = col.media.dir()
        if dir:
            for file in os.listdir(col.media.dir()):
                if os.path.isfile(file) and not os.path.getsize(file):
                    os.unlink(file)
                    col.media.db.execute(
                        "delete from log where fname = ?", file)
                    col.media.db.execute(
                        "delete from media where fname = ?", file)
                    changed = True
            if changed:
                col.media.db.commit()
        col.db.execute("update col set ver = 9")
    if ver < 10:
        col.db.execute("""
update cards set left = left + left*1000 where queue = 1""")
        col.db.execute("update col set ver = 10")
    if ver < 11:
        col.modSchema(check=False)
        for deck in col.decks.all():
            if deck['dyn']:
                order = deck['order']
                # failed order was removed
                if order >= 5:
                    order -= 1
                deck['terms'] = [[deck['search'], deck['limit'], order]]
                del deck['search']
                del deck['limit']
                del deck['order']
                deck['resched'] = True
                deck['return'] = True
            else:
                if 'extendNew' not in deck:
                    deck['extendNew'] = 10
                    deck['extendRev'] = 50
            col.decks.save(deck)
        for conf in col.decks.allConf():
            rev = conf['rev']
            rev['ivlFct'] = rev.get("ivlfct", 1)
            if 'ivlfct' in rev:
                del rev['ivlfct']
            rev['maxIvl'] = 36500
            col.decks.save(conf)
        for model in col.models.all():
            for template in model['tmpls']:
                template['bqfmt'] = ''
                template['bafmt'] = ''
            col.models.save(model)
        col.db.execute("update col set ver = 11")

def _upgradeClozeModel(col, model):
    """Change from version 4 to 5 the model of cloze card"""
    model['type'] = MODEL_CLOZE
    # convert first template
    template = model['tmpls'][0]
    for type in 'qfmt', 'afmt':
        template[type] = re.sub("{{cloze:1:(.+?)}}", r"{{cloze:\1}}", template[type])
    template['name'] = _("Cloze")
    # delete non-cloze cards for the model
    rems = []
    for template in model['tmpls'][1:]:
        if "{{cloze:" not in template['qfmt']:
            rems.append(template)
    for rem in rems:
        col.models.remTemplate(model, rem)
    del model['tmpls'][1:]
    col.models._updateTemplOrds(model)
    col.models.save(model)

# Creating a new collection
######################################################################

def _createDB(db):
    db.execute("pragma page_size = 4096")
    db.execute("pragma legacy_file_format = 0")
    db.execute("vacuum")
    _addSchema(db)
    _updateIndices(db)
    db.execute("analyze")
    return SCHEMA_VERSION

def _addSchema(db, setColConf=True):
    db.executescript("""
create table if not exists col (
    id              integer primary key,
    crt             integer not null,
    mod             integer not null,
    scm             integer not null,
    ver             integer not null,
    dty             integer not null,
    usn             integer not null,
    ls              integer not null,
    conf            text not null,
    models          text not null,
    decks           text not null,
    dconf           text not null,
    tags            text not null
);

create table if not exists notes (
    id              integer primary key,   /* 0 */
    guid            text not null,         /* 1 */
    mid             integer not null,      /* 2 */
    mod             integer not null,      /* 3 */
    usn             integer not null,      /* 4 */
    tags            text not null,         /* 5 */
    flds            text not null,         /* 6 */
    sfld            integer not null,      /* 7 */
    csum            integer not null,      /* 8 */
    flags           integer not null,      /* 9 */
    data            text not null          /* 10 */
);

create table if not exists cards (
    id              integer primary key,   /* 0 */
    nid             integer not null,      /* 1 */
    did             integer not null,      /* 2 */
    ord             integer not null,      /* 3 */
    mod             integer not null,      /* 4 */
    usn             integer not null,      /* 5 */
    type            integer not null,      /* 6 */
    queue           integer not null,      /* 7 */
    due             integer not null,      /* 8 */
    ivl             integer not null,      /* 9 */
    factor          integer not null,      /* 10 */
    reps            integer not null,      /* 11 */
    lapses          integer not null,      /* 12 */
    left            integer not null,      /* 13 */
    odue            integer not null,      /* 14 */
    odid            integer not null,      /* 15 */
    flags           integer not null,      /* 16 */
    data            text not null          /* 17 */
);

create table if not exists revlog (
    id              integer primary key,
    cid             integer not null,
    usn             integer not null,
    ease            integer not null,
    ivl             integer not null,
    lastIvl         integer not null,
    factor          integer not null,
    time            integer not null,
    type            integer not null
);

create table if not exists graves (
    usn             integer not null,
    oid             integer not null,
    type            integer not null
);

insert or ignore into col
values(1,0,0,%(second)s,%(version)s,0,0,0,'','{}','','','{}');
""" % ({'version':SCHEMA_VERSION, 'second':intTime(1000)}))
    if setColConf:
        _addColVars(db, *_getColVars(db))

def _getColVars(db):
    import anki.collection
    import anki.decks
    deck = copy.deepcopy(anki.decks.defaultDeck)
    deck['id'] = 1
    deck['name'] = _("Default")
    deck['conf'] = 1
    deck['mod'] = intTime()
    gc = copy.deepcopy(anki.decks.defaultConf)
    gc['id'] = 1
    return deck, gc, anki.collection.defaultConf.copy()

def _addColVars(db, deck, gc, conf):
    db.execute("""
update col set conf = ?, decks = ?, dconf = ?""",
                   json.dumps(conf),
                   json.dumps({'1': deck}),
                   json.dumps({'1': gc}))

def _updateIndices(db):
    "Add indices to the DB."
    db.executescript("""
-- syncing
create index if not exists ix_notes_usn on notes (usn);
create index if not exists ix_cards_usn on cards (usn);
create index if not exists ix_revlog_usn on revlog (usn);
-- card spacing, etc
create index if not exists ix_cards_nid on cards (nid);
-- scheduling and deck limiting
create index if not exists ix_cards_sched on cards (did, queue, due);
-- revlog by card
create index if not exists ix_revlog_cid on revlog (cid);
-- field uniqueness
create index if not exists ix_notes_csum on notes (csum);
""")
