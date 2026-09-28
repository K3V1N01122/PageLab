from flask import g, jsonify

from app.api.v1 import api_v1
from app.core.auth import login_required
from app.core.errors import ValidationError
from app.core.request_ctx import json_body
from app.core.validation import V
from app.services import cart_service, loyalty_service, pricing_service


def _items_from(body) -> list[dict]:
    raw = body.get("items")
    if not isinstance(raw, list) or len(raw) > cart_service.MAX_LINES:
        raise ValidationError("Lista de productos no válida.")
    out = []
    for it in raw:
        if not isinstance(it, dict):
            continue
        try:
            pid, qty = int(it.get("product_id")), int(it.get("quantity"))
        except (TypeError, ValueError):
            continue
        if pid > 0 and 0 < qty <= pricing_service.MAX_QTY_PER_LINE:
            out.append({"product_id": pid, "quantity": qty})
    return out


@api_v1.post("/cart/quote")
def guest_quote():
    """Resumen para invitados: el navegador envía IDs y cantidades; el precio
    lo calcula el servidor."""
    return jsonify(pricing_service.quote(None, _items_from(json_body())))


@api_v1.get("/cart")
@login_required
def get_cart():
    return jsonify(cart_service.view(g.user["id"]))


@api_v1.post("/cart/items")
@login_required
def add_item():
    data = V(json_body()).int("product_id", min_value=1).int("quantity", required=False, min_value=1,
                                                              max_value=pricing_service.MAX_QTY_PER_LINE, default=1).check()
    cart_service.set_quantity(g.user["id"], data["product_id"], data["quantity"], add=True)
    return jsonify(cart_service.view(g.user["id"])), 201


@api_v1.put("/cart/items/<int:product_id>")
@login_required
def update_item(product_id):
    data = V(json_body()).int("quantity", min_value=0, max_value=pricing_service.MAX_QTY_PER_LINE).check()
    cart_service.set_quantity(g.user["id"], product_id, data["quantity"])
    return jsonify(cart_service.view(g.user["id"]))


@api_v1.delete("/cart/items/<int:product_id>")
@login_required
def remove_item(product_id):
    cart_service.set_quantity(g.user["id"], product_id, 0)
    return jsonify(cart_service.view(g.user["id"]))


@api_v1.post("/cart/merge")
@login_required
def merge():
    cart_service.merge(g.user["id"], _items_from(json_body()))
    return jsonify(cart_service.view(g.user["id"]))


@api_v1.post("/cart/preview")
@login_required
def preview():
    """Vista previa del checkout con cupón, puntos y envío."""
    body = json_body()
    points = body.get("points_to_use") or 0
    if not isinstance(points, int) or isinstance(points, bool) or points < 0:
        raise ValidationError("Cantidad de puntos no válida.")
    return jsonify(cart_service.view(g.user["id"], coupon_code=body.get("coupon_code"),
                                     points_to_use=points, shipping_code=body.get("shipping_method")))
