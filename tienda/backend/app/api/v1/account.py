from flask import g, jsonify, request

from app.api.v1 import api_v1
from app.core.auth import login_required
from app.core.pagination import page_params, page_result
from app.core.request_ctx import json_body
from app.core.validation import V
from app.services import catalog_service, order_service, user_service


@api_v1.get("/account/profile")
@login_required
def profile():
    return jsonify({"user": user_service.public_user(g.user), "addresses": user_service.list_addresses(g.user["id"])})


@api_v1.put("/account/profile")
@login_required
def update_profile():
    data = V(json_body()).str("first_name", max_len=80).str("last_name", max_len=80).phone().check()
    user_service.update_profile(g.user["id"], data)
    return jsonify({"user": user_service.public_user(user_service.with_role(g.user["id"]))})


def _address_data():
    return (V(json_body()).str("label", required=False, max_len=50).str("recipient", max_len=120).phone(required=True)
            .str("line1", max_len=200).str("line2", required=False, max_len=200).str("city", max_len=100)
            .str("state", required=False, max_len=100).str("postal_code", required=False, max_len=20)
            .str("notes", required=False, max_len=300).bool("is_default")).check() | {"country": "GT"}


@api_v1.post("/account/addresses")
@login_required
def create_address():
    address_id = user_service.save_address(g.user["id"], _address_data())
    return jsonify({"id": address_id, "items": user_service.list_addresses(g.user["id"])}), 201


@api_v1.put("/account/addresses/<int:address_id>")
@login_required
def update_address(address_id):
    user_service.save_address(g.user["id"], _address_data(), address_id)
    return jsonify({"items": user_service.list_addresses(g.user["id"])})


@api_v1.delete("/account/addresses/<int:address_id>")
@login_required
def delete_address(address_id):
    user_service.delete_address(g.user["id"], address_id)
    return jsonify({"items": user_service.list_addresses(g.user["id"])})


@api_v1.get("/account/favorites")
@login_required
def favorites():
    ids = user_service.list_favorite_ids(g.user["id"])
    return jsonify({"ids": ids, "items": catalog_service.cards_by_ids(ids[:100])})


@api_v1.post("/account/favorites/<int:product_id>")
@login_required
def add_favorite(product_id):
    user_service.add_favorite(g.user["id"], product_id)
    return jsonify({"ids": user_service.list_favorite_ids(g.user["id"])}), 201


@api_v1.delete("/account/favorites/<int:product_id>")
@login_required
def remove_favorite(product_id):
    user_service.remove_favorite(g.user["id"], product_id)
    return jsonify({"ids": user_service.list_favorite_ids(g.user["id"])})


@api_v1.get("/account/orders")
@login_required
def orders():
    page, size = page_params(10)
    items, total = order_service.list_for_user(g.user["id"], request.args.get("scope", "all"), page, size)
    return jsonify(page_result(items, total, page, size))


@api_v1.get("/account/orders/<order_number>")
@login_required
def order_detail(order_number):
    return jsonify(order_service.get_order_for_user(g.user["id"], order_number=order_number[:30]))


@api_v1.post("/account/orders/<order_number>/cancel")
@login_required
def cancel_order(order_number):
    return jsonify(order_service.cancel_by_customer(g.user["id"], order_number[:30]))
