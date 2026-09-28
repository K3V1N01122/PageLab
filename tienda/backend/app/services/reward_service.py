"""Recompensas canjeables con puntos.

Cada tipo de recompensa se implementa como un "handler" que genera el
beneficio. Hoy todos generan un cupón personal de un solo uso; un tipo nuevo
(p. ej. envío de un regalo físico) solo necesita otro handler.
"""
from __future__ import annotations

import re

from app.core.errors import Conflict, NotFound, ValidationError
from app.core.security import human_code
from app.core.timeutil import iso_in, now, now_iso, parse
from app.db import IntegrityError, get_db
from app.services import loyalty_service

IDEMPOTENCY_RE = re.compile(r"^[A-Za-z0-9_-]{8,80}$")


def _coupon(db, user_id, reward, kind, *, value_cents=0, percent=0, product_id=None) -> int:
    for _ in range(10):
        code = f"R-{human_code(8)}"
        try:
            with db.transaction():
                return db.insert(
                    """INSERT INTO coupons (code, description, kind, value_cents, percent, product_id, starts_at, ends_at,
                                            max_uses, per_user_limit, user_id, source, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, 1, ?, 'reward', ?, ?)""",
                    (code, reward["name"], kind, value_cents, percent, product_id, now_iso(),
                     iso_in(days=reward["coupon_valid_days"]), user_id, now_iso(), now_iso()),
                )
        except IntegrityError:
            continue
    raise RuntimeError("No se pudo generar el cupón")


HANDLERS = {
    "fixed_discount": lambda db, uid, r: _coupon(db, uid, r, "fixed", value_cents=r["value_cents"]),
    "percent_discount": lambda db, uid, r: _coupon(db, uid, r, "percent", percent=r["percent"]),
    "free_shipping": lambda db, uid, r: _coupon(db, uid, r, "free_shipping"),
    "free_product": lambda db, uid, r: _coupon(db, uid, r, "free_product", product_id=r["product_id"]),
}
KINDS = set(HANDLERS)


def _available(r: dict) -> bool:
    if not r["is_active"]:
        return False
    if r["starts_at"] and parse(r["starts_at"]) > now():
        return False
    if r["ends_at"] and parse(r["ends_at"]) < now():
        return False
    return r["stock"] is None or r["stock"] > 0


def list_available(user_id: int | None = None) -> list[dict]:
    rows = get_db().all(
        """SELECT r.id, r.name, r.description, r.kind, r.points_cost, r.value_cents, r.percent, r.stock,
                  r.per_user_limit, r.coupon_valid_days, r.is_active, r.starts_at, r.ends_at, p.name AS product_name, p.slug AS product_slug
           FROM rewards r LEFT JOIN products p ON p.id = r.product_id ORDER BY r.points_cost"""
    )
    return [r | {"is_active": True} for r in rows if _available(r)]


def my_coupons(user_id: int) -> list[dict]:
    rows = get_db().all(
        """SELECT c.code, c.description, c.kind, c.value_cents, c.percent, c.ends_at, c.uses_count, c.max_uses
           FROM coupons c WHERE c.user_id = ? AND c.source = 'reward' ORDER BY c.created_at DESC LIMIT 50""",
        (user_id,),
    )
    for r in rows:
        r["used"] = r["uses_count"] >= (r["max_uses"] or 1)
        r["expired"] = bool(r["ends_at"] and parse(r["ends_at"]) < now())
    return rows


def redeem(user_id: int, reward_id: int, idempotency_key: str) -> dict:
    """Canje atómico e idempotente:
    1) valida puntos y disponibilidad, 2) descuenta puntos en el backend,
    3) registra el canje, 4) genera el beneficio, 5) devuelve la confirmación.
    Repetir la misma petición (mismo idempotency_key) devuelve el mismo canje."""
    if not IDEMPOTENCY_RE.match(idempotency_key or ""):
        raise ValidationError("Falta un identificador de operación válido.")
    db = get_db()
    existing = db.one("SELECT * FROM reward_redemptions WHERE user_id = ? AND idempotency_key = ?", (user_id, idempotency_key))
    if existing:
        return _confirmation(existing)
    try:
        with db.transaction():
            r = db.one("SELECT * FROM rewards WHERE id = ?", (reward_id,))
            if not r:
                raise NotFound("Recompensa no encontrada.")
            if not _available(r):
                raise Conflict("Esta recompensa ya no está disponible.", code="reward_unavailable")
            if r["per_user_limit"]:
                used = db.scalar("SELECT COUNT(*) AS n FROM reward_redemptions WHERE user_id = ? AND reward_id = ?", (user_id, reward_id))
                if used >= r["per_user_limit"]:
                    raise Conflict("Ya alcanzaste el límite de canjes de esta recompensa.", code="reward_limit")
            if r["stock"] is not None and not db.execute(
                "UPDATE rewards SET stock = stock - 1, updated_at = ? WHERE id = ? AND stock > 0", (now_iso(), reward_id)
            ):
                raise Conflict("Esta recompensa se agotó.", code="reward_unavailable")
            redemption_id = db.insert(
                "INSERT INTO reward_redemptions (user_id, reward_id, points, idempotency_key, created_at) VALUES (?, ?, ?, ?, ?)",
                (user_id, reward_id, r["points_cost"], idempotency_key, now_iso()),
            )
            loyalty_service.debit(db, user_id, r["points_cost"], "redeem", f"Canje: {r['name']}", redemption_id=redemption_id)
            coupon_id = HANDLERS[r["kind"]](db, user_id, r)
            db.execute("UPDATE reward_redemptions SET coupon_id = ? WHERE id = ?", (coupon_id, redemption_id))
    except IntegrityError:
        # Petición duplicada simultánea: la otra ya creó el canje.
        existing = db.one("SELECT * FROM reward_redemptions WHERE user_id = ? AND idempotency_key = ?", (user_id, idempotency_key))
        if existing:
            return _confirmation(existing)
        raise
    return _confirmation(db.one("SELECT * FROM reward_redemptions WHERE id = ?", (redemption_id,)))


def _confirmation(redemption: dict) -> dict:
    db = get_db()
    reward = db.one("SELECT name, kind FROM rewards WHERE id = ?", (redemption["reward_id"],))
    coupon = db.one("SELECT code, ends_at FROM coupons WHERE id = ?", (redemption["coupon_id"],)) if redemption["coupon_id"] else None
    return {
        "redemption_id": redemption["id"],
        "reward": reward["name"],
        "points_spent": redemption["points"],
        "coupon_code": coupon["code"] if coupon else None,
        "coupon_expires_at": coupon["ends_at"] if coupon else None,
        "points_available": loyalty_service.balance(redemption["user_id"]),
    }
