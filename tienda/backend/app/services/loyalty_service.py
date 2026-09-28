"""Puntos de fidelidad.

Reglas de integridad:
- Cada cambio de saldo va acompañado de un movimiento en `point_movements`
  dentro de la MISMA transacción (el historial siempre cuadra con el saldo).
- Los descuentos de saldo usan UPDATE condicional (`points_balance >= n`), así
  dos operaciones simultáneas nunca dejan el saldo en negativo.
- Los puntos de una compra nacen "pendientes" y pasan a "disponibles" cuando el
  pedido llega al estado configurado (por defecto: entregado).
"""
from __future__ import annotations

from app.core.errors import Conflict, NotFound, ValidationError
from app.core.timeutil import now_iso
from app.db import get_db
from app.services import settings_service


def card(user_id: int) -> dict:
    db = get_db()
    row = db.one(
        """SELECT lc.card_number, lc.points_balance, lc.points_pending, lc.lifetime_points, lc.tier, lc.created_at,
                  u.first_name, u.last_name, u.public_id
           FROM loyalty_cards lc JOIN users u ON u.id = lc.user_id WHERE lc.user_id = ?""",
        (user_id,),
    )
    if not row:
        # Cuentas creadas antes del programa: se crea la tarjeta al vuelo.
        from app.services.user_service import create_loyalty_card
        create_loyalty_card(db, user_id)
        return card(user_id)
    loyalty = settings_service.get("loyalty")
    used = db.scalar(
        "SELECT COALESCE(SUM(-points), 0) AS n FROM point_movements WHERE user_id = ? AND kind IN ('spend','redeem') AND status = 'posted'",
        (user_id,),
    ) or 0
    refunded = db.scalar(
        "SELECT COALESCE(SUM(points), 0) AS n FROM point_movements WHERE user_id = ? AND kind = 'refund' AND status = 'posted'",
        (user_id,),
    ) or 0
    return {
        "customer_name": f"{row['first_name']} {row['last_name']}",
        "customer_id": row["public_id"],
        "card_number": row["card_number"],
        "points_available": row["points_balance"],
        "points_pending": row["points_pending"],
        "points_earned": row["lifetime_points"],
        "points_used": max(0, used - refunded),
        "tier": row["tier"],
        "member_since": row["created_at"],
        "program_name": loyalty.get("program_name"),
        "redeem_rule": {
            "points": loyalty["redeem_block_points"],
            "value_cents": loyalty["redeem_block_value_cents"],
        },
        "earn_rule": {"points_per_currency_unit": loyalty["points_per_currency_unit"]},
    }


def balance(user_id: int) -> int:
    return get_db().scalar("SELECT points_balance FROM loyalty_cards WHERE user_id = ?", (user_id,)) or 0


def movements(user_id: int, page: int, size: int) -> tuple[list[dict], int]:
    db = get_db()
    total = db.scalar("SELECT COUNT(*) AS n FROM point_movements WHERE user_id = ?", (user_id,))
    rows = db.all(
        """SELECT pm.id, pm.kind, pm.points, pm.status, pm.description, pm.created_at, o.order_number
           FROM point_movements pm LEFT JOIN orders o ON o.id = pm.order_id
           WHERE pm.user_id = ? ORDER BY pm.created_at DESC, pm.id DESC LIMIT ? OFFSET ?""",
        (user_id, size, (page - 1) * size),
    )
    return rows, total


def _movement(db, user_id, kind, points, status, description, order_id=None, redemption_id=None, created_by=None):
    return db.insert(
        """INSERT INTO point_movements (user_id, kind, points, status, description, order_id, redemption_id, created_by, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (user_id, kind, points, status, description, order_id, redemption_id, created_by, now_iso()),
    )


def debit(db, user_id: int, points: int, kind: str, description: str, *, order_id=None, redemption_id=None) -> None:
    if points <= 0:
        return
    ok = db.execute(
        "UPDATE loyalty_cards SET points_balance = points_balance - ?, updated_at = ? WHERE user_id = ? AND points_balance >= ?",
        (points, now_iso(), user_id, points),
    )
    if not ok:
        raise Conflict("No tienes suficientes puntos para esta operación.", code="insufficient_points")
    _movement(db, user_id, kind, -points, "posted", description, order_id, redemption_id)


def add_pending_for_order(db, user_id: int, points: int, order_id: int, order_number: str) -> None:
    if points <= 0:
        return
    db.execute("UPDATE loyalty_cards SET points_pending = points_pending + ?, updated_at = ? WHERE user_id = ?",
               (points, now_iso(), user_id))
    _movement(db, user_id, "earn", points, "pending", f"Compra {order_number}", order_id)


def post_pending_for_order(db, order: dict) -> int:
    """Pasa a disponibles los puntos pendientes de un pedido. Idempotente: si
    ya se acreditaron, no hace nada."""
    mv = db.one("SELECT id, points FROM point_movements WHERE order_id = ? AND kind = 'earn' AND status = 'pending'", (order["id"],))
    if not mv:
        return 0
    changed = db.execute("UPDATE point_movements SET status = 'posted' WHERE id = ? AND status = 'pending'", (mv["id"],))
    if not changed:
        return 0
    db.execute(
        """UPDATE loyalty_cards SET points_pending = points_pending - ?, points_balance = points_balance + ?,
               lifetime_points = lifetime_points + ?, updated_at = ? WHERE user_id = ?""",
        (mv["points"], mv["points"], mv["points"], now_iso(), order["user_id"]),
    )
    return mv["points"]


def reverse_for_order(db, order: dict) -> None:
    """Pedido cancelado: devuelve los puntos gastados y anula los ganados."""
    uid = order["user_id"]
    pending = db.one("SELECT id, points FROM point_movements WHERE order_id = ? AND kind = 'earn' AND status = 'pending'", (order["id"],))
    if pending and db.execute("UPDATE point_movements SET status = 'cancelled' WHERE id = ? AND status = 'pending'", (pending["id"],)):
        db.execute("UPDATE loyalty_cards SET points_pending = points_pending - ? WHERE user_id = ?", (pending["points"], uid))
    posted = db.one("SELECT id, points FROM point_movements WHERE order_id = ? AND kind = 'earn' AND status = 'posted'", (order["id"],))
    already_revoked = db.one("SELECT id FROM point_movements WHERE order_id = ? AND kind = 'revoke'", (order["id"],))
    if posted and not already_revoked:
        # Si el cliente ya gastó esos puntos, se retira lo que haya disponible.
        bal = balance(uid)
        take = min(bal, posted["points"])
        db.execute("UPDATE loyalty_cards SET points_balance = points_balance - ? WHERE user_id = ?", (take, uid))
        _movement(db, uid, "revoke", -take, "posted", f"Anulación de puntos del pedido {order['order_number']}", order["id"])
    spent = db.one("SELECT COALESCE(SUM(-points), 0) AS n FROM point_movements WHERE order_id = ? AND kind = 'spend'", (order["id"],))["n"]
    refunded = db.one("SELECT id FROM point_movements WHERE order_id = ? AND kind = 'refund'", (order["id"],))
    if spent and not refunded:
        db.execute("UPDATE loyalty_cards SET points_balance = points_balance + ? WHERE user_id = ?", (spent, uid))
        _movement(db, uid, "refund", spent, "posted", f"Devolución de puntos del pedido {order['order_number']}", order["id"])


def admin_adjust(user_id: int, points: int, reason: str, admin_id: int) -> dict:
    if points == 0:
        raise ValidationError("El ajuste no puede ser 0.")
    db = get_db()
    with db.transaction():
        if not db.one("SELECT id FROM loyalty_cards WHERE user_id = ?", (user_id,)):
            raise NotFound("El usuario no tiene tarjeta.")
        if points < 0:
            ok = db.execute("UPDATE loyalty_cards SET points_balance = points_balance + ?, updated_at = ? WHERE user_id = ? AND points_balance >= ?",
                            (points, now_iso(), user_id, -points))
            if not ok:
                raise Conflict("El ajuste dejaría el saldo en negativo.")
        else:
            db.execute("UPDATE loyalty_cards SET points_balance = points_balance + ?, lifetime_points = lifetime_points + ?, updated_at = ? WHERE user_id = ?",
                       (points, points, now_iso(), user_id))
        _movement(db, user_id, "adjust", points, "posted", f"Ajuste: {reason}", created_by=admin_id)
    return card(user_id)
