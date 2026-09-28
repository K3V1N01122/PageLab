import json


def load_json(value, default=None):
    """Las columnas JSON llegan como str (SQLite) o ya decodificadas (PostgreSQL)."""
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


def dump_json(value) -> str | None:
    return None if value is None else json.dumps(value, ensure_ascii=False)
