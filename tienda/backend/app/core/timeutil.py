"""Fechas siempre en UTC e ISO-8601."""
from datetime import datetime, timedelta, timezone


def now() -> datetime:
    return datetime.now(timezone.utc)


def now_iso() -> str:
    return now().isoformat()


def iso_in(**delta) -> str:
    return (now() + timedelta(**delta)).isoformat()


def parse(value) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def is_past(value) -> bool:
    dt = parse(value)
    return dt is not None and dt <= now()
