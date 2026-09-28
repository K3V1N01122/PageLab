"""Carrito del lado del servidor para usuarios autenticados.

Los invitados guardan en su navegador solo {product_id, quantity}; al iniciar
sesión el frontend llama a `merge`. Los precios nunca vienen del cliente.
"""
from __future__ import annotations

from app.core.errors import NotFound, ValidationError
from app.core.timeutil import now_iso
from app.db import IntegrityError, get_db
from app.services import loyalty_service, pricing_service

MAX_LINES = 100


def _cart_id(db, user_id: int) -> int:
    row = db.one("SELECT id FROM carts WHERE user_id = ?", (user_id,))
    if row:
        return row["id"]
    try:
        return db.insert("INSERT INTO carts (user_id, updated_at) VALUES (?, ?)", (user_id, now_iso()))
    except IntegrityError:  # creado por otra petición simultánea
        return db.scalar("SELECT id FROM carts WHERE user_id = ?", (user_id,))


def items(user_id: int) -> list[dict]:
    return get_db().all(
        """SELECT ci.product_id, ci.quantity, ci.unit_price_cents FROM cart_items ci
           JOIN carts c ON c.id = ci.cart_id WHERE c.user_id = ? ORDER BY ci.id""",
        (user_id,),
    )


def _product(db, product_id: int) -> dict:
    p = db.one("SELECT id, price_cents, stock, status FROM products WHERE id = ?", (product_id,))
    if not p or p["status"] != "active":
        raise NotFound("Este producto no está disponible.")
    return p


def set_quantity(user_id: int, product_id: int, quantity: int, *, add: bool = False) -> None:
    if quantity < 0 or quantity > pricing_service.MAX_QTY_PER_LINE:
        raise ValidationError(f"La cantidad debe estar entre 1 y {pricing_service.MAX_QTY_PER_LINE}.")
    db = get_db()
    with db.transaction():
        cart_id = _cart_id(db, user_id)
        existing = db.one("SELECT id, quantity FROM cart_items WHERE cart_id = ? AND product_id = ?", (cart_id, product_id))
        new_qty = (existing["quantity"] if existing and add else 0) + quantity
        if new_qty <= 0:
            db.execute("DELETE FROM cart_items WHERE cart_id = ? AND product_id = ?", (cart_id, product_id))
        else:
            p = _product(db, product_id)
            if p["stock"] <= 0:
                raise ValidationError("Este producto está agotado.", code="out_of_stock")
            new_qty = min(new_qty, pricing_service.MAX_QTY_PER_LINE)
            if new_qty > p["stock"]:
                raise ValidationError(f"Solo hay {p['stock']} unidades disponibles.", code="insufficient_stock",
                                      details={"available": p["stock"]})
            if existing:
                db.execute("UPDATE cart_items SET quantity = ? WHERE id = ?", (new_qty, existing["id"]))
            else:
                if db.scalar("SELECT COUNT(*) AS n FROM cart_items WHERE cart_id = ?", (cart_id,)) >= MAX_LINES:
                    raise ValidationError("Tu carrito alcanzó el máximo de productos.")
                db.insert(
                    "INSERT INTO cart_items (cart_id, product_id, quantity, unit_price_cents, created_at) VALUES (?, ?, ?, ?, ?)",
                    (cart_id, product_id, new_qty, p["price_cents"], now_iso()),
                )
        db.execute("UPDATE carts SET updated_at = ? WHERE id = ?", (now_iso(), cart_id))


def merge(user_id: int, guest_items: list[dict]) -> None:
    """Fusiona el carrito de invitado. Ajusta cantidades al stock disponible
    en lugar de fallar, para no perder el carrito del cliente."""
    db = get_db()
    with db.transaction():
        cart_id = _cart_id(db, user_id)
        for it in guest_items[:MAX_LINES]:
            p = db.one("SELECT id, price_cents, stock, status FROM products WHERE id = ?", (it["product_id"],))
            if not p or p["status"] != "active" or p["stock"] <= 0:
                continue
            existing = db.one("SELECT id, quantity FROM cart_items WHERE cart_id = ? AND product_id = ?", (cart_id, p["id"]))
            qty = min(max(it["quantity"], existing["quantity"] if existing else 0), p["stock"], pricing_service.MAX_QTY_PER_LINE)
            if existing:
                db.execute("UPDATE cart_items SET quantity = ? WHERE id = ?", (qty, existing["id"]))
            else:
                db.insert("INSERT INTO cart_items (cart_id, product_id, quantity, unit_price_cents, created_at) VALUES (?, ?, ?, ?, ?)",
                          (cart_id, p["id"], qty, p["price_cents"], now_iso()))


def clear(db, user_id: int) -> None:
    db.execute("DELETE FROM cart_items WHERE cart_id IN (SELECT id FROM carts WHERE user_id = ?)", (user_id,))


def view(user_id: int, coupon_code: str | None = None, points_to_use: int = 0, shipping_code: str | None = None) -> dict:
    """Carrito con precios recalculados y aviso de cambios de precio desde que
    se agregó cada producto."""
    rows = items(user_id)
    snapshot = {r["product_id"]: r["unit_price_cents"] for r in rows}
    q = pricing_service.quote(user_id, rows, coupon_code=coupon_code, points_to_use=points_to_use,
                              shipping_code=shipping_code, points_balance=loyalty_service.balance(user_id))
    db = get_db()
    changed = []
    for line in q["lines"]:
        old = snapshot.get(line["product_id"])
        line["previous_unit_price_cents"] = old if old is not None and old != line["unit_price_cents"] else None
        if line["previous_unit_price_cents"] is not None:
            changed.append(line["product_id"])
    if changed:
        # El aviso se muestra una vez; después el precio queda como referencia nueva.
        for line in q["lines"]:
            if line["product_id"] in changed:
                db.execute(
                    "UPDATE cart_items SET unit_price_cents = ? WHERE product_id = ? AND cart_id IN (SELECT id FROM carts WHERE user_id = ?)",
                    (line["unit_price_cents"], line["product_id"], user_id),
                )
    q["price_changes"] = changed
    return q
