# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""
A convenience wrapper over pysqlite.

Anki's Collection class now uses dbproxy.py instead of this class,
but this class is still used by aqt's profile manager, and a number
of add-ons rely on it.
"""

import os
import pprint
import time
from sqlite3 import Cursor
from sqlite3 import dbapi2 as sqlite
from typing import Any, List, Type

DBError = sqlite.Error


class DB:
    def __init__(self, path: str, timeout: int = 0) -> None:
        self._db = sqlite.connect(path, timeout=timeout)
        self._db.text_factory = self._textFactory
        self._path = path
        self.echo = os.environ.get("DBECHO")
        self.mod = False

    def __repr__(self) -> str:
        d = dict(self.__dict__)
        del d["_db"]
        return f"{super().__repr__()} {pprint.pformat(d, width=300)}"

    def execute(self, sql: str, *args, **ka) -> Cursor:
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
            # print args, ka
            print(sql, "%0.3fms" % ((time.time() - startTime) * 1000))
            if self.echo == "2":
                print(args, ka)
        return res

    def executemany(self, sql: str, queryParams: Any) -> None:
        self.mod = True
        startTime = time.time()
        self._db.executemany(sql, queryParams)
        if self.echo:

            print(sql, "%0.3fms" % ((time.time() - startTime) * 1000))
            if self.echo == "2":
                print(queryParams)

    def commit(self) -> None:
        startTime = time.time()
        self._db.commit()
        if self.echo:
            print("commit %0.3fms" % ((time.time() - startTime) * 1000))

    def executescript(self, sql: str) -> None:
        self.mod = True
        if self.echo:
            print(sql)
        self._db.executescript(sql)

    def rollback(self) -> None:
        self._db.rollback()

    def scalar(self, *args, **kw) -> Any:
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

    def list(self, *args, **kw) -> List:
        return [returnedVector[0] for returnedVector in self.execute(*args, **kw)]

    def close(self) -> None:
        self._db.text_factory = None
        self._db.close()

    def set_progress_handler(self, *args) -> None:
        self._db.set_progress_handler(*args)

    def __enter__(self) -> "DB":
        self._db.execute("begin")
        return self

    def __exit__(self, exc_type, *args) -> None:
        self._db.close()

    def totalChanges(self) -> Any:
        return self._db.total_changes

    def interrupt(self) -> None:
        self._db.interrupt()

    def setAutocommit(self, autocommit: bool) -> None:
        if autocommit:
            self._db.isolation_level = None
        else:
            self._db.isolation_level = ""

    # strip out invalid utf-8 when reading from db
    def _textFactory(self, data: bytes) -> str:
        return str(data, errors="ignore")

    def cursor(self, factory: Type[Cursor] = Cursor) -> Cursor:
        return self._db.cursor(factory)
