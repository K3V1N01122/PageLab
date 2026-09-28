from flask import jsonify

from app.api.v1 import api_v1
from app.db import get_db
from app.payments import registry
from app.services import pricing_service, settings_service


@api_v1.get("/health")
def health():
    get_db().scalar("SELECT 1 AS ok")
    return jsonify({"status": "ok"})


@api_v1.get("/config")
def public_config():
    """Configuración pública centralizada: el frontend no tiene valores de
    negocio escritos en su código (nombre, redes, moneda, puntos...)."""
    s = settings_service.all_settings()
    loyalty = s["loyalty"]
    resp = jsonify({
        "store": s["store"],
        "theme": s["theme"],
        "contact": s["contact"],
        "social": s["social"],
        "seo": s["seo"],
        "loyalty": {k: loyalty[k] for k in ("enabled", "program_name", "points_per_currency_unit",
                                            "redeem_block_points", "redeem_block_value_cents", "max_points_discount_percent")},
        "shipping_methods": pricing_service.shipping_methods(),
        "free_shipping_over_cents": s["shipping"].get("free_shipping_over_cents"),
        "payment_providers": [p.public_info() for p in registry.enabled()],
    })
    resp.headers["Cache-Control"] = "public, max-age=60"
    return resp
