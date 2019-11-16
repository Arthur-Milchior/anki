# -*- coding: utf-8 -*-
# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

import os
import time
from sqlite3 import Cursor
from sqlite3 import dbapi2 as sqlite

DBError = sqlite.Error

class DB:
    def __init__(self, path, timeout=0):
        self._db = sqlite.connect(path, timeout=timeout)
        self._db.text_factory = self._textFactory
        self._path = path
        self.echo = os.environ.get("DBECHO")
        self.mod = False

    def execute(self, sql, *args, **ka):
        normalizedSql = sql.strip().lower()
        # mark modified?
        for stmt in "insert", "update", "delete":
            if normalizedSql.startswith(stmt):
                self.mod = True
        startTime = time.time()
        if ka:
            # execute("...where id = :id", id=5)
            res = self._db.execute(sql, ka)
        else:
            # execute("...where id = ?", 5)
            res = self._db.execute(sql, args)
        if self.echo:
            #print args, ka
            print(sql, "%0.3fms" % ((time.time() - startTime)*1000))
            if self.echo == "2":
                print(args, ka)
        return res

    def executemany(self, sql, queryParams):
        self.mod = True
        startTime = time.time()
        self._db.executemany(sql, queryParams)
        if self.echo:
            print(sql, "%0.3fms" % ((time.time() - startTime)*1000))
            if self.echo == "2":
                print(queryParams)

    def commit(self):
        startTime = time.time()
        self._db.commit()
        if self.echo:
            print("commit %0.3fms" % ((time.time() - startTime)*1000))

    def executescript(self, sql):
        self.mod = True
        if self.echo:
            print(sql)
        self._db.executescript(sql)

    def rollback(self):
        self._db.rollback()

    def scalar(self, *args, **kw):
        res = self.execute(*args, **kw).fetchone()
        if res:
            return res[0]
        return None

    def all(self, *args, **kw):
        return self.execute(*args, **kw).fetchall()

    def first(self, *args, **kw):
        cursor = self.execute(*args, **kw)
        res = cursor.fetchone()
        cursor.close()
        return res

    def list(self, *args, **kw):
        return [returnedVector[0] for returnedVector in self.execute(*args, **kw)]

    def close(self):
        self._db.text_factory = None
        self._db.close()

    def set_progress_handler(self, *args):
        self._db.set_progress_handler(*args)

    def __enter__(self):
        self._db.execute("begin")
        return self

    def __exit__(self, exc_type, *args):
        self._db.close()

    def totalChanges(self):
        return self._db.total_changes

    def interrupt(self):
        self._db.interrupt()

    def setAutocommit(self, autocommit):
        if autocommit:
            self._db.isolation_level = None
        else:
            self._db.isolation_level = ''

    # strip out invalid utf-8 when reading from db
    def _textFactory(self, data):
        return str(data, errors="ignore")

    def cursor(self, factory=Cursor):
        return self._db.cursor(factory)
