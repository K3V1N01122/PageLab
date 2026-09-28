from flask import g, jsonify, request

from app.core.audit import audit
from app.core.auth import permission_required
from app.core.pagination import page_params, page_result
from app.core.request_ctx import json_body
from app.services import admin_service


def routes(bp):
    @bp.get("/admin/users")
    @permission_required("users.read")
    def admin_users():
        page, size = page_params(20)
        items, total = admin_service.list_users(request.args.get("q", ""), request.args.get("role") or None, page, size)
        return jsonify(page_result(items, total, page, size))

    @bp.get("/admin/users/<int:uid>")
    @permission_required("users.read")
    def admin_user(uid):
        return jsonify(admin_service.user_detail(uid))

    @bp.patch("/admin/users/<int:uid>")
    @permission_required("users.manage")
    def admin_update_user(uid):
        body = {k: v for k, v in json_body().items() if k in {"is_active", "role"}}
        result = admin_service.update_user(g.user, uid, body)
        audit("user_updated", "user", uid, body)
        return jsonify(result)

    @bp.get("/admin/roles")
    @permission_required("users.read")
    def admin_roles():
        return jsonify({"items": admin_service.roles()})
