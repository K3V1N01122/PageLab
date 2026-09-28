from flask import g, jsonify, request

from app.core.audit import audit
from app.core.auth import permission_required
from app.core.pagination import page_params, page_result
from app.core.request_ctx import json_body
from app.core.validation import V
from app.db import get_db
from app.services import admin_service, order_service


def routes(bp):
    @bp.get("/admin/orders")
    @permission_required("orders.read")
    def admin_orders():
        page, size = page_params(20)
        items, total = admin_service.list_orders(request.args.get("q", ""), request.args.get("status") or None,
                                                 request.args.get("from") or None, request.args.get("to") or None, page, size)
        return jsonify(page_result(items, total, page, size))

    @bp.get("/admin/orders/statuses")
    @permission_required("orders.read")
    def admin_order_statuses():
        rows = get_db().all("SELECT code, label, sort_order, is_final FROM order_statuses ORDER BY sort_order")
        return jsonify({"items": rows, "transitions": {k: sorted(v) for k, v in order_service.TRANSITIONS.items()}})

    @bp.get("/admin/orders/<int:oid>")
    @permission_required("orders.read")
    def admin_order(oid):
        return jsonify(order_service.get_order_admin(oid))

    @bp.post("/admin/orders/<int:oid>/status")
    @permission_required("orders.update")
    def admin_order_status(oid):
        data = V(json_body()).str("status", max_len=30).str("note", required=False, max_len=300).check()
        order = order_service.change_status(oid, data["status"], g.user["id"], data.get("note"))
        audit("order_status", "order", oid, data)
        return jsonify(order)
