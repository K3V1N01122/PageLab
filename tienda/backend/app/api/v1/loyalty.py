from flask import g, jsonify

from app.api.v1 import api_v1
from app.core import ratelimit
from app.core.auth import login_required
from app.core.pagination import page_params, page_result
from app.core.request_ctx import json_body
from app.services import loyalty_service, reward_service


@api_v1.get("/loyalty/card")
@login_required
def card():
    return jsonify(loyalty_service.card(g.user["id"]))


@api_v1.get("/loyalty/movements")
@login_required
def movements():
    page, size = page_params(20)
    items, total = loyalty_service.movements(g.user["id"], page, size)
    return jsonify(page_result(items, total, page, size))


@api_v1.get("/rewards")
def rewards():
    return jsonify({"items": reward_service.list_available()})


@api_v1.get("/loyalty/coupons")
@login_required
def my_coupons():
    return jsonify({"items": reward_service.my_coupons(g.user["id"])})


@api_v1.post("/rewards/<int:reward_id>/redeem")
@login_required
@ratelimit.limit("redeem", "RATE_LIMIT_CHECKOUT")
def redeem(reward_id):
    body = json_body()
    return jsonify(reward_service.redeem(g.user["id"], reward_id, body.get("idempotency_key") or "")), 201
