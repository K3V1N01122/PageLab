from flask import g, jsonify, request

from app.core.audit import audit
from app.core.auth import permission_required
from app.core.errors import ValidationError
from app.core.pagination import page_params, page_result
from app.core.request_ctx import json_body
from app.core.validation import V
from app.services import catalog_admin_service as svc
from app.services import catalog_service, storage_service


def routes(bp):
    @bp.get("/admin/products")
    @permission_required("products.read")
    def admin_products():
        page, size = page_params(20)
        cat = request.args.get("category_id")
        items, total = svc.list_products_admin(
            request.args.get("q", ""), request.args.get("status"), int(cat) if cat and cat.isdigit() else None,
            request.args.get("low_stock") == "1", page, size)
        return jsonify(page_result(items, total, page, size))

    @bp.get("/admin/products/<int:pid>")
    @permission_required("products.read")
    def admin_product(pid):
        return jsonify(svc.get_product_admin(pid))

    @bp.post("/admin/products")
    @permission_required("products.write")
    def admin_create_product():
        p = svc.save_product(json_body(), None, g.user["id"])
        audit("product_created", "product", p["id"], {"sku": p["sku"]})
        return jsonify(p), 201

    @bp.put("/admin/products/<int:pid>")
    @permission_required("products.write")
    def admin_update_product(pid):
        body = json_body()
        if "stock" in body and "inventory.write" not in g.user["permissions"]:
            body.pop("stock")
        p = svc.save_product(body, pid, g.user["id"])
        audit("product_updated", "product", pid)
        return jsonify(p)

    @bp.patch("/admin/products/<int:pid>/status")
    @permission_required("products.write")
    def admin_product_status(pid):
        data = V(json_body()).choice("status", svc.STATUSES).check()
        from app.db import get_db
        from app.core.timeutil import now_iso
        if not get_db().execute("UPDATE products SET status = ?, updated_at = ? WHERE id = ?", (data["status"], now_iso(), pid)):
            raise ValidationError("Producto no encontrado.")
        audit("product_status", "product", pid, data)
        return jsonify(svc.get_product_admin(pid))

    @bp.post("/admin/products/<int:pid>/stock")
    @permission_required("inventory.write")
    def admin_adjust_stock(pid):
        data = V(json_body()).int("delta", min_value=-10**6, max_value=10**6).str("reason", required=False, max_len=30, default="adjustment").check()
        if data["delta"] == 0:
            raise ValidationError("El ajuste no puede ser 0.")
        stock = svc.adjust_stock(pid, data["delta"], g.user["id"], data["reason"])
        audit("stock_adjusted", "product", pid, data)
        return jsonify({"stock": stock})

    @bp.delete("/admin/products/<int:pid>")
    @permission_required("products.write")
    def admin_delete_product(pid):
        result = svc.delete_product(pid)
        audit(f"product_{result}", "product", pid)
        return jsonify({"result": result})

    @bp.post("/admin/uploads")
    @permission_required("products.write")
    def admin_upload():
        file = request.files.get("file")
        if not file:
            raise ValidationError("Selecciona una imagen.")
        return jsonify(storage_service.save_image(file)), 201

    @bp.get("/admin/categories")
    @permission_required("products.read")
    def admin_categories():
        return jsonify({"items": catalog_service.all_categories(include_inactive=True)})

    @bp.post("/admin/categories")
    @permission_required("products.write")
    def admin_create_category():
        c = svc.save_category(json_body(), None)
        audit("category_created", "category", c["id"])
        return jsonify(c), 201

    @bp.put("/admin/categories/<int:cid>")
    @permission_required("products.write")
    def admin_update_category(cid):
        c = svc.save_category(json_body(), cid)
        audit("category_updated", "category", cid)
        return jsonify(c)

    @bp.delete("/admin/categories/<int:cid>")
    @permission_required("products.write")
    def admin_delete_category(cid):
        svc.delete_category(cid)
        audit("category_deleted", "category", cid)
        return jsonify({"ok": True})
