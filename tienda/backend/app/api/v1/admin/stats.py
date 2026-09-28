from flask import jsonify, request

from app.core.auth import permission_required
from app.services import admin_service


def routes(bp):
    @bp.get("/admin/stats")
    @permission_required("stats.read")
    def admin_stats():
        try:
            days = max(1, min(int(request.args.get("days", 30)), 365))
        except ValueError:
            days = 30
        return jsonify(admin_service.stats(days))
