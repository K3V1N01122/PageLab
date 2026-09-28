"""Autenticación por sesiones opacas y autorización por permisos.

- El token de sesión es aleatorio (256 bits); en la BD solo se guarda su hash.
- Navegador: cookie HttpOnly + SameSite=Lax (+ Secure en producción).
- Apps móviles / integraciones futuras: mismo token vía `Authorization: Bearer`.
- Los permisos se validan SIEMPRE en el backend (decoradores de abajo).
"""
from __future__ import annotations

from functools import wraps

from flask import current_app, g, request

from app.core.errors import Forbidden, Unauthorized
from app.core.request_ctx import client_ip
from app.core.security import new_token, token_hash
from app.core.timeutil import iso_in, now, now_iso, parse
from app.db import get_db

TOUCH_INTERVAL_SECONDS = 300


def _extract_token() -> tuple[str | None, str]:
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        return header[7:].strip() or None, "bearer"
    return request.cookies.get(current_app.config["SESSION_COOKIE_NAME"]), "cookie"


def load_current_user() -> None:
    g.user = None
    g.session = None
    g.auth_via = None
    token, via = _extract_token()
    if not token or len(token) > 200:
        return
    db = get_db()
    row = db.one(
        """SELECT s.id AS session_id, s.expires_at, s.last_seen_at, s.persistent,
                  u.id, u.public_id, u.email, u.first_name, u.last_name, u.phone,
                  u.is_active, r.code AS role, r.is_staff
           FROM sessions s JOIN users u ON u.id = s.user_id JOIN roles r ON r.id = u.role_id
           WHERE s.token_hash = ? AND s.revoked_at IS NULL""",
        (token_hash(token),),
    )
    if not row or not row["is_active"] or parse(row["expires_at"]) <= now():
        return
    perms = {
        r["code"] for r in db.all(
            """SELECT p.code FROM permissions p JOIN role_permissions rp ON rp.permission_id = p.id
               JOIN roles r ON r.id = rp.role_id WHERE r.code = ?""",
            (row["role"],),
        )
    }
    row["permissions"] = perms
    row["is_staff"] = bool(row["is_staff"])
    g.user = row
    g.session = {"id": row["session_id"], "token": token}
    g.auth_via = via
    last_seen = parse(row["last_seen_at"])
    if (now() - last_seen).total_seconds() > TOUCH_INTERVAL_SECONDS:
        db.execute("UPDATE sessions SET last_seen_at = ? WHERE id = ?", (now_iso(), row["session_id"]))


def create_session(user_id: int, remember: bool) -> tuple[str, int]:
    cfg = current_app.config
    token = new_token()
    ttl = {"days": cfg["SESSION_REMEMBER_DAYS"]} if remember else {"hours": cfg["SESSION_HOURS"]}
    get_db().insert(
        """INSERT INTO sessions (token_hash, user_id, persistent, ip, user_agent, created_at, last_seen_at, expires_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (token_hash(token), user_id, remember, client_ip(), (request.user_agent.string or "")[:300],
         now_iso(), now_iso(), iso_in(**ttl)),
    )
    max_age = int(cfg["SESSION_REMEMBER_DAYS"] * 86400) if remember else None
    return token, max_age


def revoke_session(session_id: int) -> None:
    get_db().execute("UPDATE sessions SET revoked_at = ? WHERE id = ?", (now_iso(), session_id))


def revoke_all_sessions(user_id: int, except_id: int | None = None) -> None:
    get_db().execute(
        "UPDATE sessions SET revoked_at = ? WHERE user_id = ? AND revoked_at IS NULL AND id <> ?",
        (now_iso(), user_id, except_id or 0),
    )


def set_session_cookie(response, token: str, max_age: int | None):
    cfg = current_app.config
    response.set_cookie(
        cfg["SESSION_COOKIE_NAME"], token, max_age=max_age, httponly=True,
        secure=cfg["SESSION_COOKIE_SECURE"], samesite="Lax", path="/",
    )


def clear_session_cookie(response):
    response.delete_cookie(current_app.config["SESSION_COOKIE_NAME"], path="/")


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not g.get("user"):
            raise Unauthorized("Inicia sesión para continuar.")
        return fn(*args, **kwargs)
    return wrapper


def permission_required(*perms: str):
    """Exige todos los permisos indicados. Ocultar botones en el frontend es
    solo comodidad; la protección real está aquí."""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            user = g.get("user")
            if not user:
                raise Unauthorized("Inicia sesión para continuar.")
            if not user["is_staff"] or not set(perms).issubset(user["permissions"]):
                raise Forbidden("No tienes permiso para realizar esta acción.")
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def staff_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = g.get("user")
        if not user:
            raise Unauthorized("Inicia sesión para continuar.")
        if not user["is_staff"]:
            raise Forbidden("No tienes acceso al panel de administración.")
        return fn(*args, **kwargs)
    return wrapper
