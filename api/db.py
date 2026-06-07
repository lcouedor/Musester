import os
import sqlite3
from contextlib import contextmanager

DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL:
    import psycopg2
    import psycopg2.extras

    PH = "%s"

    class _PgConn:
        """Expose une interface sqlite3-like (conn.execute()) sur une connexion psycopg2."""
        def __init__(self, raw):
            self._raw = raw
            self._cur = raw.cursor()

        def execute(self, sql, params=()):
            self._cur.execute(sql, params or ())
            return self._cur

    @contextmanager
    def db_conn(path=None):
        raw = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
        conn = _PgConn(raw)
        try:
            yield conn
            raw.commit()
        except Exception:
            raw.rollback()
            raise
        finally:
            raw.close()

else:
    PH = "?"

    @contextmanager
    def db_conn(path: str):
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        with conn:
            yield conn
