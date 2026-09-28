"""Consultas del panel: pedidos, usuarios y estadísticas."""
from __future__ import annotations

from app.core.errors import Forbidden, NotFound, ValidationError
from app.core.timeutil import iso_in, now_iso
from app.core.validation import search_normalize
from app.db import get_db
from app.services import loyalty_service


def list_orders(q: str, status: str | None, date_from: str | None, date_to: str | None, page: int, size: int):
    where, args = ["1=1"], []
    if q:
        term = f"%{q.strip().lower()[:80]}%"
        where.append("(LOWER(o.order_number) LIKE ? OR LOWER(o.customer_email) LIKE ? OR LOWER(o.customer_name) LIKE ?)")
        args += [term, term, term]
    if status:
        where.append("o.status = ?")
        args.append(status)
    if date_from:
        where.append("o.created_at >= ?")
        args.append(date_from)
    if date_to:
        where.append("o.created_at < ?")
        args.append(date_to + "T23:59:59.999999+00:00" if len(date_to) == 10 else date_to)
    w = " AND ".join(where)
    db = get_db()
    total = db.scalar(f"SELECT COUNT(*) AS n FROM orders o WHERE {w}", args)
    rows = db.all(
        f"""SELECT o.id, o.order_number, o.status, s.label AS status_label, o.total_cents, o.currency, o.payment_provider,
                   o.payment_status, o.customer_name, o.customer_email, o.shipping_method, o.created_at
            FROM orders o JOIN order_statuses s ON s.code = o.status WHERE {w}
            ORDER BY o.created_at DESC, o.id DESC LIMIT ? OFFSET ?""",
        [*args, size, (page - 1) * size],
    )
    return rows, total


def list_users(q: str, role: str | None, page: int, size: int):
    where, args = ["1=1"], []
    if q:
        term = f"%{search_normalize(q)[:80]}%"
        where.append("(LOWER(u.email) LIKE ? OR LOWER(u.first_name || ' ' || u.last_name) LIKE ? OR LOWER(u.public_id) LIKE ?)")
        args += [term, term, term]
    if role:
        where.append("r.code = ?")
        args.append(role)
    w = " AND ".join(where)
    db = get_db()
    total = db.scalar(f"SELECT COUNT(*) AS n FROM users u JOIN roles r ON r.id = u.role_id WHERE {w}", args)
    rows = db.all(
        f"""SELECT u.id, u.public_id, u.email, u.first_name, u.last_name, u.phone, u.is_active, u.created_at, u.last_login_at,
                   r.code AS role, r.name AS role_name, lc.points_balance, lc.card_number,
                   (SELECT COUNT(*) FROM orders o WHERE o.user_id = u.id) AS order_count
            FROM users u JOIN roles r ON r.id = u.role_id LEFT JOIN loyalty_cards lc ON lc.user_id = u.id
            WHERE {w} ORDER BY u.created_at DESC, u.id DESC LIMIT ? OFFSET ?""",
        [*args, size, (page - 1) * size],
    )
    for r in rows:
        r["is_active"] = bool(r["is_active"])
    return rows, total


def user_detail(user_id: int) -> dict:
    db = get_db()
    u = db.one(
        """SELECT u.id, u.public_id, u.email, u.first_name, u.last_name, u.phone, u.is_active, u.created_at,
                  u.last_login_at, r.code AS role, r.name AS role_name
           FROM users u JOIN roles r ON r.id = u.role_id WHERE u.id = ?""", (user_id,))
    if not u:
        raise NotFound("Usuario no encontrado.")
    u["is_active"] = bool(u["is_active"])
    u["loyalty"] = loyalty_service.card(user_id)
    u["orders"] = db.all(
        """SELECT o.id, o.order_number, o.status, o.total_cents, o.created_at FROM orders o
           WHERE o.user_id = ? ORDER BY o.created_at DESC LIMIT 20""", (user_id,))
    u["point_movements"], _ = loyalty_service.movements(user_id, 1, 20)
    u["addresses"] = db.all("SELECT recipient, line1, city, phone FROM addresses WHERE user_id = ?", (user_id,))
    return u


def update_user(actor: dict, user_id: int, data: dict) -> dict:
    db = get_db()
    target = db.one("SELECT u.id, r.code AS role FROM users u JOIN roles r ON r.id = u.role_id WHERE u.id = ?", (user_id,))
    if not target:
        raise NotFound("Usuario no encontrado.")
    if user_id == actor["id"] and ("role" in data or data.get("is_active") is False):
        raise Forbidden("No puedes cambiar tu propio rol ni desactivar tu cuenta.")
    with db.transaction():
        if "is_active" in data:
            db.execute("UPDATE users SET is_active = ?, updated_at = ? WHERE id = ?", (bool(data["is_active"]), now_iso(), user_id))
            if not data["is_active"]:
                db.execute("UPDATE sessions SET revoked_at = ? WHERE user_id = ? AND revoked_at IS NULL", (now_iso(), user_id))
        if "role" in data:
            role = db.one("SELECT id FROM roles WHERE code = ?", (data["role"],))
            if not role:
                raise ValidationError("Rol no válido.")
            db.execute("UPDATE users SET role_id = ?, updated_at = ? WHERE id = ?", (role["id"], now_iso(), user_id))
            db.execute("UPDATE sessions SET revoked_at = ? WHERE user_id = ? AND revoked_at IS NULL", (now_iso(), user_id))
    return user_detail(user_id)


def roles() -> list[dict]:
    db = get_db()
    out = db.all("SELECT id, code, name, is_staff FROM roles ORDER BY id")
    for r in out:
        r["is_staff"] = bool(r["is_staff"])
        r["permissions"] = [p["code"] for p in db.all(
            "SELECT p.code FROM permissions p JOIN role_permissions rp ON rp.permission_id = p.id WHERE rp.role_id = ?", (r["id"],))]
    return out


def stats(days: int = 30) -> dict:
    """Métricas base del panel. Sobre millones de pedidos conviene precalcular
    en una tabla de agregados diarios (ver docs/DECISIONS.md)."""
    db = get_db()
    since = iso_in(days=-days)
    valid = "status NOT IN ('cancelled')"
    sales = db.one(
        f"""SELECT COUNT(*) AS orders, COALESCE(SUM(total_cents), 0) AS revenue_cents,
                   COALESCE(SUM(points_used), 0) AS points_used, COALESCE(AVG(total_cents), 0) AS avg_ticket_cents
            FROM orders WHERE {valid} AND created_at >= ?""", (since,))
    sales["avg_ticket_cents"] = int(sales["avg_ticket_cents"] or 0)
    by_status = db.all("SELECT status, COUNT(*) AS n FROM orders WHERE created_at >= ? GROUP BY status", (since,))
    daily_rows = db.all(
        f"SELECT SUBSTR(CAST(created_at AS TEXT), 1, 10) AS day, COUNT(*) AS orders, COALESCE(SUM(total_cents), 0) AS revenue_cents "
        f"FROM orders WHERE {valid} AND created_at >= ? GROUP BY SUBSTR(CAST(created_at AS TEXT), 1, 10) ORDER BY day", (since,))
    top = db.all(
        f"""SELECT oi.product_name AS name, SUM(oi.quantity) AS units, SUM(oi.line_total_cents) AS revenue_cents
            FROM order_items oi JOIN orders o ON o.id = oi.order_id WHERE o.{valid} AND o.created_at >= ?
            GROUP BY oi.product_name ORDER BY units DESC LIMIT 5""", (since,))
    low = db.all(
        """SELECT id, name, sku, stock, low_stock_threshold FROM products
           WHERE status = 'active' AND stock <= low_stock_threshold ORDER BY stock ASC LIMIT 10""")
    return {
        "days": days,
        "sales": sales,
        "orders_by_status": by_status,
        "daily": daily_rows,
        "top_products": top,
        "low_stock": low,
        "new_users": db.scalar("SELECT COUNT(*) AS n FROM users WHERE created_at >= ?", (since,)),
        "total_users": db.scalar("SELECT COUNT(*) AS n FROM users"),
        "active_products": db.scalar("SELECT COUNT(*) AS n FROM products WHERE status = 'active'"),
        "points_outstanding": db.scalar("SELECT COALESCE(SUM(points_balance), 0) AS n FROM loyalty_cards"),
    }
