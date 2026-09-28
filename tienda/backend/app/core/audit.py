from flask import g

from app.core.jsonutil import dump_json
from app.core.request_ctx import client_ip
from app.core.timeutil import now_iso
from app.db import get_db


def audit(action: str, entity: str | None = None, entity_id: int | None = None, data: dict | None = None) -> None:
    """Registro de acciones administrativas y de seguridad."""
    user = g.get("user")
    get_db().insert(
        "INSERT INTO audit_log (user_id, action, entity, entity_id, data, ip, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (user["id"] if user else None, action, entity, entity_id, dump_json(data), client_ip(), now_iso()),
    )
