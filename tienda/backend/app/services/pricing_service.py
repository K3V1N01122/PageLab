"""Cálculo de precios: la ÚNICA fuente de verdad para montos.

El carrito, la vista previa del checkout y la confirmación del pedido usan esta
misma función con datos leídos de la BD. El cliente solo envía IDs, cantidades,
un código de cupón y cuántos puntos quiere usar; nunca precios ni totales.
"""
from __future__ import annotations

from app.core.errors import ValidationError
from app.core.money import pct_of
from app.db import get_db
from app.services import catalog_service, coupon_service, promotion_service, settings_service

MAX_QTY_PER_LINE = 99


def shipping_methods() -> list[dict]:
    return [m for m in settings_service.get("shipping").get("methods", []) if m.get("active", True)]


def points_value_cents(points: int, loyalty: dict) -> int:
    block = loyalty["redeem_block_points"]
    return (points // block) * loyalty["redeem_block_value_cents"]


def quote(user_id: int | None, items: list[dict], *, coupon_code: str | None = None,
          points_to_use: int = 0, shipping_code: str | None = None, points_balance: int = 0) -> dict:
    db = get_db()
    issues: list[dict] = []
    merged: dict[int, int] = {}
    for it in items:
        merged[it["product_id"]] = merged.get(it["product_id"], 0) + it["quantity"]
    ids = list(merged)
    products = {}
    if ids:
        rows = db.all(
            f"""SELECT p.id, p.name, p.slug, p.sku, p.price_cents, p.compare_at_cents, p.stock, p.status, p.category_id,
                       (SELECT url FROM product_images i WHERE i.product_id = p.id ORDER BY i.sort_order, i.id LIMIT 1) AS image_url
                FROM products p WHERE p.id IN ({','.join('?' * len(ids))})""",
            ids,
        )
        products = {r["id"]: r for r in rows}

    promos = promotion_service.active_promotions()
    lines, subtotal = [], 0
    for pid, qty in merged.items():
        p = products.get(pid)
        if not p or p["status"] != "active":
            issues.append({"product_id": pid, "code": "unavailable", "message": "Este producto ya no está disponible."})
            continue
        if p["stock"] <= 0:
            issues.append({"product_id": pid, "code": "out_of_stock", "message": f"{p['name']} está agotado.", "available": 0})
            continue
        if qty > p["stock"]:
            issues.append({"product_id": pid, "code": "insufficient_stock", "available": p["stock"],
                           "message": f"Solo quedan {p['stock']} unidades de {p['name']}."})
        p["_category_ids"] = catalog_service.ancestor_ids(p["category_id"])
        unit_discount, _promo = promotion_service.unit_discount(p, promos)
        unit = p["price_cents"] - unit_discount
        line_total = unit * qty
        subtotal += line_total
        lines.append({
            "product_id": pid, "name": p["name"], "slug": p["slug"], "sku": p["sku"], "image_url": p["image_url"],
            "quantity": qty, "unit_price_cents": unit, "line_total_cents": line_total, "stock": p["stock"],
        })

    # Cupón
    discount, free_shipping, coupon = 0, False, None
    if coupon_code:
        try:
            coupon = coupon_service.find_valid(coupon_code, user_id, subtotal)
            discount, free_shipping = coupon_service.discount_for(coupon, subtotal, lines)
        except ValidationError as exc:
            issues.append({"code": "coupon_invalid", "message": exc.message})
            coupon = None

    # Envío
    methods = shipping_methods()
    method = next((m for m in methods if m["code"] == shipping_code), None) if shipping_code else None
    if shipping_code and not method:
        issues.append({"code": "shipping_invalid", "message": "Selecciona un método de entrega válido."})
    shipping_settings = settings_service.get("shipping")
    shipping = method["price_cents"] if method else 0
    threshold = shipping_settings.get("free_shipping_over_cents")
    if free_shipping or (threshold and subtotal - discount >= threshold):
        shipping = 0

    # Puntos: en bloques configurables y con tope porcentual.
    loyalty = settings_service.get("loyalty")
    points_used, points_discount = 0, 0
    if points_to_use and loyalty.get("enabled"):
        if points_to_use < 0:
            raise ValidationError("Cantidad de puntos no válida.")
        block = loyalty["redeem_block_points"]
        base = subtotal - discount
        cap = pct_of(base, loyalty.get("max_points_discount_percent", 100))
        max_blocks_by_cap = cap // loyalty["redeem_block_value_cents"] if loyalty["redeem_block_value_cents"] else 0
        blocks = min(points_to_use // block, points_balance // block, max_blocks_by_cap)
        points_used = blocks * block
        points_discount = points_value_cents(points_used, loyalty)
        if points_to_use > points_balance:
            issues.append({"code": "insufficient_points", "message": "No tienes suficientes puntos."})
        elif points_used < (points_to_use // block) * block:
            issues.append({"code": "points_capped", "severity": "info",
                           "message": "Ajustamos los puntos al máximo permitido para esta compra."})

    total = max(0, subtotal - discount - points_discount + shipping)
    earn_base = max(0, subtotal - discount - points_discount)
    points_earned = (earn_base // 100) * loyalty.get("points_per_currency_unit", 0) if loyalty.get("enabled") else 0
    blocking = [i for i in issues if i.get("severity") != "info" and i["code"] != "coupon_invalid"]

    return {
        "lines": lines,
        "issues": issues,
        "can_checkout": bool(lines) and not blocking,
        "coupon": {"code": coupon["code"], "kind": coupon["kind"], "id": coupon["id"]} if coupon else None,
        "shipping_method": method,
        "subtotal_cents": subtotal,
        "discount_cents": discount,
        "points_used": points_used,
        "points_discount_cents": points_discount,
        "shipping_cents": shipping,
        "total_cents": total,
        "points_earned": points_earned,
        "item_count": sum(l["quantity"] for l in lines),
    }
