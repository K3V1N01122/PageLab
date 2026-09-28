"""Cupones: validación, cálculo de descuento y consumo seguro."""
from __future__ import annotations

from app.core.errors import Conflict, ValidationError
from app.core.money import pct_of
from app.core.timeutil import now_iso, parse, now
from app.db import get_db

KINDS = {"fixed", "percent", "free_shipping", "free_product"}


def find_valid(code: str, user_id: int | None, subtotal_cents: int) -> dict:
    """Devuelve el cupón si puede usarse; si no, lanza ValidationError con el motivo."""
    code = (code or "").strip().upper()
    if not code:
        raise ValidationError("Ingresa un código.", code="coupon_invalid")
    db = get_db()
    c = db.one("SELECT * FROM coupons WHERE code = ?", (code,))
    err = lambda msg: ValidationError(msg, code="coupon_invalid", details={"coupon_code": msg})
    if not c or not c["is_active"]:
        raise err("El cupón no existe o no está activo.")
    if c["user_id"] and c["user_id"] != user_id:
        raise err("Este cupón pertenece a otra cuenta.")
    if c["starts_at"] and parse(c["starts_at"]) > now():
        raise err("Este cupón todavía no está vigente.")
    if c["ends_at"] and parse(c["ends_at"]) < now():
        raise err("Este cupón ya expiró.")
    if c["max_uses"] is not None and c["uses_count"] >= c["max_uses"]:
        raise err("Este cupón ya alcanzó su límite de usos.")
    if subtotal_cents < c["min_subtotal_cents"]:
        raise err("Tu compra no alcanza el mínimo para este cupón.")
    if user_id and c["per_user_limit"]:
        used = db.scalar("SELECT COUNT(*) AS n FROM coupon_usages WHERE coupon_id = ? AND user_id = ?", (c["id"], user_id))
        if used >= c["per_user_limit"]:
            raise err("Ya usaste este cupón.")
    return c


def discount_for(coupon: dict, subtotal_cents: int, lines: list[dict]) -> tuple[int, bool]:
    """(descuento en centavos, envío gratis)."""
    kind = coupon["kind"]
    if kind == "fixed":
        return min(coupon["value_cents"], subtotal_cents), False
    if kind == "percent":
        return min(pct_of(subtotal_cents, coupon["percent"]), subtotal_cents), False
    if kind == "free_shipping":
        return 0, True
    if kind == "free_product":
        line = next((l for l in lines if l["product_id"] == coupon["product_id"]), None)
        if not line:
            raise ValidationError("Agrega al carrito el producto de esta recompensa para usar el cupón.",
                                  code="coupon_invalid", details={"coupon_code": "Falta el producto."})
        return line["unit_price_cents"], False
    return 0, False


def consume(db, coupon_id: int, user_id: int, order_id: int) -> None:
    """Consumo atómico: el UPDATE condicional impide superar max_uses aunque
    lleguen muchas compras simultáneas."""
    ok = db.execute(
        """UPDATE coupons SET uses_count = uses_count + 1, updated_at = ?
           WHERE id = ? AND is_active = TRUE AND (max_uses IS NULL OR uses_count < max_uses)""",
        (now_iso(), coupon_id),
    )
    if not ok:
        raise Conflict("El cupón ya no está disponible.", code="coupon_exhausted")
    db.insert("INSERT INTO coupon_usages (coupon_id, user_id, order_id, created_at) VALUES (?, ?, ?, ?)",
              (coupon_id, user_id, order_id, now_iso()))


def release(db, order_id: int) -> None:
    for usage in db.all("SELECT id, coupon_id FROM coupon_usages WHERE order_id = ?", (order_id,)):
        db.execute("UPDATE coupons SET uses_count = uses_count - 1 WHERE id = ? AND uses_count > 0", (usage["coupon_id"],))
        db.execute("DELETE FROM coupon_usages WHERE id = ?", (usage["id"],))
