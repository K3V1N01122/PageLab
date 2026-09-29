"""Usuarios: registro, login, recuperación de contraseña, perfil, direcciones."""
from __future__ import annotations

from flask import current_app

from app.core import auth
from app.core.errors import Conflict, NotFound, Unauthorized, ValidationError
from app.core.security import hash_password, human_code, new_token, token_hash, verify_password
from app.core.timeutil import iso_in, now, now_iso, parse
from app.db import IntegrityError, get_db
from app.services import notification_service


def public_user(u: dict) -> dict:
    return {
        "id": u["public_id"],
        "email": u["email"],
        "first_name": u["first_name"],
        "last_name": u["last_name"],
        "phone": u.get("phone"),
        "role": u.get("role"),
        "is_staff": bool(u.get("is_staff")),
        "permissions": sorted(u.get("permissions", [])) if u.get("is_staff") else [],
    }


def with_role(user_id: int) -> dict:
    db = get_db()
    u = db.one("""SELECT u.*, r.code AS role, r.is_staff FROM users u JOIN roles r ON r.id = u.role_id WHERE u.id = ?""", (user_id,))
    u["permissions"] = {r["code"] for r in db.all(
        "SELECT p.code FROM permissions p JOIN role_permissions rp ON rp.permission_id = p.id WHERE rp.role_id = ?", (u["role_id"],))}
    return u


def _new_public_id(db) -> str:
    for _ in range(10):
        pid = "C" + human_code(9)
        if not db.one("SELECT id FROM users WHERE public_id = ?", (pid,)):
            return pid
    raise RuntimeError("No se pudo generar un identificador único")


def create_loyalty_card(db, user_id: int) -> None:
    for _ in range(10):
        number = "-".join(human_code(4) for _ in range(3))
        try:
            with db.transaction():
                db.insert(
                    """INSERT INTO loyalty_cards (user_id, card_number, created_at, updated_at) VALUES (?, ?, ?, ?)""",
                    (user_id, number, now_iso(), now_iso()),
                )
            return
        except IntegrityError:
            if db.one("SELECT id FROM loyalty_cards WHERE user_id = ?", (user_id,)):
                return
    raise RuntimeError("No se pudo generar la tarjeta de fidelidad")


def register(data: dict, role_code: str = "customer") -> dict:
    db = get_db()
    role_id = db.scalar("SELECT id FROM roles WHERE code = ?", (role_code,))
    if role_id is None:
        raise ValidationError("Rol no válido.")
    try:
        with db.transaction():
            user_id = db.insert(
                """INSERT INTO users (public_id, email, password_hash, first_name, last_name, phone, role_id,
                                      accepted_terms_at, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (_new_public_id(db), data["email"], hash_password(data["password"]), data["first_name"],
                 data["last_name"], data.get("phone"), role_id, now_iso(), now_iso(), now_iso()),
            )
            # Cada cliente recibe su tarjeta virtual al registrarse.
            create_loyalty_card(db, user_id)
    except IntegrityError:
        raise Conflict("Ya existe una cuenta con ese correo.", code="email_taken")
    return db.one("SELECT * FROM users WHERE id = ?", (user_id,))


def authenticate(email: str, password: str) -> dict:
    """Login con bloqueo temporal tras varios intentos fallidos."""
    cfg = current_app.config
    db = get_db()
    user = db.one("SELECT * FROM users WHERE email = ?", (email.lower(),))
    generic = Unauthorized("Correo o contraseña incorrectos.", code="invalid_credentials")
    if user and user["locked_until"] and parse(user["locked_until"]) > now():
        raise Unauthorized(
            "Demasiados intentos fallidos. Intenta de nuevo en unos minutos o recupera tu contraseña.",
            code="account_locked",
        )
    if not verify_password(user["password_hash"] if user else None, password):
        if user:
            failures = user["failed_logins"] + 1
            locked = iso_in(minutes=cfg["LOGIN_LOCK_MINUTES"]) if failures >= cfg["LOGIN_MAX_FAILURES"] else None
            db.execute(
                "UPDATE users SET failed_logins = ?, locked_until = ? WHERE id = ?",
                (0 if locked else failures, locked, user["id"]),
            )
        raise generic
    if not user["is_active"]:
        raise Unauthorized("Esta cuenta está desactivada. Contacta a la tienda.", code="account_disabled")
    db.execute(
        "UPDATE users SET failed_logins = 0, locked_until = NULL, last_login_at = ? WHERE id = ?",
        (now_iso(), user["id"]),
    )
    return user


def request_password_reset(email: str) -> None:
    """Siempre responde igual exista o no la cuenta (no revela correos)."""
    db = get_db()
    user = db.one("SELECT id, email, first_name FROM users WHERE email = ? AND is_active = TRUE", (email.lower(),))
    if not user:
        return
    token = new_token()
    db.insert(
        "INSERT INTO password_resets (user_id, token_hash, expires_at, created_at) VALUES (?, ?, ?, ?)",
        (user["id"], token_hash(token), iso_in(hours=1), now_iso()),
    )
    link = f"{current_app.config['PUBLIC_BASE_URL']}/restablecer-contrasena?token={token}"
    notification_service.notify_password_reset(user["email"], user["first_name"], link)


def reset_password(token: str, new_password: str) -> None:
    db = get_db()
    with db.transaction():
        row = db.one(
            "SELECT id, user_id, expires_at, used_at FROM password_resets WHERE token_hash = ?",
            (token_hash(token or ""),),
        )
        if not row or row["used_at"] or parse(row["expires_at"]) <= now():
            raise ValidationError("El enlace no es válido o ya expiró. Solicita uno nuevo.", code="invalid_token")
        db.execute("UPDATE password_resets SET used_at = ? WHERE id = ?", (now_iso(), row["id"]))
        db.execute(
            "UPDATE users SET password_hash = ?, failed_logins = 0, locked_until = NULL, updated_at = ? WHERE id = ?",
            (hash_password(new_password), now_iso(), row["user_id"]),
        )
        auth.revoke_all_sessions(row["user_id"])


def change_password(user_id: int, current: str, new: str, keep_session_id: int) -> None:
    db = get_db()
    user = db.one("SELECT password_hash FROM users WHERE id = ?", (user_id,))
    if not verify_password(user["password_hash"], current):
        raise ValidationError("La contraseña actual no es correcta.", details={"current_password": "Incorrecta."})
    with db.transaction():
        db.execute("UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?", (hash_password(new), now_iso(), user_id))
        auth.revoke_all_sessions(user_id, except_id=keep_session_id)


def update_profile(user_id: int, data: dict) -> None:
    get_db().execute(
        "UPDATE users SET first_name = ?, last_name = ?, phone = ?, updated_at = ? WHERE id = ?",
        (data["first_name"], data["last_name"], data.get("phone"), now_iso(), user_id),
    )


# ------------------------------------------------------------ direcciones
ADDRESS_FIELDS = ["label", "recipient", "phone", "line1", "line2", "city", "state", "postal_code", "country", "notes"]


def list_addresses(user_id: int) -> list[dict]:
    rows = get_db().all(
        f"SELECT id, {', '.join(ADDRESS_FIELDS)}, is_default FROM addresses WHERE user_id = ? ORDER BY is_default DESC, id DESC",
        (user_id,),
    )
    for r in rows:
        r["is_default"] = bool(r["is_default"])
    return rows


def save_address(user_id: int, data: dict, address_id: int | None = None) -> int:
    db = get_db()
    with db.transaction():
        count = db.scalar("SELECT COUNT(*) AS n FROM addresses WHERE user_id = ?", (user_id,))
        make_default = data.get("is_default") or count == 0
        if make_default:
            db.execute("UPDATE addresses SET is_default = FALSE WHERE user_id = ?", (user_id,))
        values = [data.get(f) for f in ADDRESS_FIELDS]
        if address_id:
            updated = db.execute(
                f"UPDATE addresses SET {', '.join(f + ' = ?' for f in ADDRESS_FIELDS)}, is_default = ?, updated_at = ? "
                "WHERE id = ? AND user_id = ?",
                (*values, bool(make_default), now_iso(), address_id, user_id),
            )
            if not updated:
                raise NotFound("Dirección no encontrada.")
            return address_id
        if count >= 20:
            raise ValidationError("Puedes guardar hasta 20 direcciones.")
        return db.insert(
            f"INSERT INTO addresses (user_id, {', '.join(ADDRESS_FIELDS)}, is_default, created_at, updated_at) "
            f"VALUES (?, {', '.join('?' * len(ADDRESS_FIELDS))}, ?, ?, ?)",
            (user_id, *values, bool(make_default), now_iso(), now_iso()),
        )


def delete_address(user_id: int, address_id: int) -> None:
    if not get_db().execute("DELETE FROM addresses WHERE id = ? AND user_id = ?", (address_id, user_id)):
        raise NotFound("Dirección no encontrada.")


# ------------------------------------------------------------ favoritos
def list_favorite_ids(user_id: int) -> list[int]:
    return [r["product_id"] for r in get_db().all(
        "SELECT product_id FROM favorites WHERE user_id = ? ORDER BY created_at DESC", (user_id,))]


def add_favorite(user_id: int, product_id: int) -> None:
    db = get_db()
    if not db.one("SELECT id FROM products WHERE id = ? AND status = 'active'", (product_id,)):
        raise NotFound("Producto no encontrado.")
    try:
        db.execute("INSERT INTO favorites (user_id, product_id, created_at) VALUES (?, ?, ?)", (user_id, product_id, now_iso()))
    except IntegrityError:
        pass  # ya estaba en favoritos: operación idempotente


def remove_favorite(user_id: int, product_id: int) -> None:
    get_db().execute("DELETE FROM favorites WHERE user_id = ? AND product_id = ?", (user_id, product_id))
