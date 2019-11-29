# -*- coding: utf-8 -*-
# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""
Anki maintains a cache of used tags so it can quickly present a list of tags
for autocomplete and in the browser. For efficiency, deletions are not
tracked, so unused tags can only be removed from the list with a DB check.

This module manages the tag cache and tags for notes.
"""

import json
import re

from anki.hooks import runHook
from anki.utils import ids2str, intTime


class TagManager:

    # Registry save/load
    #############################################################

    def __init__(self, col):
        self.col = col

    def load(self, json_):
        self.tags = json.loads(json_)
        self.changed = False

    def flush(self):
        if self.changed:
            self.col.db.execute("update col set tags=?",
                                 json.dumps(self.tags))
            self.changed = False

    # Registering and fetching tags
    #############################################################

    def register(self, tags, usn=None):
        """Given a list/set of tags, add any tag missing in the registry to
        the registry. If there is such a new tag, call the hook
        newTag.

        """
        found = False
        for tag in tags:
            if tag not in self.tags:
                found = True
                self.tags[tag] = self.col.usn() if usn is None else usn
                self.changed = True
        if found:
            runHook("newTag")

    def all(self):
        return list(self.tags.keys())

    def registerNotes(self, nids=None):
        "Add any missing tags from notes to the tags list."
        # when called without an argument, the old list is cleared first.
        if nids:
            lim = " where id in " + ids2str(nids)
        else:
            lim = ""
            self.tags = {}
            self.changed = True
        self.register(set(self.split(
            " ".join(self.col.db.list("select distinct tags from notes"+lim)))))

    def allItems(self):
        return list(self.tags.items())

    def save(self):
        self.changed = True

    def byDeck(self, did, children=False):
        basequery = "select note.tags from cards card, notes note WHERE card.nid = note.id"
        if not children:
            query = basequery + " AND card.did=?"
            res = self.col.db.list(query, did)
            return list(set(self.split(" ".join(res))))
        dids = [did] + [id for name, id in self.col.decks.children(did)]
        query = basequery + " AND card.did IN " + ids2str(dids)
        res = self.col.db.list(query)
        return list(set(self.split(" ".join(res))))

    # Bulk addition/removal from notes
    #############################################################

    def bulkAdd(self, ids, tags, add=True):
        """Add tags in bulk. TAGS is space-separated.

        keyword arguments
        ids -- a list of id
        tags -- a string of space-separated tag
        add -- whether to add (True) or to remove (False)
        """
        newTags = self.split(tags)
        if not newTags:
            return
        # cache tag names
        if add:
            self.register(newTags)
        # find notes missing the tags
        if add:
            tagsRequirement = "tags not "
            fn = self.addToStr
        else:
            tagsRequirement = "tags "
            fn = self.remFromStr
        lim = " or ".join(
            [tagsRequirement+"like :_%d" % card for card, tag in enumerate(newTags)])
        res = self.col.db.all(
            "select id, tags from notes where id in %s and (%s)" % (
                ids2str(ids), lim),
            f"""select id, tags from notes where id in
            {ids2str(ids)} and ({lim})""" ,
            **dict([("_%d" % tagIndex, '%% %s %%' % tag.replace('*', '%'))
                    for tagIndex, tag in enumerate(newTags)]))
        # update tags
        nids = []
        def fix(row):
            nids.append(row[0])
            return {'id': row[0], 'tags': fn(tags, row[1]), 'mod':intTime(),
                'usn':self.col.usn()}
        self.col.db.executemany(
            "update notes set tags=:tags,mod=:mod,usn=:usn where id = :id",
            [fix(row) for row in res])

    def bulkRem(self, ids, tags):
        self.bulkAdd(ids, tags, False)

    # String-based utilities
    ##########################################################################

    def split(self, tags):
        "Parse a string and return a list of tags."
        return [tag for tag in tags.replace('\u3000', ' ').split(" ") if tag]

    def join(self, tags):
        """Join tags into a single string, separated by whitespace, with leading
and trailing spaces."""
        if not tags:
            return ""
        return " %s " % " ".join(tags)

    def addToStr(self, addtags, tags):
        "Add tags if they don't exist, and canonify."
        currentTags = self.split(tags)
        for tag in self.split(addtags):
            if not self.inList(tag, currentTags):
                currentTags.append(tag)
        canonified = self.canonify(currentTags)
        return self.join(canonified)

    def remFromStr(self, deltags, tags):
        "Delete tags if they exist."
        def wildcard(pat, str):
            pat = re.escape(pat).replace('\\*', '.*')
            return re.match("^"+pat+"$", str, re.IGNORECASE)
        currentTags = self.split(tags)
        for tag in self.split(deltags):
            # find tags, ignoring case
            removes = [tx for tx in currentTags
                       if (tag.lower() == tx.lower()) or wildcard(tag, tx)]
            # removes them
            for remove in removes:
                currentTags.remove(remove)
        return self.join(currentTags)

    # List-based utilities
    ##########################################################################

    def canonify(self, tagList):
        "Strip duplicates, adjust case to match existing tags, and sort."
        strippedTags = []
        for tag in tagList:
            tag = re.sub("[\"']", "", tag)
            for existingTag in self.tags:
                if tag.lower() == existingTag.lower():
                    tag = existingTag
            strippedTags.append(tag)
        return sorted(set(strippedTags))

    def inList(self, tag, tags):
        """Whether tag is in tags. Ignore case."""
        return tag.lower() in [tag.lower() for tag in tags]

    # Sync handling
    ##########################################################################

    def beforeUpload(self):
        for key in list(self.tags.keys()):
            self.tags[key] = 0
        self.save()
