from flask import g, jsonify

from app.core.audit import audit
from app.core.auth import permission_required, staff_required
from app.core.request_ctx import json_body
from app.services import settings_service, user_service


def routes(bp):
    @bp.get("/admin/me")
    @staff_required
    def admin_me():
        return jsonify({"user": user_service.public_user(g.user)})

    @bp.get("/admin/settings")
    @permission_required("settings.manage")
    def admin_settings():
        return jsonify(settings_service.all_settings())

    @bp.put("/admin/settings/<key>")
    @permission_required("settings.manage")
    def admin_update_settings(key):
        value = settings_service.update(key, json_body())
        audit("settings_updated", "settings", None, {"key": key})
        return jsonify(value)
