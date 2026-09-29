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

    @bp.post("/admin/settings/test-email")
    @permission_required("settings.manage")
    def admin_test_email():
        from app.core.errors import AppError
        from app.core.validation import V
        from app.services import notification_service
        data = V(json_body()).email("to").check()
        if not notification_service.send_test(data["to"]):
            raise AppError("No se pudo enviar. Revisa SMTP_USER y SMTP_PASSWORD en el archivo .env y el log del servidor.", code="mail_failed", status=502)
        return jsonify({"message": f"Correo de prueba enviado a {data['to']}."})
