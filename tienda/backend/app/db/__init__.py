"""Acceso a base de datos.

Adaptador delgado sobre sqlite3 (desarrollo/pruebas) y psycopg 3 (producción,
PostgreSQL). Todo el SQL del proyecto usa parámetros `?` y se traduce a `%s`
para PostgreSQL. Nunca se concatenan valores en el SQL: así se evita SQL
injection por diseño.

Decisión: no se usa un ORM para mantener dependencias mínimas y SQL explícito
en las operaciones críticas (stock, puntos, pagos), donde importa controlar
exactamente qué sentencia se ejecuta y con qué bloqueo.
"""
from __future__ import annotations

import re
import sqlite3
import threading
from contextlib import contextmanager
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Iterable, Iterator

from flask import current_app, g

_PARAM_RE = re.compile(r"\?")


class IntegrityError(Exception):
    """Violación de restricción única / clave foránea, independiente del motor."""


def _normalize(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    return value


class Connection:
    def __init__(self, raw, dialect: str):
        self.raw = raw
        self.dialect = dialect
        self._depth = 0

    # -- utilidades -------------------------------------------------------
    def _sql(self, sql: str) -> str:
        if self.dialect == "postgres":
            # psycopg usa % para parámetros: un % literal (p. ej. en un comentario
            # SQL) debe escaparse como %% antes de convertir ? en %s.
            return _PARAM_RE.sub("%s", sql.replace("%", "%%"))
        return sql

    def _cursor(self, sql: str, params: Iterable[Any] = ()):
        cur = self.raw.cursor()
        try:
            cur.execute(self._sql(sql), tuple(params))
        except sqlite3.IntegrityError as exc:
            raise IntegrityError(str(exc)) from exc
        except Exception as exc:  # psycopg
            if exc.__class__.__name__ in {"UniqueViolation", "ForeignKeyViolation", "IntegrityError", "CheckViolation"}:
                raise IntegrityError(str(exc)) from exc
            raise
        return cur

    @staticmethod
    def _rows(cur) -> list[dict]:
        if cur.description is None:
            return []
        cols = [c[0] for c in cur.description]
        return [{k: _normalize(v) for k, v in zip(cols, row)} for row in cur.fetchall()]

    # -- API pública -----------------------------------------------------
    def execute(self, sql: str, params: Iterable[Any] = ()) -> int:
        """Ejecuta y devuelve filas afectadas (rowcount)."""
        cur = self._cursor(sql, params)
        return cur.rowcount

    def all(self, sql: str, params: Iterable[Any] = ()) -> list[dict]:
        return self._rows(self._cursor(sql, params))

    def one(self, sql: str, params: Iterable[Any] = ()) -> dict | None:
        rows = self.all(sql, params)
        return rows[0] if rows else None

    def scalar(self, sql: str, params: Iterable[Any] = ()) -> Any:
        row = self.one(sql, params)
        return next(iter(row.values())) if row else None

    def insert(self, sql: str, params: Iterable[Any] = ()) -> int:
        """INSERT ... RETURNING id (soportado por SQLite >= 3.35 y PostgreSQL)."""
        if "returning" not in sql.lower():
            sql = f"{sql} RETURNING id"
        row = self.one(sql, params)
        return row["id"]

    @contextmanager
    def transaction(self) -> Iterator["Connection"]:
        """Transacción anidable. En SQLite toma el bloqueo de escritura al inicio
        (BEGIN IMMEDIATE) para evitar deadlocks entre lectores que luego escriben."""
        if self._depth == 0:
            if self.dialect == "sqlite":
                self.raw.execute("BEGIN IMMEDIATE")
            else:
                self.raw.execute("BEGIN")
        else:
            self.raw.execute(f"SAVEPOINT sp_{self._depth}")
        self._depth += 1
        try:
            yield self
        except BaseException:
            self._depth -= 1
            if self._depth == 0:
                self.raw.execute("ROLLBACK")
            else:
                self.raw.execute(f"ROLLBACK TO SAVEPOINT sp_{self._depth}")
            raise
        else:
            self._depth -= 1
            if self._depth == 0:
                self.raw.execute("COMMIT")
            else:
                self.raw.execute(f"RELEASE SAVEPOINT sp_{self._depth}")

    def close(self) -> None:
        try:
            self.raw.close()
        except Exception:  # pragma: no cover
            pass


class Database:
    """Fábrica de conexiones a partir de DATABASE_URL."""

    def __init__(self, url: str):
        self.url = url
        if url.startswith("sqlite:///"):
            self.dialect = "sqlite"
            self.path = url[len("sqlite:///"):]
        elif url.startswith(("postgresql://", "postgres://")):
            self.dialect = "postgres"
            self.path = url
        else:
            raise RuntimeError("DATABASE_URL no soportada. Use sqlite:///ruta o postgresql://...")
        # :memory: compartido entre hilos para pruebas
        self._memory_uri = None
        self._keeper = None
        self._lock = threading.Lock()
        if self.dialect == "sqlite" and self.path == ":memory:":
            self._memory_uri = f"file:memdb_{id(self)}?mode=memory&cache=shared"
            self._keeper = self._raw_sqlite()

    def _raw_sqlite(self):
        target = self._memory_uri or self.path
        conn = sqlite3.connect(
            target, uri=bool(self._memory_uri), timeout=15, isolation_level=None,
            check_same_thread=False,
        )
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 15000")
        if not self._memory_uri:
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA synchronous = NORMAL")
        return conn

    def connect(self) -> Connection:
        if self.dialect == "sqlite":
            return Connection(self._raw_sqlite(), "sqlite")
        import psycopg  # dependencia solo necesaria en producción

        raw = psycopg.connect(self.path, autocommit=True)
        return Connection(raw, "postgres")


def init_app(app) -> None:
    app.extensions["db"] = Database(app.config["DATABASE_URL"])

    @app.teardown_appcontext
    def _close(_exc):
        conn = g.pop("db_conn", None)
        if conn is not None:
            conn.close()


def get_db() -> Connection:
    if "db_conn" not in g:
        g.db_conn = current_app.extensions["db"].connect()
    return g.db_conn
