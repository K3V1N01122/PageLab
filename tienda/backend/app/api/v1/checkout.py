from flask import g, jsonify

from app.api.v1 import api_v1
from app.core import ratelimit
from app.core.auth import login_required
from app.core.request_ctx import json_body
from app.payments import registry
from app.services import loyalty_service, order_service, pricing_service, user_service


@api_v1.get("/checkout/options")
@login_required
def checkout_options():
    return jsonify({
        "shipping_methods": pricing_service.shipping_methods(),
        "payment_providers": [p.public_info() for p in registry.enabled()],
        "addresses": user_service.list_addresses(g.user["id"]),
        "points_available": loyalty_service.balance(g.user["id"]),
        "customer": {"name": f"{g.user['first_name']} {g.user['last_name']}", "email": g.user["email"], "phone": g.user.get("phone")},
    })


@api_v1.post("/checkout")
@login_required
@ratelimit.limit("checkout", "RATE_LIMIT_CHECKOUT")
def place_order():
    order = order_service.place_order(g.user, json_body())
    return jsonify(order), 201
