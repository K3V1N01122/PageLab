from flask import g, jsonify

from app.core.audit import audit
from app.core.auth import permission_required
from app.core.pagination import page_params, page_result
from app.core.request_ctx import json_body
from app.core.validation import V
from app.db import get_db
from app.services import loyalty_service, promo_admin_service as svc, settings_service


def routes(bp):
    @bp.get("/admin/rewards")
    @permission_required("loyalty.manage")
    def admin_rewards():
        return jsonify({"items": svc.list_rewards()})

    @bp.post("/admin/rewards")
    @permission_required("loyalty.manage")
    def admin_create_reward():
        r = svc.save_reward(json_body(), None)
        audit("reward_created", "reward", r["id"])
        return jsonify(r), 201

    @bp.put("/admin/rewards/<int:rid>")
    @permission_required("loyalty.manage")
    def admin_update_reward(rid):
        r = svc.save_reward(json_body(), rid)
        audit("reward_updated", "reward", rid)
        return jsonify(r)

    @bp.delete("/admin/rewards/<int:rid>")
    @permission_required("loyalty.manage")
    def admin_delete_reward(rid):
        svc.delete("rewards", rid)
        audit("reward_deleted", "reward", rid)
        return jsonify({"ok": True})

    @bp.get("/admin/point-movements")
    @permission_required("loyalty.manage")
    def admin_point_movements():
        page, size = page_params(30)
        db = get_db()
        total = db.scalar("SELECT COUNT(*) AS n FROM point_movements")
        rows = db.all(
            """SELECT pm.id, pm.kind, pm.points, pm.status, pm.description, pm.created_at, u.email, u.public_id
               FROM point_movements pm JOIN users u ON u.id = pm.user_id ORDER BY pm.id DESC LIMIT ? OFFSET ?""",
            (size, (page - 1) * size))
        return jsonify(page_result(rows, total, page, size))

    @bp.post("/admin/users/<int:uid>/points")
    @permission_required("loyalty.manage")
    def admin_adjust_points(uid):
        data = V(json_body()).int("points", min_value=-10**7, max_value=10**7).str("reason", min_len=3, max_len=150).check()
        card = loyalty_service.admin_adjust(uid, data["points"], data["reason"], g.user["id"])
        audit("points_adjusted", "user", uid, data)
        return jsonify(card)

    @bp.get("/admin/loyalty/settings")
    @permission_required("loyalty.manage")
    def admin_loyalty_settings():
        return jsonify(settings_service.get("loyalty"))

    @bp.put("/admin/loyalty/settings")
    @permission_required("loyalty.manage")
    def admin_update_loyalty_settings():
        value = settings_service.update("loyalty", json_body())
        audit("settings_updated", "settings", None, {"key": "loyalty"})
        return jsonify(value)
