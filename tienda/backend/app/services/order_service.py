"""Pedidos: creación transaccional (checkout) y ciclo de vida.

`place_order` hace todo en UNA transacción: si cualquier paso falla (stock,
cupón, puntos), no queda nada a medias. Es idempotente por `idempotency_key`:
un doble clic o un reintento de red devuelve el mismo pedido.
"""
from __future__ import annotations

import logging
import re

from app.core.errors import Conflict, NotFound, ValidationError
from app.core.jsonutil import dump_json, load_json
from app.core.security import human_code
from app.core.timeutil import now, now_iso
from app.db import IntegrityError, get_db
from app.payments import registry as payments
from app.services import (cart_service, coupon_service, loyalty_service, notification_service,
                          pricing_service, settings_service)

log = logging.getLogger("app.orders")
IDEMPOTENCY_RE = re.compile(r"^[A-Za-z0-9_-]{8,80}$")

# Transiciones permitidas. Para añadir un estado: insértelo en order_statuses
# (migración) y agréguelo aquí.
TRANSITIONS = {
    "pending": {"paid", "preparing", "cancelled"},
    "paid": {"preparing", "shipped", "cancelled"},
    "preparing": {"shipped", "cancelled"},
    "shipped": {"delivered"},
    "delivered": set(),
    "cancelled": set(),
}
STATUS_RANK = {"pending": 10, "paid": 20, "preparing": 30, "shipped": 40, "delivered": 50}


def _order_number(db) -> str:
    for _ in range(10):
        num = f"PD-{now():%y%m%d}-{human_code(5)}"
        if not db.one("SELECT id FROM orders WHERE order_number = ?", (num,)):
            return num
    raise RuntimeError("No se pudo generar el número de pedido")


def _history(db, order_id, from_status, to_status, note=None, by=None):
    db.insert(
        "INSERT INTO order_status_history (order_id, from_status, to_status, note, changed_by, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (order_id, from_status, to_status, note, by, now_iso()),
    )


def place_order(user: dict, data: dict) -> dict:
    key = data.get("idempotency_key") or ""
    if not IDEMPOTENCY_RE.match(key):
        raise ValidationError("Falta un identificador de operación válido.")
    db = get_db()
    existing = db.one("SELECT id FROM orders WHERE user_id = ? AND idempotency_key = ?", (user["id"], key))
    if existing:
        return get_order_for_user(user["id"], order_id=existing["id"])

    provider = payments.get(data.get("payment_provider"))
    method_code = data.get("shipping_method")
    method = next((m for m in pricing_service.shipping_methods() if m["code"] == method_code), None)
    if not method:
        raise ValidationError("Selecciona un método de entrega.", details={"shipping_method": "Obligatorio."})
    address = data.get("address") if method.get("requires_address") else None
    if method.get("requires_address"):
        address = _validate_address(address)
    customer = _validate_customer(data.get("customer") or {}, user)
    notes = (data.get("notes") or "").strip()[:500] or None
    coupon_code = (data.get("coupon_code") or "").strip().upper() or None
    points_to_use = int(data.get("points_to_use") or 0)
    currency = settings_service.get("store").get("currency", "GTQ")

    try:
        with db.transaction():
            items = cart_service.items(user["id"])
            if not items:
                raise ValidationError("Tu carrito está vacío.", code="cart_empty")
            q = pricing_service.quote(user["id"], items, coupon_code=coupon_code, points_to_use=points_to_use,
                                      shipping_code=method_code, points_balance=loyalty_service.balance(user["id"]))
            if not q["can_checkout"]:
                raise Conflict("Hay productos de tu carrito que cambiaron. Revisa el resumen.", code="cart_changed", details=q)
            if coupon_code and not q["coupon"]:
                msg = next((i["message"] for i in q["issues"] if i["code"] == "coupon_invalid"), "Cupón no válido.")
                raise ValidationError(msg, code="coupon_invalid", details={"coupon_code": msg})
            expected = data.get("expected_total_cents")
            if expected is not None and int(expected) != q["total_cents"]:
                raise Conflict("El total de tu pedido cambió. Revisa el nuevo resumen antes de confirmar.",
                               code="price_changed", details=q)

            order_id = db.insert(
                """INSERT INTO orders (order_number, user_id, status, currency, subtotal_cents, discount_cents,
                        points_discount_cents, shipping_cents, total_cents, points_used, points_earned, coupon_code,
                        shipping_method, payment_provider, payment_status, customer_name, customer_email, customer_phone,
                        shipping_address, notes, idempotency_key, created_at, updated_at)
                   VALUES (?, ?, 'pending', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?, ?, ?, ?, ?)""",
                (_order_number(db), user["id"], currency, q["subtotal_cents"], q["discount_cents"],
                 q["points_discount_cents"], q["shipping_cents"], q["total_cents"], q["points_used"], q["points_earned"],
                 q["coupon"]["code"] if q["coupon"] else None, method_code, provider.code,
                 customer["name"], customer["email"], customer.get("phone"), dump_json(address), notes, key,
                 now_iso(), now_iso()),
            )
            order = db.one("SELECT * FROM orders WHERE id = ?", (order_id,))

            for line in q["lines"]:
                # Descuento de stock atómico: falla si otro cliente se llevó las últimas unidades.
                ok = db.execute(
                    """UPDATE products SET stock = stock - ?, sold_count = sold_count + ?, updated_at = ?
                       WHERE id = ? AND status = 'active' AND stock >= ?""",
                    (line["quantity"], line["quantity"], now_iso(), line["product_id"], line["quantity"]),
                )
                if not ok:
                    raise Conflict(f"{line['name']} se agotó mientras comprabas.", code="out_of_stock")
                db.insert(
                    """INSERT INTO order_items (order_id, product_id, product_name, sku, unit_price_cents, quantity, line_total_cents)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (order_id, line["product_id"], line["name"], line["sku"], line["unit_price_cents"], line["quantity"], line["line_total_cents"]),
                )
                db.insert(
                    "INSERT INTO inventory_movements (product_id, delta, reason, ref_type, ref_id, created_at) VALUES (?, ?, 'sale', 'order', ?, ?)",
                    (line["product_id"], -line["quantity"], order_id, now_iso()),
                )

            if q["coupon"]:
                coupon_service.consume(db, q["coupon"]["id"], user["id"], order_id)
            loyalty_service.debit(db, user["id"], q["points_used"], "spend", f"Canje en compra {order['order_number']}", order_id=order_id)
            loyalty_service.add_pending_for_order(db, user["id"], q["points_earned"], order_id, order["order_number"])
            _history(db, order_id, None, "pending", "Pedido creado", user["id"])

            result = provider.create_payment(order)
            db.insert(
                """INSERT INTO payments (order_id, provider, status, amount_cents, currency, provider_ref, details, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (order_id, provider.code, result.status, q["total_cents"], currency, result.provider_ref,
                 dump_json({"instructions": result.instructions, **result.details}), now_iso(), now_iso()),
            )
            if result.status == "paid":
                _apply_transition(db, order, "paid", None, "Pago confirmado por el proveedor")
            cart_service.clear(db, user["id"])
    except IntegrityError:
        # Dos peticiones simultáneas con la misma clave: la otra ganó.
        existing = db.one("SELECT id FROM orders WHERE user_id = ? AND idempotency_key = ?", (user["id"], key))
        if existing:
            return get_order_for_user(user["id"], order_id=existing["id"])
        raise

    full = get_order_for_user(user["id"], order_id=order_id)
    _notify_created(full)
    return full


def _validate_customer(c: dict, user: dict) -> dict:
    name = (c.get("name") or f"{user['first_name']} {user['last_name']}").strip()[:170]
    phone = (c.get("phone") or user.get("phone") or "").strip()[:30] or None
    if len(name) < 2:
        raise ValidationError("Ingresa tu nombre.", details={"customer.name": "Obligatorio."})
    return {"name": name, "email": user["email"], "phone": phone}


def _validate_address(a) -> dict:
    if not isinstance(a, dict):
        raise ValidationError("Ingresa la dirección de entrega.", details={"address": "Obligatoria."})
    out, errors = {}, {}
    for field, required, max_len in (("recipient", True, 120), ("phone", True, 30), ("line1", True, 200),
                                     ("line2", False, 200), ("city", True, 100), ("state", False, 100),
                                     ("postal_code", False, 20), ("notes", False, 300)):
        value = a.get(field)
        value = value.strip()[:max_len] if isinstance(value, str) else None
        if required and not value:
            errors[f"address.{field}"] = "Obligatorio."
        out[field] = value or None
    out["country"] = "GT"
    if errors:
        raise ValidationError("Completa la dirección de entrega.", details=errors)
    return out


def _apply_transition(db, order: dict, to_status: str, by: int | None, note: str | None) -> None:
    current = order["status"]
    if to_status == current:
        return
    if to_status not in TRANSITIONS.get(current, set()):
        raise ValidationError(f"No se puede pasar de '{current}' a '{to_status}'.", code="invalid_transition")
    # Bloqueo optimista: si otro administrador cambió el estado a la vez, falla.
    ok = db.execute("UPDATE orders SET status = ?, updated_at = ? WHERE id = ? AND status = ?",
                    (to_status, now_iso(), order["id"], current))
    if not ok:
        raise Conflict("El pedido fue modificado por otra persona. Recarga e inténtalo de nuevo.")
    _history(db, order["id"], current, to_status, note, by)

    if to_status == "paid":
        db.execute("UPDATE orders SET payment_status = 'paid' WHERE id = ?", (order["id"],))
        db.execute("UPDATE payments SET status = 'paid', updated_at = ? WHERE order_id = ? AND status = 'pending'", (now_iso(), order["id"]))
    if to_status == "delivered" and order["payment_status"] != "paid":
        # Contra entrega: el pago se cobra al entregar.
        db.execute("UPDATE orders SET payment_status = 'paid' WHERE id = ?", (order["id"],))
        db.execute("UPDATE payments SET status = 'paid', updated_at = ? WHERE order_id = ? AND status = 'pending'", (now_iso(), order["id"]))

    if to_status == "cancelled":
        for item in db.all("SELECT product_id, quantity FROM order_items WHERE order_id = ? AND product_id IS NOT NULL", (order["id"],)):
            db.execute("UPDATE products SET stock = stock + ?, sold_count = MAX(sold_count - ?, 0) WHERE id = ?"
                       if db.dialect == "sqlite" else
                       "UPDATE products SET stock = stock + ?, sold_count = GREATEST(sold_count - ?, 0) WHERE id = ?",
                       (item["quantity"], item["quantity"], item["product_id"]))
            db.insert("INSERT INTO inventory_movements (product_id, delta, reason, ref_type, ref_id, user_id, created_at) VALUES (?, ?, 'cancel', 'order', ?, ?, ?)",
                      (item["product_id"], item["quantity"], order["id"], by, now_iso()))
        coupon_service.release(db, order["id"])
        loyalty_service.reverse_for_order(db, order)
        db.execute("UPDATE payments SET status = CASE WHEN status = 'paid' THEN 'refund_due' ELSE 'cancelled' END, updated_at = ? WHERE order_id = ?",
                   (now_iso(), order["id"]))
        return

    earn_on = settings_service.get("loyalty").get("earn_on_status", "delivered")
    if STATUS_RANK.get(to_status, 0) >= STATUS_RANK.get(earn_on, 50):
        loyalty_service.post_pending_for_order(db, order)


def change_status(order_id: int, to_status: str, by: int | None, note: str | None = None) -> dict:
    db = get_db()
    if not db.one("SELECT code FROM order_statuses WHERE code = ?", (to_status,)):
        raise ValidationError("Estado desconocido.")
    with db.transaction():
        order = db.one("SELECT * FROM orders WHERE id = ?", (order_id,))
        if not order:
            raise NotFound("Pedido no encontrado.")
        _apply_transition(db, order, to_status, by, note)
    order = get_order_admin(order_id)
    notification_service.send_email(order["customer_email"], f"Tu pedido {order['order_number']}: {order['status_label']}",
                                    f"El estado de tu pedido ahora es: {order['status_label']}.")
    return order


def cancel_by_customer(user_id: int, order_number: str) -> dict:
    db = get_db()
    order = db.one("SELECT id, status FROM orders WHERE order_number = ? AND user_id = ?", (order_number, user_id))
    if not order:
        raise NotFound("Pedido no encontrado.")
    if order["status"] != "pending":
        raise Conflict("Este pedido ya se está procesando. Contacta a la tienda para cancelarlo.")
    change_status(order["id"], "cancelled", user_id, "Cancelado por el cliente")
    return get_order_for_user(user_id, order_id=order["id"])


# ------------------------------------------------------------------ lectura
def _serialize(order: dict, items: list[dict], history: list[dict] | None = None, payment: dict | None = None) -> dict:
    labels = {r["code"]: r["label"] for r in get_db().all("SELECT code, label FROM order_statuses")}
    out = {k: order[k] for k in (
        "id", "order_number", "status", "currency", "subtotal_cents", "discount_cents", "points_discount_cents",
        "shipping_cents", "total_cents", "points_used", "points_earned", "coupon_code", "shipping_method",
        "payment_provider", "payment_status", "customer_name", "customer_email", "customer_phone", "notes",
        "created_at", "updated_at")}
    out["status_label"] = labels.get(order["status"], order["status"])
    out["shipping_address"] = load_json(order["shipping_address"])
    out["items"] = items
    if history is not None:
        out["history"] = [h | {"to_label": labels.get(h["to_status"], h["to_status"])} for h in history]
    if payment:
        details = load_json(payment.get("details"), {}) or {}
        out["payment"] = {"status": payment["status"], "provider": payment["provider"], "instructions": details.get("instructions")}
    return out


def _load(order: dict, with_history=True) -> dict:
    db = get_db()
    items = db.all(
        """SELECT oi.product_id, oi.product_name, oi.sku, oi.unit_price_cents, oi.quantity, oi.line_total_cents, p.slug,
                  (SELECT url FROM product_images i WHERE i.product_id = oi.product_id ORDER BY i.sort_order, i.id LIMIT 1) AS image_url
           FROM order_items oi LEFT JOIN products p ON p.id = oi.product_id WHERE oi.order_id = ? ORDER BY oi.id""",
        (order["id"],),
    )
    history = db.all("SELECT from_status, to_status, note, created_at FROM order_status_history WHERE order_id = ? ORDER BY id", (order["id"],)) if with_history else None
    payment = db.one("SELECT provider, status, details FROM payments WHERE order_id = ? ORDER BY id DESC LIMIT 1", (order["id"],))
    return _serialize(order, items, history, payment)


def get_order_for_user(user_id: int, *, order_number: str | None = None, order_id: int | None = None) -> dict:
    db = get_db()
    if order_id is not None:
        order = db.one("SELECT * FROM orders WHERE id = ? AND user_id = ?", (order_id, user_id))
    else:
        order = db.one("SELECT * FROM orders WHERE order_number = ? AND user_id = ?", (order_number, user_id))
    if not order:
        raise NotFound("Pedido no encontrado.")
    return _load(order)


def get_order_admin(order_id: int) -> dict:
    order = get_db().one("SELECT * FROM orders WHERE id = ?", (order_id,))
    if not order:
        raise NotFound("Pedido no encontrado.")
    return _load(order)


def list_for_user(user_id: int, scope: str, page: int, size: int) -> tuple[list[dict], int]:
    active = "status IN ('pending','paid','preparing','shipped')"
    past = "status IN ('delivered','cancelled')"
    cond = {"current": active, "past": past}.get(scope, "1=1")
    db = get_db()
    total = db.scalar(f"SELECT COUNT(*) AS n FROM orders WHERE user_id = ? AND {cond}", (user_id,))
    rows = db.all(
        f"""SELECT o.id, o.order_number, o.status, o.total_cents, o.currency, o.created_at, o.points_earned,
                   (SELECT COALESCE(SUM(quantity), 0) FROM order_items WHERE order_id = o.id) AS item_count
            FROM orders o WHERE user_id = ? AND {cond} ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?""",
        (user_id, size, (page - 1) * size),
    )
    labels = {r["code"]: r["label"] for r in db.all("SELECT code, label FROM order_statuses")}
    for r in rows:
        r["status_label"] = labels.get(r["status"], r["status"])
    return rows, total


def _notify_created(order: dict) -> None:
    lines = "\n".join(f"- {i['quantity']} x {i['product_name']}" for i in order["items"])
    instructions = (order.get("payment") or {}).get("instructions") or ""
    notification_service.send_email(
        order["customer_email"], f"Recibimos tu pedido {order['order_number']}",
        f"Gracias por tu compra.\n\n{lines}\n\nTotal: {order['total_cents'] / 100:.2f} {order['currency']}\n{instructions}",
    )
