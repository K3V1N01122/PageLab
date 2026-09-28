from flask import jsonify

from app.core.audit import audit
from app.core.auth import permission_required
from app.core.pagination import page_params, page_result
from app.core.request_ctx import json_body
from app.services import promo_admin_service as svc


def routes(bp):
    @bp.get("/admin/coupons")
    @permission_required("promotions.manage")
    def admin_coupons():
        page, size = page_params(30)
        items, total = svc.list_coupons(page, size)
        return jsonify(page_result(items, total, page, size))

    @bp.post("/admin/coupons")
    @permission_required("promotions.manage")
    def admin_create_coupon():
        c = svc.save_coupon(json_body(), None)
        audit("coupon_created", "coupon", c["id"])
        return jsonify(c), 201

    @bp.put("/admin/coupons/<int:cid>")
    @permission_required("promotions.manage")
    def admin_update_coupon(cid):
        c = svc.save_coupon(json_body(), cid)
        audit("coupon_updated", "coupon", cid)
        return jsonify(c)

    @bp.delete("/admin/coupons/<int:cid>")
    @permission_required("promotions.manage")
    def admin_delete_coupon(cid):
        svc.delete("coupons", cid)
        audit("coupon_deleted", "coupon", cid)
        return jsonify({"ok": True})

    @bp.get("/admin/promotions")
    @permission_required("promotions.manage")
    def admin_promotions():
        return jsonify({"items": svc.list_promotions()})

    @bp.post("/admin/promotions")
    @permission_required("promotions.manage")
    def admin_create_promotion():
        p = svc.save_promotion(json_body(), None)
        audit("promotion_created", "promotion", p["id"])
        return jsonify(p), 201

    @bp.put("/admin/promotions/<int:pid>")
    @permission_required("promotions.manage")
    def admin_update_promotion(pid):
        p = svc.save_promotion(json_body(), pid)
        audit("promotion_updated", "promotion", pid)
        return jsonify(p)

    @bp.delete("/admin/promotions/<int:pid>")
    @permission_required("promotions.manage")
    def admin_delete_promotion(pid):
        svc.delete("promotions", pid)
        audit("promotion_deleted", "promotion", pid)
        return jsonify({"ok": True})
