"""Rate limiting con ventanas fijas guardadas en la base de datos.

Funciona con varias instancias del backend porque el contador es compartido.
Con mucho tráfico conviene cambiar el backend a Redis: basta con reimplementar
`_hit` (ver docs/DECISIONS.md).
"""
import random
import time
from functools import wraps

from flask import current_app, g

from app.core.errors import TooManyRequests
from app.core.request_ctx import client_ip
from app.db import get_db


def parse_spec(spec: str) -> tuple[int, int]:
    limit, seconds = spec.split("/")
    return int(limit), int(seconds)


def _hit(bucket: str, window_seconds: int) -> int:
    window = int(time.time()) // window_seconds * window_seconds
    db = get_db()
    row = db.one(
        """INSERT INTO rate_limits (bucket, window_start, hits) VALUES (?, ?, 1)
           ON CONFLICT (bucket, window_start) DO UPDATE SET hits = rate_limits.hits + 1
           RETURNING hits""",
        (bucket, window),
    )
    if random.random() < 0.01:  # limpieza ocasional
        db.execute("DELETE FROM rate_limits WHERE window_start < ?", (int(time.time()) - 3600,))
    return row["hits"]


def check(name: str, spec: str, key: str | None = None) -> None:
    if not current_app.config.get("RATE_LIMIT_ENABLED"):
        return
    limit, seconds = parse_spec(spec)
    ident = key or (f"u{g.user['id']}" if g.get("user") else client_ip())
    if _hit(f"{name}:{ident}", seconds) > limit:
        raise TooManyRequests("Demasiadas solicitudes. Espera un momento e inténtalo de nuevo.")


def limit(name: str, config_key: str):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            check(name, current_app.config[config_key])
            return fn(*args, **kwargs)
        return wrapper
    return decorator
